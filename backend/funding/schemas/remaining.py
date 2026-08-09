"""The remaining application types.

Grouped in one module because each is small — a handful of questions on top of
the shared applicant and banking blocks. Splitting them into eight files would
be filing, not structure.
"""

from . import ApplicationSchema, Choice, Field, FieldType, register
from .admission import COURSE_LOAD, SEMESTER
from .common import applicant, banking, signature

# ── Continuing Funding (was Form C) ─────────────────────────────────────────
# A returning student's renewal. Same award inputs as an admission application,
# minus the identity and address questions already on file.
register(ApplicationSchema(
    slug='continuing_funding',
    fields=(
        *applicant(),
        Field('date_of_birth', 'Date of birth', FieldType.DATE, section='Applicant'),

        Field('institution_name', 'Institution', FieldType.TEXT, required=True, section='Study'),
        Field('program', 'Program of study', FieldType.TEXT, required=True, section='Study'),
        Field('current_gpa', 'Current GPA', FieldType.PERCENT, section='Study'),
        Field('registrar_email', 'Registrar email', FieldType.EMAIL, section='Study'),

        Field('semester', 'Semester', FieldType.CHOICE, required=True,
              choices=SEMESTER, section='Funding'),
        Field('semester_start', 'Semester start date', FieldType.DATE, required=True,
              section='Funding'),
        Field('semester_end', 'Semester end date', FieldType.DATE, required=True,
              section='Funding'),
        Field('course_load', 'Enrollment status', FieldType.CHOICE, required=True,
              choices=COURSE_LOAD, section='Funding'),
        Field('tuition_requested', 'Tuition amount', FieldType.MONEY, section='Funding'),
        Field('has_dependents', 'Do you have dependents?', FieldType.BOOLEAN,
              section='Funding'),
        Field('dependent_count', 'Number of dependents', FieldType.INTEGER,
              section='Funding'),
        Field('receives_sfa', 'Do you receive Student Financial Assistance?',
              FieldType.BOOLEAN, section='Funding'),

        *banking(),
        *signature(),
        Field('doc_transcript', 'Transcript', FieldType.FILE, required=True,
              section='Documents'),
        Field('doc_status_card', 'Status card', FieldType.FILE, section='Documents'),
    ),
))


# ── Appeal / Reconsideration (was Form D) ───────────────────────────────────
# Pays nothing directly; it asks for a decision to be revisited.
register(ApplicationSchema(
    slug='appeal',
    fields=(
        *applicant(),
        Field('original_decision', 'Decision being appealed', FieldType.TEXT,
              required=True,
              help_text='Which decision, and roughly when it was received.',
              section='Appeal'),
        Field('appeal_reason', 'Why the decision should be reconsidered',
              FieldType.LONG_TEXT, required=True, section='Appeal'),
        Field('additional_information', 'Anything else the reviewer should know',
              FieldType.LONG_TEXT, section='Appeal'),
        *signature(),
        Field('doc_supporting', 'Supporting documents', FieldType.FILE,
              section='Documents'),
    ),
))


# ── Travel & Emergency Assistance (was Form E) ──────────────────────────────
TRAVEL_PURPOSE = (
    Choice('start_of_study', 'Travel to start of study'),
    Choice('end_of_study', 'Return travel at end of study'),
    Choice('graduation', 'Graduation ceremony'),
    Choice('compassionate', 'Compassionate or emergency travel'),
)

register(ApplicationSchema(
    slug='travel',
    fields=(
        *applicant(),
        Field('travel_purpose', 'Purpose of travel', FieldType.CHOICE, required=True,
              choices=TRAVEL_PURPOSE, section='Travel'),
        Field('travel_date', 'Date of travel', FieldType.DATE, required=True,
              section='Travel'),
        Field('travel_from', 'Travelling from', FieldType.TEXT, required=True,
              section='Travel'),
        Field('travel_to', 'Travelling to', FieldType.TEXT, required=True,
              section='Travel'),
        Field('amount_requested', 'Amount claimed', FieldType.MONEY, required=True,
              section='Travel'),
        *banking(),
        *signature(),
        Field('doc_receipts', 'Receipts', FieldType.FILE, required=True,
              help_text='Travel is reimbursed against receipts.', section='Documents'),
    ),
))


# ── Practicum Placement Allowance (was Form F) ──────────────────────────────
register(ApplicationSchema(
    slug='practicum',
    fields=(
        *applicant(),
        Field('institution_name', 'Institution', FieldType.TEXT, required=True,
              section='Placement'),
        Field('program', 'Program of study', FieldType.TEXT, required=True,
              section='Placement'),
        Field('placement_location', 'Placement location', FieldType.TEXT, required=True,
              section='Placement'),
        Field('placement_start', 'Placement start date', FieldType.DATE, required=True,
              section='Placement'),
        Field('placement_end', 'Placement end date', FieldType.DATE, required=True,
              section='Placement'),
        Field('weeks_completed', 'Weeks completed', FieldType.INTEGER, section='Placement'),
        Field('supervisor_name', 'Supervisor name', FieldType.TEXT, section='Placement'),
        Field('supervisor_email', 'Supervisor email', FieldType.EMAIL, section='Placement'),
        Field('amount_requested', 'Allowance requested', FieldType.MONEY, section='Placement'),
        *banking(),
        *signature(),
        Field('doc_placement_letter', 'Placement letter', FieldType.FILE, required=True,
              section='Documents'),
    ),
))


