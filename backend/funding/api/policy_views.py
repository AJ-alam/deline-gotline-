"""Administering funding rates.

Rates decide every award, so writing to them is restricted to administrators and
every change is recorded. Reading is open to staff, because a support worker
explaining an amount to a student needs to see the rate behind it.
"""

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from funding.models import PolicySetting, RuleSet
from funding.services import policy_admin


class PolicySettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicySetting
        fields = ('id', 'section', 'key', 'label', 'value', 'unit',
                  'is_active', 'updated_at')
        read_only_fields = fields


class PolicyChangeSerializer(serializers.Serializer):
    previous_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    new_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    effective_date = serializers.DateField()
    changed_at = serializers.DateTimeField()
    changed_by = serializers.SerializerMethodField()

    def get_changed_by(self, change):
        return change.changed_by.full_name if change.changed_by else None


class RuleSetSerializer(serializers.ModelSerializer):
    rule_count = serializers.IntegerField(source='rules.count', read_only=True)

    class Meta:
        model = RuleSet
        fields = ('id', 'name', 'version', 'status', 'effective_from',
                  'effective_to', 'notes', 'published_at', 'rule_count')
        read_only_fields = fields


def _staff(user):
    return bool(user and user.is_authenticated and (
        user.reviews_applications or user.decides_applications or user.handles_payments
    ))


class PolicySettingsView(APIView):
    """Every rate, grouped the way an administrator thinks about them."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _staff(request.user):
            return Response({'detail': 'Only staff may view funding rates.'},
                            status=status.HTTP_403_FORBIDDEN)

        grouped = policy_admin.grouped_settings()
        return Response([
            {
                'section': section,
                'settings': PolicySettingSerializer(settings, many=True).data,
            }
            for section, settings in sorted(grouped.items())
        ])


class PolicySettingDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _staff(request.user):
            return Response({'detail': 'Only staff may view funding rates.'},
                            status=status.HTTP_403_FORBIDDEN)
        try:
            setting = PolicySetting.objects.get(pk=pk)
        except PolicySetting.DoesNotExist:
            return Response({'detail': 'No such rate.'}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'setting': PolicySettingSerializer(setting).data,
            'history': PolicyChangeSerializer(
                policy_admin.history_for(setting), many=True).data,
        })

    def patch(self, request, pk):
        # Changing a rate changes what everyone is paid from here on. Restricted
        # to administrators, and recorded with who and when.
        if not (request.user.is_authenticated and request.user.role == 'admin'):
            return Response({'detail': 'Only an administrator may change a funding rate.'},
                            status=status.HTTP_403_FORBIDDEN)
        try:
            setting = PolicySetting.objects.get(pk=pk)
        except PolicySetting.DoesNotExist:
            return Response({'detail': 'No such rate.'}, status=status.HTTP_404_NOT_FOUND)

        if 'is_active' in request.data and 'value' not in request.data:
            updated = policy_admin.set_active(
                setting, bool(request.data['is_active']), actor=request.user)
            return Response(PolicySettingSerializer(updated).data)

        try:
            policy_admin.change_rate(
                setting, request.data.get('value'), actor=request.user,
                effective_from=request.data.get('effective_from') or None,
            )
        except policy_admin.PolicyEditError as exc:
            return Response({'value': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        setting.refresh_from_db()
        return Response(PolicySettingSerializer(setting).data)


class RuleSetsView(APIView):
    """Which policy governed which period."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _staff(request.user):
            return Response({'detail': 'Only staff may view rule sets.'},
                            status=status.HTTP_403_FORBIDDEN)
        return Response(RuleSetSerializer(
            RuleSet.objects.order_by('-effective_from', '-version'), many=True).data)
