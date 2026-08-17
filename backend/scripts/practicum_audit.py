"""The summer student / practicum award, driven over HTTP as a claimant.

The award is released against what the employer reports, not against what the
claimant asserts — the same principle as the enrolment verification. So what
this checks is not that the questions exist but that the *refusals* hold: an
incomplete report is rejected, and a declaration answered "no" cannot be filed.
A required BOOLEAN accepts False, which is exactly how a declaration once got
filed refused; only walking the real endpoint shows which one is in place.

Claimed as a guest, because that is the path most of these arrive on: a summer
student is often not otherwise a student here.

    python manage.py runserver 127.0.0.1:8000
    python scripts/practicum_audit.py [--base http://127.0.0.1:8000]

Exits non-zero on any failed expectation, so it is usable in a loop.
"""

from __future__ import annotations

import argparse
import sys

import requests

# One complete claim.
ANSWERS = {
    'employer_name': 'Deline Health Centre',
    'supervisor_title': 'Director of Care',

    'full_name': 'Summer Worker',
    'email': 'summer.worker@example.com',
    'placement_start': '2026-06-01', 'placement_end': '2026-08-15',

    'roles_and_responsibilities': 'Reception, intake, home visits.',
    'performance_summary': 'Punctual, no absences, strong with clients.',

    'account_holder': 'Summer Worker', 'transit_number': '12345',
    'institution_number': '003', 'account_number': '9876543210',

    'employer_declaration': True,
    'supervisor_signature': 'Rita Baton',
    'report_completed_on': '2026-08-20',
}

# What makes the employer's half an employer's half. Dropped together below, so
# the refusal is checked against the whole report rather than one field of it.
REPORT_KEYS = (
    'employer_name', 'supervisor_title',
    'roles_and_responsibilities', 'performance_summary',
    'employer_declaration', 'supervisor_signature', 'report_completed_on',
)

# Everything the form asks, checked as a set rather than one key at a time.
#
# "Is this key present" cannot notice a question that has quietly gone: the
# checks pass, the form renders, and the office assesses a placement without
# knowing when it ran. The last four are the bank details — a summer student
# usually has no account here, so there is nowhere else for finance to read
# them from.
EXPECTED_FIELDS = set(REPORT_KEYS) | {
    'full_name', 'email', 'placement_start', 'placement_end',
    'account_holder', 'transit_number', 'institution_number', 'account_number',
}


class Audit:
    def __init__(self, base: str):
        self.base = base.rstrip('/')
        self.passed = 0
        self.failed = 0

    def check(self, label: str, condition, detail: str = '') -> bool:
        if condition:
            self.passed += 1
            print(f'  ok    {label}')
        else:
            self.failed += 1
            print(f'  FAIL  {label}' + (f'\n        {detail}' if detail else ''))
        return bool(condition)

    def heading(self, text: str) -> None:
        print(f'\n{text}\n{"-" * len(text)}')

    def submit(self, answers: dict):
        return requests.post(f'{self.base}/api/guest-applications/',
                             json={'type': 'practicum', 'answers': answers},
                             timeout=15)


def run(base: str) -> int:
    audit = Audit(base)

    audit.heading('What the form asks')
    schemas = requests.get(f'{base}/api/schemas/', timeout=10).json()
    practicum = next(s for s in schemas if s['slug'] == 'practicum')
    fields = {f['key']: f for f in practicum['fields']}

    audit.check(
        'it asks exactly what the office asked for, and nothing more',
        set(fields) == EXPECTED_FIELDS,
        f'unexpected {set(fields) - EXPECTED_FIELDS}, '
        f'missing {EXPECTED_FIELDS - set(fields)}',
    )
    audit.check('the placement dates are asked, so the office knows when it ran',
                all(fields.get(key, {}).get('type') == 'date'
                    and fields[key]['required']
                    for key in ('placement_start', 'placement_end')),
                str({k: fields.get(k) for k in ('placement_start', 'placement_end')}))
    audit.check('the date the report was signed opens on today',
                fields.get('report_completed_on', {}).get('defaults_to_today') is True,
                'the supervisor is filling this in today; asking them to type '
                'the date is asking them to look it up')
    audit.check(
        'the declaration is worded as the office words it',
        fields.get('employer_declaration', {}).get('help_text') ==
        'The employer confirms that the information provided is accurate and '
        'complete. Award is contingent on regular attendance and satisfactory '
        'performance.',
        repr(fields.get('employer_declaration', {}).get('help_text')),
    )
    audit.check(
        'the sections are the ones the office asked for',
        [s for s in dict.fromkeys(f['section'] for f in practicum['fields'])]
        == ['Employer information', 'Student information',
            'Performance and roles', 'Payment', 'Declaration'],
        str([f['section'] for f in practicum['fields']]),
    )
    audit.check('no amount is asked for — the award is a published flat rate',
                'amount_requested' not in fields)
    audit.check('every part of the report is required',
                all(fields[key]['required'] for key in REPORT_KEYS if key in fields))
    audit.check("the declaration is a confirmation, not a yes/no",
                fields.get('employer_declaration', {}).get('type') == 'confirm',
                fields.get('employer_declaration', {}).get('type', 'missing'))

    audit.heading('A complete claim')
    response = audit.submit(ANSWERS)
    audit.check('is accepted', response.status_code == 201,
                f'{response.status_code} {response.text[:300]}')

    audit.heading('A claim with no employer report')
    response = audit.submit({k: v for k, v in ANSWERS.items()
                             if k not in REPORT_KEYS})
    if audit.check('is refused', response.status_code == 400,
                   str(response.status_code)):
        body = response.text
        missing = [key for key in REPORT_KEYS if key not in body]
        audit.check('and says which answers are missing, all of them at once',
                    not missing, f'silent about: {", ".join(missing)}')

    audit.heading('A report the supervisor will not stand behind')
    response = audit.submit(dict(ANSWERS, employer_declaration=False))
    audit.check('cannot be filed with the declaration refused',
                response.status_code == 400, str(response.status_code))

    total = audit.passed + audit.failed
    print(f'\n{audit.passed}/{total} checks passed')
    return 1 if audit.failed else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://127.0.0.1:8000')
    sys.exit(run(parser.parse_args().base))
