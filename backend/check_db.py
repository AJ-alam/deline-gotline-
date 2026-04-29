import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from forms.models import Form, FormField
from api.models import PolicySetting
from forms.models import FormSubmission

print('=== FORMS IN DB ===')
for f in Form.objects.all().order_by('id'):
    field_count = f.fields.count()
    print(f'  [{f.id}] "{f.title}" | active={f.is_active} | fields={field_count}')

print()
print('=== POLICY SETTINGS SECTIONS ===')
sections = PolicySetting.objects.values_list('section', flat=True).distinct().order_by('section')
for s in sections:
    count = PolicySetting.objects.filter(section=s).count()
    print(f'  {s} ({count} keys)')

print()
print('=== DGGR GRAD BURSARY POLICIES ===')
for p in PolicySetting.objects.filter(section='dggr_grad_bursary').order_by('field_key'):
    print(f'  {p.field_key} = ${p.value} {p.unit}')

print()
print('=== DGGR PRACTICUM POLICIES ===')
for p in PolicySetting.objects.filter(section='dggr_practicum_award').order_by('field_key'):
    print(f'  {p.field_key} = ${p.value} {p.unit}')

print()
print('=== RECENT SUBMISSIONS ===')
for s in FormSubmission.objects.select_related('form', 'student').order_by('-submitted_at')[:10]:
    student = s.student.email if s.student else 'Guest'
    print(f'  [{s.id}] {s.form.title} | status={s.status} | amount=${s.amount} | by={student}')
