import csv
import io
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.contrib.auth import get_user_model
User = get_user_model()
from .models import Profile, Application, Document, AuditLog, UserDocument, Payment, Appeal, ShareableLink
from .serializers import (
    UserSerializer, ProfileSerializer, ApplicationSerializer,
    DocumentSerializer, AuditLogSerializer, UserDocumentSerializer,
    PaymentSerializer, AppealSerializer, ShareableLinkSerializer
)
from notifications.utils import create_notification
from users.permissions import IsAdminUser
import uuid
from django.utils import timezone
from datetime import timedelta


def _is_staff(user):
    return user.is_authenticated and user.role in ('admin', 'director')


# ---------------------------------------------------------------------------
# SHARED CSV BUILDER
# Used by both export_csv (approved-only download) and
# dispatch_report (ALL records emailed to finance).
# ---------------------------------------------------------------------------

def _build_full_csv(funding_type='all', date_from=None, date_to=None, all_statuses=False, unsent_only=False):
    """
    Build the comprehensive student records CSV with personal + banking info.

    Columns (35 total):
      Submission info  (5)
      Personal info    (12)  — from CustomUser + Profile
      Banking info     (6)   — from CustomUser
      Enrollment info  (4)   — from CustomUser
      Application info (4)
      Payment info     (5)
      Timeline info    (3)

    Parameters
    ----------
    all_statuses : bool
        False  → only accepted/approved records  (used by export_csv download)
        True   → every record regardless of status (used by dispatch_report email)
    unsent_only : bool
        True   → only records never sent to finance (finance_sent_at__isnull=True)

    Returns
    -------
    (csv_bytes: bytes, row_count: int)
    """
    from forms.models import FormSubmission
    from django.db.models import Q

    HEADERS = [
        # ── Submission ──
        'Submission ID', 'Form/Type', 'Status', 'Stream',
        # ── Personal ──
        'Full Name', 'Email', 'Phone', 'Alternate Phone',
        'Date of Birth', 'Gender', 'Pronouns',
        'Beneficiary #', 'Treaty #', 'UPI',
        'Mailing Address', 'Town/City', 'Postal Code', 'Province',
        'No. of Dependents', 'Dependent Ages',
        'Financial Assistance Status', 'SFA Active (Profile)',
        # ── Banking ──
        'Account Holder Name', 'Account Type',
        'Bank Name', 'Transit #', 'Institution #', 'Account #',
        # ── Enrollment ──
        'Institute (Profile)', 'Institution Name', 'Program', 'Enrollment Status', 'Course Load (%)',
        # ── Funding Breakdown (Single Row) ──
        'Tuition ($)', 'Living Allowance ($)', 'Books & Supplies ($)', 'Travel ($)', 'Special Awards ($)',
        'TOTAL APPROVED ($)',
        # ── Timeline ──
        'Submitted Date', 'Decision Date', 'Decided By',
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(HEADERS)

    # ── New-model submissions ──
    if all_statuses:
        qs = FormSubmission.objects.all()
    else:
        qs = FormSubmission.objects.filter(status='accepted')

    if unsent_only:
        qs = qs.filter(finance_sent_at__isnull=True)

    qs = qs.select_related('student', 'form', 'decided_by').prefetch_related(
        'payments', 'student__profile'
    )

    # ── Legacy applications ──
    if all_statuses:
        legacy_qs = Application.objects.all()
    else:
        legacy_qs = Application.objects.filter(status='approved')

    if unsent_only:
        legacy_qs = legacy_qs.filter(finance_sent_at__isnull=True)

    legacy_qs = legacy_qs.select_related('student').prefetch_related(
        'payments', 'student__profile'
    )

    # ── Funding-type filter (only for approved download) ──
    if not all_statuses and funding_type != 'all':
        mapping = {
            'cdfn':  Q(form__title__icontains='FormA') | Q(form__title__icontains='FormC'),
            'dggr':  (Q(form__title__icontains='DGGR') | Q(form__title__icontains='Scholarship') |
                      Q(form__title__icontains='Hardship') | Q(form__title__icontains='Form D') |
                      Q(form__title__icontains='Form F') | Q(form__title__icontains='Form G')),
            'ucepp': Q(form__title__icontains='UCEPP') | Q(form__title__icontains='Upgrading'),
        }
        if funding_type in mapping:
            qs = qs.filter(mapping[funding_type])
            if funding_type == 'cdfn':
                legacy_qs = legacy_qs.filter(form_type__icontains='PSSSP')
            elif funding_type == 'dggr':
                legacy_qs = legacy_qs.filter(form_type__icontains='DGGR')
            elif funding_type == 'ucepp':
                legacy_qs = legacy_qs.filter(form_type__icontains='UCEPP')

    # ── Date filter ──
    if date_from:
        qs = qs.filter(submitted_at__date__gte=date_from)
        legacy_qs = legacy_qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(submitted_at__date__lte=date_to)
        legacy_qs = legacy_qs.filter(created_at__date__lte=date_to)

    D = '—'  # default for missing values

    def _student_personal_banking(student, profile):
        """Return the 28 personal + banking + enrollment columns for a student."""
        u = student
        p = profile
        return [
            # Personal (18 cols)
            u.full_name if u else D,
            u.email if u else D,
            (u.phone or D) if u else D,
            (u.alternate_phone or D) if u else D,
            str(u.dob) if (u and u.dob) else D,
            (u.gender or (p.gender if p else D) or D) if u else D,
            (u.pronouns or (p.pronouns if p else D) or D) if u else D,
            (u.beneficiary_number or (p.beneficiary_number if p else D) or D) if u else D,
            (u.treaty_number or D) if u else D,
            (u.upi or D) if u else D,
            (u.mailing_address or (p.mailing_address if p else D) or D) if u else D,
            (p.town_city or D) if p else D,
            (p.postal_code or D) if p else D,
            (u.province_of_residence or D) if u else D,
            str(u.num_dependents) if u else D,
            (u.dependent_ages or D) if u else D,
            (u.financial_assistance_status or D) if u else D,
            ('Yes' if p.is_sfa_active else 'No') if p else D,
            # Banking (6 cols)
            (u.account_holder_name or D) if u else D,
            (u.account_type or D) if u else D,
            (u.bank_name or D) if u else D,
            (u.transit_number or D) if u else D,
            (u.inst_number or D) if u else D,
            (u.account_number or D) if u else D,
            # Enrollment (5 cols)
            (p.institute or D) if p else D,
            (u.institution_name or D) if u else D,
            (u.program_credential or D) if u else D,
            (u.enrollment_status or D) if u else D,
            str(u.course_load) if u else D,
        ]

    row_count = 0

    # ── New-model submission rows ──
    for sub in qs.order_by('-submitted_at'):
        student = sub.student
        profile = getattr(student, 'profile', None) if student else None
        payments = sub.payments.all()

        submission_cols = [
            f"FS-{sub.id}",
            sub.form.title if sub.form else D,
            sub.status,
            student.primary_stream if student else D,
        ]
        personal_banking = _student_personal_banking(student, profile)
        dates = [
            sub.submitted_at.strftime('%Y-%m-%d') if sub.submitted_at else D,
            sub.decided_at.strftime('%Y-%m-%d') if sub.decided_at else D,
            sub.decided_by.full_name if sub.decided_by else D,
        ]

        # Consolidate payment breakdown into columns
        breakdown = {'Tuition': 0, 'Living': 0, 'Books': 0, 'Travel': 0, 'Special': 0}
        for p in payments:
            pt = p.payment_type.lower()
            if 'tuition' in pt: breakdown['Tuition'] += p.amount
            elif 'living' in pt: breakdown['Living'] += p.amount
            elif 'book' in pt: breakdown['Books'] += p.amount
            elif 'travel' in pt: breakdown['Travel'] += p.amount
            else: breakdown['Special'] += p.amount

        breakdown_cols = [
            breakdown['Tuition'] or D,
            breakdown['Living'] or D,
            breakdown['Books'] or D,
            breakdown['Travel'] or D,
            breakdown['Special'] or D,
            sub.amount or sum(breakdown.values()) or 0
        ]

        writer.writerow(submission_cols + personal_banking + breakdown_cols + dates)
        row_count += 1

    # ── Legacy application rows ──
    for app in legacy_qs.order_by('-created_at'):
        student = app.student
        profile = getattr(student, 'profile', None) if student else None
        
        submission_cols = [
            f"LEG-{app.id}",
            app.form_type,
            app.status,
            student.primary_stream if student else D,
        ]
        personal_banking = _student_personal_banking(student, profile)
        dates = [
            app.created_at.strftime('%Y-%m-%d') if app.created_at else D,
            app.decision_at.strftime('%Y-%m-%d') if app.decision_at else D,
            app.decision_by or D,
        ]

        # For legacy, just show the total in the last column
        breakdown_cols = [D, D, D, D, D, app.amount or 0]

        writer.writerow(submission_cols + personal_banking + breakdown_cols + dates)
        row_count += 1

    return output.getvalue().encode('utf-8'), row_count


def _build_full_csv_from_qs(qs):
    """
    Same 42-column CSV but built from an already-filtered FormSubmission queryset.
    Used by dispatch_report so it only includes the exact unsent submissions.
    Returns (csv_bytes, row_count).
    """
    HEADERS = [
        'Submission ID', 'Form/Type', 'Status', 'Approved Amount ($)', 'Stream',
        'Full Name', 'Email', 'Phone', 'Alternate Phone',
        'Date of Birth', 'Gender', 'Pronouns',
        'Beneficiary #', 'Treaty #', 'UPI',
        'Mailing Address', 'Town/City', 'Postal Code', 'Province',
        'No. of Dependents', 'Dependent Ages',
        'Financial Assistance Status', 'SFA Active (Profile)',
        'Account Holder Name', 'Account Type',
        'Bank Name', 'Transit #', 'Institution #', 'Account #',
        'Institute (Profile)', 'Institution Name', 'Program', 'Enrollment Status', 'Course Load (%)',
        'Payment Type', 'Payment Amount ($)', 'Payment Status', 'Payment Reference #', 'Payment Date',
        'Submitted Date', 'Decision Date', 'Decided By',
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(HEADERS)

    D = '—'

    def _pb(student, profile):
        u, p = student, profile
        return [
            u.full_name if u else D, u.email if u else D,
            (u.phone or D) if u else D, (u.alternate_phone or D) if u else D,
            str(u.dob) if (u and u.dob) else D,
            (u.gender or (p.gender if p else D) or D) if u else D,
            (u.pronouns or (p.pronouns if p else D) or D) if u else D,
            (u.beneficiary_number or (p.beneficiary_number if p else D) or D) if u else D,
            (u.treaty_number or D) if u else D, (u.upi or D) if u else D,
            (u.mailing_address or (p.mailing_address if p else D) or D) if u else D,
            (p.town_city or D) if p else D, (p.postal_code or D) if p else D,
            (u.province_of_residence or D) if u else D,
            str(u.num_dependents) if u else D, (u.dependent_ages or D) if u else D,
            (u.financial_assistance_status or D) if u else D,
            ('Yes' if p.is_sfa_active else 'No') if p else D,
            (u.account_holder_name or D) if u else D, (u.account_type or D) if u else D,
            (u.bank_name or D) if u else D, (u.transit_number or D) if u else D,
            (u.inst_number or D) if u else D, (u.account_number or D) if u else D,
            (p.institute or D) if p else D,
            (u.institution_name or D) if u else D, (u.program_credential or D) if u else D,
            (u.enrollment_status or D) if u else D, str(u.course_load) if u else D,
        ]

    row_count = 0
    for sub in qs.order_by('-submitted_at'):
        student = sub.student
        profile = getattr(student, 'profile', None) if student else None
        payments = sub.payments.all()
        sub_cols = [
            f"FS-{sub.id}", sub.form.title if sub.form else D,
            sub.status, sub.amount or 0,
            student.primary_stream if student else D,
        ]
        pb = _pb(student, profile)
        dates = [
            sub.submitted_at.strftime('%Y-%m-%d') if sub.submitted_at else D,
            sub.decided_at.strftime('%Y-%m-%d') if sub.decided_at else D,
            sub.decided_by.full_name if sub.decided_by else D,
        ]
        if payments:
            for p in payments:
                writer.writerow(sub_cols + pb + [
                    p.payment_type, p.amount, p.status,
                    p.reference_number or D,
                    p.date_issued.strftime('%Y-%m-%d') if p.date_issued else D,
                ] + dates)
                row_count += 1
        else:
            writer.writerow(sub_cols + pb + [D, D, D, D, D] + dates)
            row_count += 1

    return output.getvalue().encode('utf-8'), row_count


# ---------------------------------------------------------------------------
# VIEWS
# ---------------------------------------------------------------------------

class RegisterView(viewsets.GenericViewSet):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserSerializer

    def create(self, request):
        user = User.objects.create_user(
            username=request.data.get('email'),
            email=request.data.get('email'),
            password=request.data.get('password'),
            first_name=request.data.get('firstName', ''),
            last_name=request.data.get('lastName', '')
        )
        Profile.objects.create(
            user=user,
            beneficiary_number=request.data.get('beneficiaryNo', ''),
            indian_status=request.data.get('treatyNum', '')
        )
        return Response({'status': 'user created'}, status=status.HTTP_201_CREATED)


class UserDetailView(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class ProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)


class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Application.objects.select_related(
            'student', 
            'student__profile'
        ).prefetch_related(
            'documents'
        ).order_by('-created_at')

        if user.role == 'director':
            return qs.filter(status__in=['pending', 'approved', 'denied'])
        if user.role == 'admin':
            return qs
        return qs.filter(student=user)

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)

    def perform_update(self, serializer):
        old_status = self.get_object().status
        instance = serializer.save()
        if instance.status == 'pending' and old_status != 'pending':
            if old_status != 'review' and self.request.user.role != 'director':
                # Revert status if not approved by admin first
                instance.status = old_status
                instance.save()
                from rest_framework.exceptions import ValidationError
                raise ValidationError("Application must be in 'Review' status before forwarding to Director.")
            
            directors = User.objects.filter(role='director')
            directors = User.objects.filter(role='director')
            for director in directors:
                from notifications.models import Notification
                Notification.objects.create(
                    user=director,
                    title="Legacy Application Awaiting Approval",
                    message=f"Application #{instance.id} from {instance.student.full_name if instance.student else 'Student'} needs your decision.",
                    link="/staff/director-queue"
                )
                if director.email:
                    try:
                        from notifications.utils import email_director_approval_request
                        email_director_approval_request(
                            director_email=director.email,
                            student_name=instance.student.full_name if instance.student else 'Student',
                            form_title=instance.form_type,
                            amount=float(0),
                            submission_id=f"legacy-{instance.id}",
                        )
                    except Exception:
                        pass

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        application = self.get_object()
        application.status = Application.Status.APPROVED
        application.decision_by = request.user.username
        application.decision_notes = request.data.get('notes', '')
        application.save()
        AuditLog.objects.create(
            action=f"Approved Application {application.id}",
            performed_by=request.user,
            application=application,
            details=application.decision_notes
        )
        return Response({'status': 'application approved'})

    @action(detail=True, methods=['post'])
    def deny(self, request, pk=None):
        application = self.get_object()
        application.status = Application.Status.DENIED
        application.decision_by = request.user.username
        application.decision_notes = request.data.get('notes', '')
        application.save()
        AuditLog.objects.create(
            action=f"Denied Application {application.id}",
            performed_by=request.user,
            application=application,
            details=application.decision_notes
        )
        return Response({'status': 'application denied'})

    @action(detail=True, methods=['post'])
    def request_info(self, request, pk=None):
        application = self.get_object()
        application.status = Application.Status.INFO_REQUIRED
        application.save()
        notes = request.data.get('notes', 'More information is required for your application.')
        create_notification(
            user=application.student,
            title="Information Requested",
            message=f"Staff has requested more information for your {application.form_type} application: {notes}",
            link=f"/dashboard?appId={application.id}"
        )
        AuditLog.objects.create(
            action=f"Requested Info for Application {application.id}",
            performed_by=request.user,
            application=application,
            details=notes
        )
        return Response({'status': 'info requested'})

    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):
        from api.models import PolicySetting
        from django.conf import settings as django_settings
        application = self.get_object()
        expiry_config = PolicySetting.objects.filter(section='system_config', field_key='share_link_expiry_days').first()
        expiry_days = int(expiry_config.value) if expiry_config else 7
        token = uuid.uuid4().hex
        expires_at = timezone.now() + timedelta(days=expiry_days)
        ShareableLink.objects.create(application=application, token=token, expires_at=expires_at)
        base_url = getattr(django_settings, 'SITE_URL', request.build_absolute_uri('/').rstrip('/'))
        return Response({'token': token, 'url': f"{base_url}/shared/{token}", 'expires_at': expires_at})


