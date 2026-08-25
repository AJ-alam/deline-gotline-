"""The student's own profile.

Everything a student keeps on file about themselves, so that filing a form is
confirming what the portal already knows rather than typing it again. Three
endpoints because they are three different kinds of fact — see
`accounts.services.profile`.

All three are students only. Staff have no eligibility screening, no enrolment
and no bank account in this system, and an endpoint that quietly did nothing for
four of the five roles would be an endpoint nobody could reason about. The
office edits a *student's* answers through the application amendment path, where
the change is attached to the application it affects and the applicant is told.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.api.permissions import IsStudent
from accounts.api.serializers import (
    BankAccountSerializer, BankingSerializer, EligibilityUpdateSerializer,
    EnrolmentProfileSerializer, UserSerializer,
)
from accounts.services import profile as profile_service


class EligibilityProfileView(APIView):
    """The six screening questions, this student's answers, and the outcome."""

    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request):
        return Response(profile_service.screening_state(request.user))

    def put(self, request):
        serializer = EligibilityUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        outcome = profile_service.save_screening(
            request.user, serializer.validated_data['answers'])

        # The outcome *and* the account, in one response. The streams are shown
        # on the same screen, and a client that had to re-fetch `/api/me/` to
        # find out what its own write did would show the previous answer for as
        # long as that request took.
        return Response({
            'outcome': outcome.as_dict(),
            'user': UserSerializer(request.user).data,
            **profile_service.screening_state(request.user),
        })


class EnrolmentProfileView(APIView):
    """Where this student studies, kept so their next form opens filled in.

    Nothing here is required and nothing here decides money — see the docstring
    on `accounts.models.EnrolmentProfile`.
    """

    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request):
        profile = profile_service.enrolment_profile(request.user)
        return Response(EnrolmentProfileSerializer(profile).data)

    def put(self, request):
        """Save the profile.

        Omitting a field leaves it alone; sending it empty clears it. What
        actually holds that line is that every column on `EnrolmentProfile` is
        optional — a field absent from the payload is absent from
        `validated_data` and never reaches the row. `partial=True` is belt and
        braces for the day somebody makes one of them required, and
        `test_profile.EnrolmentProfileTests` pins the optionality itself so that
        day does not arrive silently.
        """
        profile = profile_service.enrolment_profile(request.user)
        serializer = EnrolmentProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class BankingProfileView(APIView):
    """Where this student is paid.

    Reading returns the masked account and never the digits. Writing goes
    through `funding.services.banking.set_current`, which is the same call the
    application forms route their payment section through: one account record,
    one history, and a payment already sent stays traceable to the details that
    were in force when it went out.
    """

    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request):
        # Wrapped rather than returned bare. A DRF response whose body is `None`
        # is 200 with no content type at all, which a client cannot parse — so
        # "no account on file" would arrive as a transport error rather than as
        # an answer.
        current = request.user.bank_accounts.filter(is_current=True).first()
        return Response({
            'account': BankAccountSerializer(current).data if current else None,
        })

    def put(self, request):
        from funding.models import AuditEntry
        from funding.services import banking

        serializer = BankingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        account = banking.set_current(request.user, serializer.validated_data)

        # Where somebody's money goes, changed by the person it goes to. Worth a
        # record even though the previous account is retired rather than
        # overwritten: the retired row says what it was, this says who changed it
        # and when.
        AuditEntry.objects.create(
            actor=request.user, actor_role=request.user.role,
            action='account.banking_updated',
            detail=f'{request.user.email} set their payment account to '
                   f'{account.masked_account_number}.',
        )

        return Response({'account': BankAccountSerializer(account).data},
                        status=status.HTTP_200_OK)
