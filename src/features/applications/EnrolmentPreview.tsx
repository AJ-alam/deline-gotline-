/**
 * The enrolment verification, as the registrar will receive it.
 *
 * Shown before submitting because this form is generated from the answers and
 * emailed to an institution automatically — a student should see what is being
 * sent in their name, and has the best chance of anyone of spotting that the
 * institution name is wrong or the tuition figure was mistyped.
 *
 * The preview is rendered from the server's own pre-fill, not a second copy of
 * that logic here. A preview that can disagree with what is sent is worse than
 * no preview: it would be believed.
 */

import { useState } from 'react';

import api, { type ApplicationType } from '../../api/client';
import type { ApplicationSchema } from '../../api/schema.generated';
import { Alert, Button, Dialog } from '../../components/ui';
import type { Answers } from '../../components/SchemaForm';

interface Preview {
  schema: ApplicationSchema;
  prefill: Record<string, string | number | boolean>;
  note_to_registrar: string;
  registrar_email: string;
}

export default function EnrolmentPreview({
  type,
  answers,
}: {
  type: ApplicationType;
  answers: Answers;
}) {
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState('');

  const show = async () => {
    setBusy(true);
    setFailed('');
    try {
      setPreview(await api.enrolmentPreview(type, answers));
      setOpen(true);
    } catch {
      setFailed('The preview could not be generated. You can still submit.');
    } finally {
      setBusy(false);
    }
  };

  // Only the fields the registrar actually fills in or checks, in schema order.
  const rows = preview
    ? preview.schema.fields.map((field) => ({
        key: field.key,
        label: field.label,
        value: preview.prefill[field.key],
        required: field.required,
      }))
    : [];

  return (
    <section className="formb">
      <div className="formb__head">
        <div>
          <h3 className="formb__title">Enrolment verification (Form B)</h3>
          <p className="small muted">
            Generated from your answers and emailed to your registrar when you
            submit — you do not fill it in. Please check it first.
          </p>
        </div>
        <Button type="button" busy={busy} onClick={() => void show()}>
          Preview Form B
        </Button>
      </div>

      {failed && <Alert tone="error">{failed}</Alert>}

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Enrolment verification (Form B)"
        description="What will be sent to your institution."
      >
        {preview && (
          <div className="stack">
            <Alert tone="info">{preview.note_to_registrar}</Alert>

            {preview.registrar_email ? (
              <p className="small">
                Will be emailed to <strong>{preview.registrar_email}</strong>.
              </p>
            ) : (
              <Alert tone="error">
                No registrar email has been entered yet. Without one your
                institution cannot confirm your enrolment, and tuition cannot be
                awarded.
              </Alert>
            )}

            <dl className="answers">
              {rows.map((row) => (
                <div key={row.key} className="answers__row">
                  <dt>{row.label}</dt>
                  <dd>
                    {row.value !== undefined && row.value !== '' ? (
                      String(row.value)
                    ) : (
                      <span className="muted small">
                        {row.required
                          ? 'Your institution completes this'
                          : 'Your institution may complete this'}
                      </span>
                    )}
                  </dd>
                </div>
              ))}
            </dl>

            <p className="small muted">
              Anything filled in above came from your application. If something
              is wrong, go back and correct it before submitting.
            </p>
          </div>
        )}
      </Dialog>
    </section>
  );
}
