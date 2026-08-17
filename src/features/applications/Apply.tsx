/**
 * Applying for funding.
 *
 * Every application type is served by this one page, because the questions come
 * from the API. Adding a form to the portal is a backend schema, not a new
 * thousand-line React component.
 *
 * The long forms are stepped, because they are long: forty-five questions on
 * one page is where people give up. The steps are presentation only — the
 * schema decides what is asked and the server decides what is valid — so the
 * grouping lives here and the short forms stay single-page.
 */
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import api, { ApiError, type ApplicationSchema, type ApplicationType } from '../../api/client';
import SchemaForm, { type Answers } from '../../components/SchemaForm';
import { Alert, Card } from '../../components/ui';
import { STEPS } from './steps';
import EnrolmentPreview from './EnrolmentPreview';

/** Types whose submission generates an enrolment verification for a registrar. */
const GENERATES_FORM_B: ApplicationType[] = ['admission', 'continuing_funding'];

export default function Apply() {
  const { type } = useParams<{ type: ApplicationType }>();
  const navigate = useNavigate();

  const [schema, setSchema] = useState<ApplicationSchema | null>(null);
  const [loadError, setLoadError] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);
  const [answers, setAnswers] = useState<Answers>({});
  const [initial, setInitial] = useState<Answers | null>(null);

  useEffect(() => {
    if (!type) return;
    let cancelled = false;
    setInitial(null);
    // Both together: the form is mounted once, with its opening answers
    // already in hand. Rendering first and filling in afterwards would discard
    // anything typed in between.
    Promise.all([
      api.schema(type),
      // A student with no history, or one whose prefill fails, still gets a
      // working empty form — this is a convenience, not a prerequisite.
      api.formPrefill(type).catch(() => ({})),
    ])
      .then(([definition, prefilled]) => {
        if (cancelled) return;
        setSchema(definition);
        setInitial(prefilled as Answers);
      })
      .catch(() => !cancelled && setLoadError('That application form could not be loaded.'));
    return () => { cancelled = true; };
  }, [type]);

  const submit = async (submitted: Answers) => {
    if (!type) return;
    setBusy(true);
    setErrors({});
    setFormError('');
    try {
      // The cast is the one place answers cross from an untyped form into the
      // typed client; the schema has already decided what the keys are.
      const created = await api.submit(type, submitted as never);
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
  if (!schema || initial === null) {
    return <main className="page"><div className="spinner" /></main>;
  }

  const showsFormB = Boolean(type && GENERATES_FORM_B.includes(type));

  return (
    <main className="page stack stack--loose">
      <header className="stack stack--tight">
        <h1>{schema.label}</h1>
        <p className="muted">{schema.summary}</p>
      </header>

      <Card>
        <div className="stack">
          <SchemaForm
            schema={schema}
            initial={initial}
            steps={type ? STEPS[type] : undefined}
            busy={busy}
            errors={errors}
            formError={formError}
            onChange={setAnswers}
            submitLabel="Submit application"
            footer={
              showsFormB && type ? (
                <EnrolmentPreview type={type} answers={answers} />
              ) : undefined
            }
            onSubmit={submit}
          />
        </div>
      </Card>
    </main>
  );
}
