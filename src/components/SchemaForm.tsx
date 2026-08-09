/**
 * Renders any application form from its schema.
 *
 * Replaces nine hand-written page components — FormA.tsx alone was 1,053 lines —
 * each of which restated its fields, its validation and a hand-maintained map
 * from its own state keys onto backend display strings. That map is where the
 * "renaming a label changes what a student is paid" class of bug lived.
 *
 * This component knows nothing about any particular form. It asks the API what
 * to show, and submits answers keyed by the same stable keys the backend
 * validates against.
 */

import { useMemo, useState } from 'react';

import type { ApplicationSchema, SchemaField } from '../api/schema.generated';
import { Alert, Button, Field, Input, Select, Textarea } from './ui';

export type AnswerValue = string | number | boolean;
export type Answers = Record<string, AnswerValue>;

function initialAnswers(schema: ApplicationSchema): Answers {
  const answers: Answers = {};
  for (const field of schema.fields) {
    answers[field.key] = field.type === 'boolean' ? false : '';
  }
  return answers;
}

function groupBySection(schema: ApplicationSchema): Array<[string, SchemaField[]]> {
  const groups = new Map<string, SchemaField[]>();
  for (const section of schema.sections) groups.set(section, []);
  for (const field of schema.fields) {
    const key = field.section || 'Details';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(field);
  }
  return [...groups.entries()].filter(([, fields]) => fields.length > 0);
}

/** The input type for a field. The schema decides; this only maps it to HTML. */
function ControlFor({
  field,
  value,
  invalid,
  onChange,
}: {
  field: SchemaField;
  value: AnswerValue;
  invalid: boolean;
  onChange: (next: AnswerValue) => void;
}) {
  const id = `f-${field.key}`;
  const described = invalid ? `${id}-error` : field.help_text ? `${id}-hint` : undefined;

  switch (field.type) {
    case 'choice':
      return (
        <Select
          id={id}
          invalid={invalid}
          aria-describedby={described}
          value={String(value ?? '')}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">Select…</option>
          {field.choices.map((choice) => (
            <option key={choice.value} value={choice.value}>
              {choice.label}
            </option>
          ))}
        </Select>
      );

    case 'boolean':
      return (
        <label className="checkbox" htmlFor={id}>
          <input
            id={id}
            type="checkbox"
            checked={Boolean(value)}
            aria-describedby={described}
            onChange={(e) => onChange(e.target.checked)}
          />
          <span>Yes</span>
        </label>
      );

    case 'long_text':
      return (
        <Textarea
          id={id}
          invalid={invalid}
          aria-describedby={described}
          value={String(value ?? '')}
          onChange={(e) => onChange(e.target.value)}
        />
      );

    default: {
      const htmlType =
        field.type === 'email'
          ? 'email'
          : field.type === 'phone'
            ? 'tel'
            : field.type === 'date'
              ? 'date'
              : field.type === 'integer'
                ? 'number'
                : 'text';
      return (
        <Input
          id={id}
          type={htmlType}
          invalid={invalid}
          aria-describedby={described}
          inputMode={field.type === 'money' || field.type === 'percent' ? 'decimal' : undefined}
          placeholder={field.type === 'money' ? '$0.00' : undefined}
          value={String(value ?? '')}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    }
  }
}

export function SchemaForm({
  schema,
  submitLabel = 'Submit application',
  busy,
  errors = {},
  formError,
  onSubmit,
}: {
  schema: ApplicationSchema;
  submitLabel?: string;
  busy?: boolean;
  /** Field-level messages from the API, keyed by the same stable field key. */
  errors?: Record<string, string>;
  formError?: string;
  onSubmit: (answers: Answers) => void;
}) {
  const [answers, setAnswers] = useState<Answers>(() => initialAnswers(schema));
  const sections = useMemo(() => groupBySection(schema), [schema]);

  const set = (key: string, value: AnswerValue) =>
    setAnswers((current) => ({ ...current, [key]: value }));

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    // Blanks are dropped rather than sent as empty strings: the schema treats a
    // missing optional answer as absent, and an empty string as a value.
    const filled: Answers = {};
    for (const [key, value] of Object.entries(answers)) {
      if (value !== '' && value !== false) filled[key] = value;
      if (value === false) {
        const field = schema.fields.find((f) => f.key === key);
        if (field?.type === 'boolean') filled[key] = false;
      }
    }
    onSubmit(filled);
  };

  const errorCount = Object.keys(errors).length;

  return (
    <form className="stack stack--loose" onSubmit={handleSubmit} noValidate>
      {formError && <Alert tone="error">{formError}</Alert>}
      {errorCount > 0 && (
        <Alert tone="error">
          {errorCount === 1
            ? 'One answer needs attention.'
            : `${errorCount} answers need attention.`}
        </Alert>
      )}

      {sections.map(([section, fields]) => (
        <section key={section} className="stack">
          <h3>{section}</h3>
          <div className="grid-2">
            {fields.map((field) => (
              <Field
                key={field.key}
                id={`f-${field.key}`}
                label={field.label}
                required={field.required}
                hint={field.help_text}
                error={errors[field.key]}
              >
                <ControlFor
                  field={field}
                  value={answers[field.key] ?? ''}
                  invalid={Boolean(errors[field.key])}
                  onChange={(next) => set(field.key, next)}
                />
              </Field>
            ))}
          </div>
        </section>
      ))}

      <div className="row">
        <Button type="submit" variant="primary" busy={busy}>
          {submitLabel}
        </Button>
        <span className="small muted">
          Fields marked <span className="field__required">*</span> are required.
        </span>
      </div>
    </form>
  );
}

export default SchemaForm;
