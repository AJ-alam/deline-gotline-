/**
 * Answering a request for more information.
 *
 * The same renderer the application was filled in with, opened on the answers
 * already stored. Nothing about "editing" is special: the office asked a
 * question, and the way to answer it is the form that asked the questions in
 * the first place — including its file controls, so a document can be added or
 * replaced without anybody inventing a second upload screen.
 *
 * Sends the whole answer set. The server validates a revision by the same
 * schema as the original and records that the information was provided, so the
 * application goes back into the queue rather than sitting in "more
 * information needed" with the information already in it.
 */

import { useState } from 'react';

import api, { ApiError, type Application, type ApplicationSchema } from '../../api/client';
import SchemaForm, { type Answers } from '../../components/SchemaForm';
import { Alert, Card } from '../../components/ui';

export default function ReviseForm({
  application,
  schema,
  onDone,
}: {
  application: Application;
  schema: ApplicationSchema;
  /** Reload the application, so the screen shows its new status. */
  onDone: () => void | Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState('');

  const submit = async (answers: Answers) => {
    setBusy(true);
    setErrors({});
    setFormError('');
    try {
      await api.revise(application.id, answers);
      await onDone();
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.fieldErrors);
        if (Object.keys(err.fieldErrors).length === 0) setFormError(err.message);
      } else {
        setFormError('Your changes could not be saved. Please try again.');
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Update your application">
      <div className="stack">
        <p className="muted">
          Change anything that needs changing, and attach or replace any
          document. When you send it back the office picks it up again.
        </p>
        {formError && <Alert tone="error">{formError}</Alert>}
        <SchemaForm
          schema={schema}
          // Opened on what is already stored, so the student corrects rather
          // than retypes. Private answers — a bank account, a SIN — are not in
          // `answers` and come back blank on purpose: the server keeps them out
          // of anything it returns, and leaving them blank changes nothing.
          initial={application.answers as Answers}
          busy={busy}
          errors={errors}
          revising
          submitLabel="Send back to the office"
          onSubmit={submit}
        />
      </div>
    </Card>
  );
}
