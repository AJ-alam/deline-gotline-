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

def _build_full_csv(funding_type='all', date_from=None, date_to=None, all_statuses=False):
    """
    Build the 21-column student records CSV.

    Parameters
    ----------
    all_statuses : bool
        False  → only accepted/approved records  (used by export_csv)
        True   → every record regardless of status (used by dispatch_report)

    Returns
    -------
    (csv_bytes: bytes, row_count: int)
    """
    from forms.models import FormSubmission
    from django.db.models import Q

    HEADERS = [
        'Submission ID', 'Student Name', 'Student Email', 'Beneficiary #', 'Phone Number',
        'Mailing Address', 'Town/City', 'Postal Code', 'Institute',
        'Form/Type', 'Stream', 'Status', 'Approved Amount ($)',
        'Payment Type', 'Payment Amount ($)', 'Payment Status', 'Payment Reference #', 'Payment Date',
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

    qs = qs.select_related('student', 'form', 'decided_by').prefetch_related('student__payments', 'student__profile')

    # ── Legacy applications ──
    if all_statuses:
        legacy_qs = Application.objects.all()
    else:
        legacy_qs = Application.objects.filter(status='approved')

    legacy_qs = legacy_qs.select_related('student').prefetch_related('student__payments', 'student__profile')

    # ── Funding-type filter (only meaningful for approved export) ──
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

    row_count = 0

    # ── Write new-model rows ──
    for sub in qs.order_by('-submitted_at'):
        student = sub.student
        profile = getattr(student, 'profile', None) if student else None
        payments = student.payments.all() if student else []

        base = [
            f"FS-{sub.id}",
            student.full_name if student else '—',
            student.email if student else '—',
            profile.beneficiary_number if profile else '—',
            profile.phone_number if profile else '—',
            profile.mailing_address if profile else '—',
            profile.town_city if profile else '—',
            profile.postal_code if profile else '—',
            profile.institute if profile else '—',
            sub.form.title if sub.form else '—',
            student.primary_stream if student else '—',
            sub.status,
            sub.amount or 0,
        ]
        dates = [
            sub.submitted_at.strftime('%Y-%m-%d') if sub.submitted_at else '—',
            sub.decided_at.strftime('%Y-%m-%d') if sub.decided_at else '—',
            sub.decided_by.full_name if sub.decided_by else '—',
        ]

        if payments:
            for p in payments:
                writer.writerow(base + [
                    p.payment_type, p.amount, p.status,
                    p.reference_number or '—',
                    p.date_issued.strftime('%Y-%m-%d') if p.date_issued else '—',
                ] + dates)
                row_count += 1
        else:
            writer.writerow(base + ['—', '—', '—', '—', '—'] + dates)
            row_count += 1

    # ── Write legacy-model rows ──
    for app in legacy_qs.order_by('-created_at'):
        student = app.student
        profile = getattr(student, 'profile', None) if student else None
        payments = student.payments.filter(application=app) if student else []

        base = [
            f"LEG-{app.id}",
            student.full_name if student else '—',
            student.email if student else '—',
            profile.beneficiary_number if profile else '—',
            profile.phone_number if profile else '—',
            profile.mailing_address if profile else '—',
            profile.town_city if profile else '—',
            profile.postal_code if profile else '—',
            profile.institute if profile else '—',
            app.form_type,
            student.primary_stream if student else '—',
            app.status,
            0,
        ]
        dates = [
            app.created_at.strftime('%Y-%m-%d') if app.created_at else '—',
            app.decision_at.strftime('%Y-%m-%d') if app.decision_at else '—',
            app.decision_by or '—',
        ]

        if payments:
            for p in payments:
                writer.writerow(base + [
                    p.payment_type, p.amount, p.status,
                    p.reference_number or '—',
                    p.date_issued.strftime('%Y-%m-%d') if p.date_issued else '—',
                ] + dates)
                row_count += 1
        else:
            writer.writerow(base + ['—', '—', '—', '—', '—'] + dates)
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
        if user.role == 'director':
            return self.queryset.filter(status__in=['pending', 'approved', 'denied'])
        if user.role == 'admin':
            return self.queryset.all()
        return self.queryset.filter(student=user)

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)

    def perform_update(self, serializer):
        old_status = self.get_object().status
        instance = serializer.save()
        if instance.status == 'pending' and old_status != 'pending':
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
        )

        AuditLog.objects.create(
            action="Payment CSV Export Triggered",
            performed_by=request.user,
            details=f"Exported {row_count} records"
        )

        response = HttpResponse(csv_bytes, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="payment_export.csv"'
        return response

    @action(detail=False, methods=['post'])
    def dispatch_report(self, request):
        """
        Email the COMPLETE student records CSV (ALL statuses, new + legacy)
        to the Finance Department email defined in .env (FINANCE_EMAIL).
        """
        from email_sender import send_finance_report

        # ALL records — every status, every submission, every legacy application
        csv_bytes, total_rows = _build_full_csv(all_statuses=True)

        triggered_by = getattr(request.user, 'full_name', '') or request.user.email

        ok = send_finance_report(
            csv_bytes=csv_bytes,
            total_students=total_rows,
            triggered_by=triggered_by,
        )

        if ok:
            AuditLog.objects.create(
                action=f"Finance Report Emailed — ALL records ({total_rows} rows)",
                performed_by=request.user,
                role=request.user.role,
            )
            return Response({
                'status': 'success',
                'count': total_rows,
                'message': f'Full report ({total_rows} records, all statuses) sent to Finance Department',
            })
        return Response(
            {'status': 'error', 'message': 'Failed to send email — check server logs.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    @action(detail=False, methods=['post'])
    def dispatch_report_legacy(self, request):
        # kept for backwards compat — delegates to dispatch_report
        return self.dispatch_report(request)


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
