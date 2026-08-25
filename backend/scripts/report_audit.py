"""The annual report and its programme breakdown, driven over HTTP.

The office reads this screen; the head department reads the PDF it exports.
Both go to a funder, so the thing worth checking is not that figures appear but
that they *agree* — with each other, and with the money the portal actually
awarded.

Three claims are checked against the running server rather than against a
fixture, because each has already been wrong here in a way the unit tests could
not see:

- **The breakdown reconciles.** The financial table sums award lines; the
  programme breakdown sums the rules behind those lines. They are two different
  columns of the same database and must land on the same number. A repayment
  recorded against a superseded decision once fell out of one and not the
  other.
- **The filter narrows, and the parts still make the whole.** Asking for one
  programme must not change what a *different* programme is reported to have
  spent. Summing the three filtered reports has to give back the unfiltered
  one, or some application is being counted twice or not at all.
- **A programme that is not a programme is refused.** A mistyped stream that
  quietly returns an empty report is the worst outcome available: the office
  would send a funder a page of zeroes with no indication anything was wrong.

Run it against a seeded database:

    python manage.py runserver 127.0.0.1:8000
    python scripts/report_audit.py [--base http://127.0.0.1:8000]

Exits non-zero on any failed expectation, so it is usable in a loop.
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal

import requests

PASSWORD = 'DemoPass123!'

# The three funding programmes, as the office names them. Kept here rather than
# read from the server so that a stream quietly disappearing from the API is a
# failure rather than a shorter loop.
STREAMS = ('psssp', 'dggr', 'ucepp')

# Who may read money, and who may not. The report names every funded student
# and what they were paid, so this list is the whole access-control surface of
# the screen.
MAY_READ = ('admin@dgg.test', 'director@dgg.test', 'finance@dgg.test')
MAY_NOT_READ = ('worker@dgg.test',)


class Session:
    """One signed-in person."""

    def __init__(self, base: str, label: str = ''):
        self.base, self.label = base.rstrip('/'), label
        self.http = requests.Session()

    def login(self, email: str, password: str = PASSWORD) -> bool:
        response = self.http.post(f'{self.base}/api/auth/token/',
                                  json={'email': email, 'password': password},
                                  timeout=15)
        token = response.json().get('access') if response.status_code == 200 else None
        if token:
            self.http.headers['Authorization'] = f'Bearer {token}'
        return bool(token)

    def get(self, path: str, **kw):
        return self.http.get(f'{self.base}{path}', timeout=60, **kw)


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


def money(value) -> Decimal:
    return Decimal(str(value))


def reconciles(audit: Audit, report: dict, what: str) -> None:
    """The two ways of adding the year up land on the same number."""
    rows = report['programmes']['rows']
    breakdown = sum(money(row['net']) for row in rows)
    net = money(report['financial']['total']['net'])
    audit.check(f'{what}: the programme breakdown adds up to the net',
                breakdown == net, f'breakdown {breakdown} vs net {net}')

    gross = sum(money(row['gross']) for row in rows)
    repaid = sum(money(row['repaid']) for row in rows)
    audit.check(f'{what}: and its gross and repaid do too',
                gross == money(report['financial']['total']['gross'])
                and repaid == money(report['financial']['total']['repaid']),
                f'gross {gross}, repaid {repaid}')

    audit.check(f'{what}: every row is gross minus repaid',
                all(money(r['net']) == money(r['gross']) - money(r['repaid'])
                    for r in rows))


def run(base: str) -> int:
    audit = Audit(base)

    audit.heading('Who may read the year')
    for email in MAY_READ:
        person = Session(base, email)
        if not person.login(email):
            audit.check(f'{email} can sign in', False)
            continue
        response = person.get('/api/reports/annual/')
        audit.check(f'{email} may read it', response.status_code == 200,
                    str(response.status_code))
    for email in MAY_NOT_READ:
        person = Session(base, email)
        if person.login(email):
            audit.check(f'{email} may not — the report names what each student was paid',
                        person.get('/api/reports/annual/').status_code == 403,
                        str(person.get('/api/reports/annual/').status_code))
    audit.check('a stranger may not either',
                requests.get(f'{base}/api/reports/annual/',
                             timeout=15).status_code == 401)

    admin = Session(base, 'admin')
    if not admin.login('admin@dgg.test'):
        print('\nCannot sign in as admin@dgg.test — is the database seeded?')
        return 1

    audit.heading('The year, whole')
    response = admin.get('/api/reports/annual/')
    if not audit.check('is served', response.status_code == 200,
                       f'{response.status_code} {response.text[:300]}'):
        return 1
    whole = response.json()

    for section in ('enrolment', 'graduate_awards', 'institutions', 'students',
                    'financial', 'programmes', 'filter', 'highlights',
                    'fiscal_year'):
        audit.check(f'carries {section}', section in whole)

    audit.check('and says it was not narrowed',
                whole.get('filter', {}).get('stream') == '')

    audit.heading('The programme breakdown')
    rows = {row['stream']: row for row in whole['programmes']['rows']}
    for stream in STREAMS:
        audit.check(f'{stream} is named even if it funded nothing', stream in rows)
    # The screen's filter chips are written out by hand, in this order, with
    # these labels. A unit test holds the chips to the fixture; this holds the
    # fixture's order to the server, so the two cannot drift apart unnoticed.
    order = [row['stream'] for row in whole['programmes']['rows']
             if row['stream'] in STREAMS]
    audit.check('the programmes come back in the order the screen lists them',
                order == ['psssp', 'ucepp', 'dggr'], str(order))
    audit.check('and under the names the screen uses',
                [rows[s]['label'] for s in order]
                == ['C-DFN PSSSP', 'C-DFN UCEPP', 'DGGR Bursaries'],
                str([rows[s]['label'] for s in order]))
    audit.check('the shared row is last, after every real programme',
                'shared' not in order
                and (whole['programmes']['rows'][-1]['stream'] == 'shared'
                     or all(r['stream'] != 'shared'
                            for r in whole['programmes']['rows'])))

    audit.check('every row says what it is',
                all(row.get('label') for row in whole['programmes']['rows']))
    audit.check('and the note explains why counts and money differ',
                'primary programme' in whole['programmes'].get('note', ''))
    reconciles(audit, whole, 'whole year')

    audit.check('applications are counted once across the programmes',
                sum(row['applications'] for row in whole['programmes']['rows']
                    if row['stream'] in STREAMS)
                == sum(rows[s]['applications'] for s in STREAMS))

    audit.heading('How many students, exactly')
    # The table is keyed by beneficiary number, so a row is a number and not a
    # person. On the seeded database several students share one, which is why
    # this is checked against a live database rather than a two-row fixture.
    students = whole['students']
    audit.check('the report says how many people it funded, not only how many rows',
                'distinct_students' in students and 'sharing_a_number' in students)
    if 'distinct_students' in students:
        audit.check('and there are never fewer people than rows',
                    students['distinct_students'] >= students['students'],
                    f'{students["distinct_students"]} people, '
                    f'{students["students"]} rows')
        audit.check('the shared-number count is the difference',
                    students['sharing_a_number']
                    == students['distinct_students'] - students['students'],
                    f'{students["sharing_a_number"]} reported as sharing')
        audit.check('and the headcount is at least the largest programme',
                    students['distinct_students']
                    >= max(row['students'] for row in whole['programmes']['rows']),
                    f'{students["distinct_students"]} funded vs '
                    f'{max(row["students"] for row in whole["programmes"]["rows"])} '
                    'in one programme')

    audit.heading('Narrowed to one programme')
    parts = {}
    for stream in STREAMS:
        response = admin.get('/api/reports/annual/', params={'stream': stream})
        if not audit.check(f'{stream} is served', response.status_code == 200,
                           f'{response.status_code} {response.text[:200]}'):
            continue
        parts[stream] = response.json()
        audit.check(f'{stream} says what it was narrowed to',
                    parts[stream]['filter']['stream'] == stream)
        reconciles(audit, parts[stream], stream)

    if len(parts) == len(STREAMS):
        # The whole point of a filter: the parts have to make the whole. If one
        # application answers to two programmes, or none, this is where it shows.
        counted = sum(
            sum(row['applications'] for row in part['programmes']['rows'])
            for part in parts.values())
        expected = sum(row['applications'] for row in whole['programmes']['rows'])
        audit.check('the three filtered reports count every application exactly once',
                    counted == expected, f'{counted} filtered vs {expected} whole')

        students = sum(part['students']['students'] for part in parts.values())
        audit.check('and account for every funded student',
                    students >= whole['students']['students'],
                    f'{students} across programmes vs {whole["students"]["students"]}')

        # Narrowing must not change what a *different* programme spent. It
        # would if money were attributed by the application's own stream.
        for stream, part in parts.items():
            mine = {r['stream']: r for r in part['programmes']['rows']}
            audit.check(
                f'{stream} reports no more than it does in the whole year',
                money(mine[stream]['gross']) <= money(rows[stream]['gross']),
                f'{mine[stream]["gross"]} narrowed vs {rows[stream]["gross"]} whole')

    audit.heading('A programme that is not one')
    for bad in ('psspp', 'PSSSP ', 'all', '1', 'psssp,dggr'):
        response = admin.get('/api/reports/annual/', params={'stream': bad})
        audit.check(f'{bad!r} is refused rather than reported as an empty year',
                    response.status_code == 400, str(response.status_code))

    audit.heading('The export')
    response = admin.get('/api/reports/annual/pdf/')
    ok = audit.check('produces a PDF', response.status_code == 200
                     and response.headers.get('Content-Type') == 'application/pdf',
                     f'{response.status_code} {response.headers.get("Content-Type")}')
    if ok:
        audit.check('that is actually a PDF', response.content[:5] == b'%PDF-')
        # Served inline on purpose - the office previews it in a tab
        # before sending it on. What matters is that the name identifies
        # the document.
        audit.check('and is named for the year',
                    f'DGG-annual-report-{whole["fiscal_year"]["starts"][:4]}.pdf'
                    in response.headers.get('Content-Disposition', ''),
                    response.headers.get('Content-Disposition', 'no disposition'))
        whole_size = len(response.content)

        narrowed = admin.get('/api/reports/annual/pdf/', params={'stream': 'dggr'})
        audit.check('the export takes the same filter',
                    narrowed.status_code == 200
                    and narrowed.content[:5] == b'%PDF-',
                    str(narrowed.status_code))
        if narrowed.status_code == 200:
            audit.check('and a narrowed export is not the whole year again',
                        len(narrowed.content) != whole_size,
                        f'both {whole_size} bytes — is the filter reaching the PDF?')
            # It goes to a funder on the office letterhead. Arriving with
            # the same name and title as the whole year, it reads as the
            # whole year with two thirds of the money unaccounted for.
            disposition = narrowed.headers.get('Content-Disposition', '')
            audit.check('and its filename does not claim to be the whole year',
                        'dggr' in disposition, disposition or 'no disposition')
            audit.check('and it says on its face that it covers one programme',
                        b'DGGR' in narrowed.content
                        or b'one programme' in narrowed.content,
                        'nothing in the document distinguishes it')

    audit.check('and refuses a programme that is not one',
                admin.get('/api/reports/annual/pdf/',
                          params={'stream': 'nonsense'}).status_code == 400)

    audit.heading('The figures the office reconciles against')
    financial = whole['financial']
    computed = (money(financial['total']['net'])
                + money(financial['entered_total']))
    audit.check('total program cost is the net plus what the office entered',
                computed == money(financial['grand_total']),
                f'{computed} vs {financial["grand_total"]}')
    audit.check('and gross minus repaid is the net',
                money(financial['total']['gross'])
                - money(financial['total']['repaid'])
                == money(financial['total']['net']))

    total = audit.passed + audit.failed
    print(f'\n{audit.passed}/{total} checks passed')
    return 1 if audit.failed else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://127.0.0.1:8000')
    sys.exit(run(parser.parse_args().base))
