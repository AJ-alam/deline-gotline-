import logging
from decimal import Decimal, InvalidOperation
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from django.utils import timezone
from api.utils.responses import api_response
from api.models import PolicySetting, PolicyHistory, AuditLog
from api.serializers import PolicySettingSerializer, PolicyHistorySerializer
from users.permissions import IsAdminUser

logger = logging.getLogger(__name__)


def _fmt(v) -> str:
    """Render a value for the history log: numerics keep their numeric form (no
    trailing zeros, no Decimal noise), text values stringify normally."""
    if v is None:
        return ''
    try:
        d = Decimal(str(v))
        # Strip trailing zeros so "30.00" → "30", "30.50" → "30.5"
        normalized = d.normalize()
        # normalize() can return scientific notation for large/small numbers — guard
        s = format(normalized, 'f')
        if '.' in s:
            s = s.rstrip('0').rstrip('.')
        return s
    except (InvalidOperation, ValueError, TypeError):
        return str(v)


def _log_policy_change(instance: PolicySetting, old_value, new_value, user, effective_date=None):
    """Record one PolicyHistory row when a field's value actually changes.
    Decimal-aware: "30" and "30.00" are treated as equal so spurious history
    rows aren't created by formatting differences.

    effective_date — user-specified future date (§7.5). Defaults to today if not provided.
    """
    old_s = _fmt(old_value)
    new_s = _fmt(new_value)
    if old_s == new_s:
        return
    eff = (effective_date or timezone.now().date()).isoformat() if hasattr(
        (effective_date or timezone.now().date()), 'isoformat'
    ) else str(effective_date or timezone.now().date())
    PolicyHistory.objects.create(
        setting=instance,
        user_name=(getattr(user, 'full_name', None) or getattr(user, 'email', None) or 'System'),
        field_changed=f"[{instance.section}] {instance.field_label}",
        old_value=old_s,
        new_value=new_s,
        effective_date=eff,
    )
    logger.info(
        "PolicyHistory recorded: %s.%s by %s: %s -> %s (effective %s)",
        instance.section, instance.field_key,
        getattr(user, 'email', '?'), old_s, new_s, eff,
    )


