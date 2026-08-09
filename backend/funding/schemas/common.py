"""Field groups that recur across application types.

Every form asks who is applying and where money should be sent. Defining those
once means a change to how a bank account is captured happens in one place, and
the same key means the same thing in every application type — which is what lets
one renderer and one set of generated types serve all of them.
"""

from . import Field, FieldType


def applicant(required_phone: bool = False) -> tuple[Field, ...]:
    """Who is applying."""
    return (
        Field('first_name', 'First name', FieldType.TEXT, required=True, section='Applicant'),
        Field('last_name', 'Last name', FieldType.TEXT, required=True, section='Applicant'),
        Field('email', 'Email', FieldType.EMAIL, required=True, section='Applicant'),
        Field('phone', 'Phone', FieldType.PHONE, required=required_phone, section='Applicant'),
        Field('beneficiary_number', 'Beneficiary number', FieldType.TEXT, section='Applicant'),
    )


def banking() -> tuple[Field, ...]:
    """Where the money goes. Only collected where an award is paid out."""
    return (
        Field('account_holder', 'Account holder name', FieldType.TEXT, section='Payment'),
        Field('transit_number', 'Transit number', FieldType.TEXT, section='Payment'),
        Field('institution_number', 'Bank institution number', FieldType.TEXT, section='Payment'),
        Field('account_number', 'Account number', FieldType.TEXT, section='Payment'),
    )


def signature() -> tuple[Field, ...]:
    return (
        Field('signature', 'Signature', FieldType.SIGNATURE, required=True,
              section='Declaration'),
    )
