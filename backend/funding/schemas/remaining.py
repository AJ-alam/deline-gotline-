"""The remaining application types.

Grouped in one module because each is small — a handful of questions on top of
the shared applicant and banking blocks. Splitting them into eight files would
be filing, not structure.
"""

from . import ApplicationSchema, Choice, Field, FieldType, register
from .admission import COURSE_LOAD, CREDENTIAL_LEVEL, SEMESTER
from .common import banking, signature, total_of

# Section names double as the headings a step is built from, so they read as
# instructions rather than as filing categories.
REVIEW = 'Review your information'
DOCUMENTS = 'Upload required documents'

# How many documents one application may carry. High enough that no honest
# claim meets it, low enough that a JSON column cannot be filled by one
# submission.
MAX_EVIDENCE = 20

# ── Continuing Funding (was Form C) ─────────────────────────────────────────
# A returning student's renewal, filed once a semester. Short by design: the
# admission application is already on file, so this reviews what is held rather
# than asking for it again. Everything on the first step arrives pre-filled from
# the most recent application (see api.views.prior_answers) and stays editable —
# the student is confirming it is still true, which is the only thing a renewal
# actually establishes.
#
# Three award inputs are deliberately *not* asked here:
#
#   semester_start / semester_end   the registrar confirms these on the
#   confirmed_tuition               enrolment verification, and tuition has
#                                   never been funded against a student's own
#                                   estimate.
#   registrar_email                 carried from the admission application by
#                                   workflow._request_enrolment_confirmation.
#
# Two are asked, because neither can be carried from a previous term without
# being wrong: which semester this renewal is for, and whether SFA is in play.
# SFA decides the funding stream (services/streams.py) and changes every term.
register(ApplicationSchema(
    slug='continuing_funding',
    # Says the three things a returning student needs before starting: how
    # often, what it depends on, and what happens next. It is the only prose
    # above the questions, so it carries all of it rather than being repeated
    # by a banner underneath saying the same thing again.
    summary=(
        'Submit once each semester to renew funding you already receive. Your '
        'first application must be on file. When this arrives we ask your '
        'registrar to confirm your enrolment.'
    ),
    fields=(
        Field('full_name', 'Full name', FieldType.TEXT, required=True,
              section=REVIEW),
        Field('beneficiary_number', 'Beneficiary #', FieldType.TEXT, required=True,
              help_text='Your DGG citizenship ID', section=REVIEW),
        Field('email', 'Contact email', FieldType.EMAIL, required=True,
              section=REVIEW),

        Field('institution_name', 'Institution', FieldType.TEXT, required=True,
              section=REVIEW),
        Field('program', 'Program', FieldType.TEXT, required=True, section=REVIEW),
        Field('course_load', 'Course load', FieldType.CHOICE, required=True,
              choices=COURSE_LOAD, section=REVIEW),
        # A count, not a yes/no. The engine reads `has_dependents`; it derives
        # that from this rather than asking the same thing twice.
        Field('dependent_count', 'Dependents', FieldType.INTEGER, required=True,
              section=REVIEW),

        Field('semester', 'Semester', FieldType.CHOICE, required=True,
              choices=SEMESTER,
              help_text='Which term this renewal is for.', section=REVIEW),
        Field('receives_sfa', 'Do you receive Student Financial Assistance?',
              FieldType.BOOLEAN, required=True,
              help_text='This decides which funding stream pays your award, so '
                        'it is asked every semester.',
              section=REVIEW),

        Field('doc_transcript', 'Latest transcripts', FieldType.FILE, required=True,
              section=DOCUMENTS),
        Field('doc_enrollment_confirmation', 'Enrollment confirmation',
              FieldType.FILE, required=True, section=DOCUMENTS),

        Field('declaration_confirmed', 'Confirm declaration', FieldType.CONFIRM,
              required=True,
              help_text='I declare that all information given on this '
                        'application is true and complete.',
              section='Declaration'),
        Field('signature', 'Student signature (full name)', FieldType.SIGNATURE,
              required=True, section='Declaration'),
    ),
))


