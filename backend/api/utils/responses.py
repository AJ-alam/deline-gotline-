from rest_framework.response import Response

def api_response(success=True, data=None, message="", status=200):
    """
    Standard API response wrapper.
    Matches the Node.js 'response.utils.js' pattern.
    """
    return Response({
        "success": success,
        "data": data,
        "message": message
    }, status=status)
