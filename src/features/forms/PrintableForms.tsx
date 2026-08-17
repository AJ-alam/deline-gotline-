/**
 * Forms to print and fill in by hand.
 *
 * The portal this replaces offered a "Printable Forms Packet (PDF)". Nothing
 * generated it, and a PDF generator would be a second description of every
 * form to keep in step with the schemas — which is exactly the drift the
 * schema-driven renderer exists to remove.
 *
 * So the paper form is the same schema, laid out for paper, and printing is
 * the browser's job. "Save as PDF" is in every print dialogue. A field added
 * to a schema appears on the printed form the same day, because there is
 * nothing else to update.
 */

import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import api, { type ApplicationSchema } from '../../api/client';
import { Alert, Button, Card } from '../../components/ui';
import './printable.css';

/** How much room to leave for a handwritten answer. */
function linesFor(type: string): number {
  // 'long_text', not 'textarea' — no field is ever typed 'textarea', so this
  // test never once matched and every long answer printed a single line.
  if (type === 'long_text') return 4;
  if (type === 'signature') return 2;
  return 1;
}

function PrintedField({ field }: { field: ApplicationSchema['fields'][number] }) {
  // A declaration prints as the statement plus one box to tick. Falling through
  // to the default gave it a blank line to write on, which is not what is being
  // asked of the person holding the paper.
  if (field.type === 'confirm') {
    return (
      <div className="printed-field">
        {field.help_text && (
          <div className="printed-field__declaration">{field.help_text}</div>
        )}
        <div className="printed-choices">
          <span className="printed-choice">
            <span className="printed-box" aria-hidden="true" />
            {field.label}
            {field.required && <span aria-hidden="true"> *</span>}
          </span>
        </div>
      </div>
    );
  }

  if (field.type === 'choice' || field.type === 'boolean') {
    const options =
      field.type === 'boolean'
        ? [{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }]
        : field.choices;
    return (
      <div className="printed-field">
        <div className="printed-field__label">
          {field.label}
          {field.required && <span aria-hidden="true"> *</span>}
        </div>
        <div className="printed-choices">
          {options.map((choice) => (
            <span key={choice.value} className="printed-choice">
              <span className="printed-box" aria-hidden="true" />
              {choice.label}
            </span>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="printed-field">
      <div className="printed-field__label">
        {field.label}
        {field.required && <span aria-hidden="true"> *</span>}
      </div>
      {field.help_text && <div className="printed-field__hint">{field.help_text}</div>}
      {Array.from({ length: linesFor(field.type) }, (_, index) => (
        <div key={index} className="printed-rule" aria-hidden="true" />
      ))}
    </div>
  );
}

function PrintableForm({ schema }: { schema: ApplicationSchema }) {
  const sections = new Map<string, ApplicationSchema['fields']>();
  for (const field of schema.fields) {
    const key = field.section || 'Details';
    sections.set(key, [...(sections.get(key) ?? []), field]);
  }

  return (
    <article className="printed">
      <header className="printed__head">
        <div>
          <div className="printed__org">Deline Got&rsquo;ı̨nę Government</div>
          <div className="printed__sub">Student Financial Support Program</div>
        </div>
        <h1 className="printed__title">{schema.label}</h1>
      </header>

      <p className="printed__note">
        Complete in ink and return to the DGG Education Department. Fields
        marked * are required. Applying online at the portal is faster.
      </p>

      {[...sections.entries()].map(([section, fields]) => (
        <section key={section} className="printed__section">
          <h2 className="printed__section-title">{section}</h2>
          {fields.map((field) => (
            <PrintedField key={field.key} field={field} />
          ))}
        </section>
      ))}

      <section className="printed__section">
        <h2 className="printed__section-title">Office use only</h2>
        <div className="printed-field">
          <div className="printed-field__label">Received by / date</div>
          <div className="printed-rule" aria-hidden="true" />
        </div>
      </section>
    </article>
  );
}

export default function PrintableForms() {
  const { type } = useParams<{ type?: string }>();
  const [schemas, setSchemas] = useState<ApplicationSchema[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    api
      .schemas()
      .then((result) => !cancelled && setSchemas(result))
      .catch(() => !cancelled && setError('The forms could not be loaded.'));
    return () => { cancelled = true; };
  }, []);

  if (error) return <main className="page"><Alert tone="error">{error}</Alert></main>;
  if (!schemas) {
    return (
      <main className="page">
        <div className="spinner" role="status" aria-label="Loading forms" />
      </main>
    );
  }

  // One form, ready to print.
  if (type) {
    const schema = schemas.find((candidate) => candidate.slug === type);
    if (!schema) {
      return (
        <main className="page stack">
          <Alert tone="error">There is no form of that kind.</Alert>
          <p><Link to="/forms">All printable forms</Link></p>
        </main>
      );
    }
    return (
      <main className="page stack">
        <div className="row row--between no-print">
          <Link to="/forms" className="small">&larr; All printable forms</Link>
          <Button variant="primary" onClick={() => window.print()}>
            Print or save as PDF
          </Button>
        </div>
        <PrintableForm schema={schema} />
      </main>
    );
  }

  // The index.
  return (
    <main className="page stack stack--loose">
      <header className="stack stack--tight">
        <h1>Printable forms</h1>
        <p className="muted">
          Every application can be printed and filled in by hand, then dropped
          off or mailed to the DGG Education Department. Printed forms ask the
          same questions as the ones here, because they are generated from the
          same definition.
        </p>
      </header>

      <Card>
        <ul className="form-list">
          {schemas.map((schema) => (
            <li key={schema.slug} className="form-list__row">
              <span>
                <span className="form-list__name">{schema.label}</span>
                <span className="small muted">
                  {schema.fields.length} questions, {schema.sections.length} sections
                </span>
              </span>
              <Link to={`/forms/${schema.slug}`}>
                <Button size="sm">Open to print</Button>
              </Link>
            </li>
          ))}
        </ul>
      </Card>

      <p className="small muted">
        Paper applications take longer to process than applying in the portal.
      </p>
    </main>
  );
}
