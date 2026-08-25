/**
 * Reports — what the year cost, and the report the office forwards.
 *
 * The office reads this screen; the head department reads the PDF. Those are
 * different documents and they are deliberately shaped differently: the formal
 * report is four dense ruled tables because that is what its reader expects,
 * and reproducing them here made a screen nobody in the office could take
 * anything from at a glance.
 *
 * So this is the same figures said plainly — a headline that reconciles, then
 * one card per question the office actually asks. The tables live in the
 * export.
 *
 * Every number comes from the server. Nothing is computed here, because a
 * total worked out in the browser is a second answer that can disagree with
 * the one in the PDF the office sends its funder.
 */

import { useCallback, useEffect, useState } from 'react';

import api, {
  ApiError,
  type AnnualReport as Report,
  type CurrentUser,
} from '../../api/client';
import { Alert, Button, Card, Field, Input } from '../../components/ui';
import { formatMoney } from '../../components/ui/format';
import { BarRows, Donut, Legend, StackedBar, StackedColumns } from './charts';
import { SERIES } from './palette';
import './report.css';

function fiscalYearOf(today: Date): number {
  return today.getMonth() + 1 >= 4 ? today.getFullYear() : today.getFullYear() - 1;
}

function money(value: string | number): string {
  return formatMoney(String(value));
}

/** The programme colours, in the order the office lists its programmes. */
const PROGRAMME_COLOR: Record<string, string> = {
  psssp: SERIES.university,
  ucepp: SERIES.trades,
  dggr: SERIES.college,
  shared: SERIES.unclassified,
};

/* ── The row that answers the four questions asked most ─────────────────────
   Four figures, not a chart: a single current value is a stat tile, and a
   one-bar bar chart for each of these would be four charts saying nothing a
   number does not. */
function Headline({ report }: { report: Report }) {
  const { financial, enrolment, students, graduate_awards } = report;
  const tiles = [
    { key: 'cost', label: 'Total program cost', value: money(financial.grand_total),
      // Not the same sentence as the card below it: two places saying one
      // thing is one place too many, and the reconciliation belongs with the
      // figures it reconciles.
      hint: 'students, awards and office costs' },
    // People, not rows of the table below it. Those differ whenever two
    // students hold one beneficiary number, and reporting the row count
    // here understates how many students the program reached.
    { key: 'students', label: 'Students funded',
      value: String(students.distinct_students),
      hint: `${enrolment.total.total} enrolment${enrolment.total.total === 1 ? '' : 's'}` },
    { key: 'grads', label: 'Graduate awards', value: String(graduate_awards.total.total),
      hint: `worth ${money(financial.total.categories.graduate_awards?.net ?? '0')}` },
    { key: 'back', label: 'Returned', value: money(financial.total.repaid),
      hint: 'withdrawals and repayments' },
  ];
  return (
    <ul className="rkpi">
      {tiles.map((tile) => (
        <li key={tile.key} className="rkpi__tile">
          <div className="rkpi__label">{tile.label}</div>
          <div className="rkpi__value">{tile.value}</div>
          <div className="rkpi__hint">{tile.hint}</div>
        </li>
      ))}
    </ul>
  );
}

/* ── Funding programme breakdown ────────────────────────────────────────────
   Where the money came from. Counts and money are attributed differently and
   the note says so: an application has one primary programme, but pricing
   draws on every programme the applicant qualifies for, so a DGGR top-up on a
   PSSSP application is spent from both. */
