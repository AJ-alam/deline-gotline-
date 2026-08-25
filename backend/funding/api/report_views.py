"""The annual report, and the two figures the office enters against it.

Read by the roles that already see money — Finance, the Director and an
administrator. A support worker assesses applications and does not need the
department's expenditure for the year, and the report is what goes to the head
department rather than a working screen.

Only an administrator writes: a hand-entered cost appears in the grand total
the office sends its funder, and a repayment changes what the year reports as
spent.
"""

from datetime import date

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role
from funding.models import AuditEntry
from funding.models import AwardRepayment, FundingStream, ReportedCost
from django.http import HttpResponse

from funding.services import letter_pdf, report_pdf, reporting


def _may_read(user) -> bool:
    return bool(user and user.is_authenticated
                and (user.decides_applications or user.handles_payments))


def _may_write(user) -> bool:
    return bool(user and user.is_authenticated and user.role == Role.ADMIN)


def _requested_stream(request) -> str:
    """The funding programme asked for, or empty for all of them.

    Checked against the choice set rather than passed through: an unrecognised
    value would silently narrow the report to nothing and read as a year in
    which the office funded nobody.
    """
    raw = (request.query_params.get('stream') or '').strip()
    if not raw:
        return ''
    if raw not in dict(FundingStream.choices):
        raise serializers.ValidationError(
            {'stream': f'Not a funding programme. Choose one of: '
                       f'{", ".join(dict(FundingStream.choices))}.'})
    return raw


def _requested_year(request) -> date | None:
    """The fiscal year asked for, or None for the one we are in.

    A year that is not a year is refused rather than quietly reported as the
    current one: a report headed with the wrong year is worse than an error.
    """
    raw = (request.query_params.get('year') or '').strip()
    if not raw:
        return None
    try:
        return date(int(raw), reporting.FISCAL_START_MONTH, 1)
    except (TypeError, ValueError):
        raise serializers.ValidationError(
            {'year': 'Give the calendar year the fiscal year starts in, such as 2025.'})


class AnnualReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _may_read(request.user):
            return Response({'detail': 'Only Finance, the Director and an '
                                       'administrator may read the report.'},
                            status=status.HTTP_403_FORBIDDEN)
        return Response(reporting.annual_report(_requested_year(request),
                                                stream=_requested_stream(request)))


