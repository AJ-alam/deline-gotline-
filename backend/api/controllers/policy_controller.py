from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from api.utils.responses import api_response
from api.models import PolicySetting, AuditLog
from api.serializers import PolicySettingSerializer
from users.permissions import IsAdminUser, IsDirectorUser

class PolicyViewSet(viewsets.ModelViewSet):
    queryset = PolicySetting.objects.all().order_by('section', 'field_key')
    serializer_class = PolicySettingSerializer

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'bulk_update', 'reset_section']:
            return [permissions.IsAuthenticated(), IsDirectorUser()]
        return [permissions.IsAuthenticated()]

    def perform_update(self, serializer):
        instance = serializer.save(last_updated_by=self.request.user)
        AuditLog.objects.create(
            action=f"Policy updated: [{instance.section}] — {instance.field_label} changed to {instance.value}{instance.unit}",
            performed_by=self.request.user,
            role=self.request.user.role,
        )

    @action(detail=False, methods=['post'], url_path='bulk_update')
    def bulk_update(self, request):
        """
        Allows updating multiple policy settings in a single request (e.g., an entire section).
        """
        settings_data = request.data.get('settings', [])
        if not settings_data:
            return api_response(False, None, "No settings provided", status.HTTP_400_BAD_REQUEST)

        updated_count = 0
        section_name = "Multiple Sections"
        if len(settings_data) > 0:
            section_id = settings_data[0].get('section')
            if all(s.get('section') == section_id for s in settings_data):
                section_name = section_id

        for data in settings_data:
            setting_id = data.get('id')
            try:
                instance = PolicySetting.objects.get(id=setting_id)
                serializer = self.get_serializer(instance, data=data, partial=True)
                if serializer.is_valid():
                    serializer.save(last_updated_by=request.user)
                    updated_count += 1
            except PolicySetting.DoesNotExist:
                continue

        if updated_count > 0:
            AuditLog.objects.create(
                action=f"Bulk Policy Update: [{section_name}] — {updated_count} fields updated",
                performed_by=request.user,
                role=request.user.role,
            )
            return api_response(True, {'updated_count': updated_count}, f"Successfully updated {updated_count} settings")
        
        return api_response(False, None, "No settings were updated", status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def all_settings(self, request):
        """
        Returns all policy settings grouped by section for the frontend.
        """
        settings = self.get_queryset()
        serializer = self.get_serializer(settings, many=True)
        
        # Group by section
        grouped = {}
        for item in serializer.data:
            sec = item['section']
            if sec not in grouped:
                grouped[sec] = []
            grouped[sec].append(item)
            
        return api_response(True, grouped, "All policy settings retrieved")
