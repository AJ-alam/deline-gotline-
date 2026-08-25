"""Field groups that recur across application types.

Every form asks who is applying and where money should be sent. Defining those
once means a change to how a bank account is captured happens in one place, and
the same key means the same thing in every application type — which is what lets
one renderer and one set of generated types serve all of them.
"""

from decimal import Decimal

from . import Field, FieldType


def banking(required: bool = False) -> tuple[Field, ...]:
    """Where the money goes. Only collected where an award is paid out.

    Marked private, so these are validated and then kept out of `answers`
    entirely: that column is returned whole by the detail endpoint, printed on
    the paper form and copied into the enrolment verification an institution
    receives. An account number was sitting in all three.

    They are routed to the account record instead — see
    funding.services.banking — which is also where finance reads them from.
    Collecting them into `answers` meant the payment run never saw them: a
    student who filled this in was still reported as having no account on file
    and their award was held.
    """
    return (
        Field('account_holder', 'Account holder name', FieldType.TEXT,
              required=required, private=True, section='Payment'),
        Field('transit_number', 'Transit number', FieldType.TEXT,
              required=required, private=True,
              help_text='Five digits.', section='Payment'),
        Field('institution_number', 'Bank institution number', FieldType.TEXT,
              required=required, private=True,
              help_text='Three digits.', section='Payment'),
        Field('account_number', 'Account number', FieldType.TEXT,
              required=required, private=True,
              help_text='Seven to twelve digits.', section='Payment'),
    )


def total_of(rows, column: str = 'amount') -> Decimal:
    """One money column of a table, added up.

    Shared by the two forms that itemise what they are asking for — the travel
    claim's expenses and the hardship bursary's fund breakdown. Both derive
    `amount_requested` from their rows rather than asking for it, because the
    figure the rules engine reads is the figure that gets paid: asked
    separately, it can disagree with the lines, and the one nobody itemised is
    the one that is paid.
    """
    total = Decimal('0.00')
    for row in rows or ():
        amount = row.get(column)
        if amount is not None:
            total += Decimal(str(amount))
    return total.quantize(Decimal('0.01'))


def signature() -> tuple[Field, ...]:
    return (
        Field('signature', 'Signature', FieldType.SIGNATURE, required=True,
              section='Declaration'),
    )