class PolicyViewSet(viewsets.ModelViewSet):
    queryset = PolicySetting.objects.all().order_by('section', 'field_key')
    serializer_class = PolicySettingSerializer

    def get_permissions(self):
        # Any write (create new field, edit value, bulk edit, delete, reset) is admin-only.
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'bulk_update', 'reset_section']:
            return [permissions.IsAuthenticated(), IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        instance = serializer.save(last_updated_by=self.request.user)
        PolicyHistory.objects.create(
            setting=instance,
            user_name=(getattr(self.request.user, 'full_name', None) or getattr(self.request.user, 'email', None) or 'System'),
            field_changed=f"[{instance.section}] {instance.field_label} (NEW)",
            old_value='—',
            new_value=f"{_fmt(instance.value)} {instance.unit or ''}".strip(),
            effective_date=timezone.now().date().isoformat(),
        )
        AuditLog.objects.create(
            action=f"Policy field created: [{instance.section}] — {instance.field_label}",
            performed_by=self.request.user,
            role=self.request.user.role,
        )

    def perform_destroy(self, instance):
        # Record the delete in AuditLog (PolicyHistory rows for this setting are kept
        # via SET_NULL on the FK — see api/migrations/0011_policyhistory_setting_nullable.py).
        section, label = instance.section, instance.field_label
        value_str = f"{_fmt(instance.value)} {instance.unit or ''}".strip()
        instance.delete()
        AuditLog.objects.create(
            action=f"Policy field deleted: [{section}] — {label} (was {value_str})",
            performed_by=self.request.user,
            role=self.request.user.role,
        )

    def perform_update(self, serializer):
        old_value = serializer.instance.value
        old_unit = serializer.instance.unit
        old_active = serializer.instance.is_active
        # Extract user-specified effective_date from request (may be a future date)
        eff_date_raw = self.request.data.get('effective_date')
        effective_date = None
        if eff_date_raw:
            from datetime import date as _date
            try:
                from datetime import datetime as _dt
                effective_date = _dt.strptime(str(eff_date_raw), '%Y-%m-%d').date()
            except Exception:
                pass
        instance = serializer.save(last_updated_by=self.request.user)
        # Store effective_date on the setting itself for calculation lookups
        if effective_date and instance.effective_date != effective_date:
            instance.effective_date = effective_date
            instance.save(update_fields=['effective_date'])
        if _fmt(old_value) != _fmt(instance.value):
            _log_policy_change(instance, old_value, instance.value, self.request.user, effective_date)
        if str(old_unit or '') != str(instance.unit or ''):
            _log_policy_change(instance, old_unit, instance.unit, self.request.user, effective_date)
        if old_active != instance.is_active:
            status_word = 'activated' if instance.is_active else 'DEACTIVATED'
            _log_policy_change(instance, str(old_active), str(instance.is_active), self.request.user, effective_date)
        AuditLog.objects.create(
            action=f"Policy updated: [{instance.section}] — {instance.field_label} changed to {_fmt(instance.value)} {instance.unit or ''}".strip(),
            performed_by=self.request.user,
            role=self.request.user.role,
        )

    @action(detail=False, methods=['post'], url_path='bulk_update')
    def bulk_update(self, request):
        """
        Update multiple policy settings in a single request (e.g., an entire section).
        Each value change is recorded in PolicyHistory.
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

        logger.info(f"Bulk policy update started for section: {section_name}. Settings count: {len(settings_data)}")
        # Extract shared effective_date from top-level request body
        eff_date_raw = request.data.get('effective_date')
        bulk_eff_date = None
        if eff_date_raw:
            try:
                from datetime import datetime as _dt
                bulk_eff_date = _dt.strptime(str(eff_date_raw), '%Y-%m-%d').date()
            except Exception:
                pass

        for data in settings_data:
            setting_id = data.get('id')
            # Per-item effective_date overrides bulk one
            item_eff_raw = data.get('effective_date') or eff_date_raw
            item_eff_date = bulk_eff_date
            if item_eff_raw and item_eff_raw != eff_date_raw:
                try:
                    from datetime import datetime as _dt2
                    item_eff_date = _dt2.strptime(str(item_eff_raw), '%Y-%m-%d').date()
                except Exception:
                    pass
            try:
                instance = PolicySetting.objects.get(id=setting_id)
                # Capture originals as primitives so they survive the in-place
                # mutation that serializer.save() performs on `instance`.
                old_value = instance.value
                old_unit = instance.unit
                old_active = instance.is_active
                serializer = self.get_serializer(instance, data=data, partial=True)
                if serializer.is_valid():
                    saved = serializer.save(last_updated_by=request.user)
                    if item_eff_date and saved.effective_date != item_eff_date:
                        saved.effective_date = item_eff_date
                        saved.save(update_fields=['effective_date'])
                    # Compare value (Decimal-normalized) and unit separately so
                    # text-only configs (contact_email, contact_phone, …) that
                    # change just their `unit` also produce a history row.
                    value_changed = _fmt(old_value) != _fmt(saved.value)
                    unit_changed = str(old_unit or '') != str(saved.unit or '')
                    if value_changed:
                        _log_policy_change(saved, old_value, saved.value, request.user, item_eff_date)
                    if unit_changed:
                        # Use unit as the visible "value" for text-only configs;
                        # for numeric+unit fields render as "<value><unit>".
                        old_repr = old_unit if str(old_value or '0') in ('0', '0.00') else f"{_fmt(old_value)} {old_unit}".strip()
                        new_repr = saved.unit if str(saved.value or '0') in ('0', '0.00') else f"{_fmt(saved.value)} {saved.unit}".strip()
                        _log_policy_change(saved, old_repr, new_repr, request.user, item_eff_date)
                    if old_active != saved.is_active:
                        _log_policy_change(saved, str(old_active), str(saved.is_active), request.user, item_eff_date)
                    updated_count += 1
                else:
                    logger.warning(f"Policy validation failed for ID {setting_id}: {serializer.errors}")
            except PolicySetting.DoesNotExist:
                logger.error(f"Policy setting ID {setting_id} not found during bulk update.")
                continue
            except Exception as e:
                logger.error(f"Unexpected error updating policy ID {setting_id}: {str(e)}")
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
        """Return all policy settings grouped by section for the frontend."""
        settings = self.get_queryset()
        serializer = self.get_serializer(settings, many=True)
        grouped: dict = {}
        for item in serializer.data:
            sec = item['section']
            grouped.setdefault(sec, []).append(item)
        return api_response(True, grouped, "All policy settings retrieved")

    @action(detail=False, methods=['get'])
    def history(self, request):
        """Return recent policy change history for the Change History tab."""
        try:
            limit = min(int(request.query_params.get('limit', '200')), 1000)
        except (TypeError, ValueError):
            limit = 200
        qs = PolicyHistory.objects.select_related('setting').order_by('-timestamp')[:limit]
        data = PolicyHistorySerializer(qs, many=True).data
        return api_response(True, data, f"{len(data)} history record(s)")
