from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.contrib.auth import get_user_model
from programs.models import Program
from forms.models import FormSubmission, Form
from core.utils import api_response
from users.permissions import IsAdminUser

User = get_user_model()

import time
import logging
logger = logging.getLogger(__name__)

class DashboardStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        start_time = time.time()
        from django.db.models import Sum, Count, Q
        from api.models import Payment

        funding_type = request.query_params.get('funding_type', 'all').lower()
        # Task 10.5: Date range filter
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        # Task 10.6: Status filter
        status_filter = request.query_params.get('status_filter', 'all').lower()

        # Base Submissions mapping (Robust matching for DGG form naming conventions)
        mapping = {
            'cdfn': Q(form__title__icontains='FormA') | Q(form__title__icontains='FormC'),
            'dggr': Q(form__title__icontains='DGGR') | Q(form__title__icontains='Scholarship') | Q(form__title__icontains='Hardship') | Q(form__title__icontains='Form D') | Q(form__title__icontains='Form F') | Q(form__title__icontains='Form G'),
            'ucepp': Q(form__title__icontains='UCEPP') | Q(form__title__icontains='Upgrading'),
        }

        submissions = FormSubmission.objects.all()
        if funding_type in mapping:
            submissions = submissions.filter(mapping[funding_type])

        # Apply date range filter
        if date_from:
            submissions = submissions.filter(submitted_at__date__gte=date_from)
        if date_to:
            submissions = submissions.filter(submitted_at__date__lte=date_to)

        # Apply status filter
        valid_statuses = ['pending', 'reviewed', 'forwarded', 'accepted', 'rejected']
        if status_filter in valid_statuses:
            submissions = submissions.filter(status=status_filter)
            
        # Consolidated Aggregation for better performance
        # Task: Optimize multiple DB hits into one
        base_agg = submissions.aggregate(
            total_count=Count('id'),
            accepted_count=Count('id', filter=Q(status='accepted')),
            pending_count=Count('id', filter=Q(status='pending')),
            reviewed_count=Count('id', filter=Q(status='reviewed')),
            forwarded_count=Count('id', filter=Q(status='forwarded')),
            rejected_count=Count('id', filter=Q(status='rejected')),
            total_funding=Sum('amount', filter=Q(status='accepted')),
            pending_funding=Sum('amount', filter=Q(status='forwarded')),
            pending_payments=Count('id', filter=Q(status='accepted', amount__gt=0))
        )

        total_subs_count = base_agg['total_count'] or 0
        total_funding = base_agg['total_funding'] or 0
        
        status_dict = {
            'pending': base_agg['pending_count'],
            'reviewed': base_agg['reviewed_count'],
            'forwarded': base_agg['forwarded_count'],
            'accepted': base_agg['accepted_count'],
            'rejected': base_agg['rejected_count']
        }

        # Approval Rate
        approval_rate = (base_agg['accepted_count'] / total_subs_count * 100) if total_subs_count > 0 else 0
        
        # Quarters (Optimized into a single aggregation)
        quarter_filters = {}
        for q in range(1, 5):
            months = range((q-1)*3 + 1, q*3 + 1)
            quarter_filters[f'q{q}_amount'] = Sum('amount', filter=Q(status='accepted', submitted_at__month__in=months))
            quarter_filters[f'q{q}_count'] = Count('id', filter=Q(status='accepted', submitted_at__month__in=months))
        
        quarters_agg = submissions.aggregate(**quarter_filters)
        quarterly_data = [
            {
                'quarter': f'Q{q}',
                'amount': quarters_agg[f'q{q}_amount'] or 0,
                'count': quarters_agg[f'q{q}_count'] or 0
            } for q in range(1, 5)
        ]

        # Recent payouts (Limit to essential fields for speed)
        recent_payouts_list = list(submissions.filter(status='accepted').order_by('-decided_at')[:20].values(
            'id', 'amount', 'form__title', 'student__full_name', 'decided_at', 'status'
        ))
        
        # Recent submissions
        recent_submissions = list(submissions.order_by('-submitted_at')[:10].values(
            'id', 'form__title', 'student__full_name', 'status', 'submitted_at'
        ))

        # Per-form counts (Optimized into single aggregation)
        from django.db.models import Q as Q2
        form_key_map = [
            ('FormA', Q2(form__title__icontains='FormA')),
            ('FormB', Q2(form__title__icontains='FormB')),
            ('FormC', Q2(form__title__icontains='FormC')),
            ('FormD', Q2(form__title__icontains='FormD')),
            ('FormE', Q2(form__title__icontains='FormE')),
            ('FormF', Q2(form__title__icontains='FormF')),
            ('FormG', Q2(form__title__icontains='FormG')),
            ('FormH', Q2(form__title__icontains='FormH')),
            ('scholarship', Q2(form__title__icontains='scholarship')),
        ]
        
        form_agg_params = {f"count_{key}": Count('id', filter=q) for key, q in form_key_map}
        form_counts_agg = FormSubmission.objects.aggregate(**form_agg_params)
        submissions_by_form = {key: form_counts_agg[f"count_{key}"] for key, q in form_key_map}

        form_b_pending = FormSubmission.objects.filter(
            Q2(form__title__icontains='FormB')
        ).exclude(status__in=['accepted', 'rejected']).count()

        stats = {
            "total_students": User.objects.filter(role='student').count() if funding_type == 'all' else submissions.values('student').distinct().count(),
            "total_submissions": total_subs_count,
            "total_funding_approved": total_funding,
            "approval_rate": round(approval_rate, 1),
            "quarterly_report": quarterly_data,
            "submissions_by_status": status_dict,
            "pending_payments_count": base_agg['pending_payments'],
            "pending_funding_total": base_agg['pending_funding'] or 0,
            "recent_submissions": recent_submissions,
            "recent_payouts": recent_payouts_list,
            "submissions_by_form": submissions_by_form,
            "form_b_stats": {"awaiting": form_b_pending},
        }
        
        if funding_type == 'all':
            stream_agg = FormSubmission.objects.aggregate(
                pssp_count=Count('id', filter=mapping['cdfn']),
                dggr_count=Count('id', filter=mapping['dggr']),
                ucepp_count=Count('id', filter=mapping['ucepp']),
                pssp_total=Sum('amount', filter=mapping['cdfn'] & Q(status='accepted')),
                dggr_total=Sum('amount', filter=mapping['dggr'] & Q(status='accepted')),
                ucepp_total=Sum('amount', filter=mapping['ucepp'] & Q(status='accepted'))
            )
            
            stats["stream_split"] = {
                'pssp': stream_agg['pssp_count'],
                'dggr': stream_agg['dggr_count'],
                'ucepp': stream_agg['ucepp_count'],
                'pssp_percent': (stream_agg['pssp_count'] / total_subs_count * 100) if total_subs_count > 0 else 0,
                'dggr_percent': (stream_agg['dggr_count'] / total_subs_count * 100) if total_subs_count > 0 else 0,
                'ucepp_percent': (stream_agg['ucepp_count'] / total_subs_count * 100) if total_subs_count > 0 else 0,
            }
            stats["stream_totals"] = {
                'pssp': stream_agg['pssp_total'] or 0,
                'dggr': stream_agg['dggr_total'] or 0,
                'ucepp': stream_agg['ucepp_total'] or 0,
            }

        logger.info(f"Dashboard stats calculated in {time.time() - start_time:.4f} seconds")
        return api_response(True, stats, "Dashboard stats retrieved successfully")
