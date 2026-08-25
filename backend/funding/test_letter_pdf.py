"""The approval letter as a PDF.

What matters here is not that a PDF appears — it is that the document is the
same letter, that it can render the office's own language, and that it refuses
rather than printing that language as boxes.
"""

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role
from funding.services import approval_letter as letters
from funding.services import letter_pdf
from funding.test_approval_letter import (
    approved_application, make_user, price_and_approve,
)
from funding.test_rules import seed_rates


class RenderTests(TestCase):

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.admin = make_user(Role.ADMIN)
        self.application = price_and_approve(approved_application(), self.admin)
        self.letters = letters.letters_for(self.application)

    def test_it_produces_a_pdf(self):
        content = letter_pdf.render(self.letters)
        self.assertTrue(content.startswith(b'%PDF-'), content[:20])
        self.assertGreater(len(content), 5000)

    def test_the_shipped_font_can_render_the_offices_own_language(self):
        """reportlab's built-in Times is Latin-1 and cannot encode one of these.

        The first draft used it and printed the place name as black boxes on
        the office's own letterhead. The fonts that can render it are shipped
        with the application rather than taken from the machine it runs on: the
        system fonts with this coverage are Windows-only and not
        redistributable, so a Linux deployment would have printed the boxes
        instead, silently.
        """
        from reportlab.pdfbase.ttfonts import TTFont

        for filename in ('DejaVuSerif.ttf', 'DejaVuSerif-Bold.ttf'):
            path = letter_pdf.FONT_DIR / filename
            self.assertTrue(path.exists(), f'{filename} is not shipped')
            face = TTFont(filename, str(path)).face
            for char in letter_pdf.REQUIRED_GLYPHS:
                with self.subTest(font=filename, char=char):
                    self.assertIn(ord(char), face.charToGlyph)

    def test_the_glyph_list_covers_what_the_letters_actually_use(self):
        """A required-character list that has drifted from the office's wording
        is a check that passes while the letter prints boxes."""
        used = set()
        for letter in self.letters:
            text = ''.join([
                letter['title'], letter['opening'], letter['closing'],
                letter['signatory']['organisation'], letter['office']['address'],
                *letter['paragraphs'],
            ])
            used |= {ch for ch in text if ord(ch) > 127}
        undeclared = sorted(used - set(letter_pdf.REQUIRED_GLYPHS))
        self.assertEqual(undeclared, [], f'not declared: {undeclared}')

    def test_a_missing_font_refuses_rather_than_printing_boxes(self):
        """The same rule as a missing rate: refuse, and name the gap."""
        letter_pdf._registered = False
        original = letter_pdf.FONT_DIR
        try:
            letter_pdf.FONT_DIR = original.parent / 'no-such-directory'
            with self.assertRaises(letter_pdf.LetterFontMissing):
                letter_pdf.render(self.letters)
        finally:
            letter_pdf.FONT_DIR = original
            letter_pdf._registered = False

    def test_the_letterhead_artwork_is_shipped(self):
        self.assertTrue(letter_pdf.LETTERHEAD.exists(),
                        'the letterhead image is missing from the application')

    def pages(self, content: bytes) -> int:
        """Counted through the parser: `/Type /Page` in the raw bytes also
        matches `/Type /Pages`, the page-tree node, so a byte count is always
        one too high."""
        import io as _io

        from pypdf import PdfReader

        return len(PdfReader(_io.BytesIO(content)).pages)

    def test_every_letter_gets_its_own_page(self):
        """Two programmes are two documents; they must not run together."""
        one = self.pages(letter_pdf.render(self.letters[:1]))
        both = self.pages(letter_pdf.render(self.letters))
        self.assertGreater(both, one)

    def extracted(self, content: bytes) -> str:
        """The text a reader actually gets out of the PDF.

        Through a parser, not by grepping the file: the fonts are embedded as
        subsets, so the page stream holds glyph identifiers rather than ASCII
        and searching the bytes for a word finds nothing however correct the
        document is. Written that way, the test failed against a perfectly good
        PDF — and the tempting fix is to delete the assertion.
        """
        import io as _io

        from pypdf import PdfReader

        reader = PdfReader(_io.BytesIO(content))
        return '\n'.join(page.extract_text() or '' for page in reader.pages)

    def test_the_words_in_the_pdf_are_the_letters_own(self):
        """The whole point of the PDF is that it says what the letter says."""
        text = self.extracted(letter_pdf.render(self.letters))
        for expected in ('Program Costs', 'Total Allotted', 'Sara Student',
                         'Director of Education', 'Semester'):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_the_amounts_in_the_pdf_are_the_amounts_awarded(self):
        """A letter whose figures drift from the award is the office putting
        its name to a wrong number."""
        text = self.extracted(letter_pdf.render(self.letters))
        for letter in self.letters:
            with self.subTest(programme=letter['programme_code']):
                self.assertIn(letter['total'], text)
                for row in letter['rows']:
                    self.assertIn(row['amount'], text)

    def embedded_fonts(self, content: bytes) -> set[tuple[str, bool]]:
        """Every font the document references, and whether its file is in it."""
        import io as _io

        from pypdf import PdfReader

        found = set()
        for page in PdfReader(_io.BytesIO(content)).pages:
            resources = page.get('/Resources', {}).get_object()
            for _name, ref in (resources.get('/Font', {}) or {}).get_object().items():
                font = ref.get_object()
                descriptor = font.get('/FontDescriptor')
                embedded = bool(descriptor) and any(
                    key in descriptor.get_object()
                    for key in ('/FontFile', '/FontFile2', '/FontFile3'))
                found.add((str(font.get('/BaseFont')), embedded))
        return found

    def test_the_letter_is_set_in_the_shipped_font_and_it_is_embedded(self):
        """The check that actually catches the boxes.

        Extracting the text does not: with a Latin-1 built-in the text layer is
        still correct and pypdf reads the place name back perfectly, while the
        page displays black squares where the glyphs should be. The failure is
        visual, so the thing to assert is structural — the document carries the
        font it is set in, and that font is one we shipped.
        """
        fonts = self.embedded_fonts(letter_pdf.render(self.letters))
        serif = {(name, embedded) for name, embedded in fonts if 'DejaVuSerif' in name}
        self.assertTrue(serif, f'the shipped font is not in the document: {fonts}')
        self.assertTrue(all(embedded for _name, embedded in serif),
                        f'the font is referenced but not embedded: {serif}')
        self.assertTrue(any('Bold' in name for name, _ in serif),
                        f'the bold face is missing: {serif}')

    def test_no_base_fourteen_font_is_used_for_the_letter(self):
        """Named directly as well, so a switch back reads as what it is."""
        base14 = {'Times-Roman', 'Times-Bold', 'Helvetica', 'Helvetica-Bold',
                  'Courier', 'Courier-Bold'}
        self.assertNotIn(letter_pdf.BODY, base14)
        self.assertNotIn(letter_pdf.BOLD, base14)

    def test_the_offices_own_language_survives_into_the_pdf(self):
        """Not merely that the glyphs exist in the font — that they come back
        out of the finished document as the characters they went in as."""
        text = self.extracted(letter_pdf.render(self.letters))
        self.assertIn('Délı̨nę', text)
        self.assertIn('Got’ı̨nę', text)


