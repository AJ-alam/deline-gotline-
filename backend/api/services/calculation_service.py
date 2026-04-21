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
        results = CalculationService._calculate_funding(submission)
        if not results:
            return None

        # Update submission total amount
        submission.amount = results['total']
        submission.save()

        # Create Payment records
        payment_items = [
            ('Tuition', results['tuition']['amount']),
            ('Living Allowance', results['living']['amount']),
            ('Books', results['books']['amount']),
        ]
        
        if results.get('extra_tuition') and results['extra_tuition']['amount'] > 0:
            payment_items.append(('Extra Tuition Cap Relief', results['extra_tuition']['amount']))

        created_payments = []
        for p_type, amount in payment_items:
            if amount > 0:
                payment = Payment.objects.create(
                    user=submission.student,
                    application_id=None, # Not used in new forms-first flow? 
                    # Note: We might want to link to Application if we reconcile models, 
                    # but for now we follow the FormSubmission logic.
                    amount=amount,
                    payment_type=p_type,
                    status=Payment.Status.PENDING # Status is Pending until Finance issues it
                )
                # If there's a link to submission needed on Payment, we should add it.
                # Adding a reference to submission in the save logic if possible
                created_payments.append(payment)
        
        return results

    @staticmethod
    def _calculate_funding(submission):
        # 1. Extract answers into predictable dict
        answers = {a.field.label.lower(): a.answer_text for a in submission.answers.all()}
        
        def get_val(keys):
            for k in keys:
                if k.lower() in answers:
                    return answers[k.lower()]
            return None

        stream = get_val(['bursaryStream', 'fundingStream']) or 'CDFN'
        enrollment = (get_val(['enrollmentType']) or 'full-time').lower()
        is_full_time = 'full' in enrollment
        has_deps = (get_val(['hasDependents']) or 'no').lower() == 'yes'
        requested_tuition = Decimal(get_val(['tuition']) or '0')
        
        # Duration fallback
        start_str = get_val(['semStart'])
        end_str = get_val(['semEnd'])
        months = 4
        if start_str and end_str:
            try:
                start = datetime.strptime(start_str, '%Y-%m-%d')
                end = datetime.strptime(end_str, '%Y-%m-%d')
                months = (end.year - start.year) * 12 + (end.month - start.month)
                if months <= 0: months = 4
            except:
                pass

        # 2. Logic Mapping (Standard Policy)
        # We use section keys that match the PolicySetting table refactored earlier
        living_section = 'dggr_living'
        if 'PSSSP' in stream or 'CDFN' in stream: living_section = 'psssp_living'
        elif 'UCEPP' in stream: living_section = 'ucepp_living'

        dep_key = 'with_dependents' if has_deps else 'no_dependents'
        load_key = 'fulltime' if is_full_time else 'parttime'
        field_key = f"{load_key}_{dep_key}"
        
        living_rate = CalculationService._get_policy_value(living_section, field_key)
        total_living = living_rate * Decimal(months)

        # 3. Tuition Caps
        tuition_section = 'dggr_tuition'
        if 'PSSSP' in stream or 'CDFN' in stream: tuition_section = 'psssp_tuition'
        elif 'UCEPP' in stream: tuition_section = 'ucepp_tuition'

        tuition_limit = 0
        if tuition_section in ['psssp_tuition', 'ucepp_tuition']:
             tuition_limit = CalculationService._get_policy_value(tuition_section, 'max_per_semester')
        else:
             tuition_limit = CalculationService._get_policy_value('dggr_tuition', f"{load_key}_per_semester")

        final_tuition = min(requested_tuition, tuition_limit) if requested_tuition > 0 else tuition_limit

        # 4. Extra Tuition (DGGR logic)
        extra_amount = Decimal(0)
        if 'DGGR' in stream and requested_tuition > tuition_limit:
            threshold = CalculationService._get_policy_value('dggr_extra_tuition', 'threshold_per_semester')
            if requested_tuition >= threshold:
                percent = CalculationService._get_policy_value('dggr_extra_tuition', 'max_percent_covered') / 100
                cap = CalculationService._get_policy_value('dggr_extra_tuition', 'max_per_semester')
                extra_amount = min((requested_tuition - tuition_limit) * percent, cap)

        # 5. Books
        books = Decimal(500) # Standard allowance

        return {
            'tuition': {'amount': final_tuition},
            'living': {'amount': total_living},
            'books': {'amount': books},
            'extra_tuition': {'amount': extra_amount},
            'total': final_tuition + total_living + books + extra_amount,
            'stream': stream
        }

    @staticmethod
    def _get_policy_value(section, field_key):
        try:
            return PolicySetting.objects.get(section=section, field_key=field_key).value
        except PolicySetting.DoesNotExist:
            return Decimal(0)
