/**
 * The office correcting a filed application.
 *
 * The same renderer the application was filled in with, opened on the answers
 * already stored — including its file controls, so a document can be added,
 * replaced or removed without a second upload screen existing anywhere.
 *
 * The note is not decoration. It is what the applicant is shown when they are
 * told their application changed, and what the audit trail carries: "corrected
 * the campus, confirmed by phone" is a record, "amended" is not.
 */

import { useState } from 'react';

import api, { ApiError, type Application, type ApplicationSchema } from '../../api/client';
import SchemaForm, { type Answers } from '../../components/SchemaForm';
import { Alert, Button, Card, Field, Textarea } from '../../components/ui';

export default function AmendForm({
  application,
  schema,
  onDone,
  onCancel,
}: {
  application: Application;
  schema: ApplicationSchema;
  onDone: () => void | Promise<void>;
  onCancel: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState('');
  const [note, setNote] = useState('');

  const submit = async (answers: Answers) => {
    setBusy(true);
    setErrors({});
    setFormError('');
    try {
      await api.amend(application.id, answers, note);
      await onDone();
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.fieldErrors);
        if (Object.keys(err.fieldErrors).length === 0) setFormError(err.message);
      } else {
        setFormError('The changes could not be saved. Please try again.');
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      title="Edit this application"
      actions={<Button variant="ghost" onClick={onCancel}>Cancel</Button>}
    >
      <div className="stack">
        <Alert tone="info">
          You are changing an application on the applicant’s behalf. They will be
          told what changed, and the change is recorded against your name.
        </Alert>

        <Field
          id="amend-note"
          label="What are you changing, and why?"
          hint="Shown to the applicant and kept in the audit trail."
        >
          <Textarea
            id="amend-note"
            rows={2}
            value={note}
            placeholder="Corrected the campus name, confirmed by phone."
            onChange={(e) => setNote(e.target.value)}
          />
        </Field>

        {formError && <Alert tone="error">{formError}</Alert>}

        <SchemaForm
          schema={schema}
          // Opened on what is stored. Private answers — a SIN, a bank account —
          // are not in `answers` and come back blank on purpose: the server
          // keeps them out of anything it returns, and leaving them blank
          // changes nothing.
          initial={application.answers as Answers}
          busy={busy}
          errors={errors}
          revising
          submitLabel="Save changes"
          onSubmit={submit}
        />
      </div>
    </Card>
  );
}
