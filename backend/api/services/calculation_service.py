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
        # §4.3/§7.5: lock effective-date to the submission's submitted_at so
        # policy changes made after the submission use the rate that was in effect
        # when the student applied.
        CalculationService._as_of_date = (
            submission.submitted_at.date() if submission.submitted_at else None
        )

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
        # §4.5: NO advance payments — only create payments after the application deadline
        # for the semester has passed (i.e., the payment period has begun).
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

        living_field = f"{load_key}_{dep_key}"  # e.g. fulltime_with_dependents
        payment_items = []
        total_tuition = Decimal(0)
        total_living = Decimal(0)
        streams_applied = []

        # ── C-DFN PSSSP ────────────────────────────────────────────────────────
        if has_psssp and not is_sfa:
            psssp_tuition_limit = CalculationService._get_policy_value('psssp_tuition', 'max_per_semester')
            psssp_tuition = min(requested_tuition, psssp_tuition_limit) if requested_tuition > 0 else psssp_tuition_limit
            psssp_living_rate = CalculationService._get_policy_value('psssp_living', living_field)
            psssp_living = psssp_living_rate * Decimal(months)
            payment_items.append(('Tuition (PSSSP)', psssp_tuition))
            payment_items.append(('Living Allowance (PSSSP)', psssp_living))
            total_tuition += psssp_tuition
            total_living += psssp_living
            streams_applied.append('PSSSP')

        # ── C-DFN UCEPP ────────────────────────────────────────────────────────
        if has_ucepp and not is_sfa:
            ucepp_tuition_limit = CalculationService._get_policy_value('ucepp_tuition', 'max_per_semester')
            ucepp_tuition = min(requested_tuition, ucepp_tuition_limit) if requested_tuition > 0 else ucepp_tuition_limit
            ucepp_living_rate = CalculationService._get_policy_value('ucepp_living', living_field)
            ucepp_living = ucepp_living_rate * Decimal(months)
            payment_items.append(('Tuition (UCEPP)', ucepp_tuition))
            payment_items.append(('Living Allowance (UCEPP)', ucepp_living))
            total_tuition += ucepp_tuition
            total_living += ucepp_living
            streams_applied.append('UCEPP')

        # ── DGGR ────────────────────────────────────────────────────────────────
        if has_dggr:
            dggr_tuition_limit = CalculationService._get_policy_value('dggr_tuition', f"{load_key}_per_semester")
            dggr_tuition = dggr_tuition_limit  # fixed rate, not tied to actual tuition
            dggr_living_rate = CalculationService._get_policy_value('dggr_living', living_field)
            dggr_living = dggr_living_rate * Decimal(months)
            payment_items.append(('Tuition (DGGR)', dggr_tuition))
            payment_items.append(('Living Allowance (DGGR)', dggr_living))
            total_tuition += dggr_tuition
            total_living += dggr_living
            streams_applied.append('DGGR')

            # ── DGGR Extra Tuition Bursary ──────────────────────────────────────
            # §4.3: only when tuition > threshold; inclusive of (not additive to)
            # the regular DGGR bursary; subject to $36k/year pool cap.
            if requested_tuition > 0:
                threshold = CalculationService._get_policy_value('dggr_extra_tuition', 'threshold_per_semester')
                if threshold > 0 and requested_tuition > threshold:
                    pct_raw = CalculationService._get_policy_value('dggr_extra_tuition', 'max_percent_covered')
                    percent = pct_raw / Decimal(100) if pct_raw else Decimal(0)
                    cap = CalculationService._get_policy_value('dggr_extra_tuition', 'max_per_semester')
                    total_inclusive = min(requested_tuition * percent, cap)
                    # "Inclusive" means the extra is the DIFFERENCE above regular DGGR
                    extra_before_pool = max(Decimal(0), total_inclusive - dggr_tuition)

                    if extra_before_pool > 0:
                        # §4.3 $36k annual pool cap across ALL students
                        extra_amount = CalculationService._apply_extra_tuition_pool_cap(
                            extra_before_pool, submission
                        )
                        if extra_amount > 0:
                            payment_items.append(('Extra Tuition Cap Relief', extra_amount))
                            total_tuition += extra_amount

        # ── Single-stream fallback for backward compat (no DGGR, no C-DFN chosen) ──
        if not streams_applied:
            # Default to PSSSP
            tuition_limit = CalculationService._get_policy_value('psssp_tuition', 'max_per_semester')
            final_tuition = min(requested_tuition, tuition_limit) if requested_tuition > 0 else tuition_limit
            living_rate = CalculationService._get_policy_value('psssp_living', living_field)
            total_living = living_rate * Decimal(months)
            total_tuition = final_tuition
            payment_items = [('Tuition', final_tuition), ('Living Allowance', total_living)]
            streams_applied = ['PSSSP (default)']

        # ── Books & supplies (per semester, once regardless of streams) ──
        books = CalculationService._get_policy_value('system_config', 'book_allowance')
        if books > 0:
            payment_items.append(('Books', books))

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
            'requested_tuition': requested_tuition,
            'payment_items': payment_items,
        }

    @staticmethod
    def _apply_extra_tuition_pool_cap(extra_requested, submission):
        """§4.3: Total annual pool for DGGR Extra Tuition across ALL students is $36k.
        Returns the amount this submission can receive without busting the cap."""
        from django.db.models import Sum
        from django.utils import timezone as _tz
        from datetime import date as _date

        pool_cap = CalculationService._get_policy_value('dggr_extra_tuition', 'annual_pool_cap')
        if pool_cap <= 0:
            pool_cap = Decimal('36000')  # §4.3 hard default

        # Fiscal year: April 1 to March 31
        today = (_tz.now().date() if CalculationService._as_of_date is None
                 else CalculationService._as_of_date)
        if today.month >= 4:
            fy_start = _date(today.year, 4, 1)
        else:
            fy_start = _date(today.year - 1, 4, 1)

        # Sum of all Extra Tuition payments issued so far this fiscal year
        already_used = Payment.objects.filter(
            payment_type__icontains='Extra Tuition',
            date_issued__date__gte=fy_start,
        ).aggregate(total=Sum('amount'))['total'] or Decimal(0)

        # Exclude this submission's own prior calculation (recalculation scenario)
        own_used = Payment.objects.filter(
            submission=submission,
            payment_type__icontains='Extra Tuition',
        ).aggregate(total=Sum('amount'))['total'] or Decimal(0)
        already_used = max(Decimal(0), already_used - own_used)

        remaining = pool_cap - already_used
        if remaining <= 0:
            return Decimal(0)
        return min(extra_requested, remaining)

    _policy_cache = {}
    # as_of_date set at the top of calculate_and_pay for the current submission
    _as_of_date = None

    @staticmethod
    def _get_policy_value(section, field_key):
        """Return the policy value that was in effect on _as_of_date.

        §4.3/§7.5: if the admin scheduled a future effective_date on a
        PolicyHistory entry, submissions from before that date use the old_value.
        Also returns 0 if the setting is deactivated (is_active=False).
        """
        as_of = CalculationService._as_of_date  # may be None → use current value
        cache_key = f"{section}:{field_key}:{as_of}"
        if cache_key in CalculationService._policy_cache:
            return CalculationService._policy_cache[cache_key]

        try:
            setting = PolicySetting.objects.get(section=section, field_key=field_key)

            # §3.1.G: deactivated settings return 0 — award is suspended
            if not setting.is_active:
                CalculationService._policy_cache[cache_key] = Decimal(0)
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
