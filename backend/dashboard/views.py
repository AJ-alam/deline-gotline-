from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Q
from forms.models import FormSubmission
from api.models import Application, Payment
from core.utils import api_response
from users.permissions import IsAdminUser

import logging
logger = logging.getLogger(__name__)

User = get_user_model()

# Fiscal-year quarter month ranges: Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar
FISCAL_QUARTERS = {
    'Q1': [4, 5, 6],
    'Q2': [7, 8, 9],
    'Q3': [10, 11, 12],
    'Q4': [1, 2, 3],
}

# Funding-type filter for FormSubmission.form.title
FUNDING_TYPE_Q = {
    'cdfn':  Q(form__title__icontains='FormA') | Q(form__title__icontains='FormC') | Q(form__title__icontains='PSSSP') | Q(form__title__icontains='Admission'),
    'dggr':  (Q(form__title__icontains='DGGR') | Q(form__title__icontains='Scholarship') |
               Q(form__title__icontains='Hardship') | Q(form__title__icontains='Form D') |
               Q(form__title__icontains='Form F') | Q(form__title__icontains='Form G')),
    'ucepp': Q(form__title__icontains='UCEPP') | Q(form__title__icontains='Upgrading'),
}

# Same regexes against Payment.submission.form.title — used when aggregating
# funding totals from the Payment table (truth source for dollar amounts).
FUNDING_TYPE_Q_VIA_SUB = {
    'cdfn':  (Q(submission__form__title__icontains='FormA') | Q(submission__form__title__icontains='FormC')
              | Q(submission__form__title__icontains='PSSSP') | Q(submission__form__title__icontains='Admission')),
    'dggr':  (Q(submission__form__title__icontains='DGGR') | Q(submission__form__title__icontains='Scholarship')
              | Q(submission__form__title__icontains='Hardship') | Q(submission__form__title__icontains='Form D')
              | Q(submission__form__title__icontains='Form F') | Q(submission__form__title__icontains='Form G')),
    'ucepp': Q(submission__form__title__icontains='UCEPP') | Q(submission__form__title__icontains='Upgrading'),
}


class DashboardStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        funding_type  = request.query_params.get('funding_type', 'all').lower()
        date_from     = request.query_params.get('date_from')
        date_to       = request.query_params.get('date_to')
        status_filter = request.query_params.get('status_filter', 'all').lower()

        # ── 1. Build base queryset with all filters ──────────────────────────
        qs = FormSubmission.objects.all()

        if funding_type in FUNDING_TYPE_Q:
            qs = qs.filter(FUNDING_TYPE_Q[funding_type])

        if date_from:
            qs = qs.filter(submitted_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(submitted_at__date__lte=date_to)

        valid_statuses = ['pending', 'reviewed', 'forwarded', 'accepted', 'rejected',
                          'more_info_required', 'sent_to_finance']
        if status_filter in valid_statuses:
            qs = qs.filter(status=status_filter)

        # ── 2. Single aggregation pass — all counts and sums at once ─────────
        agg = qs.aggregate(
            total=Count('id'),
            cnt_pending=Count('id', filter=Q(status='pending')),
            cnt_reviewed=Count('id', filter=Q(status='reviewed')),
            cnt_forwarded=Count('id', filter=Q(status='forwarded')),
            cnt_accepted=Count('id', filter=Q(status='accepted')),
            cnt_rejected=Count('id', filter=Q(status='rejected')),
            cnt_more_info=Count('id', filter=Q(status='more_info_required')),
            cnt_finance=Count('id', filter=Q(status='sent_to_finance')),
            # Funding amounts
            funded_total=Sum('amount', filter=Q(status='accepted')),
            pending_total=Sum('amount', filter=Q(status='forwarded')),
            # Per funding-stream counts (full queryset, filtered above)
            cnt_cdfn=Count('id', filter=FUNDING_TYPE_Q['cdfn']),
            cnt_dggr=Count('id', filter=FUNDING_TYPE_Q['dggr']),
            cnt_ucepp=Count('id', filter=FUNDING_TYPE_Q['ucepp']),
            # Per funding-stream approved amounts
            amt_cdfn=Sum('amount', filter=FUNDING_TYPE_Q['cdfn'] & Q(status='accepted')),
            amt_dggr=Sum('amount', filter=FUNDING_TYPE_Q['dggr'] & Q(status='accepted')),
            amt_ucepp=Sum('amount', filter=FUNDING_TYPE_Q['ucepp'] & Q(status='accepted')),
            # Per form-type counts (respect all active filters)
            cnt_forma=Count('id', filter=Q(form__title__icontains='FormA') | Q(form__title__icontains='PSSSP') | Q(form__title__icontains='Admission')),
            cnt_formb=Count('id', filter=Q(form__title__icontains='FormB')),
            cnt_formc=Count('id', filter=Q(form__title__icontains='FormC')),
            cnt_formd=Count('id', filter=Q(form__title__icontains='FormD')),
            cnt_forme=Count('id', filter=Q(form__title__icontains='FormE')),
            cnt_formf=Count('id', filter=Q(form__title__icontains='FormF')),
            cnt_formg=Count('id', filter=Q(form__title__icontains='FormG')),
            cnt_formh=Count('id', filter=Q(form__title__icontains='FormH')),
            cnt_scholarship=Count('id', filter=Q(form__title__icontains='scholarship')),
            # Fiscal-quarter breakdowns
            q1_amt=Sum('amount', filter=Q(status='accepted', submitted_at__month__in=FISCAL_QUARTERS['Q1'])),
            q1_cnt=Count('id',   filter=Q(status='accepted', submitted_at__month__in=FISCAL_QUARTERS['Q1'])),
            q2_amt=Sum('amount', filter=Q(status='accepted', submitted_at__month__in=FISCAL_QUARTERS['Q2'])),
            q2_cnt=Count('id',   filter=Q(status='accepted', submitted_at__month__in=FISCAL_QUARTERS['Q2'])),
            q3_amt=Sum('amount', filter=Q(status='accepted', submitted_at__month__in=FISCAL_QUARTERS['Q3'])),
            q3_cnt=Count('id',   filter=Q(status='accepted', submitted_at__month__in=FISCAL_QUARTERS['Q3'])),
            q4_amt=Sum('amount', filter=Q(status='accepted', submitted_at__month__in=FISCAL_QUARTERS['Q4'])),
            q4_cnt=Count('id',   filter=Q(status='accepted', submitted_at__month__in=FISCAL_QUARTERS['Q4'])),
            # Form B pending (not yet completed)
            cnt_formb_pending=Count('id', filter=Q(form__title__icontains='FormB') & ~Q(status__in=['accepted', 'rejected'])),
            # Unique students who submitted
            distinct_students=Count('student', distinct=True),
        )

        total = agg['total'] or 0

        # ── 2b. Funding totals from Payment (truth source) + legacy Applications ─
        # FormSubmission.amount is only populated by the calculation_service for
        # certain forms (graduation/practicum/scholarship/etc.) — for forms like
        # Admission it stays 0, which made the dashboard under-count approved
        # funding. The Payment table is the canonical source: every approved
        # disbursement has Payment row(s) with the dollar breakdown.
        pay_qs = Payment.objects.all()
        if date_from:
            pay_qs = pay_qs.filter(submission__submitted_at__date__gte=date_from)
        if date_to:
            pay_qs = pay_qs.filter(submission__submitted_at__date__lte=date_to)
        if funding_type in FUNDING_TYPE_Q_VIA_SUB:
            pay_qs = pay_qs.filter(FUNDING_TYPE_Q_VIA_SUB[funding_type])

        pay_agg = pay_qs.aggregate(
            # Approved = anything not cancelled (pending or issued — both are real $ commitments)
            approved=Sum('amount', filter=~Q(status='cancelled')),
            pending=Sum('amount', filter=Q(status='pending')),
            issued=Sum('amount', filter=Q(status='issued')),
        )

        # Legacy Application contributions — only count approved legacy rows that
        # have NO related payments (otherwise we'd double-count).
        legacy_qs = Application.objects.filter(status='approved').filter(payments__isnull=True)
        if date_from:
            legacy_qs = legacy_qs.filter(created_at__date__gte=date_from)
        if date_to:
            legacy_qs = legacy_qs.filter(created_at__date__lte=date_to)
        legacy_total = legacy_qs.aggregate(s=Sum('amount'))['s'] or 0

        funded = (pay_agg['approved'] or 0) + legacy_total
        pending_funding = pay_agg['pending'] or 0

        # ── 2c. Legacy Application status counts ─────────────────────────────
        # The Status breakdown panel was previously counting FormSubmissions
        # only — legacy Application rows (status='approved'/'denied'/'pending'/
        # 'review'/'waitingb'/'more_info_required') were invisible. Map them
        # into the same buckets so the dashboard reflects the whole system.
        legacy_status_qs = Application.objects.all()
        if date_from:
            legacy_status_qs = legacy_status_qs.filter(created_at__date__gte=date_from)
        if date_to:
            legacy_status_qs = legacy_status_qs.filter(created_at__date__lte=date_to)
        # Legacy doesn't carry form.title; map its form_type into the same
        # funding-stream buckets used for FormSubmission so funding_type filter
        # behaves consistently across both data sources.
        LEGACY_STREAM_Q = {
            'cdfn':  Q(form_type__icontains='FormA') | Q(form_type__icontains='FormC') | Q(form_type__icontains='PSSSP') | Q(form_type__icontains='Admission'),
            'dggr':  (Q(form_type__icontains='DGGR') | Q(form_type__icontains='Scholarship')
                      | Q(form_type__icontains='Hardship') | Q(form_type__icontains='FormD')
                      | Q(form_type__icontains='FormF') | Q(form_type__icontains='FormG')),
            'ucepp': Q(form_type__icontains='UCEPP') | Q(form_type__icontains='Upgrading'),
        }
        if funding_type in LEGACY_STREAM_Q:
            legacy_status_qs = legacy_status_qs.filter(LEGACY_STREAM_Q[funding_type])

        legacy_agg = legacy_status_qs.aggregate(
            total=Count('id'),
            cnt_new=Count('id', filter=Q(status='new')),
            cnt_review=Count('id', filter=Q(status='review')),
            cnt_pending_dir=Count('id', filter=Q(status='pending')),    # legacy "pending" = pending director
            cnt_approved=Count('id', filter=Q(status='approved')),
            cnt_denied=Count('id', filter=Q(status='denied')),
            cnt_waiting_b=Count('id', filter=Q(status='waitingb')),
            cnt_more_info=Count('id', filter=Q(status='more_info_required')),
            cnt_cdfn=Count('id', filter=LEGACY_STREAM_Q['cdfn']),
            cnt_dggr=Count('id', filter=LEGACY_STREAM_Q['dggr']),
            cnt_ucepp=Count('id', filter=LEGACY_STREAM_Q['ucepp']),
            distinct_students=Count('student', distinct=True),
        )

        # ── 2d. Unified status buckets — FormSubmission + legacy Application ──
        # Each bucket sums equivalent statuses across both models so the panel
        # reflects "the whole system" rather than just one table.
        unified = {
            'pending':            (agg['cnt_pending']    or 0) + (legacy_agg['cnt_new']         or 0),
            'reviewed':           (agg['cnt_reviewed']   or 0) + (legacy_agg['cnt_review']      or 0),
            'forwarded':          (agg['cnt_forwarded']  or 0) + (legacy_agg['cnt_pending_dir'] or 0),
            # Approved counts the full approved-lifetime — accepted + sent_to_finance
            # (still approved, just dispatched) + legacy approved.
            'accepted':           (agg['cnt_accepted']   or 0) + (agg['cnt_finance'] or 0) + (legacy_agg['cnt_approved'] or 0),
            'rejected':           (agg['cnt_rejected']   or 0) + (legacy_agg['cnt_denied']      or 0),
            'more_info_required': (agg['cnt_more_info']  or 0) + (legacy_agg['cnt_more_info']   or 0),
            'sent_to_finance':    (agg['cnt_finance']    or 0),
            'waiting_form_b':     (agg['cnt_formb_pending'] or 0) + (legacy_agg['cnt_waiting_b'] or 0),
        }
        combined_total = (total or 0) + (legacy_agg['total'] or 0)
        approval_rate = round((unified['accepted'] / combined_total * 100) if combined_total else 0, 1)

        # ── 3. Lightweight recent lists (2 queries, limited) ─────────────────
        recent_submissions = list(
            qs.order_by('-submitted_at')[:10].values(
                'id', 'form__title', 'student__full_name', 'status', 'submitted_at'
            )
        )
        recent_payouts = list(
            qs.filter(status='accepted').order_by('-decided_at')[:15].values(
                'id', 'amount', 'form__title', 'student__full_name', 'decided_at', 'status'
            )
        )

        # ── 4. Per-stream approved $ from Payment (more accurate than
        # FormSubmission.amount, which is 0 for non-calculated forms) ─────────
        stream_pay_agg = Payment.objects.exclude(status='cancelled').aggregate(
            cdfn=Sum('amount', filter=FUNDING_TYPE_Q_VIA_SUB['cdfn']),
            dggr=Sum('amount', filter=FUNDING_TYPE_Q_VIA_SUB['dggr']),
            ucepp=Sum('amount', filter=FUNDING_TYPE_Q_VIA_SUB['ucepp']),
        )

        # ── 5. Assemble response ──────────────────────────────────────────────
        # Unique students = union of submitting students across BOTH tables so
        # the same person showing up in both legacy and new flows is counted once.
        total_student_ids = set(
            qs.exclude(student__isnull=True).values_list('student_id', flat=True)
        ) | set(
            legacy_status_qs.exclude(student__isnull=True).values_list('student_id', flat=True)
        )

        stats = {
            # Totals — count submitting students once across both data sources.
            "total_students":        len(total_student_ids),
            # Combined submission count (FormSubmission + legacy Application) so
            # the header line and KPI card show the whole-system reality.
            "total_submissions":     combined_total,
            "total_funding_approved": funded,
            "approval_rate":         approval_rate,
            "pending_funding_total": pending_funding,
            "pending_payments_count": unified['accepted'],

            # Status breakdown — unified across FormSubmission + legacy Application.
            # Frontend keys (pending/reviewed/forwarded/accepted/rejected/
            # more_info_required/sent_to_finance) preserved for compatibility.
            "submissions_by_status": {
                "pending":            unified['pending'],
                "reviewed":           unified['reviewed'],
                "forwarded":          unified['forwarded'],
                "accepted":           unified['accepted'],
                "rejected":           unified['rejected'],
                "more_info_required": unified['more_info_required'],
                "sent_to_finance":    unified['sent_to_finance'],
                "waiting_form_b":     unified['waiting_form_b'],
            },

            # Fiscal quarters (Q1=Apr-Jun … Q4=Jan-Mar)
            "quarterly_report": [
                {'quarter': 'Q1 (Apr–Jun)', 'amount': agg['q1_amt'] or 0, 'count': agg['q1_cnt'] or 0},
                {'quarter': 'Q2 (Jul–Sep)', 'amount': agg['q2_amt'] or 0, 'count': agg['q2_cnt'] or 0},
                {'quarter': 'Q3 (Oct–Dec)', 'amount': agg['q3_amt'] or 0, 'count': agg['q3_cnt'] or 0},
                {'quarter': 'Q4 (Jan–Mar)', 'amount': agg['q4_amt'] or 0, 'count': agg['q4_cnt'] or 0},
            ],

            # Per-form counts (all respect active filters)
            "submissions_by_form": {
                "FormA":       agg['cnt_forma'],
                "FormB":       agg['cnt_formb'],
                "FormC":       agg['cnt_formc'],
                "FormD":       agg['cnt_formd'],
                "FormE":       agg['cnt_forme'],
                "FormF":       agg['cnt_formf'],
                "FormG":       agg['cnt_formg'],
                "FormH":       agg['cnt_formh'],
                "scholarship": agg['cnt_scholarship'],
            },
            "form_b_stats": {"awaiting": unified['waiting_form_b']},

            # Stream split — combined counts across both tables so the panel
            # totals match the system-wide submission count.
            "stream_split": (lambda c, d, u, t: {
                "pssp":          c,
                "dggr":          d,
                "ucepp":         u,
                "pssp_percent":  round(c / t * 100 if t else 0, 1),
                "dggr_percent":  round(d / t * 100 if t else 0, 1),
                "ucepp_percent": round(u / t * 100 if t else 0, 1),
            })(
                (agg['cnt_cdfn']  or 0) + (legacy_agg['cnt_cdfn']  or 0),
                (agg['cnt_dggr']  or 0) + (legacy_agg['cnt_dggr']  or 0),
                (agg['cnt_ucepp'] or 0) + (legacy_agg['cnt_ucepp'] or 0),
                combined_total,
            ),
            "stream_totals": {
                "pssp":  stream_pay_agg['cdfn']  or 0,
                "dggr":  stream_pay_agg['dggr']  or 0,
                "ucepp": stream_pay_agg['ucepp'] or 0,
            },

            "recent_submissions": recent_submissions,
            "recent_payouts":     recent_payouts,
        }

        return api_response(True, stats, "Dashboard stats retrieved")
