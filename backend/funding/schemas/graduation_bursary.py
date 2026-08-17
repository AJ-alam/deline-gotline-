"""Graduation Award — a one-time payment on finishing a credential.

Previously 'Form G'. The credential is a validated choice because the award tier
follows directly from it: `graduation_bursary` is a `flat_rate` rule keyed on
`{credential}`, so the answer *is* the amount. As free text, an answer matching
none of the expected substrings silently paid the cheapest tier.

Claimable with no portal account, which shapes most of what it asks. Nothing
about the person is on file, so the form collects it: the legal name the payment
is made out to, an address to reach them at, and the bank details finance pays
into. A student with an account has all of this already; a graduate who left
before the portal existed has none of it.
"""

from . import ApplicationSchema, Choice, Field, FieldType, register
from .common import banking

STUDENT = 'Student information'
ADDRESS = 'Current mailing address'
CREDENTIAL_SECTION = 'Graduation details'
DOCUMENTS = 'Documents'
RELEASE = 'Release of funds'
DECLARATION = 'Declaration'

# The values are the rate keys `graduation_bursary` is priced from — see
# seed_rules and the `graduation_bursary` section of the policy rates. Renaming
# a label here is free; renaming a value changes what somebody is paid.
#
# The list is §9(E)'s table, entry for entry. Red Seal, Juris Doctor / Bachelor
# of Laws, and Doctor of Medicine / Doctor of Dental Surgery were absent, so a
# graduate holding one of them had no answer that described their credential and
# would have had to claim under a cheaper one.
CREDENTIAL = (
    Choice('high_school_diploma', 'High school diploma'),
    Choice('certificate', 'Certificate'),
    Choice('trades_certificate', 'Trades certificate of qualification'),
    Choice('trades_journeyperson', 'Trades journeyperson licence'),
    Choice('diploma', 'Diploma'),
    Choice('pilot_licence', 'Professional pilot licence'),
    Choice('red_seal', 'Red Seal'),
    Choice('bachelors_degree', 'Bachelors degree (including Bachelor of Education)'),
    Choice('masters_degree', 'Masters degree'),
    Choice('doctorate', 'Doctorate (PhD)'),
    Choice('juris_doctor', 'Juris Doctor or Bachelor of Laws'),
    Choice('md_dds', 'Doctor of Medicine or Doctor of Dental Surgery'),
)

register(ApplicationSchema(
    slug='graduation_bursary',
    summary=(
        'A one-time award for finishing a credential — high school through to a '
        'doctorate. You can claim it without a portal account.'
    ),
    fields=(
        # ── Who is being paid ──
        # One name field, not two: this is the name on the payment, and a
        # legal name is not always a first and a last.
        Field('full_name', 'Full legal name', FieldType.TEXT, required=True,
              section=STUDENT),
        Field('date_of_birth', 'Date of birth', FieldType.DATE, required=True,
              section=STUDENT),
        Field('treaty_number', 'Treaty / SCN number', FieldType.TEXT, required=True,
              section=STUDENT),
        # Optional, unlike the admission application's. Federal reporting needs
        # one where federal money is involved; this award is paid from the
        # government's own funds, so refusing a claim for want of a SIN would
        # withhold a bursary over a number nothing here spends.
        #
        # Never lands in `answers`: split off at validation, encrypted, and
        # written to ApplicantIdentifier. That happens on the guest path too —
        # it did not until this form asked for one.
        Field('sin', 'Social Insurance Number', FieldType.SIN,
              help_text='Optional. Stored encrypted and never shown in full.',
              section=STUDENT),
        Field('phone', 'Phone', FieldType.PHONE, required=True, section=STUDENT),
        Field('email', 'Email', FieldType.EMAIL, required=True,
              help_text='Where your reference number and the decision are sent.',
              section=STUDENT),
        Field('beneficiary_number', 'Beneficiary number', FieldType.TEXT,
              section=STUDENT),

        # ── Where they can be reached ──
        # The award is processed against this, and a cheque or a letter has to
        # arrive somewhere.
        Field('city', 'Town or city', FieldType.TEXT, required=True, section=ADDRESS),
        Field('province', 'Territory or province', FieldType.TEXT, required=True,
              section=ADDRESS),
        Field('postal_code', 'Postal code', FieldType.TEXT, required=True,
              section=ADDRESS),

        # ── What was finished ──
        Field('institution_name', 'Institution', FieldType.TEXT, required=True,
              section=CREDENTIAL_SECTION),
        Field('program', 'Program of study', FieldType.TEXT, required=True,
              section=CREDENTIAL_SECTION),
        Field('graduation_date', 'Completion date', FieldType.DATE, required=True,
              section=CREDENTIAL_SECTION),
        Field('credential', 'Credential earned', FieldType.CHOICE, required=True,
              choices=CREDENTIAL, help_text='This decides the amount awarded.',
              section=CREDENTIAL_SECTION),

        Field('doc_proof_of_completion', 'Proof of completion or certificate',
              FieldType.FILE, required=True,
              help_text='A parchment, a transcript, or a letter from the '
                        'institution. PDF or photo.',
              section=DOCUMENTS),

        # ── Where the money goes ──
        # Required here, unlike every other form that asks. There is no account
        # behind a guest claim for finance to fall back on, so a claim without
        # these is one the payment run reports as unpayable.
        *banking(required=True),

        Field('release_to_other',
              'Payment goes to another person (release of funds)',
              FieldType.BOOLEAN,
              help_text='Tick only if the award should be paid to someone other '
                        'than you. The office will contact you to arrange it.',
              section=RELEASE),
        # Asked because the tick alone tells finance to do something by hand
        # without saying to whom, which is a phone call for every claim. It does
        # not authorise anything: see funding.services.finance, which holds a
        # released award out of the payment file rather than redirecting it.
        Field('release_recipient', 'Who should be paid', FieldType.TEXT,
              help_text='Their full name, and how they are connected to you.',
              section=RELEASE),

        # ── The declaration, worded as the office words it ──
        Field('declaration_confirmed', 'I confirm the declaration',
              FieldType.CONFIRM, required=True,
              help_text='I declare that the information provided is true and '
                        'complete. I understand that any false information will '
                        'result in the suspension of my graduation award.',
              section=DECLARATION),
        Field('signature', 'Student digital signature', FieldType.SIGNATURE,
              required=True, section=DECLARATION),
        Field('signed_on', 'Date', FieldType.DATE, required=True,
              defaults_to_today=True, section=DECLARATION),
    ),
))