# ── Appeal / Reconsideration (was Form D) ───────────────────────────────────
# Pays nothing directly; it asks for a decision to be revisited, and the office
# reads it as a committee rather than pricing it.
#
# It identifies the decision by the term it belongs to rather than by naming it:
# a student, a semester and an academic year is what the office looks the
# original up by. There is no field for "which decision", because on the paper
# form there is not one — see docs/PROJECT_STATE.md §8.
#
# An appeal is also the one application that can never be late (see
# services/deadlines): filing it after something has already gone wrong is what
# it is for.
CONTEXT = 'Student and academic context'
REASON = 'Reason for appeal'
EVIDENCE = 'Supporting evidence'

register(ApplicationSchema(
    slug='appeal',
    summary=(
        'Ask for a decision to be looked at again. Set out what happened, what '
        'you are asking for, and attach anything that supports it.'
    ),
    fields=(
        # `full_name` rather than a first and a last, because it arrives
        # pre-filled from the account — see services/prefill — and the student
        # is confirming who they are, not introducing themselves.
        Field('full_name', 'Student name', FieldType.TEXT, required=True,
              section=CONTEXT),
        Field('student_number', 'Student ID', FieldType.TEXT, required=True,
              help_text='Your number at the institution, not your beneficiary number.',
              section=CONTEXT),
        Field('institution_name', 'Educational institution', FieldType.TEXT,
              required=True, section=CONTEXT),
        # The term the decision belongs to. This is how the office finds the
        # original, and it is also what groups the appeal in the queue.
        Field('semester', 'Semester', FieldType.CHOICE, required=True,
              choices=SEMESTER, section=CONTEXT),
        Field('academic_year', 'Academic year', FieldType.TEXT, required=True,
              help_text='For example 2026-2027.', section=CONTEXT),

        Field('appeal_reason', 'Detailed reason for appeal', FieldType.LONG_TEXT,
              required=True,
              help_text='Explain why you believe the original decision was '
                        'incorrect and what outcome you are requesting.',
              section=REASON),
        Field('policy_reference', 'Policy reference', FieldType.TEXT,
              help_text='Optional. The section of the DGG Education Policy you '
                        'are relying on, if you know it.',
              section=REASON),

        # Several files, not one. An appeal is argued from a transcript *and* a
        # letter *and* a medical note; a single-file question meant the rest
        # were never seen by the people deciding it.
        Field('doc_supporting', 'Supporting evidence', FieldType.FILES,
              max_items=MAX_EVIDENCE,
              help_text='Transcripts, letters, medical notes — attach as many as '
                        'you need. PDF or photo.',
              section=EVIDENCE),

        Field('declaration_confirmed', 'I confirm the declaration',
              FieldType.CONFIRM, required=True,
              help_text='I confirm that the information provided is accurate and '
                        'complete. I understand that appeal decisions are '
                        'discretionary and subject to the DGG Education Policy.',
              section='Declaration'),
        Field('signature', 'Electronic signature', FieldType.SIGNATURE,
              required=True, section='Declaration'),
        Field('signed_on', 'Date', FieldType.DATE, required=True,
              defaults_to_today=True, section='Declaration'),
    ),
))


# ── Travel & Emergency Assistance (was Form E) ──────────────────────────────
# In `travel.py`. It outgrew this module when it gained a line-by-line expense
# breakdown, a total derived from it, and many-file receipts.


