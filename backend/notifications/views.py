from rest_framework import viewsets, permissions, decorators, status
from rest_framework.response import Response  # noqa: used in list() override
from .models import Notification
from .serializers import NotificationSerializer
from core.utils import api_response

class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()[:100]
        serializer = self.get_serializer(qs, many=True)
        return Response({'results': serializer.data, 'count': len(serializer.data)})

    @decorators.action(detail=True, methods=['post'], url_path='read')
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return api_response(True, {"id": notification.id, "is_read": True}, "Notification marked as read")

    @decorators.action(detail=False, methods=['post'], url_path='read-all')
    def mark_all_as_read(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return api_response(True, None, "All notifications marked as read")
