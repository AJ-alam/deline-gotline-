"""The approval letter as a PDF.

The office sends these out and files them; a printed page from a browser is not
something you can attach to an email or keep in a folder, which is what was
asked for.

**This is a renderer, not a second letter.** Every word and every figure comes
from `approval_letter.letters_for`, exactly as the portal page and the emailed
copy do. Nothing here decides what a letter says — it lays out what it was
given. The moment this file starts making that kind of decision it becomes a
third description of the same document to keep in step, which is the drift the
schema-driven renderer exists to remove.

reportlab and Pillow were already dependencies and are pinned; nothing new was
added for this. Drawing is done directly on the canvas rather than through
platypus flowables because the letter is a fixed sequence of blocks on a page
with a letterhead and a footer, not a stream of content to be flowed.
"""

from __future__ import annotations

import io
from pathlib import Path

from reportlab.lib.pagesizes import letter as LETTER
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas

PAGE_WIDTH, PAGE_HEIGHT = LETTER

# The office's own margins, measured from the supplied templates.
LEFT = 1.05 * 72
RIGHT = PAGE_WIDTH - 0.95 * 72
TOP = PAGE_HEIGHT - 1.55 * 72
BOTTOM = 0.85 * 72

# The fonts are shipped with the application rather than taken from the machine
# it runs on. reportlab's built-in Times is Latin-1 and cannot encode a single
# one of `REQUIRED_GLYPHS` — the first draft of this rendered "Délı̨nę Got’ı̨nę"
# as "Dél■■n■ Got’■■n■" on the office's own letterhead. The system fonts that
# do cover it are Windows-only and not redistributable, so a Linux deployment
# would have printed the boxes instead, silently.
#
# DejaVu Serif: Bitstream Vera licence, freely redistributable, and it carries
# the combining ogonek and acute the language needs. reportlab does no mark
# positioning, and does not need to here — the marks are zero-width in this
# font and compose correctly, which is asserted rather than assumed.
FONT_DIR = Path(__file__).resolve().parent.parent / 'assets' / 'fonts'
BODY = 'DGGSerif'
BOLD = 'DGGSerif-Bold'
BODY_SIZE = 11.0
# 11pt on 13.8 — the ratio the office's own template sets. Tightened from 14.4
# so a letter to a student with a real postal address still fits on one page:
# the address block is three lines, and at the looser setting it pushed the
# sign-off onto a second sheet carrying nothing else.
LEADING = 13.8

# Every non-ASCII character the office's own wording uses. Checked against the
# font before anything is drawn, because a letter that prints the government's
# name as boxes is worse than one that fails to print.
REQUIRED_GLYPHS = (
    'è', 'é', 'ę', 'ı', 'ǝ',
    '́', '̨', '–', '’',
)

_registered = False


class LetterFontMissing(Exception):
    """The shipped font is absent or cannot render the office's language."""


def _register_fonts() -> None:
    """Register the shipped fonts once, and refuse if they cannot do the job.

    Refusing rather than falling back to a built-in: the fallback renders the
    place name as black boxes and nothing anywhere says so, which is the same
    class as a missing rate awarding zero.
    """
    global _registered
    if _registered:
        return

    for name, filename in ((BODY, 'DejaVuSerif.ttf'), (BOLD, 'DejaVuSerif-Bold.ttf')):
        path = FONT_DIR / filename
        if not path.exists():
            raise LetterFontMissing(
                f'{filename} is missing from {FONT_DIR}. The approval letter '
                f'cannot be produced without it.')
        font = TTFont(name, str(path))
        missing = [f'U+{ord(ch):04X}' for ch in REQUIRED_GLYPHS
                   if ord(ch) not in font.face.charToGlyph]
        if missing:
            raise LetterFontMissing(
                f'{filename} cannot render {", ".join(missing)}, which the '
                f"office's own wording uses.")
        pdfmetrics.registerFont(font)

    _registered = True

# The letterhead artwork: the crest and wordmark supplied by the office, with
# the ribbon beside it, rasterised at 200dpi for the page width. It is a single
# fixed image because that is what letterhead is — there is nothing in it that
# varies per letter, and nothing in it that any code should be deciding.
LETTERHEAD = Path(__file__).resolve().parent.parent / 'assets' / 'letterhead.png'
LETTERHEAD_HEIGHT = 300 / 200 * 72  # the raster is 1700x300 at 200dpi


