"""Authentication and the signed-in user's own record."""

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.api.serializers import RegisterSerializer, UserSerializer
from accounts.services import eligibility as eligibility_service


class EligibilityView(APIView):
    """The screening questions, and the decision for a given set of answers.

    Public: someone has to be able to check before they have an account.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'questions': eligibility_service.questions_payload()})

    def post(self, request):
        outcome = eligibility_service.assess(request.data.get('answers') or {})
        return Response(outcome.as_dict())


class RegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer
    throttle_scope = 'auth'

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class MeView(generics.RetrieveUpdateAPIView):
    """The signed-in user's own record. Never anyone else's."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