# ── Summer Student / Practicum Award (was Form F) ───────────────────────────
# The employer's report, and nothing else. The office supplied its content:
# who employed the student and who supervised them, when the placement ran,
# what the student did and how they did it, and the supervisor's signed
# declaration.
#
# It asks for no amount. That is not an omission — the award is a fixed rate the
# office publishes (`practicum:allowance`), so there is no figure for anyone to
# request and no gap between what was asked for and what is paid. The rule that
# prices it is `flat_rate` for the same reason; it was `capped_request` against
# an `amount_requested` this form no longer collects, which would have priced
# every claim at zero and said "No amount requested" while doing it.
#
# Two things here are not on the office's sketch, and both are here because the
# claim cannot be paid without them:
#
#   email     this award is claimable with no account, and a receipt, a request
#             for more information and a decision all have to reach someone.
#   banking   a guest has no account for finance to pay into, and details typed
#             into a form that does not ask for them do not exist. They are
#             private (see common.banking) and never land in `answers`.
#
EMPLOYER = 'Employer information'
STUDENT = 'Student information'
REPORT = 'Performance and roles'

register(ApplicationSchema(
    slug='practicum',
    summary=(
        'Completed by the employer or supervisor to verify your placement. '
        'This report is required to release the practicum or summer incentive '
        'award.'
    ),
    fields=(
        Field('employer_name', 'Organization name', FieldType.TEXT, required=True,
              section=EMPLOYER),
        Field('supervisor_title', 'Supervisor title', FieldType.TEXT, required=True,
              help_text='e.g. Director of Operations.', section=EMPLOYER),

        # Prefilled from the account when there is one — see services/prefill —
        # which is why it is the same key the renewal uses rather than a second
        # spelling of the same fact.
        Field('full_name', 'Student full name', FieldType.TEXT, required=True,
              section=STUDENT),
        Field('email', 'Student email', FieldType.EMAIL, required=True,
              help_text='Where the decision on this claim is sent.',
              section=STUDENT),
        Field('placement_start', 'Placement start date', FieldType.DATE, required=True,
              section=STUDENT),
        Field('placement_end', 'Placement end date', FieldType.DATE, required=True,
              section=STUDENT),

        Field('roles_and_responsibilities', 'Roles and responsibilities',
              FieldType.LONG_TEXT, required=True,
              help_text='The key tasks the student was responsible for.',
              section=REPORT),
        Field('performance_summary', 'Work performance summary',
              FieldType.LONG_TEXT, required=True,
              help_text="The student's performance, attendance and contributions.",
              section=REPORT),

        *banking(),

        # A CONFIRM rather than a BOOLEAN: "no, this is not accurate" is not an
        # answer a report can be filed with, and a required BOOLEAN accepts
        # False because False is not empty.
        # Worded as the office words it. This is the sentence the employer is
        # held to, so it is quoted rather than tidied.
        Field('employer_declaration', 'Employer declaration', FieldType.CONFIRM,
              required=True,
              help_text='The employer confirms that the information provided is '
                        'accurate and complete. Award is contingent on regular '
                        'attendance and satisfactory performance.',
              section='Declaration'),
        Field('supervisor_signature', 'Supervisor digital signature',
              FieldType.SIGNATURE, required=True,
              help_text="The supervisor's full legal name.",
              section='Declaration'),
        # Opens on today, because it is the day the supervisor is signing. They
        # can change it; nothing downstream reads it as authority — see
        # Field.defaults_to_today.
        Field('report_completed_on', 'Date', FieldType.DATE,
              required=True, defaults_to_today=True, section='Declaration'),
    ),
))


# ── Emergency Relief (was Form H) ───────────────────────────────────────────
# Short-term help when something unexpected puts a term at risk. `capped_request`
# pays what is asked for up to `emergency_relief:max_per_student`, so the amount
# is an award input and stays a validated MONEY figure.
#
# The office has not supplied a screen for this one, unlike the five forms
# reworked before it. What is asked is therefore unchanged; what has been added
# is the declaration every other form now carries — this had a signature and
# nothing above it to sign, which is a signature attesting to nothing. The
# wording below is provisional and is flagged in docs/PROJECT_STATE.md §8 for
# the office to replace with its own.
EMERGENCY_CONTACT = 'Your details'
EMERGENCY = 'The emergency'
EMERGENCY_DOCS = 'Supporting documents'

