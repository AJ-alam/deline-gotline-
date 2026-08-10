/**
 * The opening screen.
 *
 * One request. The screen this replaces fetched seven endpoints every thirty
 * seconds, pulled every application with every answer, and counted them in the
 * browser — so it grew slower with every application the office received.
 */

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import api, { type DashboardSummary } from '../../api/client';
import { Alert, Badge, Card } from '../../components/ui';
import { formatMoney, statusTone } from '../../components/ui/format';

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="stat">
      <div className="stat__label">{label}</div>
      <div className="stat__value">{value}</div>
      {hint && <div className="small muted">{hint}</div>}
    </div>
  );
}

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

export default function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    api
      .dashboard()
      .then((result) => !cancelled && setSummary(result))
      .catch(() => !cancelled && setError('The summary could not be loaded.'));
    return () => { cancelled = true; };
  }, []);

  if (error) return <main className="page"><Alert tone="error">{error}</Alert></main>;
  if (!summary) {
    return (
      <main className="page">
        <div className="spinner" role="status" aria-label="Loading summary" />
      </main>
    );
  }

  const isStaff = summary.scope === 'staff';
  const statuses = Object.entries(summary.applications.by_status).filter(([, n]) => n > 0);

  return (
    <main className="page stack stack--loose">
      <h1>{isStaff ? 'Student funding' : 'Your funding'}</h1>

      {summary.waiting_on_you ? (
        <Alert tone="error">
          {summary.waiting_on_you} of your applications need more information from you.{' '}
          <Link to="/applications">Open them</Link>.
        </Alert>
      ) : null}

      <div className="stats">
        <Stat label="Applications" value={String(summary.applications.total)}
              hint={`${summary.applications.open} still open`} />
        <Stat label="Awarded" value={formatMoney(summary.money.awarded)} />
        {isStaff ? (
          <>
            <Stat label="Awaiting payment"
                  value={formatMoney(summary.money.awaiting_payment)} />
            <Stat label="Sent to finance"
                  value={formatMoney(summary.money.sent_to_finance)} />
          </>
        ) : (
          <Stat label="Paid" value={formatMoney(summary.money.paid)} />
        )}
      </div>

      {isStaff && summary.queues && (
        <Card title="Waiting on the office">
          <div className="stats">
            <Stat label="To review" value={String(summary.queues.to_review)} />
            <Stat label="Awaiting decision"
                  value={String(summary.queues.awaiting_decision)} />
            <Stat label="Awaiting enrolment confirmation"
                  value={String(summary.queues.awaiting_enrolment_confirmation)}
                  hint="Tuition cannot be awarded until these return" />
          </div>
        </Card>
      )}

      {isStaff && summary.attention &&
        (summary.attention.submitted_late > 0 ||
          summary.attention.residency_mismatch > 0) && (
        <Card title="Needs a look">
          <div className="row">
            {summary.attention.submitted_late > 0 && (
              <Badge tone="warn">{summary.attention.submitted_late} submitted late</Badge>
            )}
            {summary.attention.residency_mismatch > 0 && (
              <Badge tone="warn">
                {summary.attention.residency_mismatch} residency mismatch
              </Badge>
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
