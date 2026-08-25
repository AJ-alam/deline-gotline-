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
import { Link, useSearchParams } from 'react-router-dom';

import api, {
  type ApplicationStatus,
  type ApplicationSummary,
  type ApplicationType,
  type FundingStream,
} from '../../api/client';
import { APPLICATION_TYPE_LABELS, FUNDING_STREAM_LABELS } from '../../api/schema.generated';
import { Alert, Badge, Button, Card, Field, Select } from '../../components/ui';
import { formatDate, formatMoney, statusTone } from '../../components/ui/format';

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

/**
 * A filter value the query string offered, or nothing.
 *
 * Anything unrecognised is dropped rather than passed on. The server filters on
 * a choice field, so a junk value comes back a 400 and the queue reports itself
 * as unloadable - and reading an unoffered value as though somebody had chosen
 * it is the fault that let a screening answer nobody offered decide a stream.
 */
function offered<T extends string>(value: string | null, allowed: string[]): T | '' {
  return value && allowed.includes(value) ? (value as T) : '';
}

const STATUS_VALUES = STATUSES.map((option) => option.value).filter(Boolean) as string[];

export default function ReviewQueue() {
  const [rows, setRows] = useState<ApplicationSummary[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState('');

  // The filters live in the URL, not in component state. The dashboard links
  // into this queue already filtered - "To review" means status=submitted, a
  // stream tile means that stream - and while the filters were local state
  // every one of those links arrived at an unfiltered list showing everything,
  // with nothing to say the filter had been ignored. Same class as the global
  // DjangoFilterBackend with no filterset_fields: a filter that is silently not
  // applied still answers 200 with the whole list.
  const [params, setParams] = useSearchParams();
  const status = offered<ApplicationStatus>(params.get('status'), STATUS_VALUES);
  const type = offered<ApplicationType>(
    params.get('type'), Object.keys(APPLICATION_TYPE_LABELS));
  const stream = offered<FundingStream>(
    params.get('stream'), Object.keys(FUNDING_STREAM_LABELS));
  const page = Math.max(1, Number(params.get('page')) || 1);

  // Replacing rather than pushing. Narrowing a queue is not somewhere to go
  // back to: pushed, three filter changes put three entries between the
  // reviewer and the screen they arrived from, and Back stops meaning "leave".
  const setPage = useCallback((next: number) => {
    setParams((current) => {
      const updated = new URLSearchParams(current);
      if (next <= 1) updated.delete('page');
      else updated.set('page', String(next));
      return updated;
    }, { replace: true });
  }, [setParams]);

  // Changing a filter returns to the first page: page 4 of one filter is
  // routinely past the end of another, and an empty page reads as no work.
  const setFilter = useCallback((key: string, value: string) => {
    setParams((current) => {
      const updated = new URLSearchParams(current);
      if (value) updated.set(key, value);
      else updated.delete(key);
      updated.delete('page');
      return updated;
    }, { replace: true });
  }, [setParams]);

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
        ...(stream ? { stream } : {}),
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
  }, [page, status, type, stream, reloads]);

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
              onChange={(e) => setFilter('status', e.target.value)}
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
              onChange={(e) => setFilter('type', e.target.value)}
            >
              <option value="">Any type</option>
              {Object.entries(APPLICATION_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
          {/* The primary stream - the one whose deadline the submission was
              measured against. Pricing draws on every stream the applicant
              qualifies for, so this narrows the queue and says nothing about
              which pot paid. */}
          <Field id="filter-stream" label="Funding stream">
            <Select
              id="filter-stream"
              value={stream}
              onChange={(e) => setFilter('stream', e.target.value)}
            >
              <option value="">Any stream</option>
              {Object.entries(FUNDING_STREAM_LABELS).map(([value, label]) => (
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
                  <th>Enrolment</th>
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
                      {/* Tuition is funded against the registrar's figure, so a
                          row that is not confirmed cannot be forwarded. Saying
                          so here saves opening it to find out. */}
                      {row.enrolment.required ? (
                        <Badge tone={row.enrolment.confirmed ? 'ok' : 'warn'}>
                          {row.enrolment.label}
                        </Badge>
                      ) : (
                        <span className="small muted">&mdash;</span>
                      )}
                    </td>
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
          <Button size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>
            Previous
          </Button>
          <Button
            size="sm"
            disabled={rows !== null && page * 50 >= total}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </main>
  );
}