class Cursor:
    """Where the next block goes, and what to do when the page runs out.

    The letter is two pages in the office's own template and the footer belongs
    at the foot of the last one, so the position has to be tracked rather than
    assumed.
    """

    def __init__(self, pdf):
        self.pdf = pdf
        self.y = TOP

    def space(self, amount: float) -> None:
        self.y -= amount

    def room_for(self, needed: float) -> bool:
        # The footer sits on the baseline at BOTTOM and is one line tall, so
        # this is the clearance above it rather than an arbitrary margin.
        return self.y - needed > BOTTOM + 26

    def new_page(self) -> None:
        self.pdf.showPage()
        self.y = PAGE_HEIGHT - 1.0 * 72


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    """Break a paragraph to the measured width of the actual font.

    Measured rather than estimated by character count: the office's wording runs
    to three and four lines, and a guess puts a word over the margin on a
    document they sign.
    """
    lines, line = [], ''
    for word in text.split():
        trial = f'{line} {word}'.strip()
        if stringWidth(trial, font, size) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines or ['']


def _paragraph(cursor: Cursor, text: str, *, font: str = BODY,
               size: float = BODY_SIZE, gap: float = 10.0) -> None:
    for raw in text.split('\n'):
        for line in _wrap(raw, font, size, RIGHT - LEFT):
            if not cursor.room_for(LEADING):
                cursor.new_page()
            cursor.pdf.setFont(font, size)
            cursor.pdf.drawString(LEFT, cursor.y, line)
            cursor.space(LEADING)
    cursor.space(gap)


def _letterhead(pdf) -> None:
    if not LETTERHEAD.exists():  # pragma: no cover - the asset ships with the app
        return
    width = PAGE_WIDTH
    height = LETTERHEAD_HEIGHT
    pdf.drawImage(ImageReader(str(LETTERHEAD)), 0, PAGE_HEIGHT - height,
                  width=width, height=height, mask='auto')


def _footer(pdf, office: dict) -> None:
    """The office's address, at the foot of the page.

    Drawn from the page bottom rather than after the signature: on the office's
    own template it sits at the foot of the last sheet, and a footer that floats
    up under the signature is the giveaway that a document was generated.
    """
    text = (f"{office['address']}   |   Office: {office['phone']}   "
            f"|   {office['website']}")
    pdf.setFont(BODY, 10.5)
    pdf.drawCentredString(PAGE_WIDTH / 2, BOTTOM, text)


def _table(cursor: Cursor, letter: dict) -> None:
    """The breakdown, ruled on all sides as the office rules it."""
    pdf = cursor.pdf
    col_semester = LEFT
    col_type = LEFT + 1.55 * 72
    col_amount = LEFT + 4.30 * 72
    right = RIGHT

    rows = list(letter['rows'])
    if letter['total_label']:
        rows = rows + [{'label': letter['total_label'], 'amount': letter['total'],
                        'note': '', 'bold': True}]

    heights = []
    for row in rows:
        lines = _wrap(row['label'], BODY, BODY_SIZE, col_amount - col_type - 10)
        note_lines = _wrap(row['note'], BODY, 8.6, right - col_amount - 10) if row['note'] else []
        heights.append(max(24.0, 8 + len(lines) * 13.5 + len(note_lines) * 10.5))

    total_height = sum(heights) + 22
    if not cursor.room_for(total_height):
        cursor.new_page()

    top = cursor.y + 6
    pdf.setLineWidth(0.9)

    # Header
    pdf.setFont(BOLD, BODY_SIZE)
    header_height = 20
    pdf.rect(col_semester, top - header_height, right - col_semester, header_height)
    pdf.line(col_type, top - header_height, col_type, top)
    pdf.line(col_amount, top - header_height, col_amount, top)
    pdf.drawString(col_semester + 5, top - 14, 'Semester')
    pdf.drawString(col_type + 5, top - 14, 'Type of Assistance')
    pdf.drawString(col_amount + 5, top - 14, 'Amount')

    y = top - header_height
    body_top = y
    for row, height in zip(rows, heights):
        pdf.rect(col_type, y - height, right - col_type, height)
        pdf.line(col_amount, y - height, col_amount, y)

        font = BOLD if row.get('bold') else BODY
        pdf.setFont(font, BODY_SIZE)
        text_y = y - 15
        for line in _wrap(row['label'], BODY, BODY_SIZE, col_amount - col_type - 10):
            pdf.drawString(col_type + 5, text_y, line)
            text_y -= 13.5

        pdf.setFont(font, BODY_SIZE)
        pdf.drawRightString(right - 6, y - 15, row['amount'])
        if row['note']:
            pdf.setFont(BODY, 8.6)
            note_y = y - 26
            for line in _wrap(row['note'], BODY, 8.6, right - col_amount - 10):
                pdf.drawRightString(right - 6, note_y, line)
                note_y -= 10.5
        y -= height

    # The semester cell spans every row, as it does on the office's template.
    pdf.rect(col_semester, y, col_type - col_semester, body_top - y)
    pdf.setFont(BODY, BODY_SIZE)
    pdf.drawString(col_semester + 5, body_top - 15, letter['semester'])

    cursor.y = y - 9


