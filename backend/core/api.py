"""Endpoints that belong to the portal itself rather than to a domain app."""

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core import support


class HelpView(APIView):
    """Contact details and the questions the office is asked most.

    Open without a session on purpose. The people who most need a phone number
    are the ones who cannot get in, and a help page behind a login is help for
    everybody except them.
    """

    permission_classes = [AllowAny]
    # Nothing here is per-user, and it changes about once a year.
    authentication_classes = []

    def get(self, request):
        return Response(support.payload())