EMERGENCY_TYPE = (
    Choice('medical', 'Medical'),
    Choice('bereavement', 'Bereavement'),
    Choice('housing', 'Housing'),
    Choice('travel', 'Emergency travel'),
    Choice('other', 'Other'),
)

register(ApplicationSchema(
    slug='emergency_relief',
    summary=(
        'Short-term help when something unexpected puts your studies at risk. '
        'Tell us what happened and what it will cost; attach anything that '
        'supports it.'
    ),
    fields=(
        # Pre-filled from the account — see services/prefill. This cannot be
        # filed without one, so the student is confirming their details rather
        # than introducing themselves.
        Field('full_name', 'Full name', FieldType.TEXT, required=True,
              section=EMERGENCY_CONTACT),
        Field('email', 'Email', FieldType.EMAIL, required=True,
              help_text='Where the decision on this request is sent.',
              section=EMERGENCY_CONTACT),
        # Required here and optional everywhere else. This is the one form where
        # the office may need to reach somebody the same day, and an email
        # address is not a way to do that.
        Field('phone', 'Phone', FieldType.PHONE, required=True,
              help_text='A number you can be reached on today.',
              section=EMERGENCY_CONTACT),
        Field('beneficiary_number', 'Beneficiary number', FieldType.TEXT,
              section=EMERGENCY_CONTACT),

        Field('emergency_type', 'Nature of the emergency', FieldType.CHOICE,
              required=True, choices=EMERGENCY_TYPE, section=EMERGENCY),
        Field('emergency_description', 'What happened', FieldType.LONG_TEXT,
              required=True,
              help_text='What has happened, and how it is affecting your studies.',
              section=EMERGENCY),
        # The award input: `emergency_relief` pays this up to the published cap.
        Field('amount_requested', 'Amount requested', FieldType.MONEY, required=True,
              help_text='What you need. It is paid up to the published maximum.',
              section=EMERGENCY),

        # Plural, like every other supporting-document question: a medical note
        # and a landlord's letter are two papers, and a single-file field meant
        # the second was never seen.
        Field('doc_supporting', 'Supporting documents', FieldType.FILES,
              max_items=MAX_EVIDENCE,
              help_text='A note, a letter, a receipt — attach as many as you '
                        'have. Not required, and never a reason to delay asking.',
              section=EMERGENCY_DOCS),

        *banking(),

        Field('declaration_confirmed', 'I confirm the declaration',
              FieldType.CONFIRM, required=True,
              help_text='I declare that the information given here is true and '
                        'complete, and that the amount requested is for the '
                        'emergency described.',
              section='Declaration'),
        Field('signature', 'Signature', FieldType.SIGNATURE, required=True,
              section='Declaration'),
        Field('signed_on', 'Date', FieldType.DATE, required=True,
              defaults_to_today=True, section='Declaration'),
    ),
))


# ── Emergency Hardship Bursary (last resort) ────────────────────────────────
# A last resort, and the form says so twice: the applicant attests that they are
# still active in their programme before describing anything, and again that
# they have already tried the supports that come before this one.
#
# The amount is itemised and added up, exactly as a travel claim is, and for the
# same reason: `capped_request` pays `amount_requested` up to
# `hardship_bursary:max_per_student`, so a total asked for separately can
# disagree with the lines and the one nobody itemised is the one that is paid.
#
# The office's screen prints a $500 limit in its heading. That figure is not
# here, and not because it was missed — the cap is a policy rate the office
# edits without a deploy, and the seeded rate says $3,000. Two figures that
# agree only by habit is how a display string came to decide what somebody was
# paid. See docs/PROJECT_STATE.md §8.
HARDSHIP_STUDENT = 'Student information'
HARDSHIP_CASE = 'The emergency'
HARDSHIP_FUNDS = 'Fund breakdown'

MAX_HARDSHIP_LINES = 20

def hardship_total(answers: dict) -> dict:
    """What is being asked for: the breakdown, added up."""
    return {'amount_requested': total_of(answers.get('fund_breakdown'))}


