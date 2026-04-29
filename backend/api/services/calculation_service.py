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
        if 'form g' in form_title or 'graduation' in form_title:
            results = CalculationService._calculate_graduation_bursary(submission)
        elif 'form f' in form_title or 'practicum' in form_title or 'summer student' in form_title:
            results = CalculationService._calculate_practicum_award(submission)
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
        Form F — Practicum / Summer Student Award
        Fixed award amount from dggr_practicum_award policy.
        """
        award_amount = CalculationService._get_policy_value('dggr_practicum_award', 'award_amount')

        return {
            'award_type': 'Practicum / Summer Student Award',
            'total': award_amount,
            'payment_items': [
                ('Practicum Award', award_amount),
            ]
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

        stream = get_val(['bursaryStream', 'fundingStream', 'funding stream', 'bursary stream']) or 'CDFN'
        enrollment = (get_val(['enrollmentType', 'enrollment type', 'enrollment status']) or 'full-time').lower()
        is_full_time = 'full' in enrollment
        has_deps = (get_val(['hasDependents', 'has dependents', 'dependents']) or 'no').lower() in ('yes', 'true', '1')
        requested_tuition = Decimal(get_val(['tuition', 'tuition amount']) or '0')

        # Duration: calculate from semester start/end dates
        start_str = get_val(['semStart', 'sem start', 'semester start', 'start date'])
        end_str = get_val(['semEnd', 'sem end', 'semester end', 'end date'])
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
        if 'PSSSP' in stream or 'CDFN' in stream:
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
        if 'PSSSP' in stream or 'CDFN' in stream:
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

        # Books allowance (standard)
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
