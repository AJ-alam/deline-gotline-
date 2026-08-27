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

import api, { ApiError } from '../api/client';
import type { ReactNode } from 'react';

import type { ApplicationSchema, SchemaField } from '../api/schema.generated';
import { Alert, Button, Field, Input, Select, Textarea } from './ui';

/** One cell of a table row. Tables hold only the simple types. */
export type CellValue = string | number | boolean;
export type TableRow = Record<string, CellValue>;
export type AnswerValue = string | number | boolean | string[] | TableRow[];
export type Answers = Record<string, AnswerValue>;

function isRows(value: AnswerValue): value is TableRow[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'object');
}

function isReferences(value: AnswerValue): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

/**
 * Today, as a date input wants it.
 *
 * Built from the local parts rather than from `toISOString()`, which converts
 * to UTC first — west of Greenwich that is yesterday's date for most of the
 * working day, and Délı̨nę is seven hours behind it.
 */
function today(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

/** A row of a table with nothing in it. Blank rows are dropped by the server. */
function blankRow(field: SchemaField): TableRow {
  const row: TableRow = {};
  for (const column of field.columns) {
    row[column.key] = column.type === 'boolean' ? false : '';
  }
  return row;
}

function initialAnswers(schema: ApplicationSchema): Answers {
  const answers: Answers = {};
  for (const field of schema.fields) {
    // A required yes/no opens with no answer at all, not with 'no'. Otherwise
    // 'not yet answered' and 'no' are the same value, and the form cannot tell
    // whether the question was considered — which is how an unanswered "do you
    // receive SFA?" would quietly select the wrong funding stream.
    if (field.type === 'boolean') answers[field.key] = field.required ? '' : false;
    else if (field.type === 'confirm') answers[field.key] = false;
    else if (field.type === 'files') answers[field.key] = [];
    // Opens with one empty line, so the first expense is typed rather than
    // discovered behind an "add a row" button.
    else if (field.type === 'table') answers[field.key] = [blankRow(field)];
    // The date a declaration is signed is the day it is being filled in. Asking
    // someone to type that is asking them to look it up.
    else if (field.defaults_to_today) answers[field.key] = today();
    else answers[field.key] = '';
  }
  return answers;
}

/**
 * Whether a question has been answered.
 *
 * Not the same as "has a truthy value". 'No' is a complete answer to a yes/no
 * question, and treating it as missing made a required boolean impossible to
 * satisfy: the registrar could never report a student as *not* enrolled,
 * because the Submit button stayed disabled until they ticked the box saying
 * they were.
 */
function isAnswered(field: SchemaField, value: AnswerValue): boolean {
  if (field.type === 'boolean') return typeof value === 'boolean';
  if (field.type === 'files') return isReferences(value) && value.length > 0;
  // A table opens with a blank row, so 'has rows' would call it answered before
  // anything was typed. It counts as answered once one row has every column the
  // schema marks required — which is the same row the server keeps.
  if (field.type === 'table') {
    if (!isRows(value)) return false;
    return value.some((row) =>
      field.columns.every(
        (column) => !column.required || isAnswered(column, row[column.key] ?? ''),
      ),
    );
  }
  return Boolean(value);
}

function groupBySection(schema: ApplicationSchema): Array<[string, SchemaField[]]> {
  const groups = new Map<string, SchemaField[]>();
  for (const section of schema.sections) groups.set(section, []);
  for (const field of schema.fields) {
    // The server works these out from the other answers. There is no input to
    // render and no value to send; they appear on the application once it is
    // filed, labelled by this same schema.
    if (field.computed) continue;
    const key = field.section || 'Details';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(field);
  }
  return [...groups.entries()].filter(([, fields]) => fields.length > 0);
}

/**
 * A Social Insurance Number.
 *
 * Hidden by default with a reveal, and grouped as it is typed so a nine-digit
 * run is checkable at a glance. Never autofilled and never spellchecked: the
 * browser should not be storing this one.
 */
/**
 * The same rule the server applies, so the answer is known before submitting.
 *
 * A SIN carries a Luhn check digit — which is why most made-up numbers are
 * refused — and no issued number begins with 0. Saying so here rather than at
 * the end of a four-step form is the difference between a corrected digit and
 * an abandoned application.
 */
function sinProblem(digits: string): string {
  if (digits.length === 0) return '';
  if (digits.length < 9) return `${9 - digits.length} more digit${digits.length === 8 ? '' : 's'} to go.`;
  if (digits[0] === '0') return 'No Social Insurance Number starts with 0.';

  let total = 0;
  for (let index = 0; index < 9; index += 1) {
    const digit = Number(digits[index]);
    if (index % 2) {
      const doubled = digit * 2;
      total += doubled > 9 ? doubled - 9 : doubled;
    } else {
      total += digit;
    }
  }
  return total % 10 === 0
    ? ''
    : 'That is not a valid number — check the digits, one may be mistyped or two swapped.';
}

function SinInput({
  id,
  invalid,
  described,
  value,
  onChange,
}: {
  id: string;
  invalid: boolean;
  described?: string;
  value: string;
  onChange: (next: AnswerValue) => void;
}) {
  const [revealed, setRevealed] = useState(false);
  const [touched, setTouched] = useState(false);
  const grouped = value.replace(/(\d{3})(?=\d)/g, '$1 ').trim();
  // Held back until they have stopped typing the first few digits, so it does
  // not read as an error before there is anything to be wrong about.
  const problem = touched ? sinProblem(value) : '';

  return (
    <div className="stack stack--tight">
    <div className="auth-reveal">
      <Input
        id={id}
        type={revealed ? 'text' : 'password'}
        invalid={invalid}
        aria-describedby={described}
        inputMode="numeric"
        autoComplete="off"
        spellCheck={false}
        placeholder="000 000 000"
        value={revealed ? grouped : value}
        // Digits only: the grouping is presentation, and the server is sent
        // exactly what it validates.
        onChange={(e) => onChange(e.target.value.replace(/\D/g, '').slice(0, 9))}
        onBlur={() => setTouched(true)}
      />
      <button type="button" onClick={() => setRevealed(!revealed)} aria-pressed={revealed}
              aria-controls={id}>
        {revealed ? 'Hide' : 'Show'}
      </button>
    </div>
    {problem && (
      <span className="field__error" role="alert">{problem}</span>
    )}
    {!problem && value.length === 9 && (
      <span className="upload__done">&#10003; That looks right</span>
    )}
    </div>
  );
}

/**
 * A supporting document.
 *
 * Uploads as soon as a file is chosen rather than at submit, so someone on a
 * slow connection finds out immediately if it was too large or the wrong kind,
 * instead of after filling in the rest of the form. The answer holds the
 * reference the server gives back; the file itself never goes near the schema.
 */
function FileField({
  id,
  fieldKey,
  value,
  invalid,
  described,
  onChange,
}: {
  id: string;
  fieldKey: string;
  value: string;
  invalid: boolean;
  described?: string;
  onChange: (next: AnswerValue) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState('');
  const [failed, setFailed] = useState('');

  const choose = async (file?: File) => {
    if (!file) return;
    setBusy(true);
    setFailed('');
    try {
      const uploaded = await api.uploadDocument(file, fieldKey);
      setName(uploaded.original_name);
      onChange(uploaded.reference);
    } catch (err) {
      setFailed(
        err instanceof ApiError && err.fieldErrors.file
          ? err.fieldErrors.file
          : 'That file could not be uploaded. Please try again.',
      );
      setName('');
      onChange('');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="upload">
      <label className={`upload__button ${invalid ? 'upload__button--invalid' : ''}`.trim()}>
        <input
          id={id}
          type="file"
          className="sr-only"
          aria-describedby={described}
          accept=".pdf,.jpg,.jpeg,.png,.heic,.webp,application/pdf,image/*"
          onChange={(e) => { void choose(e.target.files?.[0]); }}
        />
        {busy ? 'Uploading…' : value ? 'Replace file' : 'Choose file'}
      </label>

      {/* Replacing is not removing. A student told to take down a document
          attached to the wrong question could only put a different one in its
          place, which leaves the wrong answer answered. */}
      {!busy && value && (
        <Button
          variant="ghost"
          aria-label={`Remove ${name || 'attached document'}`}
          onClick={() => { setName(''); setFailed(''); onChange(''); }}
        >
          Remove
        </Button>
      )}

      <span className="upload__state">
        {busy && <span className="spinner" aria-hidden="true" />}
        {!busy && value && (
          <span className="upload__done">✓ {name || 'Attached'}</span>
        )}
        {!busy && !value && !failed && (
          <span className="muted small">PDF or photo, up to 10MB</span>
        )}
        {failed && <span className="upload__failed">{failed}</span>}
      </span>
    </div>
  );
}

/** What the file picker will accept. The server refuses anything else outright. */
const ACCEPTS = '.pdf,.jpg,.jpeg,.png,.heic,.webp,application/pdf,image/*';

/**
 * Several documents answering one question.
 *
 * A travel claim has a boarding pass, a hotel folio and four taxi receipts. A
 * single-file question means they are either photographed onto one page or
 * mostly left out, and the office assesses the claim without them.
 *
 * Each file is uploaded as it is chosen, like the single-file control, so a
 * rejection is reported against the file that caused it rather than against
 * the whole selection at submit time. One failure does not discard the files
 * that worked.
 */
function MultiFileField({
  id,
  field,
  value,
  invalid,
  described,
  onChange,
}: {
  id: string;
  field: SchemaField;
  value: string[];
  invalid: boolean;
  described?: string;
  onChange: (next: AnswerValue) => void;
}) {
  const [busy, setBusy] = useState(0);
  const [names, setNames] = useState<Record<string, string>>({});
  const [failures, setFailures] = useState<string[]>([]);

  const room = field.max_items ? field.max_items - value.length : Infinity;

  const choose = async (chosen: FileList | null) => {
    const files = [...(chosen ?? [])];
    if (files.length === 0) return;

    const tooMany = files.length > room;
    const accepted = tooMany ? files.slice(0, Math.max(room, 0)) : files;

    setBusy(accepted.length);
    setFailures(
      tooMany
        ? [`Only ${field.max_items} files can be attached, so ${files.length - accepted.length} were not.`]
        : [],
    );

    const added: string[] = [];
    const labels: Record<string, string> = {};
    const problems: string[] = [];

    for (const file of accepted) {
      try {
        const uploaded = await api.uploadDocument(file, field.key);
        added.push(uploaded.reference);
        labels[uploaded.reference] = uploaded.original_name;
      } catch (err) {
        problems.push(
          `${file.name}: ${
            err instanceof ApiError && err.fieldErrors.file
              ? err.fieldErrors.file
              : 'could not be uploaded.'
          }`,
        );
      }
      setBusy((remaining) => remaining - 1);
    }

    setNames((current) => ({ ...current, ...labels }));
    setFailures((current) => [...current, ...problems]);
    // Read from the argument, not from a captured `value`: several uploads
    // finish against the same render, and each would otherwise overwrite the
    // last with a list that never saw it.
    if (added.length > 0) onChange([...value, ...added]);
  };

  const remove = (reference: string) =>
    onChange(value.filter((held) => held !== reference));

  return (
    <div className="uploads">
      <div className="upload">
        <label className={`upload__button ${invalid ? 'upload__button--invalid' : ''}`.trim()}>
          <input
            id={id}
            type="file"
            multiple
            className="sr-only"
            aria-describedby={described}
            accept={ACCEPTS}
            onChange={(e) => {
              void choose(e.target.files);
              // Cleared so choosing the same file again still fires a change —
              // which is what happens when one upload failed and is retried.
              e.target.value = '';
            }}
          />
          {busy > 0 ? 'Uploading…' : value.length > 0 ? 'Add more files' : 'Choose files'}
        </label>

        <span className="upload__state">
          {busy > 0 && <span className="spinner" aria-hidden="true" />}
          {busy === 0 && value.length === 0 && failures.length === 0 && (
            <span className="muted small">
              PDF or photo, up to 10MB each. Select several at once.
            </span>
          )}
          {busy === 0 && value.length > 0 && (
            <span className="upload__done">
              ✓ {value.length} {value.length === 1 ? 'file' : 'files'} attached
            </span>
          )}
        </span>
      </div>

      {value.length > 0 && (
        <ul className="uploads__list">
          {value.map((reference) => (
            <li key={reference}>
              <span>{names[reference] || 'Attached document'}</span>
              <button
                type="button"
                className="textbtn"
                // Six identical "Remove" buttons in a row is six identical
                // announcements; the name says which file goes.
                aria-label={`Remove ${names[reference] || 'attached document'}`}
                onClick={() => remove(reference)}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      {failures.map((problem) => (
        <span key={problem} className="upload__failed">{problem}</span>
      ))}
    </div>
  );
}

/**
 * Rows of the same few questions, entered as many times as needed.
 *
 * The expense breakdown on a travel claim is the case this exists for. A fixed
 * set of expense_1 … expense_6 fields caps the claim at a number somebody
 * guessed and puts the row number inside the field's identity, which is the
 * mistake this whole schema arrangement was built to stop.
 *
 * The running total under a money column is the table's own arithmetic and
 * nothing more. What is claimed is decided by the server, which adds up the
 * rows it kept — so a stray blank line here cannot change what is paid.
 */
function TableField({
  id,
  field,
  rows,
  invalid,
  described,
  onChange,
}: {
  id: string;
  field: SchemaField;
  rows: TableRow[];
  invalid: boolean;
  described?: string;
  onChange: (next: AnswerValue) => void;
}) {
  const setCell = (index: number, key: string, cell: CellValue) =>
    onChange(rows.map((row, at) => (at === index ? { ...row, [key]: cell } : row)));

  const addRow = () => onChange([...rows, blankRow(field)]);

  // The last row is emptied rather than removed, so the table never collapses
  // to nothing and leaves no way back to a first line.
  const removeRow = (index: number) =>
    onChange(
      rows.length === 1 ? [blankRow(field)] : rows.filter((_, at) => at !== index),
    );

  const money = field.columns.filter((column) => column.type === 'money');
  const full = Boolean(field.max_items) && rows.length >= field.max_items;

  return (
    <div
      className="rows"
      role="group"
      // A table is no more the target of htmlFor than a radiogroup is, so it
      // points back at the label the Field wrapper drew.
      aria-labelledby={`${id}-label`}
      aria-describedby={described}
    >
      <table className={`rows__table ${invalid ? 'rows__table--invalid' : ''}`.trim()}>
        <thead>
          <tr>
            {field.columns.map((column) => (
              <th key={column.key} scope="col">
                {column.label}
                {column.required && <span className="field__required" aria-hidden="true"> *</span>}
              </th>
            ))}
            <th scope="col"><span className="sr-only">Remove</span></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            // Keyed by position: a row has no identity of its own, and keying
            // by content would remount the cell being typed into.
            <tr key={index}>
              {field.columns.map((column) => (
                <td key={column.key} data-label={column.label}>
                  <ControlFor
                    field={{ ...column, key: `${field.key}-${index}-${column.key}` }}
                    value={row[column.key] ?? ''}
                    invalid={false}
                    onChange={(next) => setCell(index, column.key, next as CellValue)}
                  />
                </td>
              ))}
              <td>
                <button
                  type="button"
                  className="textbtn"
                  // Labelled rather than composed from a visually hidden span:
                  // accessible-name computation collapses the leading space,
                  // so "Remove" + " row 1" is announced as "Removerow 1".
                  aria-label={`Remove row ${index + 1}`}
                  onClick={() => removeRow(index)}
                >
                  Remove
                </button>
              </td>
            </tr>
          ))}
        </tbody>
        {money.length > 0 && (
          <tfoot>
            <tr>
              {field.columns.map((column) => (
                <td key={column.key}>
                  {column.type === 'money' ? (
                    <strong>{formatMoney(sumColumn(rows, column.key))}</strong>
                  ) : column === field.columns[0] ? (
                    <strong>Total</strong>
                  ) : null}
                </td>
              ))}
              <td />
            </tr>
          </tfoot>
        )}
      </table>

      <Button type="button" onClick={addRow} disabled={full}>
        Add a line
      </Button>
      {full && (
        <span className="muted small">
          {field.max_items} lines is the most one claim can carry.
        </span>
      )}
    </div>
  );
}

/** The numbers in one column, added up. Anything unparseable counts as nothing. */
function sumColumn(rows: TableRow[], key: string): number {
  return rows.reduce((total, row) => {
    const amount = Number(String(row[key] ?? '').replace(/[$,\s]/g, ''));
    return total + (Number.isFinite(amount) ? amount : 0);
  }, 0);
}

function formatMoney(amount: number): string {
  return `$${amount.toFixed(2)}`;
}

/**
 * A declaration the applicant signs up to.
 *
 * Rendered outside the usual Field wrapper because the statement being agreed
 * to is the point — it belongs above the box, at full width, not tucked
 * underneath as a hint. The server refuses an unconfirmed one, so this is the
 * only field type where an unticked box is an error rather than an answer.
 */
function DeclarationField({
  field,
  checked,
  error,
  onChange,
}: {
  field: SchemaField;
  checked: boolean;
  error?: string;
  onChange: (next: AnswerValue) => void;
}) {
  const id = `f-${field.key}`;
  return (
    <div className="field field--wide declaration">
      {field.help_text && <p className="declaration__text">{field.help_text}</p>}
      <label className="checkbox" htmlFor={id}>
        <input
          id={id}
          type="checkbox"
          checked={checked}
          aria-describedby={error ? `${id}-error` : undefined}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span>
          {field.label}
          <span className="field__required" aria-hidden="true"> *</span>
        </span>
      </label>
      {error && (
        <span className="field__error" id={`${id}-error`} role="alert">{error}</span>
      )}
    </div>
  );
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

    case 'boolean': {
      // Optional questions stay a single tick: leaving one alone means 'no',
      // and nothing downstream distinguishes the two.
      if (!field.required) {
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
      }
      // Required ones are asked as two explicit choices, so that answering
      // 'no' is something the form can see happen.
      return (
        <div
          className={`choices ${invalid ? 'choices--invalid' : ''}`.trim()}
          role="radiogroup"
          // Labelled by the question, not by htmlFor: a radio carrying the
          // field's id would announce itself as the whole question rather than
          // as 'Yes'.
          aria-labelledby={`${id}-label`}
          aria-describedby={described}
        >
          {[{ text: 'Yes', choice: true }, { text: 'No', choice: false }].map(
            ({ text, choice }) => (
              <label key={text} className="choices__option">
                <input
                  type="radio"
                  name={id}
                  id={`${id}-${text.toLowerCase()}`}
                  checked={value === choice}
                  onChange={() => onChange(choice)}
                />
                <span>{text}</span>
              </label>
            ),
          )}
        </div>
      );
    }

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

    // A real upload. These were text inputs, so the documents an assessment
    // depends on could be claimed but never attached.
    case 'file':
      return <FileField id={id} fieldKey={field.key} value={String(value ?? '')}
                        invalid={invalid} described={described} onChange={onChange} />;

    case 'files':
      return <MultiFileField id={id} field={field}
                             value={isReferences(value) ? value : []}
                             invalid={invalid} described={described} onChange={onChange} />;

    case 'table':
      return <TableField id={id} field={field} rows={isRows(value) ? value : []}
                         invalid={invalid} described={described} onChange={onChange} />;

    // A government identifier. Masked as it is typed, because these are filled
    // in on shared machines and over someone's shoulder, with a reveal for
    // checking a digit. The server never sends one back, so this is only ever
    // empty or freshly typed.
    case 'sin':
      return <SinInput id={id} invalid={invalid} described={described}
                       value={String(value ?? '')} onChange={onChange} />;

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
  initial,
  steps,
  footer,
  revising = false,
  privateOnFile = [],
  onChange,
  onSubmit,
}: {
  schema: ApplicationSchema;
  submitLabel?: string;
  busy?: boolean;
  /** Field-level messages from the API, keyed by the same stable field key. */
  errors?: Record<string, string>;
  formError?: string;
  /**
   * Answers the form opens with.
   *
   * The enrolment verification arrives filled in from the student's
   * application, so the registrar confirms rather than retypes — which is the
   * whole point of generating it. Every value stays editable: they are being
   * asked to check these against their own records, not to accept them.
   */
  initial?: Answers;
  /**
   * Break the form into steps, each naming the sections it holds.
   *
   * Presentation only: the schema decides what is asked and the server decides
   * what is valid. Omitted, the form renders as one page — which is what every
   * other application type still does.
   */
  steps?: Array<{ title: string; sections: string[] }>;
  /** Rendered on the final step, above the submit button. */
  footer?: ReactNode;
  /**
   * Opened on an application that already exists.
   *
   * A private answer — a SIN, a bank account — is split off at submission and
   * never returned, so the form opens with it blank. Required, those blanks
   * held the Save button disabled on every edit of every form that asks for
   * one: the office could not correct such an application and the student
   * could not answer a request for more information. Blank means unchanged;
   * typing a new value still validates it, here and on the server.
   */
  revising?: boolean;
  /**
   * Private answers the server already holds for this applicant.
   *
   * `account_number` is written once and read by nothing but the finance
   * export, so `prefill` never returns it — the portal does not show a student
   * their own account number. `Schema.clean(private_on_file=...)` accepts a
   * blank one when a `BankAccount` exists, and that pair is the only reason a
   * second application is submittable at all.
   *
   * The renderer did not know, so it counted the blank as missing and disabled
   * the submit button: a returning student opening the renewal they file every
   * semester was told "1 left on this form" against a box they can neither see
   * nor fill. `GET /api/form-prefill/{slug}/` reports these, from the same
   * function the create serializer passes to the validator, so the form and
   * the server cannot disagree about what is on file.
   */
  privateOnFile?: string[];
  /** Every change, for a caller that needs to see answers before submission —
   *  the enrolment verification preview is generated from them. */
  onChange?: (answers: Answers) => void;
  onSubmit: (answers: Answers) => void;
}) {
  const [answers, setAnswers] = useState<Answers>(
    () => ({ ...initialAnswers(schema), ...(initial ?? {}) }),
  );
  const sections = useMemo(() => groupBySection(schema), [schema]);

  // The updater stays pure. Calling the parent's onChange inside it is a side
  // effect in a function React is free to run more than once, which is how a
  // single upload failure ended up reported twice.
  const set = (key: string, value: AnswerValue) => {
    const next = { ...answers, [key]: value };
    setAnswers(next);
    onChange?.(next);
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    // Blanks are dropped rather than sent as empty strings: the schema treats a
    // missing optional answer as absent, and an empty string as a value.
    const filled: Answers = {};
    for (const [key, value] of Object.entries(answers)) {
      const field = schema.fields.find((f) => f.key === key);
      // Never sent. The server works these out and discards anything supplied
      // for them, so including one only invites the two to disagree.
      if (field?.computed) continue;

      if (Array.isArray(value)) {
        // An untouched table still holds its blank opening row, and an empty
        // list is the same as an unanswered question — both are left out so
        // the schema sees an absent optional answer rather than an empty one.
        const kept = isRows(value)
          ? value.filter((row) => Object.values(row).some((cell) => cell !== '' && cell !== false))
          : value;
        if (kept.length > 0) filled[key] = kept;
        continue;
      }
      if (value !== '' && value !== false) filled[key] = value;
      if (value === false && field?.type === 'boolean') filled[key] = false;
    }
    onSubmit(filled);
  };

  const errorCount = Object.keys(errors).length;

  // Which sections are grouped into which step. A schema with no grouping is
  // one long form, exactly as before.
  const groups = useMemo(() => {
    if (!steps || steps.length === 0) return null;
    return steps.map((step) => ({
      title: step.title,
      sections: sections.filter(([name]) => step.sections.includes(name)),
    })).filter((group) => group.sections.length > 0);
  }, [steps, sections]);

  const [step, setStep] = useState(0);
  const current = groups ? groups[Math.min(step, groups.length - 1)] : null;
  const shown = current ? current.sections : sections;
  const last = !groups || step >= groups.length - 1;

  // Headings earn their place only where they divide something. An unstepped
  // form needs them to show its structure; a step made of several sections
  // needs them to separate those; a step made of one does not.
  const showSectionHeadings = !current || current.sections.length > 1;

  /** A private answer the server already holds, so a blank is an answer. */
  const heldOnFile = (field: SchemaField) =>
    field.private === true && privateOnFile.includes(field.key);

  /** Which of this step's required questions are still blank. */
  const missing = shown.flatMap(([, fields]) =>
    fields.filter((field) => field.required
      && !(revising && field.private)
      && !heldOnFile(field)
      && !isAnswered(field, answers[field.key])),
  );

  // A server-side error on a field that is not on this step would otherwise be
  // invisible: the person is told something is wrong and shown nothing. Adjusted
  // during render rather than in an effect — the step is derived from errors
  // that just arrived, and an effect would render the wrong step first.
  // Compared by content, not identity: the default `errors = {}` is a fresh
  // object on every render, and comparing identity would set state forever.
  const errorSignature = Object.keys(errors).sort().join('|');
  const [lastErrors, setLastErrors] = useState(errorSignature);
  if (errorSignature !== lastErrors) {
    setLastErrors(errorSignature);
    if (groups && errorCount > 0) {
      const firstBad = groups.findIndex(({ sections: inStep }) =>
        inStep.some(([, fields]) => fields.some((field) => errors[field.key])),
      );
      if (firstBad >= 0) setStep(firstBad);
    }
  }

  return (
    <form
      className="stack stack--loose"
      onSubmit={(event) => {
        // Enter inside a field must not submit from step two of four.
        if (!last) {
          event.preventDefault();
          return;
        }
        handleSubmit(event);
      }}
      noValidate
    >
      {groups && (
        <ol className="steps" aria-label="Progress">
          {groups.map((group, index) => (
            <li
              key={group.title}
              className={[
                'steps__step',
                index === step ? 'steps__step--current' : '',
                index < step ? 'steps__step--done' : '',
              ].filter(Boolean).join(' ')}
              aria-current={index === step ? 'step' : undefined}
            >
              {/* Backwards only: forwards is guarded by the required answers
                  on the step being left. */}
              <button
                type="button"
                className="steps__label"
                disabled={index > step}
                onClick={() => setStep(index)}
              >
                <span className="steps__number">{index < step ? '✓' : index + 1}</span>
                <span>{group.title}</span>
              </button>
            </li>
          ))}
        </ol>
      )}

      {formError && <Alert tone="error">{formError}</Alert>}
      {errorCount > 0 && (
        <Alert tone="error">
          {errorCount === 1
            ? 'One answer needs attention.'
            : `${errorCount} answers need attention.`}
        </Alert>
      )}

      {shown.map(([section, fields]) => (
        <section key={section} className="stack">
          {/* A step holding a single section is already named by the progress
              list above. Printing that name again immediately over the fields
              was the same sentence three times before a single question. */}
          {showSectionHeadings && <h3>{section}</h3>}
          <div className="grid-2">
            {fields.map((field) => (
              field.type === 'confirm' ? (
                <DeclarationField
                  key={field.key}
                  field={field}
                  checked={answers[field.key] === true}
                  error={errors[field.key]}
                  onChange={(next) => set(field.key, next)}
                />
              ) : (
                <Field
                  key={field.key}
                  id={`f-${field.key}`}
                  label={field.label}
                  // A withheld answer is not required *of this edit*: it is
                  // already stored, and marking it so would put an asterisk on
                  // a blank nobody has to fill in.
                  required={field.required
                    && !(revising && field.private)
                    && !heldOnFile(field)}
                  hint={field.required && field.private
                    && ((revising && field.private) || heldOnFile(field))
                    ? `${field.help_text} Leave blank to keep what is on file.`.trim()
                    : field.help_text}
                  error={errors[field.key]}
                  wide={['long_text', 'signature', 'table', 'files'].includes(field.type)}
                >
                  <ControlFor
                    field={field}
                    value={answers[field.key] ?? ''}
                    invalid={Boolean(errors[field.key])}
                    onChange={(next) => set(field.key, next)}
                  />
                </Field>
              )
            ))}
          </div>
        </section>
      ))}

      {/* Anything the page wants between the last question and the button —
          the enrolment verification preview sits here. */}
      {last && footer}

      <div className="row row--between">
        <div className="row">
          {groups && step > 0 && (
            <Button type="button" onClick={() => setStep(step - 1)}>
              &larr; Back
            </Button>
          )}
        </div>

        <div className="row">
          {!last ? (
            <Button
              type="button"
              variant="primary"
              disabled={missing.length > 0}
              onClick={() => setStep(step + 1)}
            >
              Next step &rarr;
            </Button>
          ) : (
            <Button type="submit" variant="primary" busy={busy}
                    disabled={missing.length > 0}>
              {submitLabel}
            </Button>
          )}
        </div>
      </div>

      <p className="small muted">
        {missing.length > 0
          ? `Please complete all required fields — ${missing.length} left on this ${groups ? 'step' : 'form'}.`
          : 'Fields marked * are required.'}
      </p>
    </form>
  );
}

export default SchemaForm;
