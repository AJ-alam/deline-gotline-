/**
 * The funding breakdown, set by hand.
 *
 * The rules price the ordinary case. They cannot know that an institution
 * charges a fee no rate covers, or that the office agreed something at the
 * counter — and the only ways to express that were to edit a policy rate, which
 * changes what every student is paid, or to pay the wrong amount.
 *
 * Opens on whatever is currently awarded, so the office corrects rather than
 * retypes. Rows can be added and removed; the total is added up here and again
 * on the server, from the same lines.
 */

import { useEffect, useState } from 'react';

import api, {
  ApiError,
  type Application,
  type AwardLineInput,
} from '../../api/client';
import { Alert, Button, Card, Field, Input, Select } from '../../components/ui';
import { formatMoney } from '../../components/ui/format';

/** A new, empty line.
 *
 * The category defaults to the first one the server offers, not to a value
 * written in here. `'tuition'` was hard-coded, so a line added by hand carried
 * a category the office might not have on its list at all — the select showed
 * the first option while the state held something else, and saving filed the
 * line under a category nobody had chosen. The fallback only stands for the
 * moment before the categories arrive.
 */
function blank(categories: Array<{ value: string }>): AwardLineInput {
  return { category: categories[0]?.value ?? 'tuition', description: '', amount: '' };
}

export default function AwardEditor({
  application,
  onDone,
  onCancel,
}: {
  application: Application;
  onDone: () => void | Promise<void>;
  onCancel: () => void;
}) {
  const [categories, setCategories] = useState<Array<{ value: string; label: string }>>([]);
  const [lines, setLines] = useState<AwardLineInput[]>(() => {
    const current = application.decision?.lines ?? [];
    if (current.length === 0) return [blank([])];
    return current.map((line) => ({
      category: line.category,
      // The trace carries what each line is *for*; the line itself only knows
      // its category, and "Tuition" twice tells the office nothing.
      description: application.decision?.trace.rules
        .find((rule) => rule.code === line.rule_code)?.description ?? '',
      amount: line.amount,
    }));
  });
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    api.awardCategories(application.id)
      .then((available) => {
        if (cancelled || available.length === 0) return;
        setCategories(available);

        // Bring any line whose category is not on the list onto the first one
        // that is. A `<select>` given a value none of its options carries
        // displays the first option instead, so the screen said "Living
        // Allowance" while the state still held the value it was created with
        // — and saving filed the line under a category nobody had chosen. The
        // categories are fetched, so a line can always be created before they
        // arrive; this is the only place the two can be made to agree.
        const known = new Set(available.map((category) => category.value));
        setLines((current) => (
          current.every((line) => known.has(line.category))
            ? current
            : current.map((line) => (
              known.has(line.category)
                ? line
                : { ...line, category: available[0].value }
            ))
        ));
      })
      .catch(() => { /* The select falls back to what is already on the lines. */ });
    return () => { cancelled = true; };
  }, [application.id]);

  const set = (index: number, patch: Partial<AwardLineInput>) =>
    setLines(lines.map((line, at) => (at === index ? { ...line, ...patch } : line)));

  const total = lines.reduce((sum, line) => {
    const amount = Number(String(line.amount).replace(/[$,]/g, ''));
    return sum + (Number.isFinite(amount) ? amount : 0);
  }, 0);

  const save = async () => {
    setBusy(true);
    setError('');
    try {
      await api.setAward(application.id, lines, note);
      await onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The award could not be saved.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      title="Set the funding breakdown"
      actions={<Button variant="ghost" onClick={onCancel}>Cancel</Button>}
    >
      <div className="stack">
        <Alert tone="info">
          These figures replace what the rules worked out, and the applicant is
          shown them. Pressing <strong>Record award</strong> afterwards prices
          the application from the rules again and discards what you enter here.
        </Alert>

        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">What it is for</th>
                <th scope="col">Category</th>
                <th scope="col">Amount</th>
                <th scope="col"><span className="sr-only">Remove</span></th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, index) => (
                <tr key={index}>
                  <td data-label="What it is for">
                    <Input
                      aria-label={`What line ${index + 1} is for`}
                      value={line.description}
                      placeholder="Tuition as billed"
                      onChange={(e) => set(index, { description: e.target.value })}
                    />
                  </td>
                  <td data-label="Category">
                    <Select
                      aria-label={`Category for line ${index + 1}`}
                      value={line.category}
                      onChange={(e) => set(index, { category: e.target.value })}
                    >
                      {(categories.length ? categories : [{ value: line.category, label: line.category }])
                        .map((category) => (
                          <option key={category.value} value={category.value}>
                            {category.label}
                          </option>
                        ))}
                    </Select>
                  </td>
                  <td data-label="Amount">
                    <Input
                      aria-label={`Amount for line ${index + 1}`}
                      inputMode="decimal"
                      value={line.amount}
                      placeholder="0.00"
                      onChange={(e) => set(index, { amount: e.target.value })}
                    />
                  </td>
                  <td>
                    <Button
                      variant="ghost"
                      aria-label={`Remove line ${index + 1}`}
                      disabled={lines.length === 1}
                      onClick={() => setLines(lines.filter((_, at) => at !== index))}
                    >
                      Remove
                    </Button>
                  </td>
                </tr>
              ))}
              <tr>
                <td><strong>Total</strong></td>
                <td />
                <td className="num"><strong>{formatMoney(total)}</strong></td>
                <td />
              </tr>
            </tbody>
          </table>
        </div>

        <div className="row">
          <Button variant="ghost" onClick={() => setLines([...lines, blank(categories)])}>
            Add a line
          </Button>
        </div>

        <Field
          id="award-note"
          label="Why is it being set by hand?"
          hint="Kept with the award and shown against every line."
        >
          <Input
            id="award-note"
            value={note}
            placeholder="Travel agreed at the counter."
            onChange={(e) => setNote(e.target.value)}
          />
        </Field>

        {error && <Alert tone="error">{error}</Alert>}

        <div className="row">
          <Button
            variant="primary"
            busy={busy}
            disabled={lines.some((line) => !String(line.amount).trim())}
            onClick={() => void save()}
          >
            Save this breakdown
          </Button>
        </div>
      </div>
    </Card>
  );
}
