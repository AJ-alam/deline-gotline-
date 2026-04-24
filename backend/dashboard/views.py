from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.contrib.auth import get_user_model
from programs.models import Program
from forms.models import FormSubmission, Form
from core.utils import api_response
from users.permissions import IsAdminUser

User = get_user_model()

class DashboardStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
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
            
        accepted_submissions = submissions.filter(status='accepted')
        
        # Breakdown by status
        status_counts = submissions.values('status').annotate(total=Count('id'))
        status_dict = {
            'pending': 0, 'reviewed': 0, 'forwarded': 0, 'accepted': 0, 'rejected': 0
        }
        for s in status_counts:
            status_dict[s['status']] = s['total']

        # Calculation of totals
        total_subs_count = submissions.count()
        total_funding = accepted_submissions.aggregate(total=Sum('amount'))['total'] or 0
        
        # Approval Rate
        approval_rate = (accepted_submissions.count() / total_subs_count * 100) if total_subs_count > 0 else 0
        
        # Quarters (Fiscal or Calendar - using Calendar for now as per plan)
        # 1: Jan-Mar, 2: Apr-Jun, 3: Jul-Sep, 4: Oct-Dec
        quarterly_data = []
        for q in range(1, 5):
            months = range((q-1)*3 + 1, q*3 + 1)
            q_subs = accepted_submissions.filter(submitted_at__month__in=months)
            quarterly_data.append({
                'quarter': f'Q{q}',
                'amount': q_subs.aggregate(total=Sum('amount'))['total'] or 0,
                'count': q_subs.count()
            })

        # Recent payouts for reports view
        recent_payouts = accepted_submissions.order_by('-decided_at')[:20].values(
            'id', 'amount', 'form__title', 'student__full_name', 'decided_at', 'status'
        )
        recent_payouts_list = [
            {
                'id': p['id'],
                'amount': str(p['amount'] or 0),
                'payment_type': p['form__title'] or 'General',
                'user_name': p['student__full_name'] or 'Student',
                'date': p['decided_at'].isoformat() if p['decided_at'] else None,
                'status': p['status'],
            }
            for p in recent_payouts
        ]

        stats = {
            "total_students": User.objects.filter(role='student').count() if funding_type == 'all' else submissions.values('student').distinct().count(),
            "total_submissions": total_subs_count,
            "total_funding_approved": total_funding,
            "approval_rate": round(approval_rate, 1),
            "quarterly_report": quarterly_data,
            "submissions_by_status": status_dict,
            "pending_payments_count": submissions.filter(status='accepted', amount__gt=0).count(),
            "pending_funding_total": submissions.filter(status='forwarded').aggregate(total=Sum('amount'))['total'] or 0,
            "recent_submissions": list(submissions.order_by('-submitted_at')[:10].values(
                'id', 'form__title', 'student__full_name', 'status', 'submitted_at'
            )),
            "recent_payouts": recent_payouts_list,
        }
        
        # If funding_type is 'all', add the stream split for the main dashboard
        if funding_type == 'all':
            cdfn_q = FormSubmission.objects.filter(mapping['cdfn'])
            dggr_q = FormSubmission.objects.filter(mapping['dggr'])
            ucepp_q = FormSubmission.objects.filter(mapping['ucepp'])
            
            stats["stream_split"] = {
                'pssp': cdfn_q.count(),
                'dggr': dggr_q.count(),
                'ucepp': ucepp_q.count(),
                'pssp_percent': (cdfn_q.count() / total_subs_count * 100) if total_subs_count > 0 else 0,
                'dggr_percent': (dggr_q.count() / total_subs_count * 100) if total_subs_count > 0 else 0,
                'ucepp_percent': (ucepp_q.count() / total_subs_count * 100) if total_subs_count > 0 else 0,
            }
            stats["stream_totals"] = {
                'pssp': cdfn_q.filter(status='accepted').aggregate(total=Sum('amount'))['total'] or 0,
                'dggr': dggr_q.filter(status='accepted').aggregate(total=Sum('amount'))['total'] or 0,
                'ucepp': ucepp_q.filter(status='accepted').aggregate(total=Sum('amount'))['total'] or 0,
            }

        return api_response(True, stats, "Dashboard stats retrieved successfully")
