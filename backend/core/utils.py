from rest_framework.response import Response

def api_response(success=True, data=None, message="", status=200):
    return Response({
        "success": success,
        "data": data,
        "message": message
    }, status=status)
