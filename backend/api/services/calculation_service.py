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
        Handles: standard funding forms, graduation bursary (Form G), practicum award (Form F).
        """
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

        # Create Payment records for each component
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
    def _calculate_graduation_bursary(submission):
        """
        Form G — Graduation Bursary
        Award amount is determined by credential type per dggr_grad_bursary policy.
        """
        answers = {
            a.field.label.lower(): a.answer_text
            for a in submission.answers.all()
            if a.field
        }

        credential = answers.get('credential', '').lower()

        # Map credential to policy field key
        credential_map = {
            'high school diploma':          'high_school_diploma',
            'high school':                  'high_school_diploma',
            'certificate':                  'certificate',
            'trades certificate':           'trades_certificate',
            'trades certificate of qualification': 'trades_certificate',
            'trades journeyperson':         'trades_journeyperson',
            'trades journeyperson licence': 'trades_journeyperson',
            'diploma':                      'diploma',
            'professional pilot licence':   'pilot_licence',
            'pilot licence':                'pilot_licence',
            'degree (bachelors)':           'bachelors_degree',
            'bachelors':                    'bachelors_degree',
            'bachelor':                     'bachelors_degree',
            'masters':                      'masters_degree',
            'master':                       'masters_degree',
            'doctorate':                    'doctorate',
            'phd':                          'doctorate',
        }

        field_key = None
        for key, val in credential_map.items():
            if key in credential:
                field_key = val
                break

        if not field_key:
            field_key = 'certificate'  # safe default

        award_amount = CalculationService._get_policy_value('dggr_grad_bursary', field_key)

        # Fallback: if policy not found, use certificate amount
        if award_amount == 0:
            award_amount = CalculationService._get_policy_value('dggr_grad_bursary', 'certificate')

        return {
            'award_type': 'Graduation Bursary',
            'credential': credential,
            'policy_key': field_key,
            'total': award_amount,
            'payment_items': [
                ('Graduation Bursary', award_amount),
            ]
        }

    @staticmethod
    def _calculate_practicum_award(submission):
        """
        Practicum & Placement Allowance — Fixed award from dggr_practicum_award policy.
        """
        award_amount = CalculationService._get_policy_value('dggr_practicum_award', 'award_amount')
        return {
            'award_type': 'Practicum / Summer Student Award',
            'total': award_amount,
            'payment_items': [('Practicum Award', award_amount)]
        }

    @staticmethod
    def _calculate_scholarship(submission):
        """
        Academic Scholarship — Merit Award
        Award based on GPA thresholds from dggr_academic_scholarship policy.
        """
        answers = {
            a.field.label.lower(): a.answer_text
            for a in submission.answers.all() if a.field
        }

        gpa_str = answers.get('gpa / grade average', '') or answers.get('gpa', '') or '0'
        import re as _re
        gpa_str = _re.sub(r'[^\d.]', '', str(gpa_str)) or '0'
        gpa = float(gpa_str)

        high_threshold = float(CalculationService._get_policy_value('dggr_academic_scholarship', 'high_threshold_percent'))
        mid_lower = float(CalculationService._get_policy_value('dggr_academic_scholarship', 'mid_threshold_lower'))
        high_award = CalculationService._get_policy_value('dggr_academic_scholarship', 'high_achievement_award')
        mid_award = CalculationService._get_policy_value('dggr_academic_scholarship', 'mid_achievement_award')

        if gpa >= high_threshold:
            award = high_award
            tier = f'High Achievement (≥{high_threshold}%)'
        elif gpa >= mid_lower:
            award = mid_award
            tier = f'Mid Achievement ({mid_lower}–{high_threshold - 0.01}%)'
        else:
            award = Decimal(0)
            tier = f'Below threshold ({gpa}% < {mid_lower}%)'

        return {
            'award_type': 'Academic Scholarship',
            'gpa': gpa,
            'tier': tier,
            'total': award,
            'payment_items': [('Academic Scholarship', award)] if award > 0 else []
        }

    @staticmethod
    def _calculate_hardship(submission):
        """
        Hardship Bursary — Capped at dggr_hardship.max_per_student policy.
        Amount is what the student requested, capped at the policy maximum.
        """
        answers = {
            a.field.label.lower(): a.answer_text
            for a in submission.answers.all() if a.field
        }

        import re as _re
        requested_str = answers.get('amount requested', '0') or '0'
        requested_str = _re.sub(r'[^\d.]', '', str(requested_str)) or '0'
        requested = Decimal(requested_str)

        max_amount = CalculationService._get_policy_value('dggr_hardship', 'max_per_student')
        if max_amount == 0:
            max_amount = CalculationService._get_policy_value('dggr_hardship', 'max_per_incident')

        award = min(requested, max_amount) if requested > 0 else max_amount

        return {
            'award_type': 'Hardship Bursary',
            'requested': requested,
            'max_allowed': max_amount,
            'total': award,
            'payment_items': [('Hardship Bursary', award)] if award > 0 else []
        }

    @staticmethod
    def _calculate_travel(submission):
        """
        Travel & Relocation Claim — Capped at psssp_travel or dggr_travel policy.
        Amount is manually reviewed; we set a preliminary cap here.
        """
        answers = {
            a.field.label.lower(): a.answer_text
            for a in submission.answers.all() if a.field
        }

        # Determine stream from student profile
        student = submission.student
        stream = getattr(student, 'primary_stream', '') or ''

        if 'PSSSP' in stream or 'C-DFN' in stream:
            has_deps = (getattr(student, 'num_dependents', 0) or 0) > 0
            if has_deps:
                max_amount = CalculationService._get_policy_value('psssp_travel', 'max_per_trip_with_dependents')
            else:
                max_amount = CalculationService._get_policy_value('psssp_travel', 'max_per_trip_no_dependents')
        else:
            max_amount = CalculationService._get_policy_value('dggr_travel', 'max_grant')

        # Travel claims are manually reviewed — set amount to 0 pending review
        # Staff will set the actual amount during review
        return {
            'award_type': 'Travel Claim',
            'max_allowed': max_amount,
            'total': Decimal(0),  # Set to 0 — staff sets actual amount during review
            'payment_items': []
        }

    @staticmethod
    def _calculate_funding(submission):
        """
        Standard funding calculation for PSSSP / UCEPP / DGGR forms.
        Covers tuition, living allowance, books, and extra tuition cap relief.
        """
        answers = {a.field.label.lower(): a.answer_text for a in submission.answers.all()}

        def get_val(keys):
            for k in keys:
                if k.lower() in answers:
                    return answers[k.lower()]
            return None

        stream = get_val([
            'funding stream', 'bursarystream', 'fundingstream',
            'bursary stream', 'stream', 'c-dfn psssp'
        ]) or 'C-DFN PSSSP'

        enrollment = (get_val([
            'enrollment status', 'enrollmenttype', 'enrollment type',
            'course load', 'courseload'
        ]) or 'full-time').lower()
        is_full_time = 'full' in enrollment

        has_deps_val = (get_val([
            'has dependents', 'hasdependents', 'dependents'
        ]) or 'no').lower()
        has_deps = has_deps_val in ('yes', 'true', '1')

        # Tuition: try multiple label variants
        tuition_str = get_val(['tuition amount', 'tuition', 'tuitionamount']) or '0'
        # Strip non-numeric chars except decimal point
        import re as _re
        tuition_str = _re.sub(r'[^\d.]', '', str(tuition_str)) or '0'
        requested_tuition = Decimal(tuition_str)

        # Duration: calculate from semester start/end dates
        start_str = get_val([
            'semester start date', 'semstart', 'sem start',
            'semester start', 'start date', 'placement start date'
        ])
        end_str = get_val([
            'semester end date', 'semend', 'sem end',
            'semester end', 'end date', 'placement end date'
        ])
        months = 4  # default one semester
        if start_str and end_str:
            try:
                start = datetime.strptime(start_str, '%Y-%m-%d')
                end = datetime.strptime(end_str, '%Y-%m-%d')
                months = (end.year - start.year) * 12 + (end.month - start.month)
                if months <= 0:
                    months = 4
            except Exception:
                pass

        # Living allowance section
        living_section = 'dggr_living'
        if 'PSSSP' in stream or 'CDFN' in stream or 'C-DFN' in stream:
            living_section = 'psssp_living'
        elif 'UCEPP' in stream:
            living_section = 'ucepp_living'

        dep_key = 'with_dependents' if has_deps else 'no_dependents'
        load_key = 'fulltime' if is_full_time else 'parttime'
        field_key = f"{load_key}_{dep_key}"

        living_rate = CalculationService._get_policy_value(living_section, field_key)
        total_living = living_rate * Decimal(months)

        # Tuition cap
        tuition_section = 'dggr_tuition'
        if 'PSSSP' in stream or 'CDFN' in stream or 'C-DFN' in stream:
            tuition_section = 'psssp_tuition'
        elif 'UCEPP' in stream:
            tuition_section = 'ucepp_tuition'

        if tuition_section in ('psssp_tuition', 'ucepp_tuition'):
            tuition_limit = CalculationService._get_policy_value(tuition_section, 'max_per_semester')
        else:
            tuition_limit = CalculationService._get_policy_value('dggr_tuition', f"{load_key}_per_semester")

        final_tuition = min(requested_tuition, tuition_limit) if requested_tuition > 0 else tuition_limit

        # Extra tuition cap relief (DGGR only)
        extra_amount = Decimal(0)
        if 'DGGR' in stream and requested_tuition > tuition_limit:
            threshold = CalculationService._get_policy_value('dggr_extra_tuition', 'threshold_per_semester')
            if requested_tuition >= threshold:
                percent = CalculationService._get_policy_value('dggr_extra_tuition', 'max_percent_covered') / 100
                cap = CalculationService._get_policy_value('dggr_extra_tuition', 'max_per_semester')
                extra_amount = min((requested_tuition - tuition_limit) * percent, cap)

        # Books allowance — from policy (system_config.book_allowance), fallback $500
        books = CalculationService._get_policy_value('system_config', 'book_allowance')
        if books == 0:
            books = Decimal(500)

        total = final_tuition + total_living + books + extra_amount

        payment_items = [
            ('Tuition', final_tuition),
            ('Living Allowance', total_living),
            ('Books', books),
        ]
        if extra_amount > 0:
            payment_items.append(('Extra Tuition Cap Relief', extra_amount))

        return {
            'tuition': {'amount': final_tuition},
            'living': {'amount': total_living},
            'books': {'amount': books},
            'extra_tuition': {'amount': extra_amount},
            'total': total,
            'stream': stream,
            'payment_items': payment_items,
        }

    @staticmethod
    def _get_policy_value(section, field_key):
        try:
            return PolicySetting.objects.get(section=section, field_key=field_key).value
        except PolicySetting.DoesNotExist:
            return Decimal(0)
