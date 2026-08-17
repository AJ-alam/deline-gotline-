/**
 * The funding rates every award is computed from.
 *
 * Changing a rate used to require a deploy, and nobody could see what a rate had
 * been. An administrator edits it here, the change is recorded with who and
 * when, and it never alters a decision already made — an application is priced
 * with the rates in force when it was submitted.
 */

import { useCallback, useEffect, useState } from 'react';

import api, {
  ApiError,
  type CurrentUser,
  type PolicyChange,
  type PolicyRate,
  type PolicySection,
  type RuleSetSummary,
} from '../../api/client';
import { Alert, Badge, Button, Card, Field, Input } from '../../components/ui';
import { formatDate, formatRate } from '../../components/ui/format';

/** Sections are stored as machine keys; this is only how they read on screen. */
function sectionTitle(section: string): string {
  return section
    .split('_')
    .map((word) =>
      ['psssp', 'ucepp', 'dggr'].includes(word)
        ? word.toUpperCase()
        : word.charAt(0).toUpperCase() + word.slice(1),
    )
    .join(' ');
}

function RateRow({
  rate,
  canEdit,
  onChanged,
}: {
  rate: PolicyRate;
  canEdit: boolean;
  onChanged: (updated: PolicyRate) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(rate.value);
  const [effectiveFrom, setEffectiveFrom] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<PolicyChange[] | null>(null);

  const save = async () => {
    setBusy(true);
    setError('');
    try {
      onChanged(await api.changePolicyRate(rate.id, value, effectiveFrom || undefined));
      setEditing(false);
      setHistory(null);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? (err.fieldErrors.value ?? err.message)
          : 'The rate could not be changed.',
      );
    } finally {
      setBusy(false);
    }
  };

  const showHistory = async () => {
    if (history) return setHistory(null);
    const { history: entries } = await api.policyRate(rate.id);
    setHistory(entries);
  };

  return (
    <tr>
      <td>
        {rate.label}
        {!rate.is_active && (
          <>
            {' '}
            <Badge tone="warn">Suspended</Badge>
          </>
        )}
        <div className="small muted">{rate.key}</div>
        {history && (
          <ul className="stack stack--tight small muted" style={{ marginTop: 'var(--s-2)' }}>
            {history.length === 0 && <li>No changes recorded.</li>}
            {history.map((change, index) => (
              <li key={index}>
                {formatRate(change.previous_value, rate.unit)} →{' '}
                {formatRate(change.new_value, rate.unit)},
                effective {formatDate(change.effective_date)}
                {change.changed_by ? ` · ${change.changed_by}` : ''}
              </li>
            ))}
          </ul>
        )}
      </td>
      <td className="num">
        {editing ? (
          <div className="stack stack--tight">
            <Field id={`rate-${rate.id}`} label="New value" error={error}>
              <Input
                id={`rate-${rate.id}`}
                value={value}
                invalid={Boolean(error)}
                inputMode="decimal"
                onChange={(e) => setValue(e.target.value)}
              />
            </Field>
            <Field
              id={`from-${rate.id}`}
              label="Takes effect"
              hint="Leave blank for today. A future date will not affect applications already submitted."
            >
              <Input
                id={`from-${rate.id}`}
                type="date"
                value={effectiveFrom}
                onChange={(e) => setEffectiveFrom(e.target.value)}
              />
            </Field>
          </div>
        ) : (
          formatRate(rate.value, rate.unit)
        )}
      </td>
      <td>
        <div className="row">
          {canEdit &&
            (editing ? (
              <>
                <Button size="sm" variant="primary" busy={busy} onClick={() => void save()}>
                  Save
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                  Cancel
                </Button>
              </>
            ) : (
              <Button size="sm" onClick={() => setEditing(true)}>
                Change
              </Button>
            ))}
          <Button size="sm" variant="ghost" onClick={() => void showHistory()}>
            {history ? 'Hide history' : 'History'}
          </Button>
        </div>
      </td>
    </tr>
  );
}

export default function PolicyRates() {
  const [sections, setSections] = useState<PolicySection[] | null>(null);
  const [ruleSets, setRuleSets] = useState<RuleSetSummary[]>([]);
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.policyRates(), api.ruleSets(), api.me()])
      .then(([rates, sets, user]) => {
        if (cancelled) return;
        setSections(rates);
        setRuleSets(sets);
        setMe(user);
      })
      .catch(() => {
        if (!cancelled) setError('The funding rates could not be loaded.');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const applyChange = useCallback((updated: PolicyRate) => {
    setSections((current) =>
      current?.map((section) => ({
        ...section,
        settings: section.settings.map((rate) => (rate.id === updated.id ? updated : rate)),
      })) ?? null,
    );
  }, []);

  if (error) {
    return (
      <main className="page">
        <Alert tone="error">{error}</Alert>
      </main>
    );
  }
  if (!sections || !me) {
    return (
      <main className="page">
        <div className="spinner" role="status" aria-label="Loading rates" />
      </main>
    );
  }

  const canEdit = me.role === 'admin';

  return (
    <main className="page stack stack--loose">
      <header className="stack stack--tight">
        <h1>Policy rates</h1>
        <p className="muted">
          Every award is computed from these. A change is recorded with who made it
          and when it takes effect, and never alters a decision already made.
        </p>
      </header>

      {!canEdit && (
        <Alert tone="info">
          You can see the rates behind an award. Only an administrator can change them.
        </Alert>
      )}

      {sections.map((section) => (
        <Card key={section.section} title={sectionTitle(section.section)}>
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>Rate</th>
                  <th>Value</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {section.settings.map((rate) => (
                  <RateRow
                    key={rate.id}
                    rate={rate}
                    canEdit={canEdit}
                    onChanged={applyChange}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ))}

      <Card title="Policy versions">
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Version</th>
                <th>Status</th>
                <th>In force</th>
                <th>Rules</th>
              </tr>
            </thead>
            <tbody>
              {ruleSets.map((set) => (
                <tr key={set.id}>
                  <td>
                    {set.name} v{set.version}
                  </td>
                  <td>
                    <Badge
                      tone={
                        set.status === 'published'
                          ? 'ok'
                          : set.status === 'draft'
                            ? 'neutral'
                            : 'info'
                      }
                    >
                      {set.status}
                    </Badge>
                  </td>
                  <td className="small">
                    {formatDate(set.effective_from)} —{' '}
                    {set.effective_to ? formatDate(set.effective_to) : 'now'}
                  </td>
                  <td className="num">{set.rule_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </main>
  );
}