function Programmes({ report }: { report: Report }) {
  const rows = report.programmes.rows.filter(
    (r) => r.applications > 0 || Number(r.net) > 0);
  const total = rows.reduce((sum, r) => sum + Number(r.net), 0);

  return (
    <Card title="Funding programme breakdown">
      <div className="rprog">
        <Donut
          caption="Funding paid by each programme"
          unit="paid out"
          total={money(String(total))}
          segments={rows.map((r) => ({
            key: r.stream, label: r.label, value: Number(r.net),
            color: PROGRAMME_COLOR[r.stream] ?? SERIES.unclassified,
          }))}
        />
        <ul className="rprog__rows">
          {rows.map((row) => (
            <li key={row.stream}>
              <span className="clegend__dot"
                    style={{ background: PROGRAMME_COLOR[row.stream] ?? SERIES.unclassified }} />
              <div className="rprog__name">
                <strong>{row.label}</strong>
                <span className="small muted">
                  {row.applications > 0
                    ? `${row.applications} application${row.applications === 1 ? '' : 's'} · ${row.students} student${row.students === 1 ? '' : 's'}`
                    : row.stream === 'shared'
                      ? 'bursaries, travel and scholarships'
                      // A real programme with money but no applications of
                      // its own has topped up somebody else's. Calling that
                      // "bursaries" names the wrong kind of spending.
                      : 'top-ups on other programmes\u2019 applications'}
                </span>
              </div>
              <strong className="rprog__value">{money(row.net)}</strong>
            </li>
          ))}
        </ul>
      </div>
      <p className="small muted rprog__note">{report.programmes.note}</p>
    </Card>
  );
}

/* ── 1. What the year cost ──────────────────────────────────────────────────
   Replaces "Funding Approved", which showed only money approved. The office
   reconciles this against a financial statement, so it has to be everything —
   and it has to show what came back, or it cannot be reconciled at all. */
function TotalCost({ report }: { report: Report }) {
  const { financial } = report;
  const repaid = Number(financial.total.repaid);
  return (
    <Card title="What the year cost">
      <div className="rhero">
        <div className="rhero__figure">{money(financial.grand_total)}</div>
        <div className="rhero__caption">
          Total program cost — everything, to reconcile against the financial
          statement
        </div>
      </div>

      <ul className="rledger">
        <li>
          <span>Paid out to students</span>
          <strong>{money(financial.total.gross)}</strong>
        </li>
        <li className={repaid > 0 ? 'rledger__back' : undefined}>
          <span>Returned — withdrawals and repayments</span>
          <strong>{repaid > 0 ? `− ${money(financial.total.repaid)}` : money(0)}</strong>
        </li>
        <li className="rledger__sub">
          <span>Net to students</span>
          <strong>{money(financial.total.net)}</strong>
        </li>
        <li>
          {/* Office costs are recorded for the year, not per programme.
              Filtered, the whole figure sits under one programme — which
              is the only honest place for it, but it has to say so, or
              three filtered reports read as three sets of wages. */}
          <span>
            Entered by the office (staff wages and the like)
            {report.filter.stream && (
              <span className="small muted rledger__aside">
                for the whole year — not divided between programmes
              </span>
            )}
          </span>
          <strong>{money(financial.entered_total)}</strong>
        </li>
        <li className="rledger__total">
          <span>Total program cost</span>
          <strong>{money(financial.grand_total)}</strong>
        </li>
      </ul>

      {repaid === 0 && (
        <p className="small muted">
          Nothing has been recorded as returned this year. When a student
          withdraws and money comes back, record it against their award and it
          appears here.
        </p>
      )}
    </Card>
  );
}

/* ── Enrolment by semester ──────────────────────────────────────────────────
   The only chart here whose job is telling series apart, so the only one with
   a categorical palette. Stacked because both the total per season and its
   composition are wanted, and a grouped bar would make the reader add. */
