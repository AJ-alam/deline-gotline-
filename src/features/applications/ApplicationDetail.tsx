/**
 * One application: what was asked, what happened to it, and what it was awarded.
 *
 * The award breakdown shows the rule behind every line and the rules that did
 * not fire. Staff previously saw a total with no explanation, which is not
 * something anyone can defend to an applicant on appeal.
 */

import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

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
import { Alert, Badge, Button, Card, Field, Input, Textarea } from '../../components/ui';
import { formatDate, formatMoney, statusTone } from '../../components/ui/format';
import AmendForm from './AmendForm';
import AwardEditor from './AwardEditor';
import ReviseForm from './ReviseForm';

/** Which actions make sense next, mirrored from the backend transition table. */
const NEXT_ACTIONS: Record<string, TransitionAction[]> = {
  submitted: ['reviewed', 'info_requested', 'declined'],
  under_review: ['forwarded', 'info_requested', 'declined'],
  info_requested: ['info_provided', 'declined'],
  awaiting_decision: ['approved', 'declined', 'info_requested'],
  // Nothing to offer on an approved application. 'Send to finance' looked like
  // it paid someone and did not — it only recorded the transition, which the
  // payment run records for itself when the batch actually goes out. Pressing
  // it left the award unpaid while moving the application past the point the
  // run selected on, so the money went quiet.
  approved: [],
  declined: [],
  sent_to_finance: [],
  draft: [],
};

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
    !['approved', 'declined', 'sent_to_finance'].includes(application.status);

  return (
    <main className="page stack stack--loose">
      <header className="stack stack--tight">
        <div className="row row--between">
          <h1>{application.type_label}</h1>
          <div className="row">
            {canAmend && !amending && (
              <Button variant="ghost" onClick={() => setAmending(true)}>
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
            {(canReview || canDecide) && (
              <Button size="sm" busy={busy === 'preview'} onClick={() => void runPreview()}>
                Preview
              </Button>
            )}
            {canAmend && !editingAward && (
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
          <DecisionBreakdown trace={application.decision.trace} />
        ) : preview ? (
          <div className="stack">
            <Alert tone="info">Preview only — nothing has been recorded.</Alert>
            <DecisionBreakdown trace={preview} />
          </div>
        ) : (
          <p className="muted">No award has been recorded for this application.</p>
        )}
      </Card>

      {/* Whether this can be paid, without putting the account on a review
          screen. The digits used to be printed here, straight out of the
          answers; they belong in the payment file and nowhere else. A missing
          account is what holds an approved award, so it is worth saying. */}
      <Card title="Payment">
        {application.banking.on_file ? (
          <div className="row">
            <Badge tone="ok">Account on file</Badge>
            <span className="small muted">
              {application.banking.account}
              {application.banking.holder && ` · ${application.banking.holder}`}
              {application.banking.held
                && ' · held until this application is attached to an account'}
            </span>
          </div>
        ) : (
          <Alert tone="info">
            No bank account on file. An approved award will be held out of the
            payment run until one is recorded.
          </Alert>
        )}
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
        {Object.keys(application.identifiers ?? {}).length > 0 && (
          <div className="stack stack--tight" style={{ marginTop: 'var(--s-4)' }}>
            {Object.entries(application.identifiers).map(([kind, masked]) => (
              <p key={kind} className="small muted">
                {kind.toUpperCase()}: <strong>{masked}</strong> — stored
                encrypted. Reading the full number is recorded against your name.
              </p>
            ))}
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
