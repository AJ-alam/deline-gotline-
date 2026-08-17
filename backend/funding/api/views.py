"""HTTP for the funding domain.

Views resolve permissions, call a service, and serialise the result. Business
rules live in funding.services and funding.rules — the previous api/views.py ran
to 1,538 lines and held workflow, pricing and CSV export inline, which is why
the same rule existed in several slightly different versions.
"""

import hashlib
import json

from django.db import transaction
from django.db.models import Prefetch
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.api.permissions import DecidesApplications, IsStaffOrOwner
from funding.api.serializers import (
    GUEST_TYPES, ApplicationCreateSerializer, ApplicationDetailSerializer,
    ApplicationListSerializer, AttachSerializer, AwardDecisionSerializer,
    GuestApplicationSerializer, ReviseSerializer, TransitionSerializer,
    jsonable, schema_payload,
)
from accounts.models import Role, User
from funding.models import (
    Application, ApplicationEvent, ApplicationStatus, AuditEntry, Award,
)
from funding.schemas import ValidationError as SchemaValidationError, get_schema
from funding.services import banking as banking_service
from funding.services import dashboard as dashboard_service
from funding.services import decisions as decision_service
from funding.services import prefill as prefill_service
from funding.services import verification as verification_service
from funding.services import workflow


# An application whose answers are the record a decision was made from. The
# office may correct a form still in the queue; it may not rewrite one that has
# been decided, because the award is defended by the answers that were priced.
AMENDMENT_CLOSED = (
    ApplicationStatus.APPROVED,
    ApplicationStatus.DECLINED,
    ApplicationStatus.SENT_TO_FINANCE,
)


def _changed_keys(before: dict, after: dict) -> list[str]:
    """Which answers an edit actually altered.

    So the audit entry and the applicant's notice can say what changed rather
    than that something did. Compared on the stored form of the value, which is
    what both sides will be read back as.
    """
    return sorted(
        key for key in set(before) | set(after)
        if before.get(key) != after.get(key)
    )


class SchemaView(APIView):
    """What each application type asks.

    Public: an applicant needs the questions before they have an account, and a
    schema contains no data about anyone.

    Schemas are defined in code, so they cannot change between deploys. The
    payload is built once per process and served with a validator, which turns
    the client's repeat requests into 304s — this is 25KB that every visitor
    would otherwise download before seeing a single field.
    """

    permission_classes = [AllowAny]

    _cache = None
    _etag = None

    @classmethod
    def _payload(cls):
        if cls._cache is None:
            cls._cache = schema_payload()
            cls._etag = f'"{hashlib.sha256(json.dumps(cls._cache, sort_keys=True, default=str).encode()).hexdigest()[:32]}"'
        return cls._cache, cls._etag

    def get(self, request, slug=None):
        payload, etag = self._payload()

        if request.headers.get('If-None-Match') == etag:
            return Response(status=status.HTTP_304_NOT_MODIFIED)

        if slug is None:
            body = payload
        else:
            body = next((s for s in payload if s['slug'] == slug), None)
            if body is None:
                return Response({'detail': f'No schema named {slug!r}.'},
                                status=status.HTTP_404_NOT_FOUND)

        response = Response(body)
        response['ETag'] = etag
        response['Cache-Control'] = 'public, max-age=300'
        return response


class ApplicationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsStaffOrOwner]
    http_method_names = ['get', 'post', 'head', 'options']

    # Without these the list filters nothing. DjangoFilterBackend is enabled
    # globally, but a view that declares no filterset ignores every query
    # parameter and still answers 200 with the whole list — so both the
    # student's list and the staff queue asked for one status and were quietly
    # given all of them. The failure is silent by design on the backend's part,
    # which is why it survived: nothing errors, the page just shows too much.
    #
    # Filtering happens in the database against the (status, -submitted_at),
    # (type, status) and (stream, status) indexes on Application.
    filterset_fields = ('status', 'type', 'stream')
    ordering_fields = ('submitted_at', 'awarded_total', 'status')
    ordering = ('-submitted_at',)
    # Staff look people up by name; a student's list is already only their own.
    search_fields = ('student__first_name', 'student__last_name', 'student__email')

    def get_queryset(self):
        user = self.request.user
        queryset = Application.objects.select_related('student')

        if self.action == 'list':
            # The list is a queue, not a record: no answers, no events, no trace.
            queryset = queryset.only(
                'id', 'type', 'stream', 'status', 'awarded_total', 'submitted_at',
                'submitted_after_deadline', 'residency_flag', 'student',
            # Prefetched rather than joined: select_related cannot traverse a
            # relation on a queryset that has deferred columns with only().
            # One extra query for the page, not one per row.
            ).prefetch_related('enrollment_verification')
        else:
            queryset = queryset.select_related('enrollment_verification').prefetch_related(
                Prefetch('events', queryset=ApplicationEvent.objects.select_related('actor')),
                'decisions__lines',
                'identifiers',
                # The detail screen reports whether an award can be paid.
                # Without this it is a query per application to find out.
                'student__bank_accounts',
            )

        if user.is_student:
            return queryset.filter(student=user)
        return queryset

    def get_serializer_class(self):
        if self.action == 'create':
            return ApplicationCreateSerializer
        if self.action == 'list':
            return ApplicationListSerializer
        return ApplicationDetailSerializer

    def create(self, request, *args, **kwargs):
        from funding.services import streams

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            application = serializer.save()
        except streams.NoStreamAvailable as exc:
            # Registration is gated on eligibility, so this means the account
            # predates the gate or the person's circumstances have changed.
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        workflow.record(
            application, ApplicationEvent.Action.SUBMITTED, actor=request.user,
        )
        return Response(
            ApplicationDetailSerializer(application, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def transition(self, request, pk=None):
        """Move an application through review by recording what happened."""
        application = self.get_object()
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action_name = serializer.validated_data['action']

        deciding = action_name in (
            ApplicationEvent.Action.APPROVED, ApplicationEvent.Action.DECLINED,
        )
        if deciding and not request.user.decides_applications:
            return Response({'detail': DecidesApplications.message},
                            status=status.HTTP_403_FORBIDDEN)
        if not deciding and not request.user.reviews_applications:
            return Response({'detail': 'Only staff may advance an application.'},
                            status=status.HTTP_403_FORBIDDEN)

        try:
            workflow.record(application, action_name, actor=request.user,
                            note=serializer.validated_data.get('note', ''))
        except workflow.EnrolmentNotConfirmed as exc:
            # Named separately from an invalid transition: this one is not the
            # reviewer's mistake, it is the institution not having answered.
            return Response(
                {'detail': str(exc), 'blocked_by': 'enrolment_verification'},
                status=status.HTTP_409_CONFLICT,
            )
        except workflow.InvalidTransition as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)

        application.refresh_from_db()
        return Response(
            ApplicationDetailSerializer(application, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=['post'])
    def revise(self, request, pk=None):
        """The student answering a request for more information.

        The only path by which a filed application changes. It is narrow on
        purpose:

          * only the student it belongs to, and only while the office is
            actually waiting — an application under review must not change
            under the reviewer, and a decided one is a record;
          * the whole answer set, validated by the same schema as the original.
            A partial update needs a second, weaker notion of "complete", and
            the weaker one is always the one that lets something through;
          * private answers are split off exactly as on submission, so a
            corrected bank account does not land in `answers`.

        Recording INFO_PROVIDED is part of the same act. Saving the edit without
        it would leave the application sitting in "more information needed"
        while the information sat there unread.
        """
        application = self.get_object()

        if application.student_id != request.user.pk:
            return Response({'detail': 'This is not your application.'},
                            status=status.HTTP_403_FORBIDDEN)
        if application.status != ApplicationStatus.INFO_REQUESTED:
            return Response(
                {'detail': 'This application can only be edited while the office '
                           'has asked for more information.'},
                status=status.HTTP_409_CONFLICT)

        serializer = ReviseSerializer(
            data=request.data,
            context={**self.get_serializer_context(), 'application': application})
        serializer.is_valid(raise_exception=True)

        from funding.services import banking, identifiers

        schema = get_schema(application.type)
        ordinary, private = schema.split_private(serializer.validated_data['cleaned_answers'])

        with transaction.atomic():
            # Carried answers first, so a cleaned one always wins: the two sets
            # cannot overlap, and if they ever did the validated value is the
            # one to keep.
            application.answers = {**serializer.validated_data['carried_answers'],
                                   **jsonable(ordinary)}
            application.save(update_fields=['answers', 'updated_at'])
            for key in schema.sensitive_keys:
                if key in private:
                    identifiers.store(application, key, str(private[key]))
            banking.record(application, private)

            workflow.record(application, ApplicationEvent.Action.INFO_PROVIDED,
                            actor=request.user,
                            note=serializer.validated_data.get('note', ''))

        application.refresh_from_db()
        return Response(
            ApplicationDetailSerializer(application,
                                        context=self.get_serializer_context()).data)

    @action(detail=True, methods=['post'], url_path='request-enrolment')
    def request_enrolment(self, request, pk=None):
        """Ask the institution to confirm — or ask again.

        Submission raises this automatically, but only when a registrar address
        is already known: the renewal form does not ask for one, it is carried
        from the student's last application. A student whose admission was on
        paper, or the office's first renewal in the portal, therefore had no
        address to carry — and the request was skipped in silence. Tuition is
        funded against the registrar's figure, so the application could then
        never be forwarded or approved, by anybody, with nothing anywhere saying
        why. `verification.issue` had one caller and no endpoint, so the comment
        promising staff could reissue described something that did not exist.

        The same path covers the address that bounced and the request that
        expired, which had no recovery either.
        """
        application = self.get_object()

        if not request.user.reviews_applications:
            return Response({'detail': 'Only staff may request an enrolment confirmation.'},
                            status=status.HTTP_403_FORBIDDEN)
        if application.type not in workflow.NEEDS_ENROLMENT_CONFIRMATION:
            return Response(
                {'detail': 'This kind of application does not need an enrolment '
                           'confirmation.'},
                status=status.HTTP_400_BAD_REQUEST)

        registrar_email = (request.data.get('registrar_email') or '').strip()
        if not registrar_email:
            registrar_email = workflow.registrar_email_for(application)
        if not registrar_email:
            return Response(
                {'registrar_email': ['No registrar address is on file for this '
                                     'application. Enter the one to write to.']},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            verification_service.issue(application, registrar_email)
        except verification_service.VerificationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)

        AuditEntry.objects.create(
            actor=request.user, actor_role=request.user.role,
            action='application.enrolment_requested', application=application,
            detail=f'Enrolment confirmation requested from {registrar_email}.',
        )

        application.refresh_from_db()
        return Response(
            ApplicationDetailSerializer(application,
                                        context=self.get_serializer_context()).data)

    @action(detail=True, methods=['post'])
    def amend(self, request, pk=None):
        """The office correcting a filed application on the applicant's behalf.

        A student can only edit their own application while the office is
        waiting for information (`revise`). The office often has to fix
        something outside that window — a misspelled institution, a transposed
        student number, an answer given over the phone — and until this existed
        the only options were to decline the application or to ask the student
        to refile it.

        Administrators only. `reviews_applications` would include the support
        workers who assess these, and someone who can both rewrite the answers
        and advance the application can price whatever they like without a
        second person seeing it.

        The same validation as a submission, deliberately reusing `revise`'s
        serializer: the whole answer set, cleaned by the schema that defines the
        form, with the SIN and the banking fields split off exactly as they are
        anywhere else. An office edit that could put a SIN into `answers` would
        undo the entire arrangement described in §5 of the handover.

        A decided application is not amendable. Its answers are the record the
        decision was made from, and rewriting them leaves an award defended by
        answers that were never priced.
        """
        application = self.get_object()

        if request.user.role != Role.ADMIN:
            return Response(
                {'detail': 'Only an administrator may edit a filed application.'},
                status=status.HTTP_403_FORBIDDEN)

        if application.status in AMENDMENT_CLOSED:
            return Response(
                {'detail': 'This application has been decided. Its answers are '
                           'the record the decision was made from and cannot be '
                           'rewritten.'},
                status=status.HTTP_409_CONFLICT)

        serializer = ReviseSerializer(
            data=request.data,
            context={**self.get_serializer_context(), 'application': application})
        serializer.is_valid(raise_exception=True)

        from funding.services import banking, identifiers

        schema = get_schema(application.type)
        ordinary, private = schema.split_private(serializer.validated_data['cleaned_answers'])
        note = serializer.validated_data.get('note', '')

        with transaction.atomic():
            # What the answers were, so the history is not just "somebody
            # changed something". Recorded before the write, for the obvious
            # reason.
            carried = serializer.validated_data['carried_answers']
            changed = _changed_keys(application.answers or {},
                                    {**carried, **jsonable(ordinary)})

            application.answers = {**carried, **jsonable(ordinary)}
            application.save(update_fields=['answers', 'updated_at'])
            for key in schema.sensitive_keys:
                if key in private:
                    identifiers.store(application, key, str(private[key]))
            banking.record(application, private)

            AuditEntry.objects.create(
                actor=request.user, actor_role=request.user.role,
                action='application.amended', application=application,
                detail=(f'Edited {", ".join(changed) if changed else "no answers"}'
                        + (f'. Note: {note}' if note else '')),
            )
            workflow.record_amendment(application, actor=request.user, note=note)

        application.refresh_from_db()
        return Response(
            ApplicationDetailSerializer(application,
                                        context=self.get_serializer_context()).data)

    @action(detail=True, methods=['get'], url_path='decision-preview')
    def decision_preview(self, request, pk=None):
        """What this application would be awarded, without recording anything."""
        application = self.get_object()
        if not (request.user.reviews_applications or request.user.decides_applications):
            return Response({'detail': 'Only staff may preview an award.'},
                            status=status.HTTP_403_FORBIDDEN)
        try:
            result = decision_service.preview(application)
        except decision_service.NoRuleSetInForce as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(result.as_trace())

    @action(detail=True, methods=['post'])
    def price(self, request, pk=None):
        """Record an award decision. Supersedes any earlier one."""
        application = self.get_object()
        if not request.user.decides_applications:
            return Response({'detail': DecidesApplications.message},
                            status=status.HTTP_403_FORBIDDEN)
        try:
            decision = decision_service.record_decision(application, actor=request.user)
        except decision_service.IncompletePolicyError as exc:
            # Naming the missing rates makes this fixable without reading logs.
            return Response(
                {'detail': str(exc), 'missing_rates': exc.missing},
                status=status.HTTP_409_CONFLICT,
            )
        except decision_service.NoRuleSetInForce as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(AwardDecisionSerializer(decision).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def attach(self, request, pk=None):
        """Give a guest application an owner.

        The counterpart to the account-less path: someone applied for a
        graduation bursary without a portal account, later has one, and the
        office links the two. Staff only, and only onto an application that has
        no owner yet — reassigning an application away from the person who made
        it is not what this is for.
        """
        application = self.get_object()
        if not request.user.reviews_applications:
            return Response({'detail': 'Only staff may attach an application to an account.'},
                            status=status.HTTP_403_FORBIDDEN)
        if application.student_id is not None:
            return Response({'detail': 'This application already belongs to an account.'},
                            status=status.HTTP_409_CONFLICT)

        serializer = AttachSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        student = User.objects.filter(
            pk=serializer.validated_data['student_id'], role=Role.STUDENT,
        ).first()
        if student is None:
            return Response({'student_id': ['No student account with that id.']},
                            status=status.HTTP_400_BAD_REQUEST)

        application.student = student
        application.save(update_fields=['student', 'updated_at'])

        # The bank details the guest typed have been held encrypted against the
        # application, because there was no account to put them on. Now there
        # is. Without this the applicant is reported to finance as having no
        # account on file, having already given one.
        promoted = banking_service.promote(application, student)

        AuditEntry.objects.create(
            actor=request.user, actor_role=request.user.role,
            action='application.attached', application=application,
            detail=(f'Attached guest application to {student.email}.'
                    + (' Bank details from the application were recorded '
                       'against the account.' if promoted else '')),
        )

        return Response(
            ApplicationDetailSerializer(application, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=['post'], url_path='award')
    def set_award(self, request, pk=None):
        """Set the funding breakdown by hand.

        The rules price the ordinary case. They cannot know that an institution
        charges a fee no rate covers, or that the office agreed something at the
        counter — and the only ways to express that were to edit a policy rate,
        which changes what everyone is paid, or to pay the wrong amount.

        Administrators only, and refused once any of it has been paid. It is
        recorded as a decision like any other: it supersedes rather than
        overwrites, and every line says who entered it.
        """
        application = self.get_object()

        if request.user.role != Role.ADMIN:
            return Response(
                {'detail': 'Only an administrator may set an award by hand.'},
                status=status.HTTP_403_FORBIDDEN)

        lines = request.data.get('lines')
        if not isinstance(lines, list):
            return Response({'lines': ['Expected a list of award lines.']},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            decision = decision_service.record_manual_decision(
                application, lines, actor=request.user,
                note=str(request.data.get('note') or '').strip())
        except decision_service.AwardEditError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except decision_service.NoRuleSetInForce as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)

        AuditEntry.objects.create(
            actor=request.user, actor_role=request.user.role,
            action='application.award_set_by_hand', application=application,
            detail=f'Award set to {decision.total} across {len(lines)} line(s).'
                   + (f' Note: {request.data.get("note")}' if request.data.get('note') else ''),
        )
        return Response(AwardDecisionSerializer(decision).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='award-categories')
    def award_categories(self, request, pk=None):
        """The categories a line may be filed under.

        Served rather than hard-coded in the client for the same reason the
        forms are: a category added here would otherwise need a second edit in
        a file nobody remembers.
        """
        return Response([{'value': value, 'label': label}
                         for value, label in Award.Category.choices])

    @action(detail=True, methods=['get'], url_path='decisions')
    def decision_history(self, request, pk=None):
        """Every pricing this application has had. What an appeal is argued from."""
        application = self.get_object()
        return Response(
            AwardDecisionSerializer(
                decision_service.decision_history(application), many=True,
            ).data
        )


class GuestApplicationView(APIView):
    """Applying without an account.

    A summer placement allowance and a graduation bursary are both claimed
    once, after the fact, often by someone who will never use the portal again.
    Requiring them to create an account first is how those claims went unmade.

    Public, so it is throttled and it answers with as little as possible: the
    reference number and nothing else. It does not confirm whether an email
    already has an account, and it cannot be used to read anything back — there
    is no GET, and the created record is invisible until staff open the queue.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'guest_application'

    def get(self, request):
        """The two forms that can be filled in without an account."""
        payload, _etag = SchemaView._payload()
        slugs = {t.value for t in GUEST_TYPES}
        return Response([s for s in payload if s['slug'] in slugs])

    def post(self, request):
        serializer = GuestApplicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = serializer.save()

        # actor=None: nobody signed in did this, and the event log should say so
        # rather than attribute it to whoever happens to look at it later.
        workflow.record(application, ApplicationEvent.Action.SUBMITTED, actor=None)

        return Response(
            {
                'reference': f'DGG-{application.pk:06d}',
                'detail': (
                    'Your application has been received. Keep the reference '
                    'number — the Education Department will need it if you '
                    'contact them, and staff can attach this application to a '
                    'portal account for you later.'
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class EnrolmentPreviewView(APIView):
    """The enrolment verification as the registrar will receive it.

    Built from the same schema and the same pre-fill function the real request
    uses, so a student checking it before submitting is checking the actual
    thing rather than a mock-up that can drift from it.

    Nothing is stored. The application does not exist yet — these are the
    answers being typed.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        application_type = request.data.get('type')
        if application_type not in workflow.NEEDS_ENROLMENT_CONFIRMATION:
            return Response(
                {'type': ['That application type does not generate an enrolment '
                          'verification.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        answers = request.data.get('answers') or {}
        if not isinstance(answers, dict):
            return Response({'answers': ['Expected an object of answers.']},
                            status=status.HTTP_400_BAD_REQUEST)

        # An unsaved instance: prefill_for only reads `answers`, and nothing here
        # touches the database.
        draft = Application(type=application_type, schema_slug=application_type,
                            answers=answers, student=request.user)

        payload, _etag = SchemaView._payload()
        definition = next(s for s in payload if s['slug'] == 'enrollment_verification')

        return Response({
            'schema': definition,
            'prefill': verification_service.prefill_for(draft),
            'note_to_registrar': (
                'The student has verified their identity and contact information '
                'through the DGG Student Portal. Their date of birth and Social '
                'Insurance Number have been withheld from this form to protect '
                'their identity.'
            ),
            # Carried the same way the real request is, so the address shown
            # here is the address the email will actually go to.
            'registrar_email': workflow.registrar_email_for(draft),
        })


class PrefillView(APIView):
    """The answers a form opens with, for the student asking.

    Separate from the schema endpoint on purpose: a schema is the same for
    everyone and is cached and served with a validator, while this is one
    person's own answers and must never land in a shared cache.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        try:
            schema = get_schema(slug)
        except KeyError:
            return Response({'detail': 'No such application type.'},
                            status=status.HTTP_404_NOT_FOUND)

        response = Response({'answers': prefill_service.for_schema(request.user, schema)})
        response['Cache-Control'] = 'private, no-store'
        return response


class EnrollmentVerificationView(APIView):
    """The registrar's form, reached from an emailed link.

    Public by necessity — a registrar has no account here — so the token is the
    only credential. It is rate limited, single-use, and every failure returns
    the same message so the endpoint cannot be used to probe for valid tokens.
    """

    permission_classes = [AllowAny]
    throttle_scope = 'verification'

    def get(self, request, token):
        try:
            verification = verification_service.resolve(token)
        except verification_service.VerificationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)

        payload, _etag = SchemaView._payload()
        definition = next(s for s in payload if s['slug'] == 'enrollment_verification')
        return Response({
            'application': verification_service.context_for(verification),
            'schema': definition,
        })

    def post(self, request, token):
        try:
            verification = verification_service.resolve(token)
        except verification_service.VerificationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)

        try:
            verification_service.complete(verification, request.data.get('answers') or {})
        except SchemaValidationError as exc:
            return Response({'answers': exc.errors}, status=status.HTTP_400_BAD_REQUEST)
        except verification_service.VerificationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response({'detail': 'Thank you — the enrolment has been confirmed.'})


class DashboardView(APIView):
    """The numbers a person sees on opening the portal.

    One request, scoped to the role. The screen this replaces fetched seven
    endpoints every thirty seconds and counted rows in the browser.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(dashboard_service.summary(request.user))
