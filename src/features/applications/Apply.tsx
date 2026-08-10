/**
 * Applying for funding.
 *
 * Every application type is served by this one page, because the questions come
 * from the API. Adding a form to the portal is now a backend schema, not a new
 * thousand-line React component.
 */
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import api, { ApiError, type ApplicationSchema, type ApplicationType, type FundingStream } from '../../api/client';
import SchemaForm, { type Answers } from '../../components/SchemaForm';
import { Alert, Card, Field, Select } from '../../components/ui';

const STREAMS: Array<{ value: FundingStream; label: string }> = [
  { value: 'psssp', label: 'C-DFN PSSSP' },
  { value: 'ucepp', label: 'C-DFN UCEPP' },
  { value: 'dggr', label: 'DGGR Bursaries' },
];

export default function Apply() {
  const { type } = useParams<{ type: ApplicationType }>();
  const navigate = useNavigate();

  const [schema, setSchema] = useState<ApplicationSchema | null>(null);
  const [loadError, setLoadError] = useState('');
  const [stream, setStream] = useState<FundingStream>('psssp');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!type) return;
    let cancelled = false;
    api
      .schema(type)
      .then((result) => !cancelled && setSchema(result))
      .catch(() => !cancelled && setLoadError('That application form could not be loaded.'));
    return () => { cancelled = true; };
  }, [type]);

  const submit = async (answers: Answers) => {
    if (!type) return;
    setBusy(true);
    setErrors({});
    setFormError('');
    try {
      // The cast is the one place answers cross from an untyped form into the
      // typed client; the schema has already decided what the keys are.
      const created = await api.submit(type, stream, answers as never);
      navigate(`/applications/${created.id}`);
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

  if (loadError) return <main className="page"><Alert tone="error">{loadError}</Alert></main>;
  if (!schema) return <main className="page"><div className="spinner" /></main>;

  return (
    <main className="page stack stack--loose">
      <header className="stack stack--tight">
        <h1>{schema.label}</h1>
        <p className="muted">Answers are saved when you submit.</p>
      </header>

      <Card>
        <div className="stack">
          <Field id="stream" label="Funding stream" required
                 hint="Which programme you are applying under.">
            <Select id="stream" value={stream}
                    onChange={(e) => setStream(e.target.value as FundingStream)}>
              {STREAMS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </Select>
          </Field>
          <SchemaForm schema={schema} busy={busy} errors={errors} formError={formError}
                      onSubmit={submit} />
        </div>
      </Card>
    </main>
  );
}