function Enrolment({ report }: { report: Report }) {
  const { enrolment } = report;
  const columns = enrolment.rows.map((row) => ({
    label: row.season,
    segments: [
      { key: 'university', label: 'University', value: row.university,
        color: SERIES.university },
      { key: 'college', label: 'College', value: row.college, color: SERIES.college },
      { key: 'trades', label: 'Trades school', value: row.trades_school,
        color: SERIES.trades },
      { key: 'unclassified', label: 'Not classified', value: row.unclassified,
        color: SERIES.unclassified },
    ],
  }));
  const total = enrolment.total;

  return (
    <Card title="Enrolment through the year">
      <p className="small muted">
        {total.total} enrolment{total.total === 1 ? '' : 's'} across{' '}
        {enrolment.distinct_students} student
        {enrolment.distinct_students === 1 ? '' : 's'}. {enrolment.note}
      </p>
      <StackedColumns columns={columns}
                      caption="Students enrolled each semester, by type of institution" />
      <Legend items={[
        { key: 'university', label: 'University', color: SERIES.university,
          value: String(total.university) },
        { key: 'college', label: 'College', color: SERIES.college,
          value: String(total.college) },
        { key: 'trades', label: 'Trades school', color: SERIES.trades,
          value: String(total.trades_school) },
        { key: 'unclassified', label: 'Not classified', color: SERIES.unclassified,
          value: String(total.unclassified) },
      ]} />
      {(total.trades > 0 || total.upgrading > 0) && (
        <p className="small muted">
          Within those: {total.trades} in trades, {total.upgrading} in upgrading.
        </p>
      )}
    </Card>
  );
}

/* ── 2. Funding by student number ───────────────────────────────────────────
   Replaces the application pipeline, which counted statuses. */
function ByStudent({ report }: { report: Report }) {
  const { students } = report;
  const [all, setAll] = useState(false);
  const shown = all ? students.rows : students.rows.slice(0, 8);

  return (
    <Card title="Funding by student number">
      <p className="small muted">
        {students.distinct_students} student
        {students.distinct_students === 1 ? '' : 's'} funded this year, 
        most funded first.
        {students.unidentified > 0 &&
          ` ${students.unidentified} have no beneficiary number on file.`}
      </p>
      {/* One row is one beneficiary number, which is what the head
          department reconciles against — but it is not one person when a
          number is shared, and a row reading "225 applications" with no
          explanation looks like bad data rather than merged people. */}
      {students.sharing_a_number > 0 && (
        <p className="small muted">
          {students.sharing_a_number} more student
          {students.sharing_a_number === 1 ? ' is' : 's are'} counted inside a
          row above: a beneficiary number here is held by more than one
          person, so their funding is shown together.
        </p>
      )}
      {shown.length === 0 ? (
        <p className="muted">No funding was recorded this year.</p>
      ) : (
        <BarRows
          caption="Funding received by each student, most funded first"
          rows={shown.map((row) => ({
            key: `${row.student_number}-${row.name}`,
            label: row.student_number || 'No number on file',
            sub: Number(row.repaid) > 0
              ? `${row.name} · ${money(row.repaid)} returned`
              : row.name,
            value: Number(row.net),
            display: money(row.net),
            muted: !row.student_number,
          }))}
        />
      )}
      {students.rows.length > 8 && (
        <Button size="sm" onClick={() => setAll((v) => !v)}>
          {all ? 'Show the top 8' : `Show all ${students.rows.length}`}
        </Button>
      )}
    </Card>
  );
}

/* ── 3. Graduate awards ─────────────────────────────────────────────────────
   Replaces the live-metrics panel. */
function GraduateAwards({ report }: { report: Report }) {
  const { total, rows } = report.graduate_awards;
  return (
    <Card title="Graduate awards issued">
      <div className="rhero rhero--small">
        <div className="rhero__figure">{total.total}</div>
        <div className="rhero__caption">
          awards issued this year, worth{' '}
          {money(report.financial.total.categories.graduate_awards?.net ?? '0')}
        </div>
      </div>
      <StackedBar
        caption="Graduate awards by the credential they were earned for"
        segments={[
          { key: 'university', label: 'University', value: total.university,
            color: SERIES.university },
          { key: 'college', label: 'College', value: total.college,
            color: SERIES.college },
          { key: 'high_school', label: 'High school', value: total.high_school,
            color: SERIES.trades },
          { key: 'trades', label: 'Trades', value: total.trades,
            color: '#eda100' },
          { key: 'other', label: 'Other', value: total.other,
            color: SERIES.unclassified },
        ]}
      />
      <ul className="rsplit rsplit--quiet">
        {rows.map((row) => (
          <li key={row.residency}><span>{row.residency}</span><strong>{row.total}</strong></li>
        ))}
      </ul>
    </Card>
  );
}