class AnnualReportPdfView(APIView):
    """The report as the document the office forwards."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _may_read(request.user):
            return Response({'detail': 'Only Finance, the Director and an '
                                       'administrator may read the report.'},
                            status=status.HTTP_403_FORBIDDEN)
        report = reporting.annual_report(_requested_year(request),
                                         stream=_requested_stream(request))
        try:
            content = report_pdf.render(report)
        except letter_pdf.LetterFontMissing as exc:
            # The shipped fonts are what let the office's own language print.
            # Refusing names the gap rather than sending a report with the
            # government's name in black boxes.
            return Response({'detail': str(exc)},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)

        response = HttpResponse(content, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="{report_pdf.filename_for(report)}"')
        return response


class ReportedCostSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ReportedCost
        fields = ('id', 'fiscal_year_start', 'label', 'amount', 'note',
                  'recorded_by_name', 'updated_at')
        read_only_fields = ('id', 'recorded_by_name', 'updated_at')
        # The model's uniqueness is on purpose — one figure per label per year
        # — but DRF turns it into a validator that refuses the second POST
        # outright, and the second POST is how the office *corrects* a wrong
        # figure. The view treats a repeat as a correction; without this, a
        # staff-wage figure entered wrongly could never be put right.
        validators = ()

    def get_recorded_by_name(self, cost) -> str:
        return cost.recorded_by.full_name if cost.recorded_by else ''

    def validate_amount(self, value):
        if value < 0:
            raise serializers.ValidationError(
                'A cost cannot be negative. Record money that came back as a '
                'repayment against the award it came from.')
        return value

    def validate_label(self, value):
        cleaned = (value or '').strip()
        if not cleaned:
            raise serializers.ValidationError('Say what the cost is for.')
        return cleaned

    def validate_fiscal_year_start(self, value):
        """Any date inside a fiscal year means that fiscal year.

        A date of 15 June was accepted, stored, and then appeared on no report
        at all: the report looks for costs filed against 1 April, so the
        figure the office had entered simply vanished. Normalised rather than
        refused — the office is naming a year, and losing money quietly is
        worse than being forgiving about how the year is written.
        """
        return reporting.fiscal_year_of(value)


class ReportedCostsView(APIView):
    """Costs the system cannot know — staff wages, and anything like them."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _may_read(request.user):
            return Response({'detail': 'Not permitted.'},
                            status=status.HTTP_403_FORBIDDEN)
        year = _requested_year(request) or reporting.fiscal_year_of(date.today())
        costs = ReportedCost.objects.filter(fiscal_year_start=year)
        return Response(ReportedCostSerializer(costs, many=True).data)

    def post(self, request):
        if not _may_write(request.user):
            return Response({'detail': 'Only an administrator may enter a cost '
                                       'on the report.'},
                            status=status.HTTP_403_FORBIDDEN)
        serializer = ReportedCostSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        year = serializer.validated_data['fiscal_year_start']
        label = serializer.validated_data['label']

        # Entered again for the same year and label is a correction, not a
        # second line: two staff-wage rows in one year make a grand total that
        # depends on which one the reader adds up.
        cost, created = ReportedCost.objects.update_or_create(
            fiscal_year_start=year, label=label,
            defaults={'amount': serializer.validated_data['amount'],
                      'note': serializer.validated_data.get('note', ''),
                      'recorded_by': request.user},
        )
        AuditEntry.objects.create(
            actor=request.user, actor_role=request.user.role,
            action='report.cost_recorded',
            detail=f'{label} for {year:%Y}: ${cost.amount}',
        )
        return Response(ReportedCostSerializer(cost).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class RepaymentSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AwardRepayment
        fields = ('id', 'award', 'amount', 'reason', 'repaid_on',
                  'recorded_by_name', 'created_at')
        read_only_fields = ('id', 'recorded_by_name', 'created_at')

    def get_recorded_by_name(self, repayment) -> str:
        return repayment.recorded_by.full_name if repayment.recorded_by else ''

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('A repayment must be an amount.')
        return value

    def validate_reason(self, value):
        cleaned = (value or '').strip()
        if not cleaned:
            raise serializers.ValidationError(
                'Say why the money came back. The report shows this, and a '
                'repayment nobody can explain is a figure nobody can defend.')
        return cleaned

    def validate(self, attrs):
        award = attrs['award']
        already = sum(
            (row.amount for row in award.repayments.all()), start=0)
        if attrs['amount'] + already > award.amount:
            raise serializers.ValidationError(
                {'amount': f'That is more than the award. ${award.amount} was '
                           f'granted and ${already} has already come back.'})
        return attrs


class RepaymentsView(APIView):
    """Money that came back after it went out."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _may_read(request.user):
            return Response({'detail': 'Not permitted.'},
                            status=status.HTTP_403_FORBIDDEN)
        award_id = request.query_params.get('award')
        rows = AwardRepayment.objects.select_related('recorded_by')
        if award_id:
            rows = rows.filter(award_id=award_id)
        return Response(RepaymentSerializer(rows[:200], many=True).data)

    def post(self, request):
        if not _may_write(request.user):
            return Response({'detail': 'Only an administrator may record a '
                                       'repayment.'},
                            status=status.HTTP_403_FORBIDDEN)
        serializer = RepaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        repayment = serializer.save(recorded_by=request.user)
        AuditEntry.objects.create(
            actor=request.user, actor_role=request.user.role,
            action='report.repayment_recorded',
            detail=f'${repayment.amount} returned on award {repayment.award_id}: '
                   f'{repayment.reason}',
        )
        return Response(RepaymentSerializer(repayment).data,
                        status=status.HTTP_201_CREATED)
