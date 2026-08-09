"""Admission Application — a student's first request for post-secondary funding.

Previously 'Form A'. Only the fields the office acts on: who is applying, where
they are studying, what drives the award, and where the money is sent.
"""

from . import ApplicationSchema, Choice, Field, FieldType, register

COURSE_LOAD = (
    Choice('full_time', 'Full-time'),
    Choice('part_time', 'Part-time'),
)

SEMESTER = (
    Choice('fall', 'Fall'),
    Choice('winter', 'Winter'),
    Choice('spring', 'Spring'),
    Choice('summer', 'Summer'),
)

register(ApplicationSchema(
    slug='admission',
    fields=(
        # ── Applicant ──
        Field('first_name', 'First name', FieldType.TEXT, required=True, section='Applicant'),
        Field('last_name', 'Last name', FieldType.TEXT, required=True, section='Applicant'),
        Field('preferred_name', 'Preferred name', FieldType.TEXT, section='Applicant'),
        Field('date_of_birth', 'Date of birth', FieldType.DATE, required=True, section='Applicant'),
        Field('email', 'Email', FieldType.EMAIL, required=True, section='Applicant'),
        Field('phone', 'Phone', FieldType.PHONE, section='Applicant'),
        Field('beneficiary_number', 'Beneficiary number', FieldType.TEXT, section='Applicant'),

        # ── Address ──
        Field('street_address', 'Street address', FieldType.TEXT, required=True, section='Address'),
        Field('city', 'Town or city', FieldType.TEXT, required=True, section='Address'),
        Field('province', 'Province or territory', FieldType.TEXT, required=True, section='Address'),
        Field('postal_code', 'Postal code', FieldType.TEXT, section='Address'),

        # ── Study ──
        Field('institution_name', 'Institution', FieldType.TEXT, required=True, section='Study'),
        Field('institution_location', 'Institution location', FieldType.TEXT, section='Study'),
        Field('program', 'Program of study', FieldType.TEXT, required=True, section='Study'),
        Field('program_start', 'Program start date', FieldType.DATE, section='Study'),
        Field('program_end', 'Expected completion date', FieldType.DATE, section='Study'),
        Field('registrar_email', 'Registrar email', FieldType.EMAIL, required=True,
              help_text='Enrollment is confirmed with the institution before tuition is awarded.',
              section='Study'),

        # ── Award inputs ──
        # Everything the funding calculation reads is declared here and nowhere else.
        Field('semester', 'Semester', FieldType.CHOICE, required=True,
              choices=SEMESTER, section='Funding'),
        Field('semester_start', 'Semester start date', FieldType.DATE, required=True,
              section='Funding'),
        Field('semester_end', 'Semester end date', FieldType.DATE, required=True,
              section='Funding'),
        Field('course_load', 'Enrollment status', FieldType.CHOICE, required=True,
              choices=COURSE_LOAD,
              help_text='Full-time and part-time draw different living allowance rates.',
              section='Funding'),
        Field('tuition_requested', 'Tuition amount', FieldType.MONEY, section='Funding'),
        Field('has_dependents', 'Do you have dependents?', FieldType.BOOLEAN, section='Funding'),
        Field('dependent_count', 'Number of dependents', FieldType.INTEGER, section='Funding'),
        Field('receives_sfa', 'Do you receive Student Financial Assistance?',
              FieldType.BOOLEAN, section='Funding',
              help_text='SFA recipients are not eligible for C-DFN tuition or living allowance.'),

        # ── Payment ──
        Field('account_holder', 'Account holder name', FieldType.TEXT, section='Payment'),
        Field('transit_number', 'Transit number', FieldType.TEXT, section='Payment'),
        Field('institution_number', 'Bank institution number', FieldType.TEXT, section='Payment'),
        Field('account_number', 'Account number', FieldType.TEXT, section='Payment'),

        # ── Declaration ──
        Field('signature', 'Signature', FieldType.SIGNATURE, required=True, section='Declaration'),
        Field('doc_transcript', 'Transcript', FieldType.FILE, required=True, section='Documents'),
        Field('doc_letter_of_intent', 'Letter of intent', FieldType.FILE, required=True,
              section='Documents'),
        Field('doc_status_card', 'Status card', FieldType.FILE, required=True, section='Documents'),
        Field('doc_void_cheque', 'Void cheque', FieldType.FILE, required=True, section='Documents'),
        Field('doc_reference_letter', 'Reference letter', FieldType.FILE, section='Documents'),
    ),
))
