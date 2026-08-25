"""The annual report as a PDF, on the office's letterhead.

This is the document that goes to the head department. Like `letter_pdf` it is
a renderer and nothing else: every figure comes from `reporting.annual_report`,
so the page the office reads on screen and the document it forwards cannot
disagree about what the year cost.

The letterhead, the fonts and the page furniture are shared with the approval
letter rather than set up a second time — one definition of what a document
from this office looks like.
"""

from __future__ import annotations

import io
from datetime import date

from reportlab.lib.pagesizes import letter as LETTER
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as pdfcanvas

# `office` and `signatory` live with the letter content rather than its
# renderer — one definition of the office's own details, shared by both.
from funding.services.approval_letter import office, signatory
from funding.services.letter_pdf import (
    BODY, BOLD, LEFT, RIGHT, _letterhead, _register_fonts, _wrap,
)

PAGE_WIDTH, PAGE_HEIGHT = LETTER
TOP = PAGE_HEIGHT - 1.55 * 72
BOTTOM = 0.85 * 72
BODY_SIZE = 9.5
LEADING = 12.5


class Sheet:
    """A page that knows when it has run out and starts another.

    A report is many tables of unknown length; unlike the letter it cannot
    assume it fits. Every table asks for room before it draws a row, so a table
    is never cut through the middle of one.
    """

    def __init__(self, pdf, heading: str):
        self.pdf = pdf
        self.heading = heading
        self.y = TOP
        self.page = 1
        _letterhead(pdf)

    def room_for(self, needed: float) -> bool:
        return self.y - needed > BOTTOM + 24

    def ensure(self, needed: float) -> None:
        if not self.room_for(needed):
            self.break_page()

    def break_page(self) -> None:
        self._footer()
        self.pdf.showPage()
        self.page += 1
        self.y = PAGE_HEIGHT - 1.0 * 72

    def space(self, amount: float) -> None:
        self.y -= amount

    def _footer(self) -> None:
        details = office()
        text = (f"{details['address']}   |   {details['phone']}   "
                f"|   {details['website']}")
        self.pdf.setFont(BODY, 8.5)
        self.pdf.drawCentredString(PAGE_WIDTH / 2, BOTTOM, text)
        self.pdf.drawRightString(RIGHT, BOTTOM, f'Page {self.page}')

    def finish(self) -> None:
        self._footer()

    # ── Blocks ─────────────────────────────────────────────────────────────

    def title(self, text: str, size: float = 15) -> None:
        self.ensure(size + 14)
        self.pdf.setFont(BOLD, size)
        self.pdf.drawString(LEFT, self.y, text)
        self.space(size + 8)

    def heading_2(self, text: str) -> None:
        self.ensure(30)
        self.pdf.setFont(BOLD, 11)
        self.pdf.drawString(LEFT, self.y, text)
        self.space(16)

    def paragraph(self, text: str, *, size: float = BODY_SIZE, gap: float = 8) -> None:
        for line in _wrap(text, BODY, size, RIGHT - LEFT):
            self.ensure(LEADING)
            self.pdf.setFont(BODY, size)
            self.pdf.drawString(LEFT, self.y, line)
            self.space(LEADING)
        self.space(gap)

    def table(self, headers: list[str], rows: list[list[str]], widths: list[float],
              *, total_rows: int = 0) -> None:
        """One table, ruled, wrapping its cells and breaking across pages.

        `total_rows` marks how many rows at the end are totals, so they are set
        bold — a total that looks like every other row is a total the reader
        has to find.
        """
        pdf = self.pdf
        xs, x = [], LEFT
        for width in widths:
            xs.append(x)
            x += width
        right = LEFT + sum(widths)

        # Headers wrap like any other cell. Taking only the first line cut
        # "In trades" and "In upgrading" both down to "In" — two different
        # columns with the same heading, on a report going to a funder.
        header_lines = [_wrap(text, BOLD, BODY_SIZE, widths[i] - 6)
                        for i, text in enumerate(headers)]
        header_height = max(20.0, 8 + max(len(w) for w in header_lines) * 10.5)

        def draw_header():
            self.ensure(header_height + 6)
            top = self.y
            pdf.setLineWidth(0.8)
            pdf.rect(LEFT, top - header_height, right - LEFT, header_height)
            pdf.setFont(BOLD, BODY_SIZE)
            for index, lines in enumerate(header_lines):
                if index:
                    pdf.line(xs[index], top - header_height, xs[index], top)
                text_y = top - 12
                for line in lines:
                    pdf.drawString(xs[index] + 3, text_y, line)
                    text_y -= 10.5
            self.y = top - header_height

        draw_header()
        for offset, row in enumerate(rows):
            is_total = offset >= len(rows) - total_rows if total_rows else False
            font = BOLD if is_total else BODY
            wrapped = [_wrap(str(cell), font, BODY_SIZE, widths[i] - 6)
                       for i, cell in enumerate(row)]
            height = max(18.0, 6 + max(len(w) for w in wrapped) * 11.5)

            if not self.room_for(height):
                self.break_page()
                draw_header()

            top = self.y
            pdf.setLineWidth(0.8)
            pdf.rect(LEFT, top - height, right - LEFT, height)
            pdf.setFont(font, BODY_SIZE)
            for index, lines in enumerate(wrapped):
                if index:
                    pdf.line(xs[index], top - height, xs[index], top)
                text_y = top - 12
                for line in lines:
                    # Numbers right, words left — a column of money read down
                    # the page has to line up.
                    if index and _is_number(row[index]):
                        pdf.drawRightString(xs[index] + widths[index] - 3, text_y, line)
                    else:
                        pdf.drawString(xs[index] + 3, text_y, line)
                    text_y -= 11.5
            self.y = top - height
        self.space(14)


