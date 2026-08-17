"""Admission Application — a student's first request for post-secondary funding.

Previously 'Form A'. This is the form every other record derives from: the
enrolment verification sent to the registrar is generated from these answers,
and the award calculation reads its funding fields and nothing else.

Field keys are stable machine names. The rules in seed_rules and the effect
calculators in funding.rules read `course_load`, `semester_start`,
`semester_end`, `receives_sfa`, `has_dependents` and `confirmed_tuition` by
key, so those names cannot change without changing the rules that price them.
"""

from . import ApplicationSchema, Choice, Field, FieldType, register
from .common import banking

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

LEARNING_STYLE = (
    Choice('in_person', 'In-person'),
    Choice('online_hybrid', 'Online / Hybrid'),
)

GENDER = (
    Choice('female', 'Female'),
    Choice('male', 'Male'),
    Choice('other', 'Other'),
    Choice('prefer_not_to_say', 'Prefer not to say'),
)

# What the student is working towards. The registrar confirms it on the
# enrolment verification; the student states it here so the generated form
# arrives with something to confirm rather than blank.
CREDENTIAL_LEVEL = (
    Choice('certificate', 'Certificate'),
    Choice('diploma', 'Diploma'),
    Choice('degree', 'Degree'),
    Choice('masters', 'Masters'),
    Choice('doctorate', 'Doctorate'),
    Choice('other', 'Other'),
)

register(ApplicationSchema(
    slug='admission',
    summary=(
        'Start here. Establishes your file and decides which funding you qualify for.'
    ),
    fields=(
        # ── Applicant ──
        Field('first_name', 'First name', FieldType.TEXT, required=True, section='Applicant'),
        Field('last_name', 'Last name', FieldType.TEXT, required=True, section='Applicant'),
        Field('preferred_name', 'Preferred name', FieldType.TEXT, section='Applicant'),
        Field('date_of_birth', 'Date of birth', FieldType.DATE, required=True, section='Applicant'),
        Field('gender', 'Gender', FieldType.CHOICE, choices=GENDER, section='Applicant'),
        Field('email', 'Email address', FieldType.EMAIL, required=True, section='Applicant'),
        Field('phone', 'Phone', FieldType.PHONE, required=True, section='Applicant'),
        # Kept out of `answers` and out of the registrar's copy. See
        # funding.services.identifiers for how it is stored and who can read it.
        Field('sin', 'Social Insurance Number', FieldType.SIN, required=True,
              help_text='Required for federal reporting. Stored encrypted, never '
                        'shown in full again, and never sent to your institution.',
              section='Applicant'),
        Field('beneficiary_number', 'Délı̨nę beneficiary number', FieldType.TEXT,
              section='Applicant'),

        # ── Address ──
        Field('street_address', 'Permanent residential address', FieldType.TEXT,
              required=True, help_text='Street address or PO box.', section='Address'),
        Field('city', 'Town or city', FieldType.TEXT, required=True, section='Address'),
        Field('province', 'Territory or province', FieldType.TEXT, required=True,
              section='Address'),
        Field('postal_code', 'Postal code', FieldType.TEXT, required=True, section='Address'),
        Field('current_address', 'Current address', FieldType.TEXT,
              help_text='Your in-school address. Leave blank if the same as above.',
              section='Address'),

        # ── Study ──
        Field('institution_name', 'Institution', FieldType.TEXT, required=True,
              help_text='Full name of the college, university or trade school.',
              section='Study'),
        Field('institution_location', 'Institution location', FieldType.TEXT,
              section='Study'),
        Field('program', 'Program of study', FieldType.TEXT, required=True,
              help_text='For example "Nursing Degree" or "Carpentry Level 1".',
              section='Study'),
        Field('credential_level', 'Working towards', FieldType.CHOICE,
              choices=CREDENTIAL_LEVEL, section='Study'),
        Field('learning_style', 'Learning style', FieldType.CHOICE,
              choices=LEARNING_STYLE, section='Study'),
        Field('student_number', 'Student ID at your institution', FieldType.TEXT,
              help_text='If your institution has assigned you one.', section='Study'),
        Field('program_start', 'Program start date', FieldType.DATE, required=True,
              section='Study'),
        Field('program_end', 'Expected completion date', FieldType.DATE, required=True,
              section='Study'),
        Field('program_year', 'Year of program', FieldType.INTEGER,
              help_text='Which year you are entering.', section='Study'),
        Field('program_length_years', 'Length of program in years', FieldType.INTEGER,
              section='Study'),

        # ── Registrar ──
        # Where the generated enrolment verification is sent. Without a working
        # address here tuition can never be confirmed, so it is required.
        Field('registrar_email', 'Registrar or official email', FieldType.EMAIL,
              required=True,
              help_text='The enrolment verification is generated from this '
                        'application and emailed here for your institution to confirm.',
              section='Registrar'),
        Field('institution_phone', 'Institution phone', FieldType.PHONE,
              section='Registrar'),

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
        Field('tuition_requested', 'Tuition amount requested', FieldType.MONEY,
              required=True,
              help_text='As quoted by your institution. The final figure is the one '
                        'your registrar confirms.',
              section='Funding'),
        Field('has_dependents', 'Do you have dependents?', FieldType.BOOLEAN,
              section='Funding'),
        Field('dependent_count', 'Number of dependents', FieldType.INTEGER,
              section='Funding'),
        Field('receives_sfa', 'Do you receive Student Financial Assistance?',
              FieldType.BOOLEAN, section='Funding',
              help_text='SFA recipients are not eligible for C-DFN tuition or living allowance.'),

        # ── Payment ──
        # The same block every other paying form uses, required here because an
        # admission application is what puts someone on the payroll. It was
        # written out by hand and had drifted: identical keys, different
        # requiredness and hints from the shared definition.
        *banking(required=True),

        # ── Documents ──
        Field('doc_transcript', 'Transcript', FieldType.FILE, required=True,
              help_text='Recent high school or post-secondary.', section='Documents'),
        Field('doc_letter_of_intent', 'Letter of intent', FieldType.FILE, required=True,
              help_text='Explanation of your program goals.', section='Documents'),
        Field('doc_reference_letter', 'Reference letter', FieldType.FILE,
              help_text='From a non-family reference.', section='Documents'),
        Field('doc_status_card', 'Status card or beneficiary ID', FieldType.FILE,
              required=True, section='Documents'),
        Field('doc_void_cheque', 'Void cheque or direct deposit form', FieldType.FILE,
              required=True, section='Documents'),
        Field('doc_extra', 'Anything else', FieldType.FILE,
              help_text='Acceptance letter, tuition invoice, and so on.',
              section='Documents'),

        # ── Declaration ──
        Field('signature', 'Signature', FieldType.SIGNATURE, required=True,
              help_text='Type your full legal name. You declare that everything '
                        'given here is true, and authorise DGG to contact your '
                        'institution to verify your enrolment.',
              section='Declaration'),
    ),
))
