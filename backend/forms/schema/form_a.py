"""Form A — Admission Application (PSSSP).

Field keys are taken from what FormA.tsx actually submits today, and every
display string that field has been stored under is recorded in `legacy_labels`
so existing SubmissionAnswer rows migrate onto keys without guessing.

Two mismatches this makes visible, both live today:
  * seed_forms.py seeds FormField labels as camelCase ('courseLoad') while
    FormA.tsx submits display labels ('Enrollment Status') — the seeded template
    and the real submissions never agreed.
  * the field the student fills in as "Enrollment Status" is the course load the
    funding calculation depends on. Both spellings are kept below.
"""

from . import Choice, Field, FieldType, FormSchema, FundingType, register

COURSE_LOAD_CHOICES = (
    Choice('full_time', 'Full-time'),
    Choice('part_time', 'Part-time'),
)

FUNDING_STREAM_CHOICES = (
    Choice('psssp', 'PSSSP'),
    Choice('dggr', 'DGGR'),
    Choice('ucepp', 'UCEPP'),
)

SEMESTER_CHOICES = (
    Choice('fall', 'Fall'),
    Choice('winter', 'Winter'),
    Choice('spring', 'Spring'),
    Choice('summer', 'Summer'),
)

FORM_A = register(FormSchema(
    slug='form-a',
    title='Form A — Admission Application',
    description='Post-Secondary Student Support Program — initial funding application.',
    funding_type=FundingType.PSSSP,
    fields=(
        # ── Student identity ──
        Field('first_name', 'First Name', FieldType.TEXT, required=True,
              legacy_labels=('First Name', 'firstName')),
        Field('last_name', 'Last Name', FieldType.TEXT, required=True,
              legacy_labels=('Last Name', 'lastName')),
        Field('preferred_name', 'Preferred Name', FieldType.TEXT,
              legacy_labels=('Preferred Name', 'preferredName')),
        Field('date_of_birth', 'Date of Birth', FieldType.DATE, required=True,
              legacy_labels=('Date of Birth', 'dob')),
        Field('gender', 'Gender', FieldType.TEXT,
              legacy_labels=('Gender', 'sex')),
        Field('sin', 'Social Insurance Number', FieldType.TEXT,
              legacy_labels=('SIN', 'sin')),
        Field('beneficiary_number', 'Beneficiary Number', FieldType.TEXT,
              legacy_labels=('Beneficiary Number', 'beneficiaryNo')),

        # ── Contact ──
        Field('email', 'Email', FieldType.EMAIL, required=True,
              legacy_labels=('Email', 'email')),
        Field('phone', 'Phone', FieldType.PHONE,
              legacy_labels=('Phone', 'phone')),
        Field('permanent_address', 'Permanent Residential Address', FieldType.TEXT,
              legacy_labels=('Permanent Residential Address', 'address')),
        Field('current_address', 'Current Address', FieldType.TEXT,
              legacy_labels=('Current Address', 'currentAddress')),
        Field('city', 'City', FieldType.TEXT,
              legacy_labels=('City', 'city')),
        Field('province', 'Province', FieldType.TEXT,
              legacy_labels=('Province', 'province')),
        Field('postal_code', 'Postal Code', FieldType.TEXT,
              legacy_labels=('Postal Code', 'postalCode')),

        # ── Institution and program ──
        Field('student_id', 'Student ID', FieldType.TEXT,
              legacy_labels=('Student ID', 'studentId')),
        Field('institution_name', 'Institution Name', FieldType.TEXT, required=True,
              legacy_labels=('Institution Name', 'Institution', 'institution')),
        Field('institution_location', 'Institution Location', FieldType.TEXT,
              legacy_labels=('Institution Location', 'institutionLocation')),
        Field('program', 'Program', FieldType.TEXT, required=True,
              legacy_labels=('Program', 'program')),
        Field('program_start', 'Program Start Date', FieldType.DATE,
              legacy_labels=('Program Start Date', 'programStart')),
        Field('program_end', 'Program End Date', FieldType.DATE,
              legacy_labels=('Program End Date', 'programEnd')),
        Field('learning_style', 'Learning Style', FieldType.TEXT,
              legacy_labels=('Learning Style', 'learningStyle')),

        # ── Semester ──
        Field('semester', 'Semester', FieldType.CHOICE, choices=SEMESTER_CHOICES,
              legacy_labels=('Semester', 'semester')),
        Field('semester_start', 'Semester Start Date', FieldType.DATE,
              legacy_labels=('Semester Start Date', 'semStart')),
        Field('semester_end', 'Semester End Date', FieldType.DATE,
              legacy_labels=('Semester End Date', 'semEnd')),
        Field('registrar_email', 'Registrar Email', FieldType.EMAIL,
              legacy_labels=('Registrar Email', 'registrarEmail')),

        # ── Funding inputs (these drive the award) ──
        Field('course_load', 'Enrollment Status', FieldType.CHOICE,
              required=True, choices=COURSE_LOAD_CHOICES,
              help_text='Full-time and part-time draw different living allowance rates.',
              # 'Enrollment Status' is what the student sees; 'Course Load' is what
              # the calculation used to search for. Both have been stored.
              legacy_labels=('Enrollment Status', 'Course Load', 'courseLoad')),
        Field('funding_stream', 'Funding Stream', FieldType.CHOICE,
              choices=FUNDING_STREAM_CHOICES,
              legacy_labels=('Funding Stream', 'bursaryStream')),
        Field('tuition_requested', 'Tuition Amount Requested', FieldType.MONEY,
              legacy_labels=('Tuition Amount Requested', 'Tuition', 'tuition')),
        Field('has_dependents', 'Has Dependents', FieldType.BOOLEAN,
              legacy_labels=('Has Dependents', 'hasDependents')),
        Field('dependent_count', 'Number of Dependents', FieldType.INTEGER,
              legacy_labels=('Number of Dependents', 'dependentCount')),

        # ── Banking ──
        Field('account_holder', 'Account Holder', FieldType.TEXT,
              legacy_labels=('Account Holder', 'accountHolder')),
        Field('transit_number', 'Transit Number', FieldType.TEXT,
              legacy_labels=('Transit Number', 'transitNumber')),
        Field('institution_number', 'Institution Number', FieldType.TEXT,
              legacy_labels=('Institution Number', 'instNumber')),
        Field('account_number', 'Account Number', FieldType.TEXT,
              legacy_labels=('Account Number', 'accountNumber')),

        # ── Declaration and documents ──
        Field('signature', 'Signature', FieldType.SIGNATURE, required=True,
              legacy_labels=('Signature', 'signature')),
        Field('doc_transcripts', 'Transcripts', FieldType.FILE,
              legacy_labels=('Transcripts *', 'Transcripts')),
        Field('doc_letter_of_intent', 'Letter of Intent', FieldType.FILE,
              legacy_labels=('Letter of Intent *', 'Letter of Intent')),
        Field('doc_reference_letter', 'Reference Letter', FieldType.FILE,
              legacy_labels=('Reference Letter',)),
        Field('doc_status_card', 'Status Card', FieldType.FILE,
              legacy_labels=('Status Card *', 'Status Card')),
        Field('doc_void_cheque', 'Void Cheque', FieldType.FILE,
              legacy_labels=('Void Cheque *', 'Void Cheque')),
        Field('doc_extra', 'Extra Documents', FieldType.FILE,
              legacy_labels=('Extra Docs', 'Extra Documents')),
    ),
))
