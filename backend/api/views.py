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
        # Staff/Director can see more, students only see their own
        if _is_staff(user):
            return self.queryset.all()
        return self.queryset.filter(student=user)

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)

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
        
        # Create notification for student
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

        share_link = ShareableLink.objects.create(
            application=application,
            token=token,
            expires_at=expires_at
        )

        base_url = getattr(django_settings, 'SITE_URL', request.build_absolute_uri('/').rstrip('/'))
        full_url = f"{base_url}/shared/{token}"

        return Response({
            'token': token,
            'url': full_url,
            'expires_at': expires_at
        })

class SharedApplicationView(viewsets.GenericViewSet):
    permission_classes = [permissions.AllowAny]
    
    @action(detail=False, methods=['get'], url_path='view/(?P<token>[^/.]+)')
    def view_by_token(self, request, token=None):
        try:
            share_link = ShareableLink.objects.get(token=token)
            if not share_link.is_valid():
                return Response({'error': 'Link expired or invalid'}, status=status.HTTP_403_FORBIDDEN)
            
            serializer = ApplicationSerializer(share_link.application)
            return Response(serializer.data)
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
        """Return CSV of all approved FormSubmission records."""
        import csv
        import io
        from django.http import HttpResponse
        from forms.models import FormSubmission
        from django.db.models import Q

        funding_type = request.query_params.get('funding_type', 'all').lower()
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        qs = FormSubmission.objects.filter(status='accepted').select_related('student', 'form', 'decided_by')

        mapping = {
            'cdfn': Q(form__title__icontains='FormA') | Q(form__title__icontains='FormC'),
            'dggr': Q(form__title__icontains='DGGR') | Q(form__title__icontains='Scholarship') | Q(form__title__icontains='Hardship') | Q(form__title__icontains='Form D') | Q(form__title__icontains='Form F') | Q(form__title__icontains='Form G'),
            'ucepp': Q(form__title__icontains='UCEPP') | Q(form__title__icontains='Upgrading'),
        }
        if funding_type in mapping:
            qs = qs.filter(mapping[funding_type])
        if date_from:
            qs = qs.filter(submitted_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(submitted_at__date__lte=date_to)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Submission ID', 'Student Name', 'Student Email', 'Beneficiary #',
            'Form', 'Stream', 'Status', 'Approved Amount ($)',
            'Submitted Date', 'Decision Date', 'Decided By'
        ])
        for sub in qs.order_by('-decided_at'):
            student = sub.student
            stream = ''
            if student:
                stream = student.primary_stream or ''
            writer.writerow([
                sub.id,
                student.full_name if student else '',
                student.email if student else '',
                student.beneficiary_number if student else '',
                sub.form.title if sub.form else '',
                stream,
                sub.status,
                sub.amount,
                sub.submitted_at.strftime('%Y-%m-%d') if sub.submitted_at else '',
                sub.decided_at.strftime('%Y-%m-%d') if sub.decided_at else '',
                sub.decided_by.full_name if sub.decided_by else '',
            ])

        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="approved_applications.csv"'
        AuditLog.objects.create(
            action="Approved Applications CSV Exported",
            performed_by=request.user,
            role=request.user.role,
        )
        return response

    @action(detail=False, methods=['post'])
    def dispatch_report(self, request):
        import csv
        import io
        from django.core.mail import EmailMessage
        from forms.models import FormSubmission
        from api.models import PolicySetting, AuditLog

        email_config = PolicySetting.objects.filter(section='system_config', field_key='finance_email').first()
        recipient = email_config.unit if email_config else "finance@deline.ca"

        # Build CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Submission ID', 'Student Name', 'Student Email', 'Beneficiary #',
            'Form', 'Stream', 'Status', 'Approved Amount ($)',
            'Submitted Date', 'Decision Date', 'Decided By'
        ])
        qs = FormSubmission.objects.filter(status='accepted').select_related('student', 'form', 'decided_by').order_by('-decided_at')
        for sub in qs:
            student = sub.student
            writer.writerow([
                sub.id,
                student.full_name if student else '',
                student.email if student else '',
                student.beneficiary_number if student else '',
                sub.form.title if sub.form else '',
                student.primary_stream if student else '',
                sub.status,
                sub.amount,
                sub.submitted_at.strftime('%Y-%m-%d') if sub.submitted_at else '',
                sub.decided_at.strftime('%Y-%m-%d') if sub.decided_at else '',
                sub.decided_by.full_name if sub.decided_by else '',
            ])

        csv_bytes = output.getvalue().encode('utf-8')
        count = qs.count()

        try:
            email = EmailMessage(
                subject='[DGG Funding] Approved Applications Report',
                body=(
                    f"Please find attached the approved applications export.\n\n"
                    f"Total approved: {count}\n"
                    f"Dispatched by: {request.user.full_name or request.user.email}\n"
                ),
                to=[recipient],
            )
            email.attach('approved_applications.csv', csv_bytes, 'text/csv')
            email.send()
            AuditLog.objects.create(
                action=f"Finance Report Emailed to {recipient} ({count} records)",
                performed_by=request.user,
                role=request.user.role,
            )
            return Response({'status': 'success', 'recipient': recipient, 'count': count,
                             'message': f'Report with {count} records sent to {recipient}'})
        except Exception as e:
            return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        submission = self.request.query_params.get('submission')
        application = self.request.query_params.get('application')
        if submission:
            qs = qs.filter(details__icontains=f'submission {submission}')
        if application:
            qs = qs.filter(application_id=application)
        return qs