class SharedApplicationView(viewsets.GenericViewSet):
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['get'], url_path='view/(?P<token>[^/.]+)')
    def view_by_token(self, request, token=None):
        try:
            share_link = ShareableLink.objects.get(token=token)
            if not share_link.is_valid():
                return Response({'error': 'Link expired or invalid'}, status=status.HTTP_403_FORBIDDEN)
            return Response(ApplicationSerializer(share_link.application).data)
        except ShareableLink.DoesNotExist:
            return Response({'error': 'Link not found'}, status=status.HTTP_404_NOT_FOUND)


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if _is_staff(user):
            return self.queryset.all()
        return self.queryset.filter(user=user)

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        """Download CSV — approved records only (same as before)."""
        from django.http import HttpResponse

        funding_type = request.query_params.get('funding_type', 'all').lower()
        date_from    = request.query_params.get('date_from')
        date_to      = request.query_params.get('date_to')

        csv_bytes, row_count = _build_full_csv(
            funding_type=funding_type,
            date_from=date_from,
            date_to=date_to,
            all_statuses=False,   # approved-only for the download
            unsent_only=True
        )

        AuditLog.objects.create(
            action="Payment CSV Export Triggered",
            performed_by=request.user,
            details=f"Exported {row_count} records"
        )

        response = HttpResponse(csv_bytes, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="payment_export.csv"'
        return response

    @action(detail=False, methods=['post'], url_path='dispatch_report')
    def dispatch_report(self, request):
        """
        Email ONLY director-approved submissions that have NOT yet been sent to finance.
        Includes both modern FormSubmissions and legacy Applications.
        """
        from django.utils import timezone as tz
        from forms.models import FormSubmission
        from email_sender import send_finance_report, send_funding_processed

        # ── 1. Identify all approved but unsent records ──
        unsent_subs = FormSubmission.objects.filter(status='accepted', finance_sent_at__isnull=True)
        unsent_legacy = Application.objects.filter(status='approved', finance_sent_at__isnull=True)

        if not unsent_subs.exists() and not unsent_legacy.exists():
            return Response({
                'status': 'nothing_to_send',
                'count': 0,
                'message': 'No new approved applications to send — all have already been dispatched.',
            })

        # ── 2. Build combined CSV ──
        csv_bytes, total_rows = _build_full_csv(all_statuses=False, unsent_only=True)

        triggered_by = getattr(request.user, 'full_name', '') or request.user.email

        # ── 3. Send email ──
        ok = send_finance_report(
            csv_bytes=csv_bytes,
            total_students=total_rows,
            triggered_by=triggered_by,
        )

        if not ok:
            return Response(
                {'status': 'error', 'message': 'Failed to send email — check server logs.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # ── 4. Post-send: mark as sent and notify students ──
        now = tz.now()
        
        # Update FormSubmissions
        sub_ids = list(unsent_subs.values_list('id', flat=True))
        FormSubmission.objects.filter(id__in=sub_ids).update(
            status='sent_to_finance',
            finance_sent_at=now,
            finance_sent_by=request.user,
        )

        # Update Legacy Applications
        legacy_ids = list(unsent_legacy.values_list('id', flat=True))
        Application.objects.filter(id__in=legacy_ids).update(
            finance_sent_at=now,
            finance_sent_by=request.user,
        )

        # Per-submission: update payment, notify student
        for sub in unsent_subs.select_related('student', 'form'):
            student = sub.student
            if not student:
                continue

            # Mark any pending payments for this submission as issued
            # Use the new direct link to submission
            from api.models import Payment
            Payment.objects.filter(submission=sub, status=Payment.Status.PENDING).update(status=Payment.Status.ISSUED)

            # In-app notification
            create_notification(
                student,
                'Payment Sent to Finance 💰',
                f"Your approved funding for '{sub.form.title}' "
                f"(${sub.amount}) has been sent to the Finance Department. "
                f"Expect payment within 2–5 working days."
            )

            # Email notification
            if student.email:
                try:
                    # Build breakdown from payments
                    payments = list(sub.payments.filter(status=Payment.Status.ISSUED))
                    if payments:
                        breakdown = [{'name': p.payment_type, 'amount': float(p.amount)} for p in payments]
                        total = sum(b['amount'] for b in breakdown)
                    else:
                        breakdown = [{'name': sub.form.title, 'amount': float(sub.amount or 0)}]
                        total = float(sub.amount or 0)

                    send_funding_processed(
                        student_email=student.email,
                        student_name=student.full_name,
                        program_name=sub.form.title,
                        semester=sub.office_use_data.get('semester', '') if sub.office_use_data else '',
                        year=sub.office_use_data.get('year', '') if sub.office_use_data else '',
                        total_amount=total,
                        funding_breakdown=breakdown,
                    )
                except Exception as exc:
                    import logging
                    logging.getLogger(__name__).error(
                        'send_funding_processed failed for submission %s: %s', sub.id, exc
                    )

        # ── 5. Audit log ──
        AuditLog.objects.create(
            action=f"Finance Report Dispatched — {total_rows} new approved records",
            performed_by=request.user,
            role=request.user.role,
            details=f"Record counts: FormSubmissions={len(sub_ids)}, LegacyApps={len(legacy_ids)}",
        )

        return Response({
            'status': 'success',
            'count': total_rows,
            'message': f'Successfully dispatched {total_rows} records to Finance and marked them as sent.',
        })


class AppealViewSet(viewsets.ModelViewSet):
    queryset = Appeal.objects.all()
    serializer_class = AppealSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if _is_staff(user):
            return self.queryset.all()
        return self.queryset.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if _is_staff(user):
            return self.queryset.all()
        return self.queryset.filter(application__student=user)


class UserDocumentViewSet(viewsets.ModelViewSet):
    queryset = UserDocument.objects.all()
    serializer_class = UserDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if _is_staff(user):
            student_id = self.request.query_params.get('student_id')
            if student_id:
                return self.queryset.filter(user_id=student_id)
            return self.queryset.all()
        return self.queryset.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = self.queryset
        submission  = self.request.query_params.get('submission')
        application = self.request.query_params.get('application')
        if submission:
            qs = qs.filter(details__icontains=f'submission {submission}')
        if application:
            qs = qs.filter(application_id=application)
        return qs
