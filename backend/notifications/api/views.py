"""Reading notices in the portal.

A person only ever sees their own. There is no staff view of someone else's
notices: the audit trail is where a reviewer looks to see what happened to an
application, not another person's inbox.
"""

import hmac

from django.conf import settings
from django.db.models import Q
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.delivery import deliver_pending
from notifications.diagnostics import email_health
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


# How many messages one call will attempt. The queue is drained by an external
# scheduler on a short interval, so the ceiling exists to keep a single request
# inside a serverless function's time limit rather than to ration delivery — a
# backlog is cleared by the next tick, not by one long request that times out
# halfway and leaves the outbox in an unknown state.
DRAIN_LIMIT = 50


class TaskTokenView(APIView):
    """Base for the endpoints a scheduler calls, not a person.

    Authorised by a shared secret rather than by a session, because the caller
    is a cron line with no account. That makes the token the only thing standing
    in front of these, so an unset token **refuses** rather than opening them: a
    blank secret compared against a blank header is a match, and the failure mode
    of getting this backwards is a public endpoint anybody can use.

    Shared by both task endpoints on purpose. The refusals are the security of
    this pair, and a second copy of them is a copy that can drift — the drain
    was written first and the diagnostic added later, which is exactly when one
    of two hand-written checks quietly loses a case the other has.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_scope = 'email_drain'

    def authorise(self, request):
        """None when the caller may proceed; the refusal to return otherwise."""
        expected = getattr(settings, 'TASK_TOKEN', '') or ''
        if not expected:
            return Response(
                {'detail': 'TASK_TOKEN is not configured; refusing without one.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        presented = self._presented(request)
        # compare_digest rather than == so the token cannot be recovered a
        # character at a time from response timings.
        if not presented or not hmac.compare_digest(presented, expected):
            return Response({'detail': 'Not authorised.'},
                            status=status.HTTP_403_FORBIDDEN)
        return None

    @staticmethod
    def _presented(request) -> str:
        """The secret the caller offered, from either header.

        `Authorization: Bearer …` is what most schedulers send by default;
        `X-Task-Token` is accepted because some shared-hosting cron setups strip
        Authorization before it reaches the application.
        """
        header = request.META.get('HTTP_AUTHORIZATION', '')
        if header.startswith('Bearer '):
            return header[len('Bearer '):].strip()
        return request.META.get('HTTP_X_TASK_TOKEN', '').strip()


class SendQueuedEmailsView(TaskTokenView):
    """Drain the outbound queue. Called by a scheduler, not by a person.

    `send_queued_emails` exists as a management command and nothing on a
    serverless deployment can run one on a timer — which is exactly how 143
    messages once sat unsent. This is that command reachable over HTTP so an
    ordinary cron can drive it.
    """

    def post(self, request):
        refusal = self.authorise(request)
        if refusal is not None:
            return refusal

        return Response(deliver_pending(limit=DRAIN_LIMIT))


class EmailStatusView(TaskTokenView):
    """Whether mail can leave this deployment at all — read-only.

    The drain endpoint exists because nothing on serverless can run a management
    command on a timer. `email_status` is a management command for exactly the
    same reason and had no such counterpart, so the one deployment where email
    was actually broken was the one place the diagnostic could not be run: the
    office saw a portal that worked, students received nothing, and the only way
    to tell which of the three failure modes was in play was to guess.

    GET because it changes nothing. Behind the same token as the drain: it
    reports what is configured, and that is not something to publish. It reports
    no secret even to a caller holding the token.
    """

    def get(self, request):
        refusal = self.authorise(request)
        if refusal is not None:
            return refusal

        return Response(email_health())
