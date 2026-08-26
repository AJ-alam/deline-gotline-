/**
 * One application: what was asked, what happened to it, and what it was awarded.
 *
 * The award breakdown shows the rule behind every line and the rules that did
 * not fire. Staff previously saw a total with no explanation, which is not
 * something anyone can defend to an applicant on appeal.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import api, {
  ApiError,
  type Application,
  type ApplicationSchema,
  type AttachedDocument,
  type CurrentUser,
  type DecisionTrace,
  type SchemaField,
  type TransitionAction,
} from '../../api/client';
// Emitted from funding.services.workflow.ALLOWED_ACTIONS. This screen used to
// carry its own copy, which is how the office's ability to approve a reviewed
// application without forwarding it reached the server and never reached a
// button.
import {
  AWARDED_STATUSES,
  DECIDED_STATUSES,
  NEXT_ACTIONS,
} from '../../api/schema.generated';
import { Alert, Badge, Button, Card, Field, Input, Textarea } from '../../components/ui';
import { formatDate, formatMoney, statusTone } from '../../components/ui/format';
import AmendForm from './AmendForm';
import AwardEditor from './AwardEditor';
import ReviseForm from './ReviseForm';

const ACTION_LABELS: Record<TransitionAction, string> = {
  submitted: 'Submit',
  reviewed: 'Mark reviewed',
  info_requested: 'Request more information',
  info_provided: 'Information received',
  forwarded: 'Forward to Director',
  approved: 'Approve',
  declined: 'Decline',
  sent_to_finance: 'Send to finance',
};

const DECIDING: TransitionAction[] = ['approved', 'declined'];

/**
 * Actions that are meaningless without words.
 *
 * "More information needed" with no note reaches the student as "Please review
 * your application" — a request to guess. The server has carried the note since
 * this path existed; the screen never collected one.
 */
const NEEDS_NOTE: TransitionAction[] = ['info_requested', 'declined'];

/**
 * One stored answer, shown as the question was asked.
 *
 * Two of the field types hold a list. A reviewer was shown `[object Object]`
 * for an expense breakdown and the literal text `document:12` for a receipt —
 * both of which mean the answer is on file and unreadable, which is the same as
 * not having it.
 */