register(ApplicationSchema(
    slug='hardship_bursary',
    summary=(
        'A last resort for a short-term emergency, once other supports have been '
        'tried. Set out what happened and itemise what you need.'
    ),
    derive=hardship_total,
    fields=(
        # Pre-filled from the account — see services/prefill.
        Field('full_name', 'Student full name', FieldType.TEXT, required=True,
              section=HARDSHIP_STUDENT),
        Field('beneficiary_number', 'Student ID / beneficiary number',
              FieldType.TEXT, section=HARDSHIP_STUDENT),
        Field('institution_name', 'Educational institution', FieldType.TEXT,
              required=True, section=HARDSHIP_STUDENT),
        # A CONFIRM, not a BOOLEAN. "No, I am not active in my programme" is not
        # an answer this bursary can be filed with, and a required BOOLEAN
        # accepts False because False is not empty. The office's screen shows it
        # ticked by default; it opens unticked here, because a box nobody read
        # is not an attestation.
        Field('active_and_compliant',
              'I am currently active in my program and compliant with reporting',
              FieldType.CONFIRM, required=True, section=HARDSHIP_STUDENT),

        Field('hardship_reason', 'Nature of hardship', FieldType.LONG_TEXT,
              required=True,
              help_text='What happened, when, and the immediate impact.',
              section=HARDSHIP_CASE),
        # The question that makes this a last resort rather than a first one.
        Field('other_supports_attempted', 'Other supports attempted',
              FieldType.LONG_TEXT, required=True,
              help_text='For example food banks, family support, campus '
                        'emergency funds. How have you tried to resolve this '
                        'already?',
              section=HARDSHIP_CASE),

        Field('fund_breakdown', 'Fund breakdown', FieldType.TABLE, required=True,
              max_items=MAX_HARDSHIP_LINES,
              help_text='One line per thing the money is for.',
              columns=(
                  Field('purpose', 'Expense / purpose', FieldType.TEXT, required=True),
                  Field('amount', 'Amount', FieldType.MONEY, required=True),
              ),
              section=HARDSHIP_FUNDS),
        Field('amount_requested', 'Total requested', FieldType.MONEY, computed=True,
              help_text='The breakdown added up. Paid up to the published '
                        'maximum, which the office sets.',
              section=HARDSHIP_FUNDS),

        Field('declaration_confirmed', 'I confirm the declaration',
              FieldType.CONFIRM, required=True,
              help_text='I confirm that the information provided is accurate and '
                        'complete. I understand that hardship support is '
                        'discretionary and considered a last resort.',
              section='Declaration'),
        Field('signature', 'Student digital signature', FieldType.SIGNATURE,
              required=True, section='Declaration'),
        Field('signed_on', 'Date', FieldType.DATE, required=True,
              defaults_to_today=True, section='Declaration'),
    ),
))


# ── Academic Achievement Scholarship ────────────────────────────────────────
# Recognition for a completed semester. The GPA decides the amount — the
# `academic_scholarship` rule is `tiered` on it — which is why it is a validated
# percentage and why the transcript behind it is required.
#
# The award bands are *not* stated here. The amounts and the thresholds are
# policy rates the office edits without a deploy (`academic_scholarship` in the
# policy screen), and quoting them in help text would put the same figure in two
# places that agree only by habit — which is how a display string came to decide
# what a student was paid. See docs/PROJECT_STATE.md §8.
#
# No banking block: unlike the practicum and graduation awards this cannot be
# claimed without an account, so finance already has somewhere to pay. Asking
# again would be a second set of details that can disagree with the first.
PROGRAM = 'Program information'
ACHIEVEMENT = 'Achievements'

# Where the transcript is coming from. A copy is attached either way — the GPA
# decides the amount, and an amount decided from an unverified figure is the
# same mistake as funding tuition against a student's own estimate.
TRANSCRIPT_STATUS = (
    Choice('uploading_now', 'Uploading now'),
    Choice('already_on_file', 'Already on file with the Education Department'),
    Choice('sent_by_institution', 'Sent directly by my institution'),
)

