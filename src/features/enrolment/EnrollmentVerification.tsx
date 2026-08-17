/**
 * The registrar's confirmation form.
 *
 * Reached from an emailed link, with no account. The token in the URL is the
 * only credential, so this page shows only what is needed to answer the
 * question — a name, an institution and a programme — and never the student's
 * address, banking or beneficiary number.
 *
 * Tuition is funded against the figure entered here, not the student's estimate,
 * so nothing is awarded for tuition until this is returned.
 */

import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import { API_BASE_URL } from '../../api/config';
import type { ApplicationSchema } from '../../api/schema.generated';
import SchemaForm, { type Answers } from '../../components/SchemaForm';
import { Alert, Card } from '../../components/ui';
import { formatDate } from '../../components/ui/format';

interface VerificationContext {
  student_name: string;
  institution_name: string;
  program: string;
  expires_at: string;
  /** Why the student's date of birth and SIN are not on this form. */
  note_to_registrar: string;
  /** The form, already filled in from the student's application. */
  prefill: Record<string, string | number | boolean>;
}

type Load =
  | { state: 'loading' }
  | { state: 'ready'; application: VerificationContext; schema: ApplicationSchema }
  | { state: 'unavailable'; message: string };

export default function EnrollmentVerification() {
  const { token } = useParams<{ token: string }>();
  const [load, setLoad] = useState<Load>({ state: 'loading' });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState('');

  useEffect(() => {
    let cancelled = false;

    // Deliberately not the authenticated client: this page has no session, and
    // attaching a stale token from another account would be wrong.
    fetch(`${API_BASE_URL}/enrolment/${token}/`)
      .then(async (response) => {
        const body = await response.json().catch(() => ({}));
        if (cancelled) return;
        if (!response.ok) {
          setLoad({
            state: 'unavailable',
            message: body.detail ?? 'This link is not valid.',
          });
          return;
        }
        setLoad({ state: 'ready', application: body.application, schema: body.schema });
      })
      .catch(() => {
        if (!cancelled) {
          setLoad({ state: 'unavailable', message: 'This link could not be opened.' });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  const submit = async (answers: Answers) => {
    setBusy(true);
    setErrors({});
    setFormError('');
    try {
      const response = await fetch(`${API_BASE_URL}/enrolment/${token}/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers }),
      });
      const body = await response.json().catch(() => ({}));

      if (response.ok) {
        setDone(body.detail ?? 'Thank you — the enrolment has been confirmed.');
        return;
      }
      if (body.answers) {
        setErrors(body.answers);
      } else {
        setFormError(body.detail ?? 'The confirmation could not be submitted.');
      }
    } catch {
      setFormError('The confirmation could not be submitted. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  if (load.state === 'loading') {
    return (
      <main className="page">
        <div className="spinner" role="status" aria-label="Loading" />
      </main>
    );
  }

  if (load.state === 'unavailable') {
    return (
      <main className="page">
        <Card title="Enrolment verification">
          <Alert tone="error">{load.message}</Alert>
          <p className="small muted" style={{ marginTop: 'var(--s-3)' }}>
            If you still need to confirm this student&rsquo;s enrolment, contact the
            Deline Got&rsquo;ı̨nę Government student funding office for a new link.
          </p>
        </Card>
      </main>
    );
  }

  if (done) {
    return (
      <main className="page">
        <Card title="Enrolment confirmed">
          <Alert tone="ok">{done}</Alert>
          <p className="small muted" style={{ marginTop: 'var(--s-3)' }}>
            Nothing further is needed. You can close this page.
          </p>
        </Card>
      </main>
    );
  }

  const { application, schema } = load;

  return (
    <main className="page stack stack--loose">
      <header className="stack stack--tight">
        <h1>Confirm a student&rsquo;s enrolment</h1>
        <p className="muted">
          The Deline Got&rsquo;ı̨nę Government funds tuition against the amount your
          institution has billed. This form is used once and expires on{' '}
          {formatDate(application.expires_at)}.
        </p>
      </header>

      <Card title="Student">
        <dl className="answers">
          <div className="answers__row">
            <dt>Name</dt>
            <dd>{application.student_name}</dd>
          </div>
          <div className="answers__row">
            <dt>Institution</dt>
            <dd>{application.institution_name}</dd>
          </div>
          <div className="answers__row">
            <dt>Programme</dt>
            <dd>{application.program}</dd>
          </div>
        </dl>

        {application.note_to_registrar && (
          <p className="small muted" style={{ marginTop: 'var(--s-4)' }}>
            {application.note_to_registrar}
          </p>
        )}
      </Card>

      <Card>
        <SchemaForm
          schema={schema}
          // Filled in from the student's application: the institution is asked
          // to check these against its own records, not to retype them.
          initial={application.prefill}
          submitLabel="Confirm enrolment"
          busy={busy}
          errors={errors}
          formError={formError}
          onSubmit={submit}
        />
      </Card>
    </main>
  );
}