# ── Emergency Relief (was Form H) ───────────────────────────────────────────
EMERGENCY_TYPE = (
    Choice('medical', 'Medical'),
    Choice('bereavement', 'Bereavement'),
    Choice('housing', 'Housing'),
    Choice('travel', 'Emergency travel'),
    Choice('other', 'Other'),
)

register(ApplicationSchema(
    slug='emergency_relief',
    fields=(
        *applicant(),
        Field('emergency_type', 'Nature of the emergency', FieldType.CHOICE,
              required=True, choices=EMERGENCY_TYPE, section='Emergency'),
        Field('emergency_description', 'What happened', FieldType.LONG_TEXT,
              required=True, section='Emergency'),
        Field('amount_requested', 'Amount requested', FieldType.MONEY, required=True,
              section='Emergency'),
        *banking(),
        *signature(),
        Field('doc_supporting', 'Supporting documents', FieldType.FILE,
              section='Documents'),
    ),
))


# ── Hardship Bursary ────────────────────────────────────────────────────────
register(ApplicationSchema(
    slug='hardship_bursary',
    fields=(
        *applicant(),
        Field('hardship_reason', 'Nature of the hardship', FieldType.LONG_TEXT,
              required=True, section='Hardship'),
        Field('supporting_details', 'Supporting details', FieldType.LONG_TEXT,
              section='Hardship'),
        Field('amount_requested', 'Amount requested', FieldType.MONEY, required=True,
              section='Hardship'),
        *banking(),
        *signature(),
        Field('doc_supporting', 'Supporting documents', FieldType.FILE,
              section='Documents'),
    ),
))


# ── Academic Scholarship ────────────────────────────────────────────────────
register(ApplicationSchema(
    slug='academic_scholarship',
    fields=(
        *applicant(),
        Field('institution_name', 'Institution', FieldType.TEXT, required=True,
              section='Achievement'),
        Field('program', 'Program of study', FieldType.TEXT, required=True,
              section='Achievement'),
        Field('semester', 'Qualifying semester', FieldType.CHOICE, required=True,
              choices=SEMESTER, section='Achievement'),
        Field('academic_year', 'Academic year', FieldType.TEXT, section='Achievement'),
        # The award tier is chosen from this, so it is a validated percentage
        # rather than free text.
        Field('gpa_achieved', 'GPA achieved', FieldType.PERCENT, required=True,
              help_text='Determines which achievement band applies.',
              section='Achievement'),
        *banking(),
        *signature(),
        Field('doc_transcript', 'Official transcript', FieldType.FILE, required=True,
              section='Documents'),
    ),
))


# ── Enrollment Verification (was Form B) ────────────────────────────────────
# Completed by the institution's registrar, not the student. It confirms the
# facts the funding calculation depends on, which is why tuition is not awarded
# until it arrives.
register(ApplicationSchema(
    slug='enrollment_verification',
    fields=(
        Field('student_name', 'Student name', FieldType.TEXT, required=True,
              section='Student'),
        Field('student_number', 'Student number', FieldType.TEXT, section='Student'),
        Field('institution_name', 'Institution', FieldType.TEXT, required=True,
              section='Enrollment'),
        Field('program', 'Program of study', FieldType.TEXT, required=True,
              section='Enrollment'),
        Field('is_enrolled', 'Is the student currently enrolled?', FieldType.BOOLEAN,
              required=True, section='Enrollment'),
        Field('course_load', 'Enrollment status', FieldType.CHOICE, required=True,
              choices=COURSE_LOAD, section='Enrollment'),
        Field('semester_start', 'Semester start date', FieldType.DATE, required=True,
              section='Enrollment'),
        Field('semester_end', 'Semester end date', FieldType.DATE, required=True,
              section='Enrollment'),
        # The figure the award is actually based on.
        Field('confirmed_tuition', 'Tuition billed for this semester', FieldType.MONEY,
              required=True,
              help_text='Tuition is funded against this amount, not the estimate '
                        'given by the student.',
              section='Enrollment'),
        Field('registrar_name', 'Registrar name', FieldType.TEXT, required=True,
              section='Declaration'),
        Field('registrar_title', 'Position', FieldType.TEXT, section='Declaration'),
        Field('signature', 'Signature', FieldType.SIGNATURE, required=True,
              section='Declaration'),
    ),
))
