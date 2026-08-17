/**
 * Creating an account.
 *
 * Two steps, because the office screens for eligibility before anyone fills in
 * a full application. Someone who qualifies for nothing is told so here, and
 * told where else to ask, rather than discovering it after submitting.
 *
 * The questions and the decision both come from the server. The previous
 * version held those rules inside this component, where they could be bypassed
 * by calling the API directly and where nobody could test them.
 */

import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import api, {
  ApiError,
  type EligibilityOutcome,
  type EligibilityQuestion,
} from '../../api/client';
import { Alert, Button, Field, Input } from '../../components/ui';
import AuthLayout from './AuthLayout';

type Step = 'eligibility' | 'details';

export default function Register() {
  const navigate = useNavigate();

  const [step, setStep] = useState<Step>('eligibility');
  const [questions, setQuestions] = useState<EligibilityQuestion[] | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [outcome, setOutcome] = useState<EligibilityOutcome | null>(null);

  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    password: '',
    confirm_password: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .eligibilityQuestions()
      .then((result) => !cancelled && setQuestions(result))
      .catch(() => !cancelled && setFormError('The eligibility questions could not be loaded.'));
    return () => {
      cancelled = true;
    };
  }, []);

  const answered = questions?.every((q) => answers[q.key]) ?? false;

  const check = async () => {
    setBusy(true);
    setFormError('');
    try {
      setOutcome(await api.checkEligibility(answers));
    } catch {
      setFormError('Your answers could not be checked. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const set = (key: keyof typeof form) => (event: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [key]: event.target.value });

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setErrors({});
    setFormError('');
    try {
      await api.register({ ...form, eligibility: answers });
      await api.signIn(form.email, form.password);
      navigate('/dashboard');
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.fieldErrors);
        if (Object.keys(err.fieldErrors).length === 0) setFormError(err.message);
      } else {
        setFormError('The account could not be created. Please try again.');
      }
    } finally {
      setBusy(false);
    }
  };

  // ── Step one: screening ──
  if (step === 'eligibility') {
    return (
      <AuthLayout>
        <header>
          <h1 className="auth-panel__title">Check your eligibility</h1>
          <p className="auth-panel__lead">
            Six questions, so we can tell you what you may apply for before you
            fill anything in.
          </p>
        </header>

        <div className="stack" style={{ marginTop: 'var(--s-6)' }}>

            {formError && <Alert tone="error">{formError}</Alert>}
            {!questions && <div className="spinner" role="status" aria-label="Loading" />}

            {questions?.map((question) => (
              <fieldset key={question.key} className="quiz">
                <legend className="quiz__question">{question.text}</legend>
                {question.help && <p className="field__hint">{question.help}</p>}
                <div className="row">
                  {question.choices.map((choice) => (
                    <label key={choice.value} className="quiz__choice">
                      <input
                        type="radio"
                        name={question.key}
                        value={choice.value}
                        checked={answers[question.key] === choice.value}
                        onChange={() => {
                          setAnswers({ ...answers, [question.key]: choice.value });
                          setOutcome(null);
                        }}
                      />
                      <span>{choice.label}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
            ))}

            {outcome && (
              <Alert tone={outcome.eligible ? 'ok' : 'error'}>
                <strong>{outcome.title}</strong>
                <div style={{ marginTop: 'var(--s-1)' }}>{outcome.message}</div>
              </Alert>
            )}

            <div className="row">
              {!outcome?.eligible && (
                <Button
                  variant="primary"
                  busy={busy}
                  disabled={!answered}
                  onClick={() => void check()}
                >
                  Check eligibility
                </Button>
              )}
              {outcome?.eligible && (
                <Button variant="primary" onClick={() => setStep('details')}>
                  Continue
                </Button>
              )}
            </div>

          <p className="auth-panel__foot">
            Already registered? <Link to="/signin">Sign in</Link>
          </p>
        </div>
      </AuthLayout>
    );
  }

  // ── Step two: the account itself ──
  return (
    <AuthLayout>
      <header>
        <h1 className="auth-panel__title">Create your account</h1>
      </header>

      <form className="stack" onSubmit={submit} noValidate style={{ marginTop: 'var(--s-6)' }}>
          {outcome && (
            <Alert tone="ok">
              You may apply for {outcome.streams.map((s) => s.toUpperCase()).join(' and ')}.
            </Alert>
          )}
          {formError && <Alert tone="error">{formError}</Alert>}
          {errors.eligibility && <Alert tone="error">{errors.eligibility}</Alert>}

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
            <Input id="password" type="password" value={form.password}
                   onChange={set('password')} invalid={Boolean(errors.password)}
                   autoComplete="new-password" />
          </Field>

          <Field id="confirm_password" label="Confirm password" required
                 error={errors.confirm_password}>
            <Input id="confirm_password" type="password" value={form.confirm_password}
                   onChange={set('confirm_password')}
                   invalid={Boolean(errors.confirm_password)}
                   autoComplete="new-password" />
          </Field>

          <div className="row">
            <Button type="submit" variant="primary" busy={busy}>
              Create account
            </Button>
            <Button type="button" variant="ghost" onClick={() => setStep('eligibility')}>
              Back
            </Button>
          </div>
      </form>
    </AuthLayout>
  );
}
