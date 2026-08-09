"""Graduation Bursary — a one-time award on completing a credential.

Previously 'Form G'. The credential is a validated choice because the award tier
follows directly from it. As free text, an answer matching none of the expected
substrings silently paid the cheapest tier.
"""

from . import ApplicationSchema, Choice, Field, FieldType, register

CREDENTIAL = (
    Choice('high_school_diploma', 'High school diploma'),
    Choice('certificate', 'Certificate'),
    Choice('trades_certificate', 'Trades certificate'),
    Choice('trades_journeyperson', 'Journeyperson certification'),
    Choice('diploma', 'Diploma'),
    Choice('pilot_licence', 'Pilot licence'),
    Choice('bachelors_degree', 'Bachelor degree'),
    Choice('masters_degree', 'Master degree'),
    Choice('doctorate', 'Doctorate'),
)

register(ApplicationSchema(
    slug='graduation_bursary',
    fields=(
        Field('first_name', 'First name', FieldType.TEXT, required=True, section='Applicant'),
        Field('last_name', 'Last name', FieldType.TEXT, required=True, section='Applicant'),
        Field('email', 'Email', FieldType.EMAIL, required=True, section='Applicant'),
        Field('beneficiary_number', 'Beneficiary number', FieldType.TEXT, section='Applicant'),

        Field('institution_name', 'Institution', FieldType.TEXT, required=True,
              section='Credential'),
        Field('program', 'Program completed', FieldType.TEXT, required=True, section='Credential'),
        Field('credential', 'Credential earned', FieldType.CHOICE, required=True,
              choices=CREDENTIAL, help_text='Determines the bursary amount.',
              section='Credential'),
        Field('graduation_date', 'Graduation date', FieldType.DATE, required=True,
              section='Credential'),

        Field('signature', 'Signature', FieldType.SIGNATURE, required=True, section='Declaration'),
        Field('doc_proof_of_completion', 'Proof of completion', FieldType.FILE,
              required=True, section='Documents'),
    ),
))