function Answer({ field, raw }: { field: SchemaField; raw: unknown }) {
  if (field.type === 'table' && Array.isArray(raw)) {
    return (
      <table className="answers__table">
        <thead>
          <tr>
            {field.columns.map((column) => (
              <th key={column.key} scope="col">{column.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {(raw as Array<Record<string, unknown>>).map((row, index) => (
            <tr key={index}>
              {field.columns.map((column) => (
                <td key={column.key} data-label={column.label}>
                  <Answer field={column} raw={row[column.key]} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  if (field.type === 'files' && Array.isArray(raw)) {
    return <span>{raw.length} {raw.length === 1 ? 'file' : 'files'} attached</span>;
  }

  if (raw === undefined || raw === null || raw === '') return <span className="muted">—</span>;

  if (field.type === 'choice') {
    return <span>{field.choices.find((c) => c.value === raw)?.label ?? String(raw)}</span>;
  }
  if (field.type === 'boolean') return <span>{raw ? 'Yes' : 'No'}</span>;
  // Without this a reviewer read the literal word 'true' against the declaration.
  if (field.type === 'confirm') return <span>{raw ? 'Confirmed' : 'Not confirmed'}</span>;
  if (field.type === 'money') return <span>${String(raw)}</span>;
  return <span>{String(raw)}</span>;
}

/** The question a document answers, as it was asked. */
function labelFor(schema: ApplicationSchema | null, key: string): string {
  return schema?.fields.find((field) => field.key === key)?.label || key;
}

function AnswerList({
  application,
  schema,
}: {
  application: Application;
  schema: ApplicationSchema | null;
}) {
  // Labels come from the schema so the screen shows the question as it was
  // asked, while the stored answer stays keyed by its stable key.
  const fields = schema?.fields ?? [];
  const answered = fields.filter((field) => application.answers[field.key] !== undefined);

  if (answered.length === 0) return <p className="muted">No answers recorded.</p>;

  const bySection = new Map<string, typeof answered>();
  for (const field of answered) {
    const section = field.section || 'Details';
    if (!bySection.has(section)) bySection.set(section, []);
    bySection.get(section)!.push(field);
  }

  return (
    <div className="stack stack--loose">
      {[...bySection.entries()].map(([section, sectionFields]) => (
        <div key={section} className="stack stack--tight">
          <h3>{section}</h3>
          <dl className="answers">
            {sectionFields.map((field) => (
              <div key={field.key} className="answers__row">
                <dt>{field.label}</dt>
                <dd><Answer field={field} raw={application.answers[field.key]} /></dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
    </div>
  );
}

function DecisionBreakdown({ trace }: { trace: DecisionTrace }) {
  const applied = trace.rules.filter((rule) => rule.applied && Number(rule.amount) > 0);
  const skipped = trace.rules.filter((rule) => !applied.includes(rule));

  return (
    <div className="stack">
      {trace.missing_rates.length > 0 && (
        <Alert tone="error">
          Not all rates are configured: {trace.missing_rates.join(', ')}. This award cannot
          be recorded until they are set.
        </Alert>
      )}

      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th>Award</th>
              <th>Amount</th>
              <th>Why</th>
            </tr>
          </thead>
          <tbody>
            {applied.map((rule) => (
              <tr key={rule.code}>
                <td>{rule.description}</td>
                <td className="num">{formatMoney(rule.amount)}</td>
                <td className="small muted">{rule.reason}</td>
              </tr>
            ))}
            <tr>
              <td>
                <strong>Total</strong>
              </td>
              <td className="num">
                <strong>{formatMoney(trace.total)}</strong>
              </td>
              <td className="small muted">Priced under {trace.rule_set}</td>
            </tr>
          </tbody>
        </table>
      </div>

      {skipped.length > 0 && (
        <details>
          <summary className="small muted">
            {skipped.length} rule{skipped.length === 1 ? '' : 's'} did not apply
          </summary>
          <ul className="stack stack--tight small muted">
            {skipped.map((rule) => (
              <li key={rule.code}>
                <strong>{rule.description}</strong> — {rule.reason}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

export default function ApplicationDetail() {
  const { id } = useParams<{ id: string }>();
  const applicationId = Number(id);

  const [application, setApplication] = useState<Application | null>(null);
  const [schema, setSchema] = useState<ApplicationSchema | null>(null);
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [preview, setPreview] = useState<DecisionTrace | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [amending, setAmending] = useState(false);
  const [editingAward, setEditingAward] = useState(false);
  /** The action waiting on a note, and the note being typed for it. */
  const [asking, setAsking] = useState<TransitionAction | null>(null);
  const [note, setNote] = useState('');
  const [registrarEmail, setRegistrarEmail] = useState('');
  // What an administrator has chosen to look at. Held here rather than fetched
  // with the application: the detail endpoint masks both on purpose, and
  // reading the real values writes an audit entry — one per page load would
  // make that log unable to answer who actually looked at whose file.
  const [revealed, setRevealed] = useState<{
    identifiers: Record<string, string>;
    bank_account: {
      account_holder: string;
      transit_number: string;
      institution_number: string;
      account_number: string;
      source: 'account' | 'held';
    } | null;
  } | null>(null);
  const [revealing, setRevealing] = useState(false);
  const [revealError, setRevealError] = useState('');

  const load = useCallback(async () => {
    try {
      const [detail, user] = await Promise.all([api.application(applicationId), api.me()]);
      setApplication(detail);
      setMe(user);
      setSchema(await api.schema(detail.schema_slug));
    } catch {
      setError('This application could not be loaded.');
    }
  }, [applicationId]);

  useEffect(() => {
    void load();
  }, [load]);

  const act = async (action: TransitionAction, actionNote = '') => {
    setBusy(action);
    setError('');
    setNotice('');
    try {
      setApplication(await api.transition(applicationId, action, actionNote));
      setAsking(null);
      setNote('');
      setNotice(`Recorded: ${ACTION_LABELS[action]}.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'That action could not be recorded.');
    } finally {
      setBusy(null);
    }
  };

  const runPreview = async () => {
    setBusy('preview');
    setError('');
    try {
      setPreview(await api.previewDecision(applicationId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The award could not be previewed.');
    } finally {
      setBusy(null);
    }
  };

  /**
   * The tab is opened before the request, not after it: a window opened once an
   * await has resolved is a pop-up as far as the browser is concerned, and gets
   * blocked. The document itself has to be fetched rather than linked, because
   * the endpoint is authorised by the bearer token and a navigation carries none.
   */
  const openDocument = async (document: AttachedDocument) => {
    const tab = window.open('', '_blank');
    try {
      const blob = await api.openDocument(document.url);
      const href = URL.createObjectURL(blob);
      if (tab) tab.location.href = href;
      else window.location.href = href;
    } catch (err) {
      tab?.close();
      setError(err instanceof ApiError ? err.message : 'That document could not be opened.');
    }
  };

  const askInstitution = async () => {
    setBusy('enrolment');
    setError('');
    setNotice('');
    try {
      setApplication(await api.requestEnrolment(applicationId, registrarEmail.trim()));
      setRegistrarEmail('');
      setNotice('The institution has been asked to confirm this enrolment.');
    } catch (err) {
      setError(err instanceof ApiError
        ? (err.fieldErrors.registrar_email ?? err.message)
        : 'That request could not be sent.');
    } finally {
      setBusy(null);
    }
  };

  const record = async () => {
    setBusy('price');
    setError('');
    try {
      await api.recordDecision(applicationId);
      setNotice('Award recorded.');
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The award could not be recorded.');
    } finally {
      setBusy(null);
    }
  };

  if (error && !application) {
    return (
      <main className="page">
        <Alert tone="error">{error}</Alert>
      </main>
    );
  }
  if (!application || !me) {
    return (
      <main className="page">
        <div className="spinner" role="status" aria-label="Loading application" />
      </main>
    );
  }

  const canReview = me.role === 'support_worker' || me.role === 'admin';
  const canDecide = me.role === 'director' || me.role === 'admin';
  const available = (NEXT_ACTIONS[application.status] ?? []).filter((action) =>
    DECIDING.includes(action) ? canDecide : canReview,
  );
  // Administrators only, and never on an application already decided: its
  // answers are the record the decision was made from. Both rules are the
  // server's; repeated here so the button is not offered where it would fail.
  const canAmend =
    me.role === 'admin' &&
    !DECIDED_STATUSES.includes(application.status);
  // The award editor's rule is not the amendment rule. The server refuses a
  // hand-set award only on a declined application - an approved one stays
  // editable until the money is paid, which is the whole point of the editor.
  // Borrowing `canAmend` hid the button on exactly the two statuses where an
  // award exists, and offered it on the ones where there is nothing to seed
  // it with, so the editor could only ever open empty and save over the
  // breakdown.
  const canEditAward =
    me.role === 'admin' &&
    application.status !== 'declined' &&
    Boolean(application.decision);

  // Administrators only, matching the server. A support worker assesses these
  // and does not read regulated identifiers; finance is paid from the file the
  // payment run builds rather than from a screen.
  const canReveal = me.role === 'admin';
  const hasIdentifiers = Object.keys(application.identifiers ?? {}).length > 0;
  const reveal = async () => {
    setRevealing(true);
    setRevealError('');
    try {
      setRevealed(await api.readIdentifiers(application.id));
    } catch {
      setRevealError('Those details could not be read.');
    } finally {
      setRevealing(false);
    }
  };

  return (
    <main className="page stack stack--loose">
      <header className="stack stack--tight">
        <div className="row row--between">
          <h1>{application.type_label}</h1>
          <div className="row">
            {/* Secondary, not ghost. This is the office rewriting a filed
                application on the applicant's behalf — the same weight of
                action as "Edit breakdown" below it, and it was the only
                control on the page drawn with no border, no background and
                muted text. Beside a status badge that reads as a caption
                rather than as something you can press. Sized to match every
                other action here, which are all `sm`; at the default size it
                was simultaneously the least visible and the largest. */}
            {canAmend && !amending && (
              <Button variant="secondary" size="sm" onClick={() => setAmending(true)}>
                Edit application
              </Button>
            )}
            <Badge tone={statusTone(application.status)}>{application.status_label}</Badge>
          </div>
        </div>
        <p className="muted">
          {application.student_name} · submitted {formatDate(application.submitted_at)}
        </p>
      </header>

      {amending && schema && (
        <AmendForm
          application={application}
          schema={schema}
          onCancel={() => setAmending(false)}
          onDone={async () => {
            setAmending(false);
            setNotice('Saved. The applicant has been told what changed.');
            await load();
          }}
        />
      )}

      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="ok">{notice}</Alert>}

      {available.length > 0 && (
        <Card title="Actions">
          <div className="stack">
            <div className="row">
              {available.map((action) => (
                <Button
                  key={action}
                  variant={action === 'declined' ? 'danger' : 'primary'}
                  busy={busy === action}
                  onClick={() => (NEEDS_NOTE.includes(action)
                    ? setAsking(action)
                    : void act(action))}
                >
                  {ACTION_LABELS[action]}
                </Button>
              ))}
            </div>

            {/* Asking for more information without saying what is needed sends
                the student a notice that reads "Please review your
                application." The server has always carried the note; nothing
                ever collected one. Declining carries its reason the same way. */}
            {asking && (
              <div className="stack stack--tight">
                <Field
                  id="action-note"
                  label={asking === 'declined'
                    ? 'Why is this being declined?'
                    : 'What do you need from the applicant?'}
                  hint="Sent to the applicant, by email and in the portal."
                >
                  <Textarea
                    id="action-note"
                    rows={3}
                    value={note}
                    autoFocus
                    placeholder={asking === 'declined'
                      ? 'The programme is under twelve weeks.'
                      : 'Please attach your transcript for the Fall term.'}
                    onChange={(e) => setNote(e.target.value)}
                  />
                </Field>
                <div className="row">
                  <Button
                    variant={asking === 'declined' ? 'danger' : 'primary'}
                    busy={busy === asking}
                    disabled={!note.trim()}
                    onClick={() => void act(asking, note)}
                  >
                    {asking === 'declined' ? 'Decline application' : 'Send request'}
                  </Button>
                  <Button variant="ghost" onClick={() => { setAsking(null); setNote(''); }}>
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </div>
        </Card>
      )}

      <Card
        title="Award"
        actions={
          <div className="row">
            {/* Only once there is an approval to congratulate somebody on. The
                letter is emailed at the moment of the decision; this is where
                it is read again, and where the office opens the copy the
                student was sent rather than describing it down the phone. */}
            {AWARDED_STATUSES.includes(application.status) && application.decision && (
              <Link className="btn btn--secondary btn--sm" to={`/applications/${application.id}/approval-letter`}>
                Approval letter
              </Link>
            )}
            {(canReview || canDecide) && (
              <Button size="sm" busy={busy === 'preview'} onClick={() => void runPreview()}>
                Preview
              </Button>
            )}
            {canEditAward && !editingAward && (
              <Button size="sm" onClick={() => setEditingAward(true)}>
                Edit breakdown
              </Button>
            )}
            {canDecide && (
              <Button size="sm" variant="primary" busy={busy === 'price'} onClick={() => void record()}>
                Record award
              </Button>
            )}
          </div>
        }
      >
        {editingAward ? (
          <AwardEditor
            application={application}
            onCancel={() => setEditingAward(false)}
            onDone={async () => {
              setEditingAward(false);
              setNotice('The breakdown was saved.');
              await load();
            }}
          />
        ) : application.decision ? (
          <div className="stack">
            {/* A recorded decision is a pricing. It only becomes an award when
                somebody approves the application, and until then saying so is
                the difference between "here is what you would get" and "here
                is what you have been given". A student was shown a breakdown
                on an application still under review, and again after it was
                declined, with nothing on the screen distinguishing either from
                money that had been granted. The figures stay — an appeal is
                argued from them — and the sentence above them changes.

                `info`, not `error`: neither state is a fault. The status badge
                already says the application was declined; this is explaining
                what the figures underneath it are. */}
            {!AWARDED_STATUSES.includes(application.status) && (
              <Alert tone="info">
                {application.status === 'declined'
                  ? 'This application was declined. The breakdown below is what it '
                    + 'was priced at and is not being paid — it is kept so the '
                    + 'decision can be explained if you appeal.'
                  : 'Nothing has been awarded yet. This is what the rules work out '
                    + 'for the answers on file, and it can still change — it '
                    + 'becomes an award only once the application is approved.'}
              </Alert>
            )}
            <DecisionBreakdown trace={application.decision.trace} />
          </div>
        ) : preview ? (
          <div className="stack">
            <Alert tone="info">Preview only — nothing has been recorded.</Alert>
            <DecisionBreakdown trace={preview} />
          </div>
        ) : (
          <p className="muted">No award has been recorded for this application.</p>
        )}
      </Card>

      {/* Whether this can be paid. Masked by default, because a review screen
          that carries an account number puts it in every staff response and
          every browser cache. An administrator can read the real one — the
          office does need it, and until this control existed there was no way
          to see it at all from anywhere in the portal. */}
      <Card
        title="Payment"
        actions={
          canReveal && (application.banking.on_file || hasIdentifiers) ? (
            <Button busy={revealing} onClick={() => void reveal()}>
              {revealed ? 'Refresh details' : 'Show full details'}
            </Button>
          ) : undefined
        }
      >
        {application.banking.on_file ? (
          <div className="stack stack--tight">
            <div className="row">
              <Badge tone="ok">Account on file</Badge>
              <span className="small muted">
                {revealed?.bank_account
                  ? `${revealed.bank_account.account_number} · ${revealed.bank_account.account_holder}`
                  : `${application.banking.account}${
                      application.banking.holder ? ` · ${application.banking.holder}` : ''
                    }`}
                {application.banking.held
                  && ' · held until this application is attached to an account'}
              </span>
            </div>
            {revealed?.bank_account && (
              <dl className="answers">
                <div className="answers__row">
                  <dt>Account holder</dt>
                  <dd>{revealed.bank_account.account_holder}</dd>
                </div>
                <div className="answers__row">
                  <dt>Transit number</dt>
                  <dd>{revealed.bank_account.transit_number}</dd>
                </div>
                <div className="answers__row">
                  <dt>Institution number</dt>
                  <dd>{revealed.bank_account.institution_number}</dd>
                </div>
                <div className="answers__row">
                  <dt>Account number</dt>
                  <dd>{revealed.bank_account.account_number}</dd>
                </div>
              </dl>
            )}
          </div>
        ) : (
          <Alert tone="info">
            No bank account on file. An approved award will be held out of the
            payment run until one is recorded.
          </Alert>
        )}
        {revealError && <Alert tone="error">{revealError}</Alert>}
      </Card>

      {/* The institution's side of the file. Above the student's answers,
          because whether it has come back decides what can be done next. */}
      {application.enrolment.required && (
        <Card title="Enrolment verification (Form B)">
          <div className="stack">
            <div className="row">
              <Badge tone={application.enrolment.confirmed ? 'ok' : 'warn'}>
                {application.enrolment.label}
              </Badge>
              {application.enrolment.registrar_email && (
                <span className="small muted">
                  Sent to {application.enrolment.registrar_email}
                </span>
              )}
            </div>

            {!application.enrolment.confirmed && (
              <Alert tone="info">
                Tuition is funded against the figure the institution confirms,
                not the student&rsquo;s estimate. This application cannot be
                forwarded or approved until the verification comes back.
              </Alert>
            )}

            {/* Submission raises the request by itself, but only when a
                registrar address is already known — it is carried from the
                student's last application, and a renewal by somebody whose
                admission was on paper has nothing to carry from. Without this
                the application could never be forwarded by anybody, and the
                screen said the confirmation was "not required". */}
            {canReview && !application.enrolment.confirmed && (
              <div className="stack stack--tight">
                {application.enrolment.status === 'not_requested' && (
                  <Alert tone="error">
                    No confirmation has been requested. Nothing can be awarded
                    for tuition until the institution is asked.
                  </Alert>
                )}
                <Field
                  id="registrar-email"
                  label="Registrar’s email address"
                  hint={application.enrolment.registrar_email
                    ? `Leave blank to write to ${application.enrolment.registrar_email} again.`
                    : 'Nothing is on file for this application.'}
                >
                  <Input
                    id="registrar-email"
                    type="email"
                    value={registrarEmail}
                    placeholder="registrar@institution.ca"
                    onChange={(e) => setRegistrarEmail(e.target.value)}
                  />
                </Field>
                <div className="row">
                  <Button
                    busy={busy === 'enrolment'}
                    disabled={!registrarEmail.trim()
                      && !application.enrolment.registrar_email}
                    onClick={() => void askInstitution()}
                  >
                    {application.enrolment.status === 'not_requested'
                      ? 'Request confirmation'
                      : 'Send the request again'}
                  </Button>
                </div>
              </div>
            )}

            {application.enrolment_answers && (
              <dl className="answers">
                {Object.entries(application.enrolment_answers).map(([key, value]) => (
                  <div key={key} className="answers__row">
                    <dt>{key.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())}</dt>
                    <dd>{String(value)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
        </Card>
      )}

      {application.information_requested && (
        <Card title="More information needed">
          <div className="stack stack--tight">
            <p>
              {application.information_requested.note
                || 'The office has asked you to review this application.'}
            </p>
            <p className="muted small">
              Asked by {application.information_requested.asked_by || 'the office'}
              {' on '}{formatDate(application.information_requested.asked_at)}
            </p>
          </div>
        </Card>
      )}

      {application.can_revise && schema && (
        <ReviseForm application={application} schema={schema} onDone={load} />
      )}

      {application.documents.length > 0 && (
        <Card title="Documents">
          {/* The answers hold a reference like `document:12`, which is
              meaningless to a person. A reviewer was shown that string and had
              no way to open the transcript an assessment depends on. */}
          <ul className="documents">
            {application.documents.map((document) => (
              <li key={document.id} className="documents__item">
                <button
                  type="button"
                  className="linklike"
                  onClick={() => openDocument(document)}
                >
                  {document.original_name}
                </button>
                <span className="muted small">
                  {labelFor(schema, document.field_key)}
                  {' · '}
                  {formatDate(document.uploaded_at)}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card title="Answers">
        <AnswerList application={application} schema={schema} />
        {hasIdentifiers && (
          <div className="stack stack--tight" style={{ marginTop: 'var(--s-4)' }}>
            {Object.entries(application.identifiers).map(([kind, masked]) => (
              <p key={kind} className="small muted">
                {kind.toUpperCase()}:{' '}
                <strong>{revealed?.identifiers?.[kind] || masked}</strong>
                {' — stored encrypted.'}
                {canReveal
                  ? ' Reading the full number is recorded against your name.'
                  : ' Only an administrator can read the full number.'}
              </p>
            ))}
            {canReveal && !revealed && (
              <Button busy={revealing} onClick={() => void reveal()}>
                Show full number
              </Button>
            )}
          </div>
        )}
      </Card>

      <Card title="History">
        <ol className="stack stack--tight">
          {application.events.map((event) => (
            <li key={event.id} className="row">
              <Badge tone="neutral">{event.action_label}</Badge>
              <span className="small muted">
                {formatDate(event.occurred_at)}
                {event.actor_name ? ` · ${event.actor_name}` : ''}
                {event.note ? ` · ${event.note}` : ''}
              </span>
            </li>
          ))}
        </ol>
      </Card>
    </main>
  );
}
