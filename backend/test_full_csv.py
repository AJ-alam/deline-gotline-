"""
Run from backend/ directory:
    python test_full_csv.py
"""
import os, sys, csv, io
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from api.views import _build_full_csv
from email_sender import send_finance_report

print('Building CSV — ALL statuses + full personal/banking info...')
csv_bytes, total_rows = _build_full_csv(all_statuses=True)

lines = csv_bytes.decode('utf-8').splitlines()
headers = lines[0].split(',')
print(f'Total columns : {len(headers)}')
print(f'Total rows    : {total_rows}')
print(f'File size     : {len(csv_bytes):,} bytes')
print()
print('ALL COLUMNS:')
for i, h in enumerate(headers, 1):
    print(f'  {i:2}. {h}')

reader = csv.DictReader(io.StringIO(csv_bytes.decode('utf-8')))
first = next(reader, None)
if first:
    print()
    print('SAMPLE ROW — first record:')
    check_cols = [
        'Full Name', 'Email', 'Phone', 'Alternate Phone',
        'Date of Birth', 'Gender', 'Beneficiary #', 'Treaty #', 'UPI',
        'Mailing Address', 'Town/City', 'Postal Code', 'Province',
        'No. of Dependents', 'Financial Assistance Status', 'SFA Active (Profile)',
        'Account Holder Name', 'Account Type', 'Bank Name',
        'Transit #', 'Institution #', 'Account #',
        'Institute (Profile)', 'Institution Name', 'Program',
        'Enrollment Status', 'Course Load (%)',
        'Payment Type', 'Payment Amount ($)', 'Payment Reference #',
    ]
    for col in check_cols:
        val = first.get(col, 'COLUMN MISSING')
        print(f'  {col}: {val}')

print()
print('Sending full CSV to alamjabbar571@gmail.com...')
ok = send_finance_report(
    csv_bytes=csv_bytes,
    total_students=total_rows,
    triggered_by='System Test — Full Personal + Banking CSV',
)
print('Email sent:', ok)
if ok:
    print('SUCCESS — check alamjabbar571@gmail.com for the full CSV')
else:
    print('FAILED — check logs above')
