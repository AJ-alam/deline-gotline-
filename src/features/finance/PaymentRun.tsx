/**
 * The payment run.
 *
 * Finance sees what is ready, what is blocked and why, before committing to a
 * dispatch — rather than discovering afterwards that four students were missing
 * from the file.
 */

import { useCallback, useEffect, useState } from 'react';

import api, { ApiError, type PaymentRun as Run } from '../../api/client';
import { Alert, Badge, Button, Card } from '../../components/ui';
import { formatMoney } from '../../components/ui/format';
import { groupBlocked } from './blocked';

export default function PaymentRun() {
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState('');
  const [sent, setSent] = useState('');
  const [busy, setBusy] = useState(false);
  const [reloads, setReloads] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .paymentRun()
      .then((result) => {
        if (cancelled) return;
        setRun(result);
        setError('');
      })
      .catch((err) => {
        if (cancelled) return;
        setError(
          err instanceof ApiError && err.status === 403
            ? 'Only Finance can open the payment run.'
            : 'The payment run could not be loaded.',
        );
      });
    return () => {
      cancelled = true;
    };
  }, [reloads]);

  const refresh = useCallback(() => setReloads((n) => n + 1), []);

  const dispatch = async () => {
    setBusy(true);
    setError('');
    setSent('');
    try {
      const result = await api.dispatchPaymentRun();

      // Hand the file straight to the browser; the run is already recorded
      // server-side, so a failed download does not mean an unsent batch.
      const url = URL.createObjectURL(new Blob([result.csv], { type: 'text/csv' }));
      const link = document.createElement('a');
      link.href = url;
      link.download = result.filename;
      link.click();
      URL.revokeObjectURL(url);

      setSent(
        `${result.count} award${result.count === 1 ? '' : 's'} sent, ` +
          `totalling ${formatMoney(result.total)}.` +
          (result.blocked > 0
            ? ` ${result.blocked} could not be sent and remain pending.`
            : ''),
      );
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The batch could not be sent.');
    } finally {
      setBusy(false);
    }
  };

  if (error && !run) {
    return (
      <main className="page">
        <Alert tone="error">{error}</Alert>
      </main>
    );
  }
  if (!run) {
    return (
      <main className="page">
        <div className="spinner" role="status" aria-label="Loading payment run" />
      </main>
    );
  }

  return (
    <main className="page stack stack--loose">
      <header className="row row--between">
        <div className="stack stack--tight">
          <h1>Payment run</h1>
          <p className="muted">
            Approved awards waiting to be paid. Each is sent once.
          </p>
        </div>
        <Button onClick={refresh}>Refresh</Button>
      </header>

      {error && <Alert tone="error">{error}</Alert>}
      {sent && <Alert tone="ok">{sent}</Alert>}

      {/* Not a wall of red. Banking is required on every form that pays out,
          so "no bank account on file" is no longer a thing the office reads
          about weeks later on a screen the applicant never sees - it is asked
          for where the person who knows the answer is sitting. What remains
          here is rare and genuinely needs a person: a release of funds to
          somebody else, a guest claim with no account attached yet, an award
          whose pricing went missing. Reported quietly and never dropped,
          because a payment missing from the file is a person who does not get
          paid - the reason this list exists at all. */}
      {run.blocked.length > 0 && (() => {
        const groups = groupBlocked(run.blocked);
        return (
          <Card title={`${formatMoney(run.blocked_total)} needs a person before it can be paid`}>
            <ul className="stack stack--tight small">
              {groups.map((group) => (
                <li key={group.key}>
                  Application #{group.application_id} — {group.reason}
                </li>
              ))}
            </ul>
          </Card>
        );
      })()}

      <Card
        title={`Ready to pay — ${formatMoney(run.total)}`}
        actions={
          <Button
            variant="primary"
            busy={busy}
            disabled={run.count === 0}
            onClick={() => void dispatch()}
          >
            Send {run.count} payment{run.count === 1 ? '' : 's'} to finance
          </Button>
        }
      >
        {run.count === 0 ? (
          <p className="muted">Nothing is ready to pay.</p>
        ) : (
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Application</th>
                  <th>Covers</th>
                  {/* Where it is going, beside what is going. The account was
                      in the dispatched CSV and nowhere else, so checking a
                      transit number meant sending the batch first — and every
                      award in a sent batch is marked paid and cannot go
                      again. */}
                  <th>Paying into</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {run.awards.map((award) => (
                  <tr key={award.id}>
                    <td>{award.student}</td>
                    <td>
                      <Badge tone="neutral">#{award.application_id}</Badge>
                    </td>
                    <td>
                      {award.category}
                      {award.lines > 1 && (
                        <span className="muted small"> ({award.lines} lines)</span>
                      )}
                    </td>
                    <td className="small">
                      {award.account}
                      <span className="muted">
                        {' '}
                        · {award.transit_number}-{award.institution_number}
                      </span>
                      <br />
                      <span className="muted">{award.account_holder}</span>
                    </td>
                    <td className="num">{formatMoney(award.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </main>
  );
}
