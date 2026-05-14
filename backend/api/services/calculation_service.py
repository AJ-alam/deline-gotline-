from decimal import Decimal
from datetime import datetime
from api.models import PolicySetting, Payment, Application
from forms.models import FormSubmission


def _derive_form_type_code(form_title: str) -> str | None:
    """Map a form title to the Application.form_type code.

    Mirrors the title categories in api.services.form_service.pretty_form_title
    so payments stay in sync with the canonical form taxonomy. Returns None when
    the title doesn't fit any known bucket — caller then leaves application=None.
    """
    t = (form_title or '').lower()
    if any(x in t for x in ('form a', 'forma', 'psssp', 'c-dfn', 'new student', 'admission')):
        return 'FormA'
    if any(x in t for x in ('form b', 'formb', 'enrollment verif', 'enrolment verif', 'profile update')):
        return 'FormB'
    if any(x in t for x in ('form c', 'formc', 'continuing fund')):
        return 'FormC'
    if any(x in t for x in ('form d', 'formd', 'appeal', 'reconsider', 'specialized train')):
        return 'FormD'
    if any(x in t for x in ('form e', 'forme', 'travel', 'emergency fund')):
        return 'FormE'
    if any(x in t for x in ('form f', 'formf', 'practicum', 'placement')):
        return 'FormF'
    if any(x in t for x in ('form g', 'formg', 'graduation')):
        return 'FormG'
    if any(x in t for x in ('form h', 'formh', 'summer student')):
        return 'FormH'
    if 'hardship' in t:
        return 'FormHardship'
    if 'scholarship' in t:
        return 'FormScholarship'
    return None


def _resolve_or_create_application(submission):
    """Resolve the Application row tied to a submission, creating one if absent.

    The Payments dashboard groups by Application FK first, falling back to the
    raw FormSubmission. To make the linkage fully dynamic — so every payment
    always rolls up under the student's matching application — we ensure an
    Application row exists for the (student, form_type) pair the moment a
    payment is generated. Returns None for guest/anonymous submissions where
    no student is attached (Payments require a student anyway).
    """
    if not submission.student or not submission.form:
        return None
    code = _derive_form_type_code(submission.form.title)
    if not code:
        return None

    # Pull metadata from submission answers for richer Application context.
    answers = {
        (a.field.label or '').strip().lower(): a.answer_text
        for a in submission.answers.all() if a.field
    }
    def pick(*keys):
        for k in keys:
            for label, text in answers.items():
                if k in label and text:
                    return text
        return None

    semester = (pick('semester', 'term') or '').strip().lower() or None
    if semester and semester not in {'fall', 'winter', 'spring', 'summer'}:
        semester = None  # only keep recognised tokens; Application.Semester enforces a choice
    academic_year = pick('academic year', 'year of study')
    institution = pick('institution', 'school name', 'university', 'college')
    program = pick('program', 'major', 'field of study')

    # Reuse the most recent matching Application; otherwise auto-create one so
    # the Payment row has a stable FK target.
    app = (Application.objects
           .filter(student=submission.student, form_type=code)
           .order_by('-created_at')
           .first())
    if app:
        return app
    return Application.objects.create(
        student=submission.student,
        form_type=code,
        status=Application.Status.APPROVED,  # payment generation implies approval
        amount=submission.amount or 0,
        semester=semester,
        academic_year=academic_year,
        institution=institution,
        program=program,
    )

