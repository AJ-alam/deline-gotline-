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
import uuid
from django.utils import timezone
from datetime import timedelta

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
        if user.is_staff:
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
        application = self.get_object()
        # Generate a 7-day share link by default
        token = uuid.uuid4().hex
        expires_at = timezone.now() + timedelta(days=7)
        
        share_link = ShareableLink.objects.create(
            application=application,
            token=token,
            expires_at=expires_at
        )
        
        # In a real app, you'd use a site-wide config for the base URL
        base_url = "http://localhost:5173/shared" 
        full_url = f"{base_url}/{token}"
        
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
        if user.is_staff:
            return self.queryset.all()
        return self.queryset.filter(user=user)

    @action(detail=False, methods=['post'])
    def dispatch_report(self, request):
        from api.models import PolicySetting, AuditLog
        
        # Get the finance email from config
        email_config = PolicySetting.objects.filter(section='system_config', field_key='finance_email').first()
        recipient = email_config.unit if email_config else "finance@organization.com"
        
        # In a real production environment, this would trigger a Celery task to send an actual email
        # For now, we log the event and simulate success
        AuditLog.objects.create(
            action=f"Finance Report Dispatched to {recipient}",
            performed_by=request.user,
            details=f"Report included {Payment.objects.filter(status='released').count()} released payments."
        )
        
        return Response({
            'status': 'success',
            'recipient': recipient,
            'message': f"Report successfully dispatched to {recipient}"
        })

class AppealViewSet(viewsets.ModelViewSet):
    queryset = Appeal.objects.all()
    serializer_class = AppealSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return self.queryset.all()
        return self.queryset.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset.all()
        return self.queryset.filter(application__student=self.request.user)

class UserDocumentViewSet(viewsets.ModelViewSet):
    queryset = UserDocument.objects.all()
    serializer_class = UserDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAdminUser]