register(ApplicationSchema(
    slug='academic_scholarship',
    summary=(
        'Recognition for strong results in a completed semester. The award band '
        'follows from your final grade, so an official transcript has to come '
        'with it.'
    ),
    fields=(
        # Pre-filled from the account — see services/prefill. The student is
        # confirming who they are, not introducing themselves.
        Field('full_name', 'Student name', FieldType.TEXT, required=True,
              section=PROGRAM),
        Field('beneficiary_number', 'Student ID / beneficiary number',
              FieldType.TEXT, section=PROGRAM),
        Field('institution_name', 'Educational institution', FieldType.TEXT,
              required=True, section=PROGRAM),
        Field('semester', 'Qualifying semester', FieldType.CHOICE, required=True,
              choices=SEMESTER,
              help_text='The completed term these results are from.',
              section=PROGRAM),
        Field('academic_year', 'Academic year', FieldType.TEXT, required=True,
              help_text='For example 2026-2027.', section=PROGRAM),

        # The award tier is chosen from this, so it is a validated percentage
        # rather than free text: an answer matching no expected substring
        # silently paid the cheapest tier.
        Field('gpa_achieved', 'GPA achieved / final grade %', FieldType.PERCENT,
              required=True,
              help_text='As a percentage — for example 85. This decides which '
                        'achievement band applies.',
              section=ACHIEVEMENT),
        Field('transcripts_status', 'Transcripts status', FieldType.CHOICE,
              required=True, choices=TRANSCRIPT_STATUS,
              help_text='Attach a copy either way — the band is awarded against '
                        'the transcript, not against the figure typed above.',
              section=ACHIEVEMENT),
        Field('doc_transcript', 'Official transcript or grades letter',
              FieldType.FILE, required=True,
              help_text='Must show your full name and the name of the institution.',
              section=ACHIEVEMENT),

        Field('declaration_confirmed', 'I confirm the declaration',
              FieldType.CONFIRM, required=True,
              help_text='I confirm that the information provided is accurate. I '
                        'understand that eligibility for the scholarship is '
                        'subject to enrollment verification and meeting the DGG '
                        'Education Policy requirements.',
              section='Declaration'),
        Field('signature', 'Digital signature', FieldType.SIGNATURE,
              required=True, section='Declaration'),
        Field('signed_on', 'Date', FieldType.DATE, required=True,
              defaults_to_today=True, section='Declaration'),
    ),
))


# ── Enrollment Verification (was Form B) ────────────────────────────────────
# Completed by the institution's registrar, not the student. It confirms the
# facts the funding calculation depends on, which is why tuition is not awarded
# until it arrives.
# What the department reports against. The office's annual report splits
# students into university and college, and its own note says trades and
# upgrading are *subsets* of that split rather than alternatives to it — which
# is why these are two questions and not one.
INSTITUTION_TYPE = (
    Choice('university', 'University'),
    Choice('college', 'College or polytechnic'),
    Choice('trades_school', 'Trades school'),
    Choice('other', 'Other'),
)

PROGRAM_TYPE = (
    Choice('post_secondary', 'Post-secondary education'),
    Choice('trades', 'Trades'),
    Choice('upgrading', 'Upgrading'),
)


