"""The payment run.

Restricted to finance: the people who review and decide an application are not
the people who release the money, and keeping those apart is the ordinary
control on a funding body.
"""

from decimal import Decimal

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
        batches = finance.payment_batches(ready)
        blocked_total = sum((row['award'].amount for row in blocked), Decimal('0.00'))
        ready_total = sum((batch['amount'] for batch in batches), Decimal('0.00'))
        return Response({
            # One payment per application, because that is what finance is
            # asked to do. `count` counts payments, not award lines: "Send 4
            # awards" against one student and one bank transfer described the
            # rules rather than the act.
            'count': len(batches),
            'total': str(ready_total),
            # Both figures, on the screen that has to explain them. The
            # dashboard counts every pending award; this screen counted only the
            # payable ones, so "$80,650.00 awaiting payment" sat beside "Ready
            # to pay $0.00" with nothing saying the difference was blocked. Two
            # numbers for one pot, and neither admitted the other existed.
            'blocked_total': str(blocked_total),
            'pending_total': str(ready_total + blocked_total),
            'awards': [
                {
                    'id': batch['application'].pk,
                    'student': batch['student'].full_name,
                    'application_id': batch['application'].pk,
                    'category': '; '.join(batch['categories']),
                    'lines': len(batch['awards']),
                    # The award lines this one payment is made of. The row's own
                    # `id` is the application now, so without these there is no
                    # way to ask whether a superseded pricing is still being
                    # offered — an invariant that must survive the payment file
                    # becoming a lump sum, because it is what stops money going
                    # out twice.
                    'award_ids': [award.pk for award in batch['awards']],
                    'amount': str(batch['amount']),
                    # Where this payment is going, on the screen where somebody
                    # commits to sending it. The account was in the CSV and
                    # nowhere else, so the only way to check a transit number
                    # before releasing money was to send the batch first and
                    # open the file afterwards — by which point every award in
                    # it is marked paid and cannot be sent again.
                    #
                    # Masked to the last four. Finance is releasing money to an
                    # account already on file, not transcribing it: the digits
                    # that matter for a sanity check are the ones that identify
                    # which account it is, and the file carries the whole thing.
                    'account_holder': batch['account'].account_holder,
                    'account': f"••••{batch['account'].account_number[-4:]}",
                    'transit_number': batch['account'].transit_number,
                    'institution_number': batch['account'].institution_number,
                }
                for batch in batches
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
