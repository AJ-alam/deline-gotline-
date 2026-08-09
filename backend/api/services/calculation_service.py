import threading
from decimal import Decimal
from datetime import datetime
from api.models import PolicySetting, Payment
from forms.models import FormSubmission


class MissingPolicySettingError(Exception):
    """Raised when an award would be committed using policy settings that do not exist.

    Without this, an unseeded or mistyped PolicySetting produced a $0.00 award that
    looked exactly like a legitimate calculation, and the payment was written anyway.
    """

    def __init__(self, missing):
        self.missing = list(missing)
        super().__init__(
            "Cannot compute award — missing policy settings: " + ", ".join(self.missing)
        )


class CalculationService:
    @staticmethod
    def calculate_and_pay(submission, create_payments=True, commit=True):
        """
        Calculates funding based on submission answers and policy settings,
        then optionally creates individual payment records.

        commit=False computes and returns the result without touching the
        database — used by the staff breakdown preview.
        """
        # §4.3/§7.5: lock effective-date to the submission's submitted_at so
        # policy changes made after the submission use the rate that was in effect
        # when the student applied. Scoped to this thread and always torn down, so
        # a concurrent calculation cannot observe or overwrite this submission's date.
        CalculationService._begin_calculation(
            submission.submitted_at.date() if submission.submitted_at else None
        )
        try:
            return CalculationService._calculate_and_pay(
                submission, create_payments=create_payments, commit=commit
            )
        finally:
            CalculationService._end_calculation()

    @staticmethod
    def _calculate_and_pay(submission, create_payments=True, commit=True):
        """Body of calculate_and_pay. Must only be called with calculation state
        already established by _begin_calculation."""
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

        if not commit:
            # Preview path: hand the misconfiguration to the caller so staff see
            # "policy not configured" rather than a confident $0.00 breakdown.
            results['missing_policy_settings'] = list(CalculationService.get_missing_policies())
            return results

        # Never persist an amount derived from settings that don't exist. The award
        # would read as a real $0.00 decision and a payment row would be written for it.
        missing = CalculationService.get_missing_policies()
        if missing:
            raise MissingPolicySettingError(missing)

        # Update submission total amount
        submission.amount = results['total']
        submission.save()

        # Create Payment records for each component (only if a student is linked AND create_payments is True)
        # §4.5: NO advance payments — only create payments after the application deadline
        # for the semester has passed (i.e., the payment period has begun).
        if submission.student and create_payments:
            # Clear existing pending payments for this submission to avoid duplicates
            Payment.objects.filter(submission=submission, status=Payment.Status.PENDING).delete()

            # The submission is the application. Generating a payment used to also
            # mint a shadow Application row (already marked approved) purely to give
            # Payment.application an FK target — which made the same application
            # appear twice on the staff dashboard, with two independently mutable
            # statuses, and let it be "approved" down a path that pays nobody and
            # notifies nobody. Payments link to the submission and nothing else.
            for p_type, amount in results.get('payment_items', []):
                if amount and amount > 0:
                    Payment.objects.create(
                        user=submission.student,
                        submission=submission,
                        amount=amount,
                        payment_type=p_type,
                        status=Payment.Status.PENDING
                    )

        return results

    @staticmethod
    def _to_decimal(raw):
        """Pull a Decimal out of free-text money/number answers ('$5,200.00' → 5200.00)."""
        import re as _re
        if raw is None:
            return None
        cleaned = _re.sub(r'[^\d.]', '', str(raw))
        if not cleaned or cleaned == '.':
            return None
        try:
            return Decimal(cleaned)
        except Exception:
            return None

    @staticmethod
    def _resolve_dependents(get_val, student):
        """
        True when the student has at least one dependent.

        Answers arrive in two shapes: a yes/no ('Has Dependents') and a count
        ('Number of Dependents' = '2'). Reading a count as a yes/no is what made
        students with dependents fall onto the no-dependent rate.
        """
        raw = get_val(['has dependents', 'dependents'])
        if raw is not None:
            text = str(raw).strip().lower()
            if text in ('yes', 'true', 'y', '1'):
                return True
            if text in ('no', 'false', 'n', '0', ''):
                # A plain '0' count and an explicit 'no' agree — but keep looking
                # at the profile in case the form field was left blank.
                if text != '':
                    return False
            count = CalculationService._to_decimal(text)
            if count is not None:
                return count > 0
        return (getattr(student, 'num_dependents', 0) or 0) > 0

    @staticmethod
    def _resolve_full_time(get_val, student):
        """
        True for a full-time course load.

        'Course Load' holds a percentage ('100'), not the words full/part-time, so
        a substring test for 'full' silently demoted those students to part-time
        rates. Percentages are compared against the policy threshold instead.
        """
        raw = get_val(['enrollment status', 'enrollmenttype', 'enrollment type'])
        if raw is None and student:
            raw = student.enrollment_status
        text = str(raw or '').strip().lower()
        if 'full' in text:
            return True
        if 'part' in text:
            return False

        load = CalculationService._to_decimal(get_val(['course load', 'load percent']))
        if load is None and student:
            load = CalculationService._to_decimal(getattr(student, 'course_load', None))
        if load is not None:
            threshold = CalculationService._get_policy_value(
                'eligibility_rules', 'fulltime_min_load_percent'
            ) or Decimal(60)
            return load >= threshold

        return True  # nothing said otherwise — full-time is the common case

    @staticmethod
    def _count_months(start_str, end_str, default=4):
        """
        Months of study, counting every month the student is in class.

        Sept 3 → Dec 20 is four monthly living payments (Sept, Oct, Nov, Dec),
        not three: the old elapsed-months arithmetic dropped the final partial
        month and left every standard semester one payment short.
        """
        if not start_str or not end_str:
            return default
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
            try:
                start = datetime.strptime(str(start_str).strip(), fmt)
                end = datetime.strptime(str(end_str).strip(), fmt)
            except ValueError:
                continue
            months = (end.year - start.year) * 12 + (end.month - start.month) + 1
            return months if months > 0 else default
        return default

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
        """Travel & Relocation Claim — PSSSP only (§4.3).

        §4.3 rules enforced:
        - Regular travel: max 2 trips/year. Returns 0 if student already used 2 this year.
        - Graduation travel: one-time, only for 2+ year programs. Returns 0 if already received.
        """
        student = submission.student
        has_deps = (getattr(student, 'num_dependents', 0) if student else 0) > 0

        form_title = (submission.form.title.lower() if submission.form else '')
        is_graduation = 'graduation' in form_title

        if is_graduation:
            # One-time only — check if student already received it
            if student:
                already_received = Payment.objects.filter(
                    user=student,
                    payment_type__icontains='Graduation Travel',
                ).exclude(submission=submission).exists()
                if already_received:
                    return {
                        'award_type': 'Graduation Travel (already received)',
                        'max_allowed': Decimal(0),
                        'total': Decimal(0),
                        'payment_items': [],
                        'ineligible_reason': 'Graduation Travel Bursary is a one-time award and has already been received.',
                    }
            max_amount = CalculationService._get_policy_value('psssp_graduation_travel', 'max_total')
        else:
            # Regular travel: max 2 trips per fiscal year
            if student:
                from django.utils import timezone as _tz
                from datetime import date as _date
                today = _tz.now().date()
                fy_start = _date(today.year if today.month >= 4 else today.year - 1, 4, 1)
                trips_used = Payment.objects.filter(
                    user=student,
                    payment_type__icontains='Travel',
                    date_issued__date__gte=fy_start,
                ).exclude(submission=submission).count()
                if trips_used >= 2:
                    return {
                        'award_type': 'Travel Bursary (max trips reached)',
                        'max_allowed': Decimal(0),
                        'total': Decimal(0),
                        'payment_items': [],
                        'ineligible_reason': 'Maximum 2 travel bursary trips per year already used.',
                    }
            field_key = 'max_per_trip_with_dependents' if has_deps else 'max_per_trip_no_dependents'
            max_amount = CalculationService._get_policy_value('psssp_travel', field_key)

        return {
            'award_type': 'Graduation Travel Claim' if is_graduation else 'Travel Claim',
            'max_allowed': max_amount,
            'total': Decimal(0),  # Reimbursement only — finance enters actual amount after travel
            'payment_items': [],
        }

    @staticmethod
    def _calculate_funding(submission):
        """Standard funding (Form A/B/C).

        §4.1 STACKING: if a student qualifies for both a C-DFN stream AND DGGR,
        both are calculated and combined. DGGR supplements C-DFN — it does not
        replace it. Living allowances are additive (each stream has its own rate).

        Policy sections used:
          - Living:           {psssp|ucepp|dggr}_living . {fulltime|parttime}_{no|with}_dependents
          - Tuition (PSSSP):  psssp_tuition . max_per_semester
          - Tuition (UCEPP):  ucepp_tuition . max_per_semester
          - Tuition (DGGR):   dggr_tuition  . {fulltime|parttime}_per_semester
          - Extra (DGGR):     dggr_extra_tuition . {threshold_per_semester, max_percent_covered, max_per_semester}
          - Books:            system_config . book_allowance
        """
        answers, get_val = CalculationService._get_answers_and_helper(submission)

        student = submission.student
        # Stream — may be comma-separated for stacking e.g. "C-DFN PSSSP, DGGR"
        stream_val = get_val(['funding stream', 'bursarystream', 'stream', 'c-dfn psssp'])
        if not stream_val and student: stream_val = student.primary_stream
        stream_raw = (stream_val or 'C-DFN PSSSP').upper()

        # Determine which streams apply
        has_psssp = 'PSSSP' in stream_raw
        has_ucepp = 'UCEPP' in stream_raw
        has_dggr  = 'DGGR'  in stream_raw
        # If nothing matched, default to PSSSP
        if not any([has_psssp, has_ucepp, has_dggr]):
            has_psssp = True

        # SFA active? — C-DFN living + tuition not available to SFA recipients
        profile = getattr(student, 'profile', None) if student else None
        is_sfa = getattr(profile, 'is_sfa_active', False) if profile else False

        # Enrollment status and dependents
        is_full_time = CalculationService._resolve_full_time(get_val, student)
        load_key = 'fulltime' if is_full_time else 'parttime'
        has_deps = CalculationService._resolve_dependents(get_val, student)
        dep_key = 'with_dependents' if has_deps else 'no_dependents'

        # Tuition actually billed — from the registrar's Form B confirmation where
        # available, otherwise what the student entered. None means "not yet known":
        # no tuition is awarded until a figure is confirmed, because assuming the
        # cap over-pays every student whose real tuition is lower.
        actual_tuition = CalculationService._to_decimal(
            get_val(['confirmed tuition', 'tuition amount', 'tuition'])
        )
        tuition_confirmed = actual_tuition is not None and actual_tuition > 0
        unfunded_tuition = actual_tuition if tuition_confirmed else Decimal(0)

        months = CalculationService._count_months(
            get_val(['semester start date', 'semstart', 'start date']),
            get_val(['semester end date', 'semend', 'end date']),
        )

        living_field = f"{load_key}_{dep_key}"  # e.g. fulltime_with_dependents
        payment_items = []
        breakdown = []
        total_tuition = Decimal(0)
        total_living = Decimal(0)
        streams_applied = []

        def add(category, stream, amount, rule):
            """Record a funded line for the payment run and the staff breakdown."""
            breakdown.append({
                'category': category, 'stream': stream,
                'amount': amount, 'rule': rule,
            })
            payment_items.append((category, amount))

        # Tuition is allocated stream by stream against the real bill, so no two
        # streams fund the same dollar and nobody is funded above what they owe.
        def award_tuition(category, stream, cap, rule):
            nonlocal unfunded_tuition, total_tuition
            if not tuition_confirmed:
                breakdown.append({
                    'category': category, 'stream': stream, 'amount': Decimal(0),
                    'rule': 'Awaiting confirmed tuition (Form B) — nothing awarded yet',
                })
                return Decimal(0)
            granted = min(unfunded_tuition, cap)
            if granted <= 0:
                breakdown.append({
                    'category': category, 'stream': stream, 'amount': Decimal(0),
                    'rule': 'Tuition already fully funded by another stream',
                })
                return Decimal(0)
            unfunded_tuition -= granted
            total_tuition += granted
            add(category, stream, granted, rule)
            return granted

        # ── C-DFN PSSSP ────────────────────────────────────────────────────────
        if has_psssp and not is_sfa:
            psssp_cap = CalculationService._get_policy_value('psssp_tuition', 'max_per_semester')
            award_tuition('Tuition (PSSSP)', 'PSSSP', psssp_cap, f"PSSSP cap ${psssp_cap} per semester")
            psssp_living_rate = CalculationService._get_policy_value('psssp_living', living_field)
            psssp_living = psssp_living_rate * Decimal(months)
            add('Living Allowance (PSSSP)', 'PSSSP', psssp_living,
                f"${psssp_living_rate}/month × {months} months")
            total_living += psssp_living
            streams_applied.append('PSSSP')

        # ── C-DFN UCEPP ────────────────────────────────────────────────────────
        if has_ucepp and not is_sfa:
            ucepp_cap = CalculationService._get_policy_value('ucepp_tuition', 'max_per_semester')
            award_tuition('Tuition (UCEPP)', 'UCEPP', ucepp_cap, f"UCEPP cap ${ucepp_cap} per semester")
            ucepp_living_rate = CalculationService._get_policy_value('ucepp_living', living_field)
            ucepp_living = ucepp_living_rate * Decimal(months)
            add('Living Allowance (UCEPP)', 'UCEPP', ucepp_living,
                f"${ucepp_living_rate}/month × {months} months")
            total_living += ucepp_living
            streams_applied.append('UCEPP')

        # ── DGGR ────────────────────────────────────────────────────────────────
        if has_dggr:
            dggr_rate = CalculationService._get_policy_value('dggr_tuition', f"{load_key}_per_semester")
            # DGGR tops up what the C-DFN caps left unpaid, never more than its
            # own rate and never more than the tuition still owing.
            dggr_tuition = award_tuition(
                'Tuition Top-Up (DGGR)', 'DGGR', dggr_rate,
                f"Tops up unfunded tuition, max ${dggr_rate} ({'full' if is_full_time else 'part'}-time)",
            )
            dggr_living_rate = CalculationService._get_policy_value('dggr_living', living_field)
            dggr_living = dggr_living_rate * Decimal(months)
            add('Living Allowance (DGGR)', 'DGGR', dggr_living,
                f"${dggr_living_rate}/month × {months} months")
            total_living += dggr_living
            streams_applied.append('DGGR')

            # ── DGGR Extra Tuition Bursary ──────────────────────────────────────
            # §4.3: only when tuition exceeds the threshold; inclusive of (not
            # additive to) the regular DGGR bursary; subject to the per-student
            # annual cap and the pool cap shared by all students.
            if tuition_confirmed and unfunded_tuition > 0:
                threshold = CalculationService._get_policy_value('dggr_extra_tuition', 'threshold_per_semester')
                if threshold > 0 and actual_tuition > threshold:
                    pct_raw = CalculationService._get_policy_value('dggr_extra_tuition', 'max_percent_covered')
                    percent = pct_raw / Decimal(100) if pct_raw else Decimal(0)
                    cap = CalculationService._get_policy_value('dggr_extra_tuition', 'max_per_semester')
                    total_inclusive = min(actual_tuition * percent, cap)
                    # "Inclusive" means the extra is the DIFFERENCE above regular DGGR
                    extra_before_caps = max(Decimal(0), total_inclusive - dggr_tuition)
                    extra_before_caps = min(extra_before_caps, unfunded_tuition)

                    if extra_before_caps > 0:
                        extra_amount = CalculationService._apply_extra_tuition_annual_cap(
                            extra_before_caps, submission
                        )
                        extra_amount = CalculationService._apply_extra_tuition_pool_cap(
                            extra_amount, submission
                        )
                        if extra_amount > 0:
                            unfunded_tuition -= extra_amount
                            total_tuition += extra_amount
                            add('Extra Tuition Cap Relief', 'DGGR', extra_amount,
                                f"{pct_raw}% of ${actual_tuition}, capped at ${cap} and inclusive of the DGGR top-up")

        # ── Single-stream fallback for backward compat (no DGGR, no C-DFN chosen) ──
        # Only when no stream was *identified*. A student whose streams were all
        # excluded because they receive SFA must not land here: the fallback used
        # to hand them the full PSSSP award, undoing the exclusion entirely.
        excluded_by_sfa = is_sfa and (has_psssp or has_ucepp)
        if not streams_applied and excluded_by_sfa:
            return {
                'total': Decimal(0),
                'stream': 'None — SFA active',
                'enrollment': 'Full-Time' if is_full_time else 'Part-Time',
                'has_dependents': has_deps,
                'months': months,
                'living_rate': Decimal(0),
                'tuition_cap': Decimal(0),
                'requested_tuition': actual_tuition or Decimal(0),
                'tuition_confirmed': tuition_confirmed,
                'unfunded_tuition': unfunded_tuition,
                'total_tuition': Decimal(0),
                'total_living': Decimal(0),
                'ineligible_reason': (
                    'Student receives GNWT Student Financial Assistance, so C-DFN '
                    'PSSSP/UCEPP funding does not apply and no DGGR stream was found.'
                ),
                'breakdown': [],
                'payment_items': [],
            }

        if not streams_applied:
            # Default to PSSSP
            tuition_limit = CalculationService._get_policy_value('psssp_tuition', 'max_per_semester')
            award_tuition('Tuition', 'PSSSP', tuition_limit, f"PSSSP cap ${tuition_limit} per semester")
            living_rate = CalculationService._get_policy_value('psssp_living', living_field)
            fallback_living = living_rate * Decimal(months)
            add('Living Allowance', 'PSSSP', fallback_living,
                f"${living_rate}/month × {months} months")
            total_living += fallback_living
            streams_applied = ['PSSSP (default)']

        # ── Books & supplies (per semester, once regardless of streams) ──
        books = CalculationService._get_policy_value('system_config', 'book_allowance')
        if books > 0:
            add('Books', None, books, 'Books & supplies allowance per semester')

        total = total_tuition + total_living + books
        # Deduplicate living_rate for return (use primary stream)
        primary_section = 'psssp_living' if has_psssp else ('ucepp_living' if has_ucepp else 'dggr_living')
        living_rate = CalculationService._get_policy_value(primary_section, living_field)
        primary_tuition_limit = (
            CalculationService._get_policy_value('psssp_tuition', 'max_per_semester') if has_psssp else
            CalculationService._get_policy_value('ucepp_tuition', 'max_per_semester') if has_ucepp else
            CalculationService._get_policy_value('dggr_tuition', f"{load_key}_per_semester")
        )
        return {
            'total': total,
            'stream': ' + '.join(streams_applied) or stream_raw,
            'enrollment': 'Full-Time' if is_full_time else 'Part-Time',
            'has_dependents': has_deps,
            'months': months,
            'living_rate': living_rate,
            'tuition_cap': primary_tuition_limit,
            'requested_tuition': actual_tuition or Decimal(0),
            'tuition_confirmed': tuition_confirmed,
            'unfunded_tuition': unfunded_tuition,
            'total_tuition': total_tuition,
            'total_living': total_living,
            'breakdown': breakdown,
            'payment_items': payment_items,
        }

    # Breakdown rows that draw on the per-semester program-cost cap. Tuition is
    # only part of it: a student whose registrar-confirmed tuition comes in under
    # the cap can later be funded for a laptop or supplies out of what is left.
    PROGRAM_COST_KEYWORDS = ('tuition', 'laptop', 'computer', 'supplies',
                             'equipment', 'materials', 'software', 'program cost')

    @staticmethod
    def is_program_cost_row(row):
        """
        True when a breakdown row draws on the program-cost cap.

        An explicit cost_type set by staff always wins; otherwise the label is
        matched, so existing rows keep working without being re-tagged.
        """
        cost_type = (row.get('cost_type') or '').strip().lower()
        if cost_type:
            return cost_type == 'program'
        label = (row.get('label') or '').strip().lower()
        if 'living' in label or 'book' in label or 'travel' in label:
            return False
        return any(word in label for word in CalculationService.PROGRAM_COST_KEYWORDS)

    @staticmethod
    def program_cost_cap(submission):
        """The per-semester program-cost ceiling for this student's stream."""
        student = submission.student
        streams = ' '.join(filter(None, [
            getattr(student, 'primary_stream', '') or '',
            getattr(student, 'secondary_stream', '') or '',
        ])).upper()

        if 'PSSSP' in streams:
            return CalculationService._get_policy_value('psssp_tuition', 'max_per_semester')
        if 'UCEPP' in streams:
            return CalculationService._get_policy_value('ucepp_tuition', 'max_per_semester')
        if 'DGGR' in streams:
            load = 'fulltime'
            if 'part' in (getattr(student, 'enrollment_status', '') or '').lower():
                load = 'parttime'
            return CalculationService._get_policy_value('dggr_tuition', f'{load}_per_semester')
        return CalculationService._get_policy_value('psssp_tuition', 'max_per_semester')

    @staticmethod
    def check_program_cost_cap(submission, breakdown_rows):
        """
        Returns an error message when the program-cost rows exceed the cap for
        the semester, otherwise None.

        Extra Tuition Cap Relief is excluded: it is a separate award that exists
        precisely to go beyond this ceiling.
        """
        cap = CalculationService.program_cost_cap(submission)
        if cap <= 0:
            return None

        total = Decimal(0)
        counted = []
        for row in breakdown_rows or []:
            if 'extra tuition' in (row.get('label') or '').lower():
                continue
            if not CalculationService.is_program_cost_row(row):
                continue
            try:
                amount = Decimal(str(row.get('amount') or 0))
            except Exception:
                continue
            total += amount
            counted.append(f"{row.get('label') or 'Item'} ${amount:,.2f}")

        if total > cap:
            return (
                f"Program-cost items total ${total:,.2f}, which exceeds the "
                f"${cap:,.2f} per-semester cap for this student "
                f"({'; '.join(counted)}). Reduce a line or record the excess as a "
                "separate award."
            )
        return None

    @staticmethod
    def _fiscal_year_start():
        """DGG fiscal year runs April 1 → March 31."""
        from django.utils import timezone as _tz
        from datetime import date as _date

        as_of = CalculationService._get_as_of_date()
        today = _tz.now().date() if as_of is None else as_of
        return _date(today.year if today.month >= 4 else today.year - 1, 4, 1)

    @staticmethod
    def _extra_tuition_used(submission, student=None):
        """Extra Tuition already paid this fiscal year, ignoring this submission's own."""
        from django.db.models import Sum

        qs = Payment.objects.filter(
            payment_type__icontains='Extra Tuition',
            date_issued__date__gte=CalculationService._fiscal_year_start(),
        )
        if student is not None:
            qs = qs.filter(user=student)
        used = qs.aggregate(total=Sum('amount'))['total'] or Decimal(0)

        # Exclude this submission's own prior calculation (recalculation scenario)
        own = qs.filter(submission=submission).aggregate(total=Sum('amount'))['total'] or Decimal(0)
        return max(Decimal(0), used - own)

    @staticmethod
    def _apply_extra_tuition_annual_cap(extra_requested, submission):
        """§4.3: one student may receive at most `max_per_year` of Extra Tuition.

        Only the per-semester cap was enforced before, so a student could clear
        the yearly limit over two or three semesters.
        """
        annual_cap = CalculationService._get_policy_value('dggr_extra_tuition', 'max_per_year')
        if annual_cap <= 0 or not submission.student:
            return extra_requested

        remaining = annual_cap - CalculationService._extra_tuition_used(submission, submission.student)
        if remaining <= 0:
            return Decimal(0)
        return min(extra_requested, remaining)

    @staticmethod
    def _apply_extra_tuition_pool_cap(extra_requested, submission):
        """§4.3: Total annual pool for DGGR Extra Tuition across ALL students is $36k.
        Returns the amount this submission can receive without busting the cap."""
        # Seeded as 'annual_cap_all_students'; 'annual_pool_cap' is accepted too so
        # an installation that renamed the key keeps working. Reading only the
        # latter meant every admin edit to the pool was ignored in favour of the
        # hard-coded default below.
        pool_cap = CalculationService._get_policy_value('dggr_extra_tuition', 'annual_cap_all_students')
        if pool_cap <= 0:
            pool_cap = CalculationService._get_policy_value('dggr_extra_tuition', 'annual_pool_cap')
        if pool_cap <= 0:
            pool_cap = Decimal('36000')  # §4.3 hard default

        remaining = pool_cap - CalculationService._extra_tuition_used(submission)
        if remaining <= 0:
            return Decimal(0)
        return min(extra_requested, remaining)

    # Per-calculation state. This MUST NOT be class-level: the effective date and
    # the policy cache belong to one submission, and Gunicorn (gthread) and Vercel
    # Fluid Compute both run concurrent requests inside a single process. As class
    # attributes, two overlapping calculations raced — the second submission's
    # as_of_date overwrote the first's, so an application submitted in 2024 was
    # priced with 2026 policy rates. Thread-local storage scopes it correctly, and
    # calculate_and_pay clears it in a finally block so nothing leaks into the next
    # calculation on the same worker thread.
    _state = threading.local()

    @staticmethod
    def _get_as_of_date():
        return getattr(CalculationService._state, 'as_of_date', None)

    @staticmethod
    def _begin_calculation(as_of_date):
        CalculationService._state.as_of_date = as_of_date
        CalculationService._state.policy_cache = {}
        CalculationService._state.missing_policies = []

    @staticmethod
    def _end_calculation():
        CalculationService._state.as_of_date = None
        CalculationService._state.policy_cache = {}
        CalculationService._state.missing_policies = []

    @staticmethod
    def _record_missing_policy(section, field_key):
        missing = CalculationService.get_missing_policies()
        entry = f"{section}:{field_key}"
        if entry not in missing:
            missing.append(entry)

    @staticmethod
    def get_missing_policies():
        """Policy settings this calculation needed but could not find."""
        missing = getattr(CalculationService._state, 'missing_policies', None)
        if missing is None:
            missing = []
            CalculationService._state.missing_policies = missing
        return missing

    @staticmethod
    def _get_policy_cache():
        cache = getattr(CalculationService._state, 'policy_cache', None)
        if cache is None:
            cache = {}
            CalculationService._state.policy_cache = cache
        return cache

    @staticmethod
    def _get_policy_value(section, field_key):
        """Return the policy value that was in effect on the current as_of date.

        §4.3/§7.5: if the admin scheduled a future effective_date on a
        PolicyHistory entry, submissions from before that date use the old_value.
        Also returns 0 if the setting is deactivated (is_active=False).
        """
        as_of = CalculationService._get_as_of_date()  # may be None → use current value
        policy_cache = CalculationService._get_policy_cache()
        cache_key = f"{section}:{field_key}:{as_of}"
        if cache_key in policy_cache:
            return policy_cache[cache_key]

        try:
            setting = PolicySetting.objects.get(section=section, field_key=field_key)

            # §3.1.G: deactivated settings return 0 — award is suspended
            if not setting.is_active:
                policy_cache[cache_key] = Decimal(0)
                return Decimal(0)

            val = setting.value

            # §7.5: if a future-dated change exists and our submission predates it,
            # walk PolicyHistory to find the value that was in effect on as_of
            if as_of is not None:
                from api.models import PolicyHistory
                # Find history entries whose effective_date is AFTER as_of_date
                # (meaning those changes hadn't taken effect yet)
                future_changes = PolicyHistory.objects.filter(
                    setting=setting,
                    effective_date__gt=str(as_of),
                ).order_by('effective_date')
                if future_changes.exists():
                    # The oldest "not-yet-active" change's old_value is what applied on as_of
                    try:
                        val = Decimal(future_changes.first().old_value)
                    except Exception:
                        pass  # fall back to current value

            policy_cache[cache_key] = val
            return val
        except PolicySetting.DoesNotExist:
            # A missing setting is a misconfiguration, not a zero rate. Returning 0
            # silently produced awards of $0.00 that were indistinguishable from a
            # legitimate calculation. Record it so calculate_and_pay can refuse to
            # write payments, and so the staff preview can show why.
            CalculationService._record_missing_policy(section, field_key)
            import logging
            logging.getLogger(__name__).error(
                "Missing policy setting: %s:%s. Award cannot be computed from it.",
                section, field_key,
            )
            return Decimal(0)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Error fetching policy %s:%s - %s", section, field_key, e)
            return Decimal(0)