class CalculationService:
    @staticmethod
    def calculate_and_pay(submission, create_payments=True):
        """
        Calculates funding based on submission answers and policy settings,
        then optionally creates individual payment records.
        """
        # Clear cache to ensure fresh policy values
        CalculationService._policy_cache = {}
        
        form_title = submission.form.title.lower() if submission.form else ''

        # Route to the correct calculator based on form type
        if 'graduation bursary' in form_title:
            results = CalculationService._calculate_graduation_bursary(submission)
        elif 'practicum' in form_title or 'placement allowance' in form_title or 'summer student' in form_title:
            results = CalculationService._calculate_practicum_award(submission)
        elif 'scholarship' in form_title:
            results = CalculationService._calculate_scholarship(submission)
        elif 'hardship' in form_title:
            results = CalculationService._calculate_hardship(submission)
        elif 'travel' in form_title:
            results = CalculationService._calculate_travel(submission)
        else:
            results = CalculationService._calculate_funding(submission)

        if not results:
            return None

        # Update submission total amount
        submission.amount = results['total']
        submission.save()

        # Create Payment records for each component (only if a student is linked AND create_payments is True)
        if submission.student and create_payments:
            # Clear existing pending payments for this submission to avoid duplicates
            Payment.objects.filter(submission=submission, status=Payment.Status.PENDING).delete()

            # Resolve (or auto-create) the matching Application so every payment
            # is fully linked: user → application → submission. This is what makes
            # the Payments dashboard group correctly under the student's
            # application instead of falling back to "No application linked".
            application = _resolve_or_create_application(submission)

            for p_type, amount in results.get('payment_items', []):
                if amount and amount > 0:
                    Payment.objects.create(
                        user=submission.student,
                        submission=submission,
                        application=application,
                        amount=amount,
                        payment_type=p_type,
                        status=Payment.Status.PENDING
                    )

        return results

    @staticmethod
    def _get_answers_and_helper(submission):
        """Returns a dict of lowercase labels to text and a fuzzy getter helper."""
        answers = {a.field.label.lower(): a.answer_text for a in submission.answers.all() if a.field}
        
        def get_val(keys):
            # Try exact match first
            for k in keys:
                if k.lower() in answers: return answers[k.lower()]
            # Try fuzzy match (substring)
            for k in keys:
                for label, text in answers.items():
                    if k.lower() in label: return text
            return None
        
        return answers, get_val

    @staticmethod
    def _calculate_graduation_bursary(submission):
        """Form G — Graduation Bursary"""
        answers, get_ans = CalculationService._get_answers_and_helper(submission)
        
        # Use fuzzy search for credential
        credential = (get_ans(['credential', 'degree', 'program type', 'graduating from']) or '').lower()
        if not credential and submission.student:
            credential = (submission.student.program_credential or '').lower()

        # Map credential to policy field key
        credential_map = {
            'high school': 'high_school_diploma',
            'certificate': 'certificate',
            'trades': 'trades_certificate',
            'journeyperson': 'trades_journeyperson',
            'diploma': 'diploma',
            'pilot': 'pilot_licence',
            'degree': 'bachelors_degree',
            'bachelor': 'bachelors_degree',
            'master': 'masters_degree',
            'doctorate': 'doctorate',
            'phd': 'doctorate',
        }

        field_key = 'certificate'
        for key, val in credential_map.items():
            if key in credential:
                field_key = val
                break

        award_amount = CalculationService._get_policy_value('dggr_grad_bursary', field_key)
        if award_amount == 0:
            award_amount = CalculationService._get_policy_value('dggr_grad_bursary', 'certificate')

        return {
            'award_type': 'Graduation Bursary',
            'total': award_amount,
            'payment_items': [('Graduation Bursary', award_amount)]
        }

    @staticmethod
    def _calculate_practicum_award(submission):
        """Practicum & Placement Allowance — section: dggr_practicum_award, field: award_amount."""
        award_amount = CalculationService._get_policy_value('dggr_practicum_award', 'award_amount')

        return {
            'award_type': 'Practicum / Summer Student Award',
            'total': award_amount,
            'payment_items': [('Practicum Award', award_amount)]
        }

    @staticmethod
    def _calculate_scholarship(submission):
        """Academic Scholarship — Merit Award"""
        answers, get_ans = CalculationService._get_answers_and_helper(submission)
        
        gpa_str = get_ans(['gpa', 'grade average', 'academic standing']) or '0'
        import re as _re
        gpa_str = _re.sub(r'[^\d.]', '', str(gpa_str)) or '0'
        gpa = float(gpa_str)

        high_threshold = float(CalculationService._get_policy_value('dggr_academic_scholarship', 'high_threshold_percent') or 80)
        mid_lower = float(CalculationService._get_policy_value('dggr_academic_scholarship', 'mid_threshold_lower') or 70)
        high_award = CalculationService._get_policy_value('dggr_academic_scholarship', 'high_achievement_award')
        mid_award = CalculationService._get_policy_value('dggr_academic_scholarship', 'mid_achievement_award')

        award = 0
        if gpa >= high_threshold: award = high_award
        elif gpa >= mid_lower: award = mid_award

        return {
            'award_type': 'Academic Scholarship',
            'total': award,
            'payment_items': [('Academic Scholarship', award)] if award > 0 else []
        }

    @staticmethod
    def _calculate_hardship(submission):
        """Hardship Bursary — section: dggr_hardship, field: max_per_student."""
        answers, get_ans = CalculationService._get_answers_and_helper(submission)

        requested_str = get_ans(['amount requested', 'hardship amount', 'requested amount']) or '0'
        import re as _re
        requested_str = _re.sub(r'[^\d.]', '', str(requested_str)) or '0'
        requested = Decimal(requested_str)

        max_amount = CalculationService._get_policy_value('dggr_hardship', 'max_per_student')

        award = min(requested, max_amount) if requested > 0 else max_amount

        return {
            'award_type': 'Hardship Bursary',
            'total': award,
            'payment_items': [('Hardship Bursary', award)] if award > 0 else []
        }

    @staticmethod
    def _calculate_travel(submission):
        """Travel & Relocation Claim — sections: psssp_travel, psssp_graduation_travel.
        DGGR has no dedicated travel bursary in the seeded policy; we surface the PSSSP
        per-trip max as the displayed cap (manual director review still required)."""
        student = submission.student
        has_deps = (getattr(student, 'num_dependents', 0) if student else 0) > 0

        # Graduation travel uses its own section if the form title hints at it
        form_title = (submission.form.title.lower() if submission.form else '')
        if 'graduation' in form_title:
            max_amount = CalculationService._get_policy_value('psssp_graduation_travel', 'max_total')
        else:
            field_key = 'max_per_trip_with_dependents' if has_deps else 'max_per_trip_no_dependents'
            max_amount = CalculationService._get_policy_value('psssp_travel', field_key)

        return {
            'award_type': 'Travel Claim',
            'max_allowed': max_amount,
            'total': Decimal(0),  # Manual review required — finance enters actual amount
            'payment_items': []
        }

    @staticmethod
    def _calculate_funding(submission):
        """Standard funding (Form A/B/C). Reads from seeded policy sections:
          - Living:           {psssp|ucepp|dggr}_living . {fulltime|parttime}_{no|with}_dependents
          - Tuition (PSSSP):  psssp_tuition . max_per_semester
          - Tuition (UCEPP):  ucepp_tuition . max_per_semester
          - Tuition (DGGR):   dggr_tuition  . {fulltime|parttime}_per_semester
          - Extra (DGGR):     dggr_extra_tuition . {threshold_per_semester, max_percent_covered, max_per_semester}
          - Books:            system_config . book_allowance
        See `backend/api/management/commands/seed_policies.py` for canonical key names.
        """
        answers, get_val = CalculationService._get_answers_and_helper(submission)

        student = submission.student
        # Stream
        stream_val = get_val(['funding stream', 'bursarystream', 'stream', 'c-dfn psssp'])
        if not stream_val and student: stream_val = student.primary_stream
        stream = (stream_val or 'C-DFN PSSSP').upper()

        # Enrollment status
        enrollment_val = get_val(['enrollment status', 'enrollmenttype', 'course load'])
        if not enrollment_val and student: enrollment_val = student.enrollment_status
        enrollment = (enrollment_val or 'full-time').lower()
        is_full_time = 'full' in enrollment
        load_key = 'fulltime' if is_full_time else 'parttime'

        # Dependents
        has_deps_val = get_val(['has dependents', 'dependents'])
        if has_deps_val is None and student:
            has_deps = (student.num_dependents or 0) > 0
        else:
            has_deps = (has_deps_val or 'no').lower() in ('yes', 'true', '1')
        dep_key = 'with_dependents' if has_deps else 'no_dependents'

        # Requested tuition (from Form B confirmation, falls back to student form input)
        tuition_str = get_val(['tuition amount', 'confirmed tuition', 'tuition']) or '0'
        import re as _re
        tuition_str = _re.sub(r'[^\d.]', '', str(tuition_str)) or '0'
        requested_tuition = Decimal(tuition_str)

        # Semester duration in months (defaults to 4)
        start_str = get_val(['semester start date', 'semstart', 'start date'])
        end_str = get_val(['semester end date', 'semend', 'end date'])
        months = 4
        if start_str and end_str:
            try:
                start = datetime.strptime(start_str, '%Y-%m-%d')
                end = datetime.strptime(end_str, '%Y-%m-%d')
                months = (end.year - start.year) * 12 + (end.month - start.month)
                if months <= 0: months = 4
            except Exception:
                pass

        # ── Living allowance (per month × months) ──
        if 'PSSSP' in stream:
            living_section = 'psssp_living'
        elif 'UCEPP' in stream:
            living_section = 'ucepp_living'
        else:
            living_section = 'dggr_living'

        living_field = f"{load_key}_{dep_key}"  # e.g. fulltime_with_dependents
        living_rate = CalculationService._get_policy_value(living_section, living_field)
        total_living = living_rate * Decimal(months)

        # ── Tuition cap ──
        if 'PSSSP' in stream:
            tuition_limit = CalculationService._get_policy_value('psssp_tuition', 'max_per_semester')
        elif 'UCEPP' in stream:
            tuition_limit = CalculationService._get_policy_value('ucepp_tuition', 'max_per_semester')
        else:
            tuition_limit = CalculationService._get_policy_value('dggr_tuition', f"{load_key}_per_semester")

        final_tuition = min(requested_tuition, tuition_limit) if requested_tuition > 0 else tuition_limit

        # ── DGGR Extra Tuition Bursary (only when DGGR + tuition > threshold) ──
        extra_amount = Decimal(0)
        if 'DGGR' in stream and requested_tuition > 0:
            threshold = CalculationService._get_policy_value('dggr_extra_tuition', 'threshold_per_semester')
            if threshold > 0 and requested_tuition >= threshold:
                pct_raw = CalculationService._get_policy_value('dggr_extra_tuition', 'max_percent_covered')
                percent = pct_raw / Decimal(100) if pct_raw else Decimal(0)
                cap = CalculationService._get_policy_value('dggr_extra_tuition', 'max_per_semester')
                # Extra = (% of tuition − regular tuition top-up), capped, never negative.
                extra_amount = min(requested_tuition * percent, cap) - final_tuition
                if extra_amount < 0:
                    extra_amount = Decimal(0)

        # ── Books & supplies (per semester) ──
        books = CalculationService._get_policy_value('system_config', 'book_allowance')

        total = final_tuition + total_living + books + extra_amount
        return {
            'total': total,
            'stream': stream,
            'enrollment': 'Full-Time' if is_full_time else 'Part-Time',
            'has_dependents': has_deps,
            'months': months,
            'living_rate': living_rate,
            'tuition_cap': tuition_limit,
            'requested_tuition': requested_tuition,
            'payment_items': [
                ('Tuition', final_tuition),
                ('Living Allowance', total_living),
                ('Books', books),
            ] + ([('Extra Tuition Cap Relief', extra_amount)] if extra_amount > 0 else [])
        }

    _policy_cache = {}

    @staticmethod
    def _get_policy_value(section, field_key):
        cache_key = f"{section}:{field_key}"
        if cache_key in CalculationService._policy_cache:
            return CalculationService._policy_cache[cache_key]

        try:
            val = PolicySetting.objects.get(section=section, field_key=field_key).value
            CalculationService._policy_cache[cache_key] = val
            return val
        except PolicySetting.DoesNotExist:
            import logging
            logging.getLogger(__name__).warning("Missing policy setting: %s:%s. Falling back to 0.", section, field_key)
            return Decimal(0)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Error fetching policy %s:%s - %s", section, field_key, e)
            return Decimal(0)