class EndpointTests(TestCase):

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.admin = make_user(Role.ADMIN)
        self.student = make_user()
        self.application = price_and_approve(
            approved_application(student=self.student), self.admin)
        self.client = APIClient(HTTP_X_FORWARDED_PROTO='https')

    def url(self, application=None):
        target = application or self.application
        return f'/api/applications/{target.pk}/approval-letter/pdf/'

    def test_the_student_can_download_their_own(self):
        self.client.force_authenticate(self.student)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('.pdf', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF-'))

    def test_the_office_can_download_it_too(self):
        self.client.force_authenticate(make_user(Role.SUPPORT_WORKER))
        self.assertEqual(self.client.get(self.url()).status_code, 200)

    def test_another_student_cannot(self):
        self.client.force_authenticate(make_user())
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_a_stranger_cannot(self):
        self.assertEqual(self.client.get(self.url()).status_code, 401)

    def test_an_application_with_no_letter_says_why(self):
        other = approved_application(student=self.student)
        self.client.force_authenticate(self.student)
        response = self.client.get(self.url(other))
        self.assertEqual(response.status_code, 409)
        self.assertIn('approved', response.json()['detail'].lower())


class AttachmentTests(TestCase):
    """The PDF has to leave the building, not merely exist."""

    def setUp(self):
        seed_rates()
        call_command('seed_rules', '--publish', '--effective-from', '2020-01-01',
                     verbosity=0)
        self.admin = make_user(Role.ADMIN)

    def latest(self):
        from notifications.models import OutboundEmail
        return OutboundEmail.objects.latest('id')

    def test_the_approval_email_carries_the_pdf(self):
        from funding.services import messages

        application = price_and_approve(approved_application(), self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            messages.send_decision(application, approved=True)

        queued = self.latest()
        self.assertTrue(queued.attachment_name.endswith('.pdf'), queued.attachment_name)
        self.assertEqual(queued.attachment_type, 'application/pdf')
        self.assertTrue(bytes(queued.attachment).startswith(b'%PDF-'))

    def test_a_decline_carries_none(self):
        from funding.services import messages

        application = price_and_approve(approved_application(), self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            messages.send_decision(application, approved=False, reason='No')
        self.assertFalse(self.latest().attachment_name)

    def test_the_attachment_actually_reaches_the_message(self):
        """Asserted through what Django sends. A column holding bytes that
        `deliver` never attaches is a state with a writer and no reader — the
        same fault as an award status nothing ever wrote."""
        from django.core import mail
        from funding.services import messages
        from notifications.delivery import deliver

        application = price_and_approve(approved_application(), self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            messages.send_decision(application, approved=True)

        self.assertTrue(deliver(self.latest()))
        sent = mail.outbox[-1]
        names = [name for name, _content, _type in sent.attachments]
        self.assertTrue(any(name.endswith('.pdf') for name in names), names)

    def test_a_letter_that_cannot_be_rendered_does_not_swallow_the_decision(self):
        """A fault in the attachment must never cost somebody the notice that
        they were approved."""
        from funding.services import messages

        application = price_and_approve(approved_application(), self.admin)
        original = letter_pdf.FONT_DIR
        letter_pdf._registered = False
        try:
            letter_pdf.FONT_DIR = original.parent / 'no-such-directory'
            with self.captureOnCommitCallbacks(execute=True):
                messages.send_decision(application, approved=True)
        finally:
            letter_pdf.FONT_DIR = original
            letter_pdf._registered = False

        queued = self.latest()
        self.assertFalse(queued.attachment_name)
        self.assertIn('approved', queued.body_html.lower())
