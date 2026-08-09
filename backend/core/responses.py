"""Error handling for the API.

The previous handler wrapped every response in {success, data, message} and
flattened field errors down to a single string taken from the first field. A
client could not tell which question was wrong, and the envelope duplicated
information the HTTP status code already carried.

Errors now use DRF's standard shape, which every client library and the OpenAPI
schema already understand. The only thing added is a guard so an unhandled
exception returns a generic message instead of a stack trace.
"""

import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)

    if response is None:
        # Not a DRF exception: log it in full, tell the client nothing useful
        # to an attacker.
        logger.exception(
            'Unhandled exception in %s: %s', context.get('view', '?'), exc,
        )
        return Response({'detail': 'An unexpected error occurred.'}, status=500)

    return response
