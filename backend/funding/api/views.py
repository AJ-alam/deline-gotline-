"""HTTP for the funding domain.

Views resolve permissions, call a service, and serialise the result. Business
rules live in funding.services and funding.rules — the previous api/views.py ran
to 1,538 lines and held workflow, pricing and CSV export inline, which is why
the same rule existed in several slightly different versions.
"""

import hashlib
import json

from django.db.models import Prefetch
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.api.permissions import DecidesApplications, IsStaffOrOwner
from funding.api.serializers import (
    ApplicationCreateSerializer, ApplicationDetailSerializer,
    ApplicationListSerializer, AwardDecisionSerializer, TransitionSerializer,
    schema_payload,
)
from funding.models import Application, ApplicationEvent
from funding.schemas import ValidationError as SchemaValidationError
from funding.services import dashboard as dashboard_service
from funding.services import decisions as decision_service
from funding.services import verification as verification_service
from funding.services import workflow


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

    def get_queryset(self):
        user = self.request.user
        queryset = Application.objects.select_related('student')

        if self.action == 'list':
            # The list is a queue, not a record: no answers, no events, no trace.
            queryset = queryset.only(
                'id', 'type', 'stream', 'status', 'awarded_total', 'submitted_at',
                'submitted_after_deadline', 'residency_flag', 'student',
            )
        else:
            queryset = queryset.prefetch_related(
                Prefetch('events', queryset=ApplicationEvent.objects.select_related('actor')),
                'decisions__lines',
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
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = serializer.save()
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
        except workflow.InvalidTransition as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)

        application.refresh_from_db()
        return Response(
            ApplicationDetailSerializer(application, context=self.get_serializer_context()).data
        )

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

    @action(detail=True, methods=['get'], url_path='decisions')
    def decision_history(self, request, pk=None):
        """Every pricing this application has had. What an appeal is argued from."""
        application = self.get_object()
        return Response(
            AwardDecisionSerializer(
                decision_service.decision_history(application), many=True,
            ).data
        )


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
