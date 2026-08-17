/**
 * A student's own applications, and what else they can apply for.
 *
 * A card list rather than a table. The staff queue is a table because it is
 * scanned by people who use it daily; this is read a few times a year by
 * someone who is not practised at it, and a row of four columns is harder to
 * follow than a labelled block. It also survives a narrow screen without
 * sideways scrolling.
 *
 * Filtering is done in the database, not by pulling everything down and
 * filtering in the browser, and a slow response for one filter cannot land
 * after a newer one and overwrite it.
 */

import { useEffect, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';

import api, {
  type ApplicationSchema,
  type ApplicationStatus,
  type ApplicationSummary,
  type CurrentUser,
} from '../../api/client';
import Icon from '../../app/icons';
import { Alert, Badge, Card } from '../../components/ui';
import { formatDate, formatMoney, statusTone } from '../../components/ui/format';
import './applications.css';

/** The filters a student would actually want, in their words. */
const FILTERS: Array<{ value: ApplicationStatus | ''; label: string }> = [
  { value: '', label: 'All' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'under_review', label: 'Being reviewed' },
  { value: 'info_requested', label: 'Needs your reply' },
  { value: 'approved', label: 'Approved' },
  { value: 'declined', label: 'Declined' },
];

export default function Applications() {
  /**
   * This is the student's own list. Staff have a queue of everybody's at
   * /review, which is where their navigation points — but nothing stopped one
   * arriving here, and what they got was the student's page: "My applications",
   * "Everything you have submitted", and an invitation to apply for funding.
   * With a populated database it read as a plausible queue; on an empty one it
   * told a support worker to start their own admission application.
   */
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [rows, setRows] = useState<ApplicationSummary[] | null>(null);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<ApplicationStatus | ''>('');
  const [schemas, setSchemas] = useState<ApplicationSchema[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    api.me().then((user) => !cancelled && setMe(user)).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    api
      .applications(status ? { status } : undefined)
      .then((page) => {
        if (cancelled) return;
        setRows(page.results);
        setTotal(page.count);
        setError('');
      })
      .catch(() => {
        if (cancelled) return;
        setError('Your applications could not be loaded.');
        setRows([]);
      });
    return () => { cancelled = true; };
  }, [status]);

  useEffect(() => {
    let cancelled = false;
    api
      .schemas()
      .then((available) => !cancelled && setSchemas(available))
      .catch(() => { /* The list of things to apply for is not worth an error. */ });
    return () => { cancelled = true; };
  }, []);

  // Which forms a student may start is the schema's own answer, not a list of
  // exceptions kept here: the enrolment verification is the registrar's form.
  const canApplyFor = schemas.filter((schema) => schema.apply_in_portal);

  // Sent to the queue they came for. Rendered nothing in the meantime rather
  // than the student's page for a frame.
  if (me && me.role !== 'student') return <Navigate to="/review" replace />;

  return (
    <main className="page stack stack--loose">
      <header className="page-head">
        <div>
          <h1>My applications</h1>
          <p className="muted">
            Everything you have submitted, and how far along it is.
          </p>
        </div>
        <Link to="/apply/admission" className="page-head__action">
          <Icon name="newApplication" width="18" height="18" />
          Start an application
        </Link>
      </header>

      {error && <Alert tone="error">{error}</Alert>}

      {/* Hidden until there is something to filter: a row of filters above an
          empty list is furniture. */}
      {(rows === null || rows.length > 0 || status !== '') && (
        <div className="filters" role="group" aria-label="Filter by status">
          {FILTERS.map((filter) => (
            <button
              key={filter.value}
              type="button"
              className={`chip ${status === filter.value ? 'chip--on' : ''}`.trim()}
              aria-pressed={status === filter.value}
              onClick={() => setStatus(filter.value)}
            >
              {filter.label}
            </button>
          ))}
        </div>
      )}

      {rows === null ? (
        <div className="spinner" role="status" aria-label="Loading applications" />
      ) : rows.length === 0 ? (
        <Card>
          <div className="empty">
            <Icon name="inbox" width="40" height="40" className="empty__icon" />
            <p className="empty__title">
              {status ? 'Nothing with that status' : 'No applications yet'}
            </p>
            <p className="empty__detail">
              {status
                ? 'Try another filter, or choose All to see everything.'
                : 'Start with the admission application — it establishes your file and decides what else you can apply for.'}
            </p>
          </div>
        </Card>
      ) : (
        <>
          <ul className="app-list">
            {rows.map((row) => (
              <li key={row.id}>
                <Link to={`/applications/${row.id}`} className="app-card">
                  <span className="app-card__icon" aria-hidden="true">
                    <Icon name="applications" width="20" height="20" />
                  </span>

                  <span className="app-card__body">
                    <span className="app-card__title">{row.type_label}</span>
                    <span className="app-card__when">
                      Submitted {formatDate(row.submitted_at)}
                    </span>
                  </span>

                  <span className="app-card__side">
                    {Number(row.awarded_total) > 0 && (
                      <span className="app-card__amount">
                        {formatMoney(row.awarded_total)}
                      </span>
                    )}
                    <Badge tone={statusTone(row.status)}>{row.status_label}</Badge>
                    {row.submitted_after_deadline && <Badge tone="warn">Late</Badge>}
                  </span>

                  <Icon name="arrowRight" width="18" height="18" className="app-card__go" />
                </Link>
              </li>
            ))}
          </ul>
          <p className="small muted">
            {total} application{total === 1 ? '' : 's'}
            {status ? ' with this status' : ''}.
          </p>
        </>
      )}

      <section className="stack">
        <h2>Apply for funding</h2>
        <div className="apply-grid">
          {canApplyFor.map((schema) => (
            <Link key={schema.slug} to={`/apply/${schema.slug}`} className="apply-card">
              <span className="apply-card__title">{schema.label}</span>
              {schema.summary && (
                <span className="apply-card__summary">{schema.summary}</span>
              )}
              <span className="apply-card__go">
                Start
                <Icon name="arrowRight" width="16" height="16" />
              </span>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
