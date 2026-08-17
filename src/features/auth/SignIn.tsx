import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import api, { ApiError, type GuestApplicationType } from '../../api/client';
import { Alert, Button, Dialog, Field, Input } from '../../components/ui';
import AuthLayout from './AuthLayout';

/**
 * The awards that can be claimed without an account.
 *
 * Phrased as the question the person is answering rather than the name of the
 * form: someone who finished a trades ticket in May does not know they are
 * looking for a 'graduation bursary'.
 */
const ONE_OFF: Array<{
  type: GuestApplicationType;
  question: string;
  detail: string;
}> = [
  {
    type: 'practicum',
    question: 'Working in Deline this summer?',
    detail: 'Support for clinical placements or work experience.',
  },
  {
    type: 'graduation_bursary',
    question: 'Completed high school, post-secondary or a training programme?',
    detail: 'A one-time award recognising the credential you finished.',
  },
];

export default function SignIn() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [reveal, setReveal] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [oneOffOpen, setOneOffOpen] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api.signIn(email, password);
      navigate('/dashboard');
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? 'That email and password do not match an account.'
          : err instanceof ApiError
            ? err.message
            : 'Could not sign in. Please try again.',
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout>
      <header>
        <h1 className="auth-panel__title">Sign in</h1>
        <p className="auth-panel__lead">
          New student? <Link to="/register">Create your account &rarr;</Link>
        </p>
      </header>

      <form className="stack" onSubmit={submit} noValidate style={{ marginTop: 'var(--s-6)' }}>
        {error && <Alert tone="error">{error}</Alert>}

        <Field id="email" label="Email" required>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>

        <Field id="password" label="Password" required>
          <div className="auth-reveal">
            <Input
              id="password"
              type={reveal ? 'text' : 'password'}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button
              type="button"
              onClick={() => setReveal(!reveal)}
              aria-pressed={reveal}
              aria-controls="password"
            >
              {reveal ? 'Hide' : 'Show'}
            </button>
          </div>
        </Field>

        <Button type="submit" variant="primary" block busy={busy}>
          Sign in to portal
        </Button>
      </form>

      <div className="auth-panel__aside">
        <div className="auth-panel__rule">One-off awards</div>
        <Button block onClick={() => setOneOffOpen(true)}>
          Applying for a single award?
        </Button>
      </div>

      <p className="auth-panel__foot">
        Staff sign in here too — you will be taken to your own queue.
      </p>

      <Dialog
        open={oneOffOpen}
        onClose={() => setOneOffOpen(false)}
        title="One-off award applications"
        description="Continue without an account for these specific short-term programmes."
      >
        <div className="choice-list">
          {ONE_OFF.map((award) => (
            <button
              key={award.type}
              type="button"
              className="choice"
              onClick={() => navigate(`/apply-once/${award.type}`)}
            >
              <span className="choice__title">{award.question}</span>
              <span className="choice__detail">{award.detail}</span>
            </button>
          ))}
        </div>
        <p className="small muted" style={{ marginTop: 'var(--s-4)' }}>
          You will get a reference number by email. Staff can attach the
          application to a portal account later if you create one.
        </p>
      </Dialog>
    </AuthLayout>
  );
}