/* ── 4. Spending by category ────────────────────────────────────────────────
   Replaces the quarterly bar chart, which showed when money moved rather than
   what it was for. */
function ByCategory({ report, isAdmin, year, onSaved }: {
  report: Report; isAdmin: boolean; year: number; onSaved: () => void;
}) {
  const { financial } = report;
  const figures = financial.categories.map((c) => ({
    key: c.key,
    label: c.label,
    net: Number(financial.total.categories[c.key]?.net ?? 0),
  }));

  return (
    <Card title="What the money was spent on">
      <BarRows
        caption="What the year's money was spent on, by category"
        rows={[
          ...figures.map((f) => ({
            key: f.key, label: f.label, value: f.net, display: money(f.net),
          })),
          // Hand-entered costs are marked as such rather than folded silently
          // into figures the system computed.
          ...financial.entered.map((item) => ({
            key: item.label,
            label: item.label,
            sub: 'entered by the office',
            value: Number(item.amount),
            display: money(item.amount),
            muted: true,
          })),
        ]}
      />
      {isAdmin && <CostEntry year={year} onSaved={onSaved} />}
    </Card>
  );
}

/* ── 5. Where students studied ──────────────────────────────────────────────
   Replaces the recent-applications table. */
function ByInstitution({ report }: { report: Report }) {
  const { sections } = report.institutions;
  const { enrolment } = report;
  return (
    <Card title="Where students studied">
      <p className="small muted">
        {enrolment.total.total} enrolment
        {enrolment.total.total === 1 ? '' : 's'} across{' '}
        {enrolment.distinct_students} student
        {enrolment.distinct_students === 1 ? '' : 's'}. A student who studied in
        two semesters is counted in each.
      </p>
      {sections.length === 0 && <p className="muted">No enrolments this year.</p>}
      {sections.map((section) => (
        <div key={section.institution_type || 'none'} className="rinst">
          <h3 className="rinst__head">
            {section.label}
            <span className="muted"> · {section.students} student
              {section.students === 1 ? '' : 's'}</span>
          </h3>
          <BarRows
            caption={`Students at each ${section.label.toLowerCase()}`}
            formatValue={(v) => String(v)}
            rows={section.rows.map((row) => ({
              key: row.name,
              label: row.name,
              sub: row.programs.join(' · ') || '—',
              value: row.students,
              display: String(row.students),
            }))}
          />
        </div>
      ))}
      {enrolment.unclassified > 0 && (
        <Alert tone="info">
          {enrolment.unclassified} enrolment
          {enrolment.unclassified === 1 ? '' : 's'} are not split between
          university and college — the institution did not say when it confirmed
          the enrolment. They are still counted in every total.
        </Alert>
      )}
    </Card>
  );
}

