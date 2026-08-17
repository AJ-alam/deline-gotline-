/**
 * Applying for a one-off award without an account.
 *
 * A summer placement allowance and a graduation bursary are both claimed once,
 * after the fact, by people who often will not use the portal again. This is
 * the same schema-driven form the signed-in pages use — the difference is only
 * that there is no session, so there is no application page to return to and
 * the reference number is all the applicant is given to hold onto.
 */

import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import api, {
  ApiError,
  type ApplicationSchema,
  type GuestApplicationType,
  type GuestReceipt,
} from '../../api/client';
import SchemaForm, { type Answers } from '../../components/SchemaForm';
import { Alert, Button } from '../../components/ui';
import AuthLayout from './AuthLayout';

const OFFERED: GuestApplicationType[] = ['practicum', 'graduation_bursary'];

export default function GuestApply() {
  const { type } = useParams<{ type: GuestApplicationType }>();

  const [schema, setSchema] = useState<ApplicationSchema | null>(null);
  const [loadError, setLoadError] = useState('');
  const [receipt, setReceipt] = useState<GuestReceipt | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);

  const offered = Boolean(type && OFFERED.includes(type));

  useEffect(() => {
    if (!offered) return;
    let cancelled = false;
    api
      .guestSchemas()
      .then((all) => {
        if (cancelled) return;
        const found = all.find((s) => s.slug === type);
        if (found) setSchema(found);
        else setLoadError('That form is not available without an account.');
      })
      .catch(() => !cancelled && setLoadError('That form could not be loaded.'));
    return () => {
      cancelled = true;
    };
  }, [type, offered]);

  const submit = async (answers: Answers) => {
    if (!type) return;
    setBusy(true);
    setErrors({});
    setFormError('');
    try {
      setReceipt(await api.submitGuest(type, answers));
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.fieldErrors);
        if (Object.keys(err.fieldErrors).length === 0) setFormError(err.message);
      } else {
        setFormError('Could not submit the application. Please try again.');
      }
    } finally {
      setBusy(false);
    }
  };

  if (!offered) {
    return (
      <AuthLayout>
        <Alert tone="error">
          That award cannot be applied for without an account.
        </Alert>
        <p className="auth-panel__foot">
          <Link to="/signin">Back to sign in</Link>
        </p>
      </AuthLayout>
    );
  }

  // Submitted. There is nowhere to send them, so the reference number is the
  // whole of what they leave with — it is the only handle they have on it.
  if (receipt) {
    return (
      <AuthLayout>
        <header>
          <h1 className="auth-panel__title">Application received</h1>
        </header>
        <div className="stack" style={{ marginTop: 'var(--s-5)' }}>
          <Alert tone="ok">{receipt.detail}</Alert>
          <div className="receipt">
            <div className="receipt__label">Your reference number</div>
            <div className="receipt__value">{receipt.reference}</div>
          </div>
          <p className="auth-panel__foot">
            <Link to="/signin">Back to sign in</Link> &middot;{' '}
            <Link to="/register">Create an account</Link>
          </p>
        </div>
      </AuthLayout>
    );
  }

  if (loadError) {
    return (
      <AuthLayout>
        <Alert tone="error">{loadError}</Alert>
        <p className="auth-panel__foot">
          <Link to="/signin">Back to sign in</Link>
        </p>
      </AuthLayout>
    );
  }

  if (!schema) {
    return (
      <AuthLayout>
        <div className="spinner" role="status" aria-label="Loading" />
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <header>
        <h1 className="auth-panel__title">{schema.label}</h1>
        <p className="auth-panel__lead">
          You do not need an account for this one. We will email you a reference
          number when it is submitted.
        </p>
      </header>

      <div className="stack" style={{ marginTop: 'var(--s-5)' }}>
        <SchemaForm
          schema={schema}
          busy={busy}
          errors={errors}
          formError={formError}
          onSubmit={submit}
        />
        <p className="auth-panel__foot">
          <Button variant="ghost" size="sm" onClick={() => history.back()}>
            Cancel
          </Button>
        </p>
      </div>
    </AuthLayout>
  );
}
