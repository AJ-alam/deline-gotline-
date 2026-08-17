"""Reading notices in the portal.

A person only ever sees their own. There is no staff view of someone else's
notices: the audit trail is where a reviewer looks to see what happened to an
application, not another person's inbox.
"""

from django.db.models import Q
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.models import Notification

# A person who has ignored a hundred notices does not need all hundred sent to
# their browser; the rest are history rather than something to act on.
PAGE_SIZE = 50


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ('id', 'kind', 'title', 'message', 'link', 'is_read',
                  'created_at')
        read_only_fields = fields


class NotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Notification.objects.filter(user=request.user)
        unread = queryset.filter(is_read=False).count()

        if request.query_params.get('unread') == 'true':
            queryset = queryset.filter(is_read=False)

        return Response({
            'unread': unread,
            'results': NotificationSerializer(queryset[:PAGE_SIZE], many=True).data,
        })

    def post(self, request):
        """Mark notices read.

        With no ids, marks everything read. Scoped to the signed-in user, so an
        id belonging to someone else simply matches nothing.
        """
        ids = request.data.get('ids')
        queryset = Notification.objects.filter(user=request.user, is_read=False)
        if ids:
            if not isinstance(ids, list):
                return Response({'ids': 'Expected a list of notification ids.'},
                                status=status.HTTP_400_BAD_REQUEST)
            queryset = queryset.filter(id__in=ids)

        marked = queryset.update(is_read=True)
        return Response({
            'marked': marked,
            'unread': Notification.objects.filter(
                user=request.user, is_read=False).count(),
        })
