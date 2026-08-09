/**
 * The staff queue.
 *
 * Replaces the applications view inside a 6,966-line component that held 94
 * pieces of state and fetched seven endpoints every thirty seconds, two of them
 * for the same records under two different models.
 *
 * One request, filtered server-side. The row carries no answers and no history,
 * because a queue is scanned rather than read.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import api, {
  type ApplicationStatus,
  type ApplicationSummary,
  type ApplicationType,
} from '../api/client';
import { APPLICATION_TYPE_LABELS } from '../api/schema.generated';
import { Alert, Badge, Button, Card, Field, Select } from '../components/ui';
import { formatDate, formatMoney, statusTone } from '../components/ui/format';

const STATUSES: Array<{ value: ApplicationStatus | ''; label: string }> = [
  { value: '', label: 'Any status' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'under_review', label: 'Under review' },
  { value: 'info_requested', label: 'Information requested' },
  { value: 'awaiting_decision', label: 'Awaiting decision' },
  { value: 'approved', label: 'Approved' },
  { value: 'declined', label: 'Declined' },
  { value: 'sent_to_finance', label: 'Sent to finance' },
];

export default function ReviewQueue() {
  const [rows, setRows] = useState<ApplicationSummary[] | null>(null);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<ApplicationStatus | ''>('');
  const [type, setType] = useState<ApplicationType | ''>('');
  const [page, setPage] = useState(1);
  const [error, setError] = useState('');

  const [reloads, setReloads] = useState(0);

  useEffect(() => {
    // Guarded against a slow response for one set of filters landing after a
    // newer one and overwriting it.
    let cancelled = false;

    // Filtering happens in the database against an index, not by pulling
    // everything down and filtering in the browser.
    api
      .applications({
        page,
        ...(status ? { status } : {}),
        ...(type ? { type } : {}),
      })
      .then((result) => {
        if (cancelled) return;
        setRows(result.results);
        setTotal(result.count);
        setError('');
      })
      .catch(() => {
        if (cancelled) return;
        setError('The queue could not be loaded.');
        setRows([]);
      });

    return () => {
      cancelled = true;
    };
  }, [page, status, type, reloads]);

  const refresh = useCallback(() => setReloads((n) => n + 1), []);

  return (
    <main className="page stack stack--loose">
      <header className="row row--between">
        <h1>Applications</h1>
        <Button onClick={refresh}>Refresh</Button>
      </header>

      {error && <Alert tone="error">{error}</Alert>}

      <Card>
        <div className="grid-2">
          <Field id="filter-status" label="Status">
            <Select
              id="filter-status"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value as ApplicationStatus | '');
                setPage(1);
              }}
            >
              {STATUSES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field id="filter-type" label="Application type">
            <Select
              id="filter-type"
              value={type}
              onChange={(e) => {
                setType(e.target.value as ApplicationType | '');
                setPage(1);
              }}
            >
              <option value="">Any type</option>
              {Object.entries(APPLICATION_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
        </div>
      </Card>

      {rows === null ? (
        <div className="spinner" role="status" aria-label="Loading applications" />
      ) : rows.length === 0 ? (
        <Card>
          <p className="muted">No applications match these filters.</p>
        </Card>
      ) : (
        <Card>
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>Applicant</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Submitted</th>
                  <th>Awarded</th>
                  <th>Flags</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <Link to={`/review/${row.id}`}>{row.student_name ?? 'Unknown'}</Link>
                    </td>
                    <td>{row.type_label}</td>
                    <td>
                      <Badge tone={statusTone(row.status)}>{row.status_label}</Badge>
                    </td>
                    <td>{formatDate(row.submitted_at)}</td>
                    <td className="num">{formatMoney(row.awarded_total)}</td>
                    <td>
                      <div className="row">
                        {row.submitted_after_deadline && <Badge tone="warn">Late</Badge>}
                        {row.residency_flag && <Badge tone="warn">Residency</Badge>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <div className="row row--between">
        <span className="small muted">
          {total} application{total === 1 ? '' : 's'}
        </span>
        <div className="row">
          <Button size="sm" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
            Previous
          </Button>
          <Button
            size="sm"
            disabled={rows !== null && page * 50 >= total}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </main>
  );
}
