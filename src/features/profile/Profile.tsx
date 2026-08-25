/**
 * Everything the portal knows about you, in one place you can correct.
 *
 * Four sections, four saves. They are four different kinds of fact and they are
 * refused for four different reasons, so bundling them into one Save would mean
 * a mistyped transit number discarding a corrected address.
 *
 *   Your details      identity. Yours to correct at any time.
 *   Eligibility       the office's six questions. Re-answering them re-runs the
 *                     office's rule; the funding streams that come back are its
 *                     decision, never a choice made here.
 *   Where you study   convenience only. It pre-fills your next application and
 *                     decides nothing about what you are paid.
 *   Payment           where an approved award is sent.
 *
 * The point of all of it is the next form: what is here arrives already filled
 * in, and every box stays editable, because a pre-filled answer carries no more
 * authority than a typed one.
 */

import { useCallback, useEffect, useState } from 'react';

import api, {
  ApiError,
  type ApplicationSchema,
  type BankAccountSummary,
  type BankingInput,
  type CurrentUser,
  type EligibilityOutcome,
  type EnrolmentProfile,
  type ScreeningState,
  type SchemaField,
} from '../../api/client';
import { Alert, Badge, Button, Card, Field, Input, Select } from '../../components/ui';
import { formatDate } from '../../components/ui/format';

const STREAM_LABELS: Record<string, string> = {
  psssp: 'C-DFN PSSSP',
  ucepp: 'C-DFN UCEPP',
  dggr: 'DGGR Bursaries',
};

/** The identity boxes, in the order a person would read them out. */
const DETAIL_FIELDS: Array<{
  key: keyof CurrentUser;
  label: string;
  type?: string;
  hint?: string;
}> = [
  { key: 'first_name', label: 'First name' },
  { key: 'last_name', label: 'Last name' },
  { key: 'preferred_name', label: 'Preferred name', hint: 'What you would rather be called.' },
  { key: 'date_of_birth', label: 'Date of birth', type: 'date' },
  { key: 'pronouns', label: 'Pronouns' },
  { key: 'phone', label: 'Phone', type: 'tel' },
  { key: 'alternate_phone', label: 'Another number', type: 'tel' },
  { key: 'street_address', label: 'Street address' },
  { key: 'city', label: 'Community or city' },
  { key: 'province', label: 'Province or territory' },
  { key: 'postal_code', label: 'Postal code' },
  { key: 'beneficiary_number', label: 'Beneficiary number' },
  { key: 'treaty_number', label: 'Treaty number' },
];

/**
 * The study boxes.
 *
 * `choiceOf` names a field on the admission schema. The options are fetched
 * from the server rather than written out here: a profile holding a value the
 * schema does not recognise would pre-fill a form with an answer it refuses,
 * and the student would meet a validation error on something they never typed.
 * The labels are this screen's own — it is not an application form — but the
 * values have to be the schema's.
 */
const STUDY_FIELDS: Array<{
  key: keyof EnrolmentProfile;
  label: string;
  type?: string;
  hint?: string;
  choiceOf?: string;
}> = [
  { key: 'institution_name', label: 'Institution' },
  { key: 'institution_location', label: 'Where it is' },
  { key: 'program', label: 'Programme of study' },
  { key: 'credential_level', label: 'Working towards', choiceOf: 'credential_level' },
  { key: 'learning_style', label: 'Learning style', choiceOf: 'learning_style' },
  { key: 'course_load', label: 'Course load', choiceOf: 'course_load' },
  { key: 'student_number', label: 'Your student ID' },
  { key: 'program_start', label: 'Programme starts', type: 'date' },
  { key: 'program_end', label: 'Expected to finish', type: 'date' },
  { key: 'program_year', label: 'Year of the programme', type: 'number' },
  { key: 'program_length_years', label: 'Length in years', type: 'number' },
  {
    key: 'registrar_email',
    label: 'Registrar’s email',
    type: 'email',
    hint: 'Who we ask to confirm your enrolment. Without it, tuition cannot be confirmed.',
  },
  { key: 'institution_phone', label: 'Institution phone', type: 'tel' },
  { key: 'dependent_count', label: 'Number of dependants', type: 'number' },
];

