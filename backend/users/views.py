# DEPRECATED: Logic migrated to backend/api/controllers/auth_controller.py
from django.http import HttpResponse

def deprecated_view(request):
    return HttpResponse("This view has been migrated to the new API structure.", status=410)
