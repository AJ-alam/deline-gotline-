from decimal import Decimal
from datetime import datetime
from api.models import PolicySetting, Payment
from forms.models import FormSubmission

class CalculationService:
    @staticmethod
    def calculate_and_pay(submission):
        """
        Calculates funding based on submission answers and policy settings,
        then creates individual payment records.
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

        # Create Payment records for each component (only if a student is linked)
        if submission.student:
            for p_type, amount in results.get('payment_items', []):
                if amount and amount > 0:
                    Payment.objects.create(
                        user=submission.student,
                        application_id=None,
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
        """Practicum & Placement Allowance"""
        award_amount = CalculationService._get_policy_value('dggr_rates', 'summer_practicum_award')
        if award_amount == 0:
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
        """Hardship Bursary"""
        answers, get_ans = CalculationService._get_answers_and_helper(submission)
        
        requested_str = get_ans(['amount requested', 'hardship amount', 'requested amount']) or '0'
        import re as _re
        requested_str = _re.sub(r'[^\d.]', '', str(requested_str)) or '0'
        requested = Decimal(requested_str)

        max_amount = CalculationService._get_policy_value('dggr_hardship', 'max_per_student')
        if max_amount == 0:
            max_amount = CalculationService._get_policy_value('dggr_hardship', 'max_per_incident')

        award = min(requested, max_amount) if requested > 0 else max_amount

        return {
            'award_type': 'Hardship Bursary',
            'total': award,
            'payment_items': [('Hardship Bursary', award)] if award > 0 else []
        }

    @staticmethod
    def _calculate_travel(submission):
        """Travel & Relocation Claim"""
        student = submission.student
        stream = getattr(student, 'primary_stream', '') if student else ''
        
        if 'PSSSP' in stream:
            has_deps = (getattr(student, 'num_dependents', 0) if student else 0) > 0
            if has_deps:
                max_amount = CalculationService._get_policy_value('psssp_travel', 'max_per_trip_with_dependents')
            else:
                max_amount = CalculationService._get_policy_value('psssp_travel', 'max_per_trip_no_dependents')
        else:
            max_amount = CalculationService._get_policy_value('dggr_travel', 'max_grant')

        return {
            'award_type': 'Travel Claim',
            'max_allowed': max_amount,
            'total': Decimal(0), # Manual review required
            'payment_items': []
        }

    @staticmethod
    def _calculate_funding(submission):
        """Standard funding (A, B, C)"""
        answers, get_val = CalculationService._get_answers_and_helper(submission)

        student = submission.student
        # Determine Funding Stream
        stream_val = get_val(['funding stream', 'bursarystream', 'stream', 'c-dfn psssp'])
        if not stream_val and student: stream_val = student.primary_stream
        stream = (stream_val or 'C-DFN PSSSP').upper()

        # Determine Enrollment Status
        enrollment_val = get_val(['enrollment status', 'enrollmenttype', 'course load'])
        if not enrollment_val and student: enrollment_val = student.enrollment_status
        enrollment = (enrollment_val or 'full-time').lower()
        is_full_time = 'full' in enrollment

        # Determine Dependents
        has_deps_val = get_val(['has dependents', 'dependents'])
        if has_deps_val is None and student: has_deps = student.num_dependents > 0
        else: has_deps = (has_deps_val or 'no').lower() in ('yes', 'true', '1')

        # Tuition
        tuition_str = get_val(['tuition amount', 'tuition']) or '0'
        import re as _re
        tuition_str = _re.sub(r'[^\d.]', '', str(tuition_str)) or '0'
        requested_tuition = Decimal(tuition_str)

        # Duration
        start_str = get_val(['semester start date', 'semstart', 'start date'])
        end_str = get_val(['semester end date', 'semend', 'end date'])
        months = 4
        if start_str and end_str:
            try:
                start = datetime.strptime(start_str, '%Y-%m-%d')
                end = datetime.strptime(end_str, '%Y-%m-%d')
                months = (end.year - start.year) * 12 + (end.month - start.month)
                if months <= 0: months = 4
            except Exception: pass

        # Rates (Unified with frontend)
        living_section = 'dggr_rates'
        if 'PSSSP' in stream: living_section = 'psssp_rates'
        elif 'UCEPP' in stream: living_section = 'ucepp_rates'

        dep_key = 'with_dep' if has_deps else 'no_dep'
        load_key = 'full' if is_full_time else 'part'
        field_key = f"living_{load_key}_{dep_key}"

        living_rate = CalculationService._get_policy_value(living_section, field_key)
        total_living = living_rate * Decimal(months)

        # Tuition cap
        tuition_limit = 0
        if living_section in ('psssp_rates', 'ucepp_rates'):
            tuition_limit = CalculationService._get_policy_value(living_section, 'tuition_cap')
        else:
            tuition_limit = CalculationService._get_policy_value('dggr_rates', f"tuition_{load_key}")

        final_tuition = min(requested_tuition, tuition_limit) if requested_tuition > 0 else tuition_limit

        # Extra relief
        extra_amount = Decimal(0)
        if 'DGGR' in stream and requested_tuition > tuition_limit:
            threshold = CalculationService._get_policy_value('dggr_extra_tuition', 'trigger_semester')
            if requested_tuition >= threshold:
                percent = CalculationService._get_policy_value('dggr_extra_tuition', 'relief_percent') / 100
                cap = CalculationService._get_policy_value('dggr_extra_tuition', 'relief_max_semester')
                extra_amount = min(requested_tuition * percent, cap) - final_tuition
                if extra_amount < 0: extra_amount = 0

        # Books
        books = CalculationService._get_policy_value('system_config', 'book_allowance')
        if books == 0: books = Decimal(500)

        total = final_tuition + total_living + books + extra_amount
        return {
            'total': total,
            'payment_items': [('Tuition', final_tuition), ('Living Allowance', total_living), ('Books', books)] + 
                             ([('Extra Tuition Cap Relief', extra_amount)] if extra_amount > 0 else [])
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
