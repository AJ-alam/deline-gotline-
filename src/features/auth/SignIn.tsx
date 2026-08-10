import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import api, { ApiError } from '../../api/client';
import { Alert, Button, Card, Field, Input } from '../../components/ui';

export default function SignIn() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const user = await api.signIn(email, password);
      navigate(user.role === 'student' ? '/applications' : '/review');
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
    <main className="auth-page">
      <Card title="Sign in">
        <form className="stack" onSubmit={submit} noValidate>
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
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          <Button type="submit" variant="primary" block busy={busy}>
            Sign in
          </Button>
          <p className="small muted">
            No account? <a href="/register">Create one</a>
          </p>
        </form>
      </Card>
    </main>
  );
}