const BANK_FIELDS: Array<{ key: keyof BankingInput; label: string; hint: string }> = [
  { key: 'account_holder', label: 'Account holder', hint: 'The name on the account.' },
  { key: 'transit_number', label: 'Transit number', hint: 'Five digits.' },
  { key: 'institution_number', label: 'Institution number', hint: 'Three digits.' },
  { key: 'account_number', label: 'Account number', hint: 'Seven to twelve digits.' },
];

const EMPTY_BANK: BankingInput = {
  account_holder: '',
  transit_number: '',
  institution_number: '',
  account_number: '',
};

/** A section's save state. Each section owns its own, for the reason above. */
function useSaving() {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const run = useCallback(
    async (action: () => Promise<void>, done: string) => {
      setBusy(true);
      setNotice('');
      setError('');
      setFieldErrors({});
      try {
        await action();
        setNotice(done);
      } catch (err) {
        if (err instanceof ApiError) {
          setFieldErrors(err.fieldErrors);
          // A message only where nothing landed against a box. Both at once
          // says the same thing twice and hides which box is wrong.
          if (Object.keys(err.fieldErrors).length === 0) setError(err.message);
        } else {
          setError('That could not be saved. Please try again.');
        }
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  return { busy, notice, error, fieldErrors, run };
}

function SectionMessages({ notice, error }: { notice: string; error: string }) {
  return (
    <>
      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="ok">{notice}</Alert>}
    </>
  );
}

export default function Profile() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [screening, setScreening] = useState<ScreeningState | null>(null);
  const [study, setStudy] = useState<EnrolmentProfile | null>(null);
  const [account, setAccount] = useState<BankAccountSummary | null>(null);
  const [schema, setSchema] = useState<ApplicationSchema | null>(null);
  const [loadError, setLoadError] = useState('');

  // The screening's own verdict on the answers just saved. Kept apart from the
  // generic "Saved" notice: "you no longer qualify for PSSSP" is the whole
  // point of the section, not a confirmation that a write succeeded.
  const [outcome, setOutcome] = useState<EligibilityOutcome | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [bank, setBank] = useState<BankingInput>(EMPTY_BANK);

  const details = useSaving();
  const eligibility = useSaving();
  const enrolment = useSaving();
  const payment = useSaving();

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api.me(),
      api.screening(),
      api.enrolmentProfile(),
      api.banking(),
      // Only for the choice values. A failure here must not take the page down
      // with it — the rest of the profile is still editable without it.
      api.schema('admission').catch(() => null),
    ])
      .then(([me, screeningState, profile, bankAccount, admission]) => {
        if (cancelled) return;
        setUser(me);
        setScreening(screeningState);
        setAnswers(screeningState.answers);
        setStudy(profile);
        setAccount(bankAccount);
        setSchema(admission);
      })
      .catch(() => !cancelled && setLoadError('Your profile could not be loaded.'));
    return () => {
      cancelled = true;
    };
  }, []);

  const choicesFor = (key?: string) => {
    if (!key) return null;
    const field = schema?.fields.find((f: SchemaField) => f.key === key);
    return field && field.type === 'choice' ? field.choices : null;
  };

  if (loadError) {
    return (
      <main className="page">
        <Alert tone="error">{loadError}</Alert>
      </main>
    );
  }
  if (!user || !screening || !study) {
    return (
      <main className="page">
        <div className="spinner" role="status" aria-label="Loading your profile" />
      </main>
    );
  }

  const setDetail = (key: keyof CurrentUser, value: string) =>
    setUser({ ...user, [key]: value });

  const setStudyValue = (key: keyof EnrolmentProfile, value: string) =>
    setStudy({ ...study, [key]: value });

  return (
    <main className="page stack stack--loose">
      <header className="stack stack--tight">
        <h1>Your profile</h1>
        <p className="muted">
          What we already know about you. Keeping it up to date means your next
          application opens filled in — and you can still change any answer on
          the form itself.
        </p>
      </header>

      {/* ── Your details ── */}
      <Card
        title="Your details"
        actions={
          <Button
            variant="primary"
            size="sm"
            busy={details.busy}
            onClick={() =>
              void details.run(async () => {
                setUser(
                  await api.updateMe(
                    Object.fromEntries(
                      DETAIL_FIELDS.map(({ key }) => [key, user[key] ?? '']),
                    ) as Partial<CurrentUser>,
                  ),
                );
              }, 'Your details were saved.')
            }
          >
            Save details
          </Button>
        }
      >
        <div className="stack">
          <SectionMessages notice={details.notice} error={details.error} />
          <p className="small muted">
            Signed in as {user.email}. To change the address you sign in with,
            contact the Education Department.
          </p>
          <div className="grid-2">
            {DETAIL_FIELDS.map(({ key, label, type, hint }) => (
              <Field
                key={key}
                id={`detail-${key}`}
                label={label}
                hint={hint}
                error={details.fieldErrors[key]}
              >
                <Input
                  id={`detail-${key}`}
                  type={type ?? 'text'}
                  value={(user[key] as string | null) ?? ''}
                  invalid={Boolean(details.fieldErrors[key])}
                  onChange={(e) => setDetail(key, e.target.value)}
                />
              </Field>
            ))}
          </div>
        </div>
      </Card>

      {/* ── Eligibility ── */}
      <Card
        title="What you qualify for"
        actions={
          <Button
            variant="primary"
            size="sm"
            busy={eligibility.busy}
            onClick={() =>
              void eligibility.run(async () => {
                const result = await api.saveScreening(answers);
                setUser(result.user);
                setScreening(result);
                setAnswers(result.answers);
                setOutcome(result.outcome);
              }, 'Your answers were saved.')
            }
          >
            Save answers
          </Button>
        }
      >
        <div className="stack">
          <SectionMessages notice={eligibility.notice} error={eligibility.error} />

          <div className="row">
            {screening.streams.length > 0 ? (
              screening.streams.map((stream) => (
                <Badge key={stream} tone="ok">
                  {STREAM_LABELS[stream] ?? stream.toUpperCase()}
                </Badge>
              ))
            ) : (
              <Badge tone="warn">No funding stream</Badge>
            )}
            {screening.assessed_at && (
              <span className="small muted">
                Last answered {formatDate(screening.assessed_at)}
              </span>
            )}
          </div>

          {/* The screening's own words. It is the office's rule, and it is the
              rule that decides — this screen only carries the answers to it. */}
          {outcome && (
            <Alert tone={outcome.eligible ? 'info' : 'error'}>
              <strong>{outcome.title}</strong> — {outcome.message}
            </Alert>
          )}

          <p className="small muted">
            These are the six questions you answered when you signed up. They
            decide which funding you can apply for, so answer them as they are
            true today — if you have started receiving Student Financial
            Assistance, say so here.
          </p>

          <div className="stack">
            {screening.questions.map((question) => (
              <Field
                key={question.key}
                id={`screening-${question.key}`}
                label={question.text}
                hint={question.help}
                error={eligibility.fieldErrors[question.key]}
              >
                <Select
                  id={`screening-${question.key}`}
                  value={answers[question.key] ?? ''}
                  onChange={(e) =>
                    setAnswers({ ...answers, [question.key]: e.target.value })
                  }
                >
                  <option value="">Not answered</option>
                  {question.choices.map((choice) => (
                    <option key={choice.value} value={choice.value}>
                      {choice.label}
                    </option>
                  ))}
                </Select>
              </Field>
            ))}
          </div>
        </div>
      </Card>

      {/* ── Where you study ── */}
      <Card
        title="Where you study"
        actions={
          <Button
            variant="primary"
            size="sm"
            busy={enrolment.busy}
            onClick={() =>
              void enrolment.run(async () => {
                setStudy(
                  await api.saveEnrolmentProfile(
                    Object.fromEntries(
                      STUDY_FIELDS.map(({ key }) => [key, study[key] ?? '']),
                    ) as Partial<EnrolmentProfile>,
                  ),
                );
              }, 'Your enrolment details were saved.')
            }
          >
            Save enrolment
          </Button>
        }
      >
        <div className="stack">
          <SectionMessages notice={enrolment.notice} error={enrolment.error} />
          <p className="small muted">
            None of this is required, and none of it decides what you are paid —
            it is here so you do not type it again on every form. The semester,
            its dates and the tuition you are quoted are asked on each
            application, because they change every term.
          </p>
          <div className="grid-2">
            {STUDY_FIELDS.map(({ key, label, type, hint, choiceOf }) => {
              const choices = choicesFor(choiceOf);
              const value = (study[key] as string | number | null) ?? '';
              return (
                <Field
                  key={key}
                  id={`study-${key}`}
                  label={label}
                  hint={hint}
                  error={enrolment.fieldErrors[key]}
                >
                  {choices ? (
                    <Select
                      id={`study-${key}`}
                      value={String(value)}
                      onChange={(e) => setStudyValue(key, e.target.value)}
                    >
                      <option value="">Not said</option>
                      {choices.map((choice) => (
                        <option key={choice.value} value={choice.value}>
                          {choice.label}
                        </option>
                      ))}
                    </Select>
                  ) : (
                    <Input
                      id={`study-${key}`}
                      type={type ?? 'text'}
                      value={String(value)}
                      invalid={Boolean(enrolment.fieldErrors[key])}
                      onChange={(e) => setStudyValue(key, e.target.value)}
                    />
                  )}
                </Field>
              );
            })}
          </div>
        </div>
      </Card>

      {/* ── Payment ── */}
      <Card
        title="Where you are paid"
        actions={
          <Button
            variant="primary"
            size="sm"
            busy={payment.busy}
            onClick={() =>
              void payment.run(async () => {
                setAccount(await api.saveBanking(bank));
                // Cleared once it is stored. The digits are never read back to
                // this screen, so leaving them in the boxes would be the only
                // place in the portal they can be read off a display.
                setBank(EMPTY_BANK);
              }, 'Your payment account was saved.')
            }
          >
            Save account
          </Button>
        }
      >
        <div className="stack">
          <SectionMessages notice={payment.notice} error={payment.error} />

          {account ? (
            <div className="row">
              <Badge tone="ok">Account on file</Badge>
              <span className="small muted">
                {account.account_number} · {account.account_holder}
              </span>
            </div>
          ) : (
            <Alert tone="info">
              No account on file. An approved award is held until one is
              recorded, so this is worth filling in before you are decided.
            </Alert>
          )}

          <p className="small muted">
            We never show the full number back, here or anywhere else. Entering
            an account replaces the one above from now on; anything already paid
            stays recorded against the account it went to.
          </p>

          <div className="grid-2">
            {BANK_FIELDS.map(({ key, label, hint }) => (
              <Field
                key={key}
                id={`bank-${key}`}
                label={label}
                hint={hint}
                error={payment.fieldErrors[key]}
              >
                <Input
                  id={`bank-${key}`}
                  value={bank[key]}
                  autoComplete="off"
                  invalid={Boolean(payment.fieldErrors[key])}
                  onChange={(e) => setBank({ ...bank, [key]: e.target.value })}
                />
              </Field>
            ))}
          </div>
        </div>
      </Card>
    </main>
  );
}