function CostEntry({ year, onSaved }: { year: number; onSaved: () => void }) {
  const [label, setLabel] = useState('Administration — Staff Wages/Benefits');
  const [amount, setAmount] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState('');

  const save = async () => {
    setBusy(true); setError(''); setSaved('');
    try {
      await api.recordReportedCost({
        fiscal_year_start: `${year}-04-01`, label, amount,
      });
      setSaved('Recorded. The total program cost is up to date.');
      setAmount('');
      onSaved();
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message
        : 'That could not be recorded.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rentry">
      <h3 className="rinst__head">Add a cost the system cannot see</h3>
      <p className="small muted">
        Staff wages and benefits, and anything like them. Entering the same
        description again for this year corrects the figure rather than adding a
        second line.
      </p>
      {error && <Alert tone="error">{error}</Alert>}
      {saved && <Alert tone="ok">{saved}</Alert>}
      <div className="grid-2">
        <Field id="cost-label" label="What the cost is for">
          <Input id="cost-label" value={label}
                 onChange={(e) => setLabel(e.target.value)} />
        </Field>
        <Field id="cost-amount" label="Amount">
          <Input id="cost-amount" inputMode="decimal" value={amount}
                 placeholder="25000.00"
                 onChange={(e) => setAmount(e.target.value)} />
        </Field>
      </div>
      <Button variant="primary" busy={busy} disabled={!amount.trim()}
              onClick={() => void save()}>
        Record cost
      </Button>
    </div>
  );
}

/**
 * The filter chips.
 *
 * Same order and same names as the breakdown below them, which is the order
 * the funding streams are declared in on the server. A chip reading one thing
 * and the row it filters to reading another makes the reader check whether
 * they are the same programme — and these are held apart, so `chips match the
 * breakdown` is a test rather than an intention.
 */
const PROGRAMMES = [
  { value: '', label: 'All programmes' },
  { value: 'psssp', label: 'C-DFN PSSSP' },
  { value: 'ucepp', label: 'C-DFN UCEPP' },
  { value: 'dggr', label: 'DGGR Bursaries' },
];

export default function AnnualReport() {
  const [year, setYear] = useState(() => fiscalYearOf(new Date()));
  const [stream, setStream] = useState('');
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState('');
  const [reloads, setReloads] = useState(0);
  const [exporting, setExporting] = useState(false);

  const refresh = useCallback(() => setReloads((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [result, user] = await Promise.all([
          api.annualReport(year, stream), api.me()]);
        if (!cancelled) { setReport(result); setMe(user); setError(''); }
      } catch (problem) {
        if (cancelled) return;
        setError(problem instanceof ApiError ? problem.message
          : 'The report could not be loaded.');
      }
    })();
    return () => { cancelled = true; };
  }, [year, stream, reloads]);

  /**
   * The formal report, as the office forwards it.
   *
   * The tab is opened before the request, not in the promise: a browser blocks
   * `window.open` that is not the direct result of a click.
   */
  const exportPdf = async () => {
    const tab = window.open('', '_blank');
    setExporting(true);
    try {
      const blob = await api.annualReportPdf(year, stream);
      const href = URL.createObjectURL(blob);
      if (tab) tab.location.href = href;
      else window.location.href = href;
    } catch (problem) {
      tab?.close();
      setError(problem instanceof ApiError ? problem.message
        : 'The report PDF could not be produced.');
    } finally {
      setExporting(false);
    }
  };

  if (error) return <main className="page"><Alert tone="error">{error}</Alert></main>;
  if (!report) {
    return (
      <main className="page">
        <div className="spinner" role="status" aria-label="Building the report" />
      </main>
    );
  }

  const isAdmin = me?.role === 'admin';

  return (
    <main className="page stack stack--loose">
      <header className="row row--between rhead">
        <div>
          <h1>Reports</h1>
          <p className="muted">{report.fiscal_year.label}</p>
        </div>
        <div className="row rhead__actions">
          <Field id="report-year" label="Fiscal year starting">
            <Input id="report-year" type="number" value={String(year)}
                   onChange={(e) => setYear(Number(e.target.value) || year)} />
          </Field>
          <Button variant="primary" busy={exporting} onClick={() => void exportPdf()}>
            Export the annual report
          </Button>
        </div>
      </header>

      {/* One row of filters above the charts, as a dashboard's filters should
          be — and the export follows the filter, so what the office is looking
          at is what it sends. */}
      <div className="rfilter">
        <span className="rfilter__label">Funding programme</span>
        {PROGRAMMES.map((option) => (
          <button
            key={option.value || 'all'}
            type="button"
            className={option.value === stream ? 'chip chip--on' : 'chip'}
            aria-pressed={option.value === stream}
            onClick={() => setStream(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>

      <p className="small muted rhead__note">
        This screen is the year at a glance. <strong>Export the annual
        report</strong> produces the formal document for the head department —
        the tables, on the office letterhead — for whatever is selected here.
      </p>

      <Headline report={report} />

      <div className="rgrid">
        <Programmes report={report} />
        <TotalCost report={report} />
      </div>

      <Enrolment report={report} />

      <div className="rgrid">
        <ByStudent report={report} />
        <GraduateAwards report={report} />
      </div>

      <ByCategory report={report} isAdmin={isAdmin} year={year} onSaved={refresh} />
      <ByInstitution report={report} />
    </main>
  );
}