def _is_number(value) -> bool:
    text = str(value).replace('$', '').replace(',', '').strip()
    if not text:
        return False
    try:
        float(text)
        return True
    except ValueError:
        return False


def _money(value) -> str:
    try:
        return f'${float(str(value).replace(",", "")):,.2f}'
    except (TypeError, ValueError):
        return str(value)


def render(report: dict) -> bytes:
    """The whole report, in the order the office's mock-up sets out."""
    _register_fonts()
    buffer = io.BytesIO()
    pdf = pdfcanvas.Canvas(buffer, pagesize=LETTER)
    # A report narrowed to one programme is a different document from the
    # annual report, and has to introduce itself as one. Sent to the head
    # department under the same title and filename as the whole year, it
    # reads as the whole year with a third of the money missing.
    narrowed = _programme_label(report)
    pdf.setTitle(
        f"DGG annual student funding report {report['fiscal_year']['label']}"
        + (f' — {narrowed} only' if narrowed else ''))
    sheet = Sheet(pdf, 'Annual report'
                  + (f' — {narrowed}' if narrowed else ''))

    highlights = report['highlights']

    sheet.title('Annual Délı̨nę Student Financial Support Program Report')
    sheet.paragraph(report['fiscal_year']['label'] + '  ·  Department of Education',
                    size=10.5, gap=14 if not narrowed else 6)
    if narrowed:
        sheet.paragraph(
            f'This report covers {narrowed} only. Figures on it are not '
            f'the whole program.', size=10.5, gap=14)

    # ── Executive summary, computed rather than typed ──────────────────────
    sheet.heading_2('Summary')
    sheet.paragraph(
        f"During this fiscal year the program supported "
        f"{highlights['semester_enrolments']} semester enrolments and issued "
        f"{highlights['graduate_awards_issued']} graduate awards. "
        f"{_money(highlights['direct_funding_gross'])} was paid out in direct "
        f"funding and {_money(highlights['repaid'])} was returned, leaving "
        f"{_money(highlights['direct_funding_net'])} net. With "
        f"{_money(highlights['entered_total'])} entered by the office, total "
        f"program expenditure was {_money(highlights['grand_total'])}.")

    # ── Table 1 ────────────────────────────────────────────────────────────
    sheet.heading_2('Table 1: Student enrolment by semester')
    enrolment = report['enrolment']
    rows = [[r['season'], r['university'], r['college'], r['trades_school'],
             r['unclassified'], r['total'], r['trades'], r['upgrading']]
            for r in enrolment['rows']]
    total = enrolment['total']
    rows.append([total['season'], total['university'], total['college'],
                 total['trades_school'], total['unclassified'], total['total'],
                 total['trades'], total['upgrading']])
    sheet.table(
        ['Season', 'University', 'College', 'Trades school', 'Not classified',
         'Total', 'In trades', 'In upgrading'],
        rows, [72, 62, 58, 62, 66, 46, 52, 60], total_rows=1)
    sheet.paragraph(enrolment['note'], size=8.2, gap=12)

    # ── Table 2 ────────────────────────────────────────────────────────────
    sheet.heading_2('Table 2: Graduate awards')
    grads = report['graduate_awards']
    grad_rows = [[r['residency'], r['university'], r['college'], r['high_school'],
                  r['trades'], r['other'], r['total']]
                 for r in grads['rows'] + [grads['total']]]
    sheet.table(
        ['Residency', 'University', 'College', 'High school', 'Trades', 'Other',
         'Total'],
        grad_rows, [136, 62, 56, 64, 50, 46, 50], total_rows=1)

    # ── Table 3 ────────────────────────────────────────────────────────────
    sheet.heading_2('Table 3: Institutions attended')
    sections = report['institutions']['sections']
    if not sections:
        sheet.paragraph('No enrolments were recorded in this year.')
    for section in sections:
        sheet.ensure(50)
        sheet.pdf.setFont(BOLD, BODY_SIZE)
        sheet.pdf.drawString(LEFT, sheet.y,
                             f"{section['label']} — {section['students']} students")
        sheet.space(14)
        sheet.table(
            ['Institution', 'Programs', 'Students'],
            [[r['name'], ', '.join(r['programs']) or '—', r['students']]
             for r in section['rows']],
            [150, 264, 50])

    # ── Funding by student number ──────────────────────────────────────────
    # The office asked for the funding broken down by student number, and the
    # number rather than the name is what the head department reconciles
    # against.
    sheet.heading_2('Table 4: Funding by student number')
    students = report['students']
    if not students['rows']:
        sheet.paragraph('No funding was recorded in this year.')
    else:
        sheet.table(
            ['Student number', 'Applications', 'Paid', 'Returned', 'Net'],
            [[row['student_number'] or 'Not on file', row['applications'],
              _money(row['gross']), _money(row['repaid']), _money(row['net'])]
             for row in students['rows']],
            [130, 84, 100, 90, 60])
        if students['unidentified']:
            sheet.paragraph(
                f"{students['unidentified']} of these have no beneficiary "
                'number on file. They are listed so the rows still account for '
                'the year.', size=8.2)
        # A funder reading a row count as a headcount would understate the
        # program's reach. The table is by number, so say what a number is.
        if students.get('sharing_a_number'):
            sheet.paragraph(
                f"The program funded {students['distinct_students']} students "
                f"across {len(students['rows'])} beneficiary numbers: "
                f"{students['sharing_a_number']} of them share a number with "
                'someone else and are reported on that number’s row.',
                size=8.2)

    # ── Table 5 ────────────────────────────────────────────────────────────
    sheet.heading_2('Table 5: Financial summary')
    financial = report['financial']
    headers = ['Season'] + [c['label'] for c in financial['categories']] + \
              ['Gross', 'Repaid', 'Net']
    money_rows = []
    for row in financial['rows'] + [financial['total']]:
        money_rows.append(
            [row['season']]
            + [_money(row['categories'][c['key']]['net']) for c in financial['categories']]
            + [_money(row['gross']), _money(row['repaid']), _money(row['net'])])
    width = (RIGHT - LEFT)
    first = 68
    each = (width - first) / (len(headers) - 1)
    sheet.table(headers, money_rows, [first] + [each] * (len(headers) - 1),
                total_rows=1)

    if financial['entered']:
        sheet.heading_2('Entered by the office')
        sheet.table(
            ['Cost', 'Entered by', 'Amount'],
            [[item['label'], item['recorded_by'] or '—', _money(item['amount'])]
             for item in financial['entered']],
            [230, 150, 84])

    sheet.heading_2('Total program cost')
    sheet.table(
        ['', 'Amount'],
        [['Direct student funding (net of repayments)', _money(financial['total']['net'])],
         ['Entered by the office', _money(financial['entered_total'])],
         ['Total program cost', _money(financial['grand_total'])]],
        [330, 134], total_rows=1)

    sheet.space(6)
    sheet.paragraph(
        'Prepared from the funding portal on '
        f"{date.today():%d %B %Y}. Direct funding is computed from the awards "
        'recorded against each application; costs entered by the office are '
        'listed separately above.', size=8.2)

    signed = signatory()
    sheet.ensure(46)
    sheet.pdf.setFont(BODY, BODY_SIZE)
    for line in (signed['name'], signed['title'], signed['organisation']):
        sheet.pdf.drawString(LEFT, sheet.y, line)
        sheet.space(12)

    sheet.finish()
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _programme_label(report: dict) -> str:
    """The programme this report was narrowed to, as the office names it.

    Read back off the report rather than passed in, so a narrowed report
    cannot be rendered as the whole year by a caller that forgot.
    """
    stream = (report.get('filter') or {}).get('stream') or ''
    if not stream:
        return ''
    for row in (report.get('programmes') or {}).get('rows', []):
        if row['stream'] == stream:
            return row['label']
    return stream.upper()


def filename_for(report: dict) -> str:
    starts = report['fiscal_year']['starts'][:4]
    stream = (report.get('filter') or {}).get('stream') or ''
    if stream:
        # Two exports of the same year must not arrive under one name — the
        # second silently replaces the first in the reader's downloads folder.
        return f'DGG-annual-report-{starts}-{stream}.pdf'
    return f'DGG-annual-report-{starts}.pdf'
