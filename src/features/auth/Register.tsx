import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import api, { ApiError } from '../../api/client';
import { Alert, Button, Card, Field, Input } from '../../components/ui';

export default function Register() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    first_name: '', last_name: '', email: '', password: '', phone: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [key]: e.target.value });

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setErrors({});
    setFormError('');
    try {
      await api.register(form);
      await api.signIn(form.email, form.password);
      navigate('/applications');
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.fieldErrors);
        if (Object.keys(err.fieldErrors).length === 0) setFormError(err.message);
      } else {
        setFormError('Could not create the account. Please try again.');
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="auth-page">
      <Card title="Create an account">
        <form className="stack" onSubmit={submit} noValidate>
          {formError && <Alert tone="error">{formError}</Alert>}
          <div className="grid-2">
            <Field id="first_name" label="First name" required error={errors.first_name}>
              <Input id="first_name" value={form.first_name} onChange={set('first_name')}
                     invalid={Boolean(errors.first_name)} autoComplete="given-name" />
            </Field>
            <Field id="last_name" label="Last name" required error={errors.last_name}>
              <Input id="last_name" value={form.last_name} onChange={set('last_name')}
                     invalid={Boolean(errors.last_name)} autoComplete="family-name" />
            </Field>
          </div>
          <Field id="email" label="Email" required error={errors.email}>
            <Input id="email" type="email" value={form.email} onChange={set('email')}
                   invalid={Boolean(errors.email)} autoComplete="email" />
          </Field>
          <Field id="phone" label="Phone" error={errors.phone}>
            <Input id="phone" type="tel" value={form.phone} onChange={set('phone')}
                   autoComplete="tel" />
          </Field>
          <Field id="password" label="Password" required hint="At least 8 characters."
                 error={errors.password}>
            <Input id="password" type="password" value={form.password} onChange={set('password')}
                   invalid={Boolean(errors.password)} autoComplete="new-password" />
          </Field>
          <Button type="submit" variant="primary" block busy={busy}>Create account</Button>
          <p className="small muted">Already registered? <a href="/signin">Sign in</a></p>
        </form>
      </Card>
    </main>
  );
}
