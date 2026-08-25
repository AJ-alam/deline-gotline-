/**
 * What the office sees on opening the portal.
 *
 * Three queues and two flags — the work waiting to be done, not a report on
 * the year. Each queue links to the list filtered to it, so the number is a
 * way into the work rather than a figure to be read and acted on elsewhere.
 */

import { Link } from 'react-router-dom';

import type { DashboardSummary } from '../../api/client';
import { FUNDING_STREAM_LABELS } from '../../api/schema.generated';
import { Badge, Card } from '../../components/ui';
import { formatMoney, statusTone } from '../../components/ui/format';

const STATUS_LABELS: Record<string, string> = {
  draft: 'Draft',
  submitted: 'Submitted',
  under_review: 'Under review',
  info_requested: 'Information requested',
  awaiting_decision: 'Awaiting decision',
  approved: 'Approved',
  declined: 'Declined',
  sent_to_finance: 'Sent to finance',
};

function Stat({
  label,
  value,
  hint,
  to,
}: {
  label: string;
  value: string;
  hint?: string;
  to?: string;
}) {
  const inner = (
    <>
      <div className="stat__label">{label}</div>
      <div className="stat__value">{value}</div>
      {hint && <div className="small muted">{hint}</div>}
    </>
  );
  return to ? (
    <Link to={to} className="stat stat--link">{inner}</Link>
  ) : (
    <div className="stat">{inner}</div>
  );
}

export default function StaffDashboard({ summary }: { summary: DashboardSummary }) {
  const statuses = Object.entries(summary.applications.by_status).filter(([, n]) => n > 0);
  const attention = summary.attention;
  // Rendered whole or not at all: every stream is present even at zero, so a
  // short list would mean the server sent nothing, not that a pot is empty.
  const streams = summary.streams;

  return (
    <main className="page stack stack--loose">
      <h1>Student funding</h1>

      {summary.queues && (
        <Card title="Waiting on the office">
          <div className="stats">
            <Stat label="To review" value={String(summary.queues.to_review)}
                  to="/review?status=submitted" />
            <Stat label="Awaiting decision"
                  value={String(summary.queues.awaiting_decision)}
                  to="/review?status=awaiting_decision" />
            <Stat label="Awaiting enrolment confirmation"
                  value={String(summary.queues.awaiting_enrolment_confirmation)}
                  hint="Tuition cannot be awarded until these return" />
          </div>
        </Card>
      )}

      <div className="stats">
        <Stat label="Applications" value={String(summary.applications.total)}
              hint={`${summary.applications.open} still open`} />
        <Stat label="Awarded" value={formatMoney(summary.money.awarded)} />
        <Stat label="Awaiting payment"
              value={formatMoney(summary.money.awaiting_payment)} />
        <Stat label="Paid" value={formatMoney(summary.money.paid)} />
      </div>

      {/* Counts, not money. An award line carries no stream and could not
          honestly be given one: a rule is gated against every stream the
          applicant qualifies for, and DGGR tops up rather than replaces, so a
          PSSSP application routinely carries DGGR money. A figure here labelled
          DGGR would be read as what DGGR paid, and it is not. */}
      {streams && (
        <Card title="By funding stream">
          <div className="stats">
            {streams.map((row) => (
              <Stat
                key={row.stream}
                label={row.label}
                value={String(row.total)}
                hint={`${row.open} still open`}
                /* Only where the queue can actually filter on it. `stream` is a
                   CharField with choices and no database constraint, and the
                   server filters on the choice set: `?stream=` with a value
                   outside it is a 400, and the queue would drop the filter and
                   show every application in the office. A tile reading 4 that
                   opens a list of 515 is the same lie as the dashboard links
                   that were being ignored — arriving by a different door. */
                to={
                  row.stream in FUNDING_STREAM_LABELS
                    ? `/review?stream=${row.stream}`
                    : undefined
                }
              />
            ))}
          </div>
          <p className="small muted stream-split__note">
            Applications, by the stream their deadline is measured against.
            Pricing draws on every stream an applicant qualifies for, so these
            are not amounts of money.
          </p>
        </Card>
      )}

      {attention && (attention.submitted_late > 0 || attention.residency_mismatch > 0) && (
        <Card title="Needs a look">
          <div className="row">
            {attention.submitted_late > 0 && (
              <Badge tone="warn">{attention.submitted_late} submitted late</Badge>
            )}
            {attention.residency_mismatch > 0 && (
              <Badge tone="warn">{attention.residency_mismatch} residency mismatch</Badge>
            )}
          </div>
        </Card>
      )}

      {statuses.length > 0 && (
        <Card title="By status">
          <div className="row">
            {statuses.map(([status, count]) => (
              <Badge key={status} tone={statusTone(status)}>
                {STATUS_LABELS[status] ?? status}: {count}
              </Badge>
            ))}
          </div>
        </Card>
      )}
    </main>
  );
}
