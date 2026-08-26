"""The travel claim.

Its own module rather than another entry in `remaining.py`, which groups the
types that are a handful of questions on top of the shared blocks. This one is
not: it carries a line-by-line expense breakdown, a total the server works out
from it, and the only many-file question in the portal.

Reimbursement, not an estimate. Everything here describes travel that has
already happened, which is why receipts are mandatory and why the amount claimed
is the sum of the lines rather than a figure typed on its own.
"""

from decimal import Decimal

from . import ApplicationSchema, Choice, Field, FieldType, register
from .common import banking, total_of

ZERO = Decimal('0.00')

STUDENT = 'Student'
TRAVEL = 'Travel'
EXPENSES = 'Expenses'
RECEIPTS = 'Receipts'
PAYMENT = 'Payment'
DECLARATION = 'Declaration'

# Why the trip was made. Kept because it is what the award is capped by:
# `seed_rules.travel_assistance` resolves the rate key
# `max_{travel_purpose}_{dependants}`, so an absent purpose is an absent cap.
#
# The policy funds two things here and no others: a C-DFN Travel Assistance
# Bursary for up to two round-trips a year between home and school (§7(C)), and
# a Graduation Travel Bursary for family to attend a ceremony (§7(D)).
# 'Compassionate' was offered and has no programme behind it, so a claim filed
# under it resolved a rate key that does not exist — an award of nothing,
# reported as an unconfigured rate rather than as an ineligible claim.
TRAVEL_PURPOSE = (
    Choice('start_of_study', 'Travel to start of study'),
    Choice('end_of_study', 'Return travel at end of study'),
    Choice('graduation', 'Graduation ceremony'),
)

# The paper form offers Air and Land as two boxes, either or both of which can
# be ticked — a flight out and a drive back is a real trip. Two booleans would
# allow a third state that is not a journey (neither ticked), so the ways of
# travelling are enumerated instead and the form cannot record a claim for
# travel by no means at all.
TRAVEL_MODE = (
    Choice('air', 'Air'),
    Choice('land', 'Land'),
    Choice('air_and_land', 'Air and land'),
)

# A trip has a flight, a hotel, and some taxis — not fifty of either. High
# enough that no honest claim meets it, low enough that `answers` cannot be
# filled by one submission.
MAX_EXPENSE_ROWS = 20
MAX_RECEIPTS = 20


def total_claimed(answers: dict) -> dict:
    """The amount claimed: the expense lines, added up.

    Not asked. `travel_assistance` pays `amount_requested` up to the cap for the
    purpose, so a total typed separately from the lines is a total that can
    disagree with them — and the one that gets paid is the one nobody itemised.
    """
    return {'amount_requested': total_of(answers.get('expenses'))}


register(ApplicationSchema(
    slug='travel',
    summary=(
        'Claim back what you spent travelling to or from your institution. '
        'Receipts are required, and the claim is paid against them.'
    ),
    derive=total_claimed,
    fields=(
        # ── Who is claiming ──
        Field('first_name', 'First name', FieldType.TEXT, required=True,
              section=STUDENT),
        Field('last_name', 'Last name', FieldType.TEXT, required=True,
              section=STUDENT),
        Field('date_of_birth', 'Date of birth', FieldType.DATE, required=True,
              section=STUDENT),
        Field('treaty_number', 'Treaty number', FieldType.TEXT, required=True,
              help_text='Your registration number under the treaty.',
              section=STUDENT),
        Field('beneficiary_number', 'Beneficiary number', FieldType.TEXT,
              section=STUDENT),
        Field('email', 'Email', FieldType.EMAIL, required=True, section=STUDENT),
        Field('phone', 'Phone', FieldType.PHONE, section=STUDENT),

        # ── The journey ──
        Field('travel_purpose', 'Purpose of travel', FieldType.CHOICE, required=True,
              choices=TRAVEL_PURPOSE,
              help_text='This decides the maximum that can be reimbursed.',
              section=TRAVEL),
        Field('travel_from', 'Travelling from', FieldType.TEXT, required=True,
              help_text='Town or city, and territory or province.', section=TRAVEL),
        Field('travel_to', 'Travelling to', FieldType.TEXT, required=True,
              help_text='Town or city, and territory or province.', section=TRAVEL),
        Field('departure_date', 'Departure date', FieldType.DATE, required=True,
              section=TRAVEL),
        # Optional: a claim for the outbound leg of a trip that is not over is a
        # real claim, and demanding a return date would have it invented.
        Field('return_date', 'Return date', FieldType.DATE, section=TRAVEL),
        Field('travel_mode', 'How you travelled', FieldType.CHOICE, required=True,
              choices=TRAVEL_MODE, section=TRAVEL),
        Field('total_km', 'Total kilometres', FieldType.INTEGER,
              help_text='Only if any part of the journey was by road.',
              section=TRAVEL),

        # ── What it cost ──
        Field('expenses', 'Expenses claimed', FieldType.TABLE, required=True,
              help_text='One line per expense. Every line needs a receipt.',
              max_items=MAX_EXPENSE_ROWS,
              columns=(
                  Field('description', 'Description', FieldType.TEXT, required=True),
                  Field('amount', 'Amount', FieldType.MONEY, required=True),
                  Field('receipt_attached', 'Receipt attached', FieldType.BOOLEAN),
              ),
              section=EXPENSES),
        Field('amount_requested', 'Total claimed', FieldType.MONEY, computed=True,
              help_text='The expense lines added up.', section=EXPENSES),

        Field('doc_receipts', 'Receipts', FieldType.FILES, required=True,
              help_text='Attach every receipt — select them all at once, or add '
                        'them one at a time. PDF or photo.',
              max_items=MAX_RECEIPTS, section=RECEIPTS),

        # ── Where the money goes ──
        *banking(required=True),

        # ── The declaration, as the office words it ──
        Field('declaration_confirmed', 'I confirm the declaration',
              FieldType.CONFIRM, required=True,
              help_text='I declare that the expenses incurred have been used for '
                        'the purpose of traveling to and from my post-secondary '
                        'institution. Any false information will result in the '
                        'denial of reimbursement.',
              section=DECLARATION),
        Field('signature', 'Student signature (full name)', FieldType.SIGNATURE,
              required=True, section=DECLARATION),
    ),
))
