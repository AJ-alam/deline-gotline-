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
  type CurrentUser,
  type DecisionTrace,
  type TransitionAction,
} from '../../api/client';
import { Alert, Badge, Button, Card } from '../../components/ui';
import { formatDate, formatMoney, statusTone } from '../../components/ui/format';

/** Which actions make sense next, mirrored from the backend transition table. */
const NEXT_ACTIONS: Record<string, TransitionAction[]> = {
  submitted: ['reviewed', 'info_requested', 'declined'],
  under_review: ['forwarded', 'info_requested', 'declined'],
  info_requested: ['info_provided', 'declined'],
  awaiting_decision: ['approved', 'declined', 'info_requested'],
  approved: ['sent_to_finance'],
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
            {sectionFields.map((field) => {
              const raw = application.answers[field.key];
              const display =
                field.type === 'choice'
                  ? (field.choices.find((c) => c.value === raw)?.label ?? String(raw))
                  : field.type === 'boolean'
                    ? raw
                      ? 'Yes'
                      : 'No'
                    : String(raw);
              return (
                <div key={field.key} className="answers__row">
                  <dt>{field.label}</dt>
                  <dd>{display}</dd>
                </div>
              );
            })}
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

  const act = async (action: TransitionAction) => {
    setBusy(action);
    setError('');
    setNotice('');
    try {
      setApplication(await api.transition(applicationId, action));
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

  return (
    <main className="page stack stack--loose">
      <header className="stack stack--tight">
        <div className="row row--between">
          <h1>{application.type_label}</h1>
          <Badge tone={statusTone(application.status)}>{application.status_label}</Badge>
        </div>
        <p className="muted">
          {application.student_name} · submitted {formatDate(application.submitted_at)}
        </p>
      </header>

      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="ok">{notice}</Alert>}

      {available.length > 0 && (
        <Card title="Actions">
          <div className="row">
            {available.map((action) => (
              <Button
                key={action}
                variant={action === 'declined' ? 'danger' : 'primary'}
                busy={busy === action}
                onClick={() => void act(action)}
              >
                {ACTION_LABELS[action]}
              </Button>
            ))}
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
            {canDecide && (
              <Button size="sm" variant="primary" busy={busy === 'price'} onClick={() => void record()}>
                Record award
              </Button>
            )}
          </div>
        }
      >
        {application.decision ? (
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

      <Card title="Answers">
        <AnswerList application={application} schema={schema} />
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
