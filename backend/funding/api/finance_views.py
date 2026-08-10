"""The payment run.

Restricted to finance: the people who review and decide an application are not
the people who release the money, and keeping those apart is the ordinary
control on a funding body.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import HttpResponse

from funding.services import finance


def _finance_only(user):
    return bool(user and user.is_authenticated and user.handles_payments)


class PendingAwardsView(APIView):
    """What is ready to pay, and what is blocking anything from being paid."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _finance_only(request.user):
            return Response({'detail': 'Only Finance may view the payment run.'},
                            status=status.HTTP_403_FORBIDDEN)

        ready, blocked = finance.preview()
        return Response({
            'count': len(ready),
            'total': sum((row['award'].amount for row in ready), 0),
            'awards': [
                {
                    'id': row['award'].pk,
                    'student': row['award'].application.student.full_name,
                    'application_id': row['award'].application_id,
                    'category': row['award'].get_category_display(),
                    'amount': str(row['award'].amount),
                }
                for row in ready
            ],
            'blocked': [
                {
                    'award_id': row['award'].pk,
                    'application_id': row['award'].application_id,
                    'reason': row['reason'],
                }
                for row in blocked
            ],
        })


class DispatchView(APIView):
    """Send the batch and return the file."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _finance_only(request.user):
            return Response({'detail': 'Only Finance may send a payment run.'},
                            status=status.HTTP_403_FORBIDDEN)

        try:
            result = finance.dispatch(actor=request.user)
        except finance.DispatchError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)

        response = HttpResponse(result['csv'], content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{result["filename"]}"'
        # Counts travel in headers so the browser can report them alongside the
        # download without a second request.
        response['X-Award-Count'] = str(result['count'])
        response['X-Award-Total'] = str(result['total'])
        response['X-Blocked-Count'] = str(len(result['blocked']))
        return response