def render(letters: list[dict]) -> bytes:
    """One PDF holding every letter this approval earned, a page each.

    A single file rather than one per programme: a student funded by two
    programmes is owed both letters and should not have to collect them
    separately, and the office files one document per decision.
    """
    _register_fonts()

    buffer = io.BytesIO()
    pdf = pdfcanvas.Canvas(buffer, pagesize=LETTER)
    pdf.setTitle('DGG approval letter')

    for index, letter in enumerate(letters):
        if index:
            pdf.showPage()
        _letterhead(pdf)
        cursor = Cursor(pdf)

        if letter['date']:
            pdf.setFont(BODY, BODY_SIZE)
            pdf.drawString(LEFT, cursor.y, f"Date: {letter['date']}")
            cursor.space(30)

        # The recipient's address block, as on the office's template: the
        # letters are posted as well as emailed, and a letter with nowhere to
        # write the address cannot be put in a window envelope.
        identifier = letter['identifier']
        pdf.setFont(BODY, BODY_SIZE)
        label = f"{identifier['label']} {identifier['value']}".strip()
        pdf.drawRightString(RIGHT, cursor.y, label)
        cursor.space(14)

        for line in letter.get('address_lines') or []:
            pdf.setFont(BODY, BODY_SIZE)
            pdf.drawString(LEFT, cursor.y, line)
            cursor.space(14)
        cursor.space(12)

        title = f"RE: {letter['title']} {letter['term']}".strip()
        _paragraph(cursor, title, font=BOLD, gap=8)
        _paragraph(cursor, f"Dear {letter['recipient']}", gap=9)
        _paragraph(cursor, letter['opening'])
        _paragraph(cursor, letter['breakdown_lead'], gap=4)

        _table(cursor, letter)

        if letter['footnote']:
            for line in _wrap('*' + letter['footnote'], BODY, 9.2, RIGHT - LEFT):
                pdf.setFont(BODY, 9.2)
                pdf.drawString(LEFT, cursor.y, line)
                cursor.space(11.5)
        cursor.space(6)

        for text in letter['paragraphs']:
            _paragraph(cursor, text)

        # The sign-off is one block: "Kind regards," and the name beneath it.
        # Measured and moved together, because a page carrying a signature and
        # nothing else — or worse, a "Kind regards," with the name overleaf —
        # is the mark of a document that was generated rather than written.
        cursor.space(4)
        signatory = letter['signatory']
        sign_off = (signatory['name'], signatory['title'],
                    signatory['organisation'], f"Email: {signatory['email']}")
        block = LEADING + 14 + len(sign_off) * 14
        if not cursor.room_for(block):
            cursor.new_page()

        pdf.setFont(BODY, BODY_SIZE)
        pdf.drawString(LEFT, cursor.y, letter['closing'])
        cursor.space(LEADING + 14)

        for line in sign_off:
            pdf.setFont(BODY, BODY_SIZE)
            pdf.drawString(LEFT, cursor.y, line)
            cursor.space(14)

        _footer(pdf, letter['office'])

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def filename_for(application_id: int) -> str:
    return f'DGG-approval-letter-{application_id}.pdf'