register(ApplicationSchema(
    slug='enrollment_verification',
    summary=(
        "Completed by the institution's registrar from an emailed link, not by you."
    ),
    apply_in_portal=False,
    fields=(
        # ── Student, carried over from the admission application ──
        # The registrar confirms these rather than retyping them; they arrive
        # pre-filled. Date of birth and SIN are deliberately absent: the
        # institution does not need either to confirm an enrolment, and sending
        # them would put a government identifier in an unencrypted mailbox.
        Field('student_name', 'Student name', FieldType.TEXT, required=True,
              section='Student'),
        Field('student_number', 'Student ID', FieldType.TEXT, section='Student'),
        Field('student_phone', 'Student phone', FieldType.PHONE, section='Student'),
        Field('student_email', 'Student email', FieldType.EMAIL, section='Student'),

        # ── Enrolment, confirmed by the institution ──
        Field('institution_name', 'Name of institution', FieldType.TEXT, required=True,
              section='Enrollment'),
        Field('program', "Name of student's program", FieldType.TEXT, required=True,
              section='Enrollment'),
        Field('is_enrolled', 'Is the student currently enrolled?', FieldType.BOOLEAN,
              required=True, section='Enrollment'),
        Field('course_load', "Student's course load", FieldType.CHOICE, required=True,
              choices=COURSE_LOAD, section='Enrollment'),
        Field('credential_level', 'Working towards', FieldType.CHOICE,
              choices=CREDENTIAL_LEVEL, section='Enrollment'),
        # The two classifications the department's annual report is built on.
        # Asked of the registrar rather than the student, and rather than being
        # guessed from the institution's name: "Northern Lights College" grants
        # degrees, and a report figure decided by matching words in a typed name
        # is a display string deciding what the office tells its funder — the
        # fault this system was rebuilt to remove.
        #
        # Not required. The registrar's answer governs tuition, and a
        # confirmation that cannot be submitted because of a reporting question
        # would hold up an award; an enrolment nobody classified is reported as
        # unclassified rather than refused.
        Field('institution_type', 'Type of institution', FieldType.CHOICE,
              choices=INSTITUTION_TYPE, section='Enrollment',
              help_text='Used for the department\'s annual reporting.'),
        Field('program_type', 'This program qualifies as', FieldType.CHOICE,
              choices=PROGRAM_TYPE, section='Enrollment',
              help_text='Used for the department\'s annual reporting.'),
        Field('semester', 'Semester enrolled', FieldType.CHOICE, choices=SEMESTER,
              section='Enrollment'),
        Field('program_year', 'Year of program', FieldType.INTEGER,
              help_text='Year ___ of a ___ year program.', section='Enrollment'),
        Field('program_length_years', 'Length of program in years', FieldType.INTEGER,
              section='Enrollment'),
        Field('semester_start', 'Semester start date', FieldType.DATE, required=True,
              section='Enrollment'),
        Field('semester_end', 'Semester end date', FieldType.DATE, required=True,
              section='Enrollment'),

        # ── Costs ──
        # The figure the award is actually based on.
        Field('confirmed_tuition', 'Tuition billed for this semester', FieldType.MONEY,
              required=True,
              help_text='Tuition is funded against this amount, not the estimate '
                        'given by the student.',
              section='Costs'),
        Field('books_amount', 'Books', FieldType.MONEY, section='Costs'),
        Field('other_fees_amount', 'Other fees', FieldType.MONEY, section='Costs'),
        Field('other_fees_explanation', 'What the other fees are for',
              FieldType.LONG_TEXT,
              help_text='Required if any other fees are entered.', section='Costs'),

        # ── Institution contact ──
        Field('institution_email', 'Institution email', FieldType.EMAIL,
              section='Institution'),
        Field('institution_phone', 'Institution phone', FieldType.PHONE,
              section='Institution'),

        # ── Declaration by the official ──
        Field('registrar_name', 'Name of official', FieldType.TEXT, required=True,
              section='Declaration'),
        Field('registrar_title', 'Title of official', FieldType.TEXT, required=True,
              section='Declaration'),
        Field('signature', 'Signature of official', FieldType.SIGNATURE, required=True,
              section='Declaration'),
        Field('completed_on', 'Date', FieldType.DATE, required=True,
              section='Declaration'),
        Field('registrar_notes', 'Additional notes', FieldType.LONG_TEXT,
              help_text='Discrepancies, inaccuracies, partial loads, anything the '
                        'office should know.',
              section='Declaration'),
    ),
))
