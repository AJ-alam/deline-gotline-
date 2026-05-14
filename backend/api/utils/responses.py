import logging
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def api_response(success=True, data=None, message="", status=200):
    return Response({
        "success": success,
        "data": data,
        "message": message,
    }, status=status)


def custom_exception_handler(exc, context):
    """
    Wraps DRF's default handler so all error responses use the api_response
    format. Prevents raw Django error HTML and internal stack traces from
    reaching API clients.
    """
    response = drf_exception_handler(exc, context)

    if response is None:
        # Unhandled exception — log it and return a generic 500
        logger.exception(
            "Unhandled exception in view %s: %s",
            context.get('view', '?'),
            exc,
        )
        return api_response(False, None, "An unexpected error occurred.", status=500)

    # Re-wrap DRF's structured error in our standard envelope
    error_data = response.data
    if isinstance(error_data, dict) and 'detail' in error_data:
        message = str(error_data['detail'])
        data = None
    elif isinstance(error_data, list) and error_data:
        # ValidationError raised with a plain string becomes a list
        message = str(error_data[0])
        data = None
    elif isinstance(error_data, dict):
        # Field-level errors: grab first message from first field
        msgs = []
        for v in error_data.values():
            msgs.extend(v if isinstance(v, list) else [v])
        message = str(msgs[0]) if msgs else "Request failed."
        data = error_data
    else:
        message = "Request failed."
        data = error_data

    return api_response(False, data, message, status=response.status_code)
