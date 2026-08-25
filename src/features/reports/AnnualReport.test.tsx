/**
 * The Reports screen.
 *
 * The office reads this; the head department reads the exported PDF. They are
 * shaped differently on purpose — reproducing the report's four ruled tables
 * here made a screen nobody in the office could take anything from at a
 * glance, which is what the office said about the version before it.
 *
 * These pin the five things the office asked to see, that the screen computes
 * none of them, and that the export is reachable.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import '@testing-library/jest-dom';

import type { AnnualReport as Report } from '../../api/client';

const annualReport = vi.fn();
const annualReportPdf = vi.fn();
const me = vi.fn();
const recordReportedCost = vi.fn();

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client');
  const stub = { annualReport, annualReportPdf, me, recordReportedCost };
  return { ...actual, default: stub, api: stub };
});

const { default: AnnualReport } = await import('./AnnualReport');

function report(overrides: Partial<Report> = {}): Report {
  return {
    fiscal_year: { starts: '2026-04-01', ends: '2027-04-01',
                   label: '1 April 2026 – 31 March 2027' },
    enrolment: {
      rows: [], total: {
        season: 'Total', university: 6, college: 9, trades_school: 0,
        unclassified: 2, total: 17, trades: 3, upgrading: 1,
      },
      note: 'Trades and upgrading are counted within.',
      distinct_students: 12, unclassified: 2,
    },
    graduate_awards: {
      rows: [
        { residency: 'Délı̨nę residents', university: 2, college: 1,
          high_school: 0, trades: 1, other: 0, total: 4 },
        { residency: 'Beneficiaries outside Délı̨nę', university: 1, college: 0,
          high_school: 1, trades: 0, other: 0, total: 2 },
      ],
      total: { residency: 'Total', university: 3, college: 1, high_school: 1,
               trades: 1, other: 0, total: 6 },
    },
    institutions: {
      sections: [{
        institution_type: 'college', label: 'College or polytechnic', students: 9,
        rows: [{ name: 'Northern Lights College',
                 programs: ['Practical Nursing', 'Business Admin'], students: 9 }],
      }],
    },
    programmes: {
      rows: [
        // In the order the server declares the streams, which is the order
        // the chips are written in.
        { stream: 'psssp', label: 'C-DFN PSSSP', applications: 9, students: 7,
          gross: '9000.00', repaid: '0.00', net: '9000.00' },
        { stream: 'ucepp', label: 'C-DFN UCEPP', applications: 0, students: 0,
          gross: '0.00', repaid: '0.00', net: '0.00' },
        { stream: 'dggr', label: 'DGGR Bursaries', applications: 4, students: 4,
          gross: '4000.00', repaid: '500.00', net: '3500.00' },
        { stream: 'shared', label: 'Not tied to one programme', applications: 0,
          students: 0, gross: '2000.00', repaid: '0.00', net: '2000.00' },
      ],
      note: 'Applications are counted against their primary programme.',
    },
    filter: { stream: '' },
    students: {
      rows: [
        { student_number: 'B-1001', name: 'Sara Student', applications: 2,
          gross: '12000.00', repaid: '500.00', net: '11500.00' },
        { student_number: '', name: 'No Number', applications: 1,
          gross: '3000.00', repaid: '0.00', net: '3000.00' },
      ],
      // Three people on two rows: two of them share one beneficiary
      // number, which is the case the office's own data is full of.
      students: 2, distinct_students: 3, sharing_a_number: 1,
      unidentified: 1,
    },
    financial: {
      categories: [
        { key: 'tuition', label: 'Direct student funding — tuition and fees' },
        { key: 'living', label: 'Monthly allowances' },
        { key: 'graduate_awards', label: 'Graduate awards' },
        { key: 'summer_awards', label: 'Summer student awards' },
        { key: 'achievement_awards', label: 'Achievement awards' },
        { key: 'other_support', label: 'Other student support' },
      ],
      rows: [],
      total: {
        season: 'Total', gross: '15000.00', repaid: '500.00', net: '14500.00',
        categories: {
          tuition: { gross: '9000.00', repaid: '0.00', net: '9000.00' },
          living: { gross: '4000.00', repaid: '500.00', net: '3500.00' },
          graduate_awards: { gross: '2000.00', repaid: '0.00', net: '2000.00' },
          summer_awards: { gross: '0.00', repaid: '0.00', net: '0.00' },
          achievement_awards: { gross: '0.00', repaid: '0.00', net: '0.00' },
          other_support: { gross: '0.00', repaid: '0.00', net: '0.00' },
        },
      },
      entered: [{ label: 'Administration — Staff Wages/Benefits', amount: '25000.00',
                  note: '', recorded_by: 'Wajiha Shah', updated_at: '2026-08-25' }],
      entered_total: '25000.00',
      grand_total: '39500.00',
    },
    highlights: {},
    ...overrides,
  } as Report;
}

function show() {
  return render(<MemoryRouter><AnnualReport /></MemoryRouter>);
}

describe('Reports screen', () => {
  beforeEach(() => {
    annualReport.mockReset();
    annualReportPdf.mockReset();
    me.mockReset();
    recordReportedCost.mockReset();
    annualReport.mockResolvedValue(report());
    me.mockResolvedValue({ role: 'admin' });
  });

  /** The grand total appears twice on purpose — as the headline and as the
   *  last line of the reconciliation — so it is matched by count, not by
   *  assuming it is unique. */
  async function settled() {
    return (await screen.findAllByText('$39,500.00'))[0];
  }

  it('leads with the total the office reconciles against', async () => {
    show();
    await settled();
    // Queried after the load, not before it: the element does not exist while
    // the spinner is up.
    expect(document.querySelector('.rhero__figure')).toHaveTextContent('$39,500.00');
    expect(screen.getByText(/reconcile against the financial statement/i))
      .toBeInTheDocument();
  });

  it('shows what came back, not only what went out', async () => {
    // The whole reason the office asked for this: a figure that only counts
    // money leaving cannot be reconciled.
    show();
    await settled();
    expect(screen.getByText(/Returned — withdrawals and repayments/)).toBeInTheDocument();
    expect(screen.getByText('− $500.00')).toBeInTheDocument();

    const ledger = document.querySelector('.rledger') as HTMLElement;
    expect(within(ledger).getByText('$14,500.00')).toBeInTheDocument();

    // And the programme breakdown adds back up to it. The two are computed
    // from different columns — the ledger from award lines, the breakdown from
    // the rule that priced each line — so agreeing is worth asserting.
    const donut = document.querySelector('.cdonut__total') as SVGTextElement;
    expect(donut).toHaveTextContent('$14,500.00');
  });

  it('breaks the funding down by student number', async () => {
    show();
    const card = (await screen.findByRole('heading', { name: 'Funding by student number' }))
      .closest('.card') as HTMLElement;
    expect(within(card).getByText('B-1001')).toBeInTheDocument();
    expect(within(card).getByText('$11,500.00')).toBeInTheDocument();
    // A student with no number is listed rather than dropped, or the
    // breakdown stops adding up to the year.
    expect(within(card).getByText('No number on file')).toBeInTheDocument();
  });

  it('shows the number of graduate awards issued', async () => {
    show();
    const card = (await screen.findByRole('heading', { name: 'Graduate awards issued' }))
      .closest('.card') as HTMLElement;
    expect(within(card).getByText('6')).toBeInTheDocument();
    expect(within(card).getByText(/Délı̨nę residents/)).toBeInTheDocument();
  });

  it('shows what the money was spent on, category by category', async () => {
    show();
    const card = (await screen.findByRole('heading', { name: 'What the money was spent on' }))
      .closest('.card') as HTMLElement;
    for (const label of ['Direct student funding — tuition and fees',
                         'Monthly allowances', 'Graduate awards',
                         'Summer student awards', 'Achievement awards']) {
      expect(within(card).getByText(label)).toBeInTheDocument();
    }
    // The hand-entered cost appears, and is marked as entered rather than
    // folded silently into the computed figures.
    expect(within(card).getByText('Administration — Staff Wages/Benefits'))
      .toBeInTheDocument();
    expect(within(card).getByText(/entered by the office/)).toBeInTheDocument();
  });

  it('lists institutions and programmes by student number', async () => {
    show();
    const card = (await screen.findByRole('heading', { name: 'Where students studied' }))
      .closest('.card') as HTMLElement;
    expect(within(card).getByText('Northern Lights College')).toBeInTheDocument();
    expect(within(card).getByText(/Practical Nursing · Business Admin/))
      .toBeInTheDocument();
  });

  it('says how many enrolments the institution did not classify', async () => {
    show();
    expect(await screen.findByText(/2 enrolments are not split between/))
      .toBeInTheDocument();
  });

  it('exports the formal report', async () => {
    // The document the office forwards. Reached from this screen, which is
    // the whole point of it being here.
    annualReportPdf.mockResolvedValue(new Blob(['%PDF-'], { type: 'application/pdf' }));
    const open = vi.spyOn(window, 'open').mockReturnValue(null as never);
    const url = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:x');

    show();
    fireEvent.click(await screen.findByRole('button', { name: /Export the annual report/ }));
    // The export follows the filter, so what the office is looking at is what
    // it sends.
    await waitFor(() => expect(annualReportPdf).toHaveBeenCalledWith(2026, ''));

    open.mockRestore();
    url.mockRestore();
  });

  it('narrows the whole screen to one funding programme', async () => {
    // The filter is the office's, not the chart's: picking DGGR must go back
    // to the server, because the money split cannot be recomputed here — a
    // client-side filter over `programmes` would leave every other card
    // showing all three programmes.
    show();
    await settled();
    expect(annualReport).toHaveBeenCalledWith(2026, '');

    fireEvent.click(screen.getByRole('button', { name: 'DGGR Bursaries' }));
    await waitFor(() => expect(annualReport).toHaveBeenCalledWith(2026, 'dggr'));
    expect(screen.getByRole('button', { name: 'DGGR Bursaries' }))
      .toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'All programmes' }))
      .toHaveAttribute('aria-pressed', 'false');
  });

  it('exports what the office is looking at, not always everything', async () => {
    const url = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:x');
    const open = vi.spyOn(window, 'open').mockReturnValue(null);
    annualReportPdf.mockResolvedValue(new Blob(['%PDF']));

    show();
    await settled();
    fireEvent.click(screen.getByRole('button', { name: 'C-DFN PSSSP' }));
    await waitFor(() => expect(annualReport).toHaveBeenCalledWith(2026, 'psssp'));

    fireEvent.click(screen.getByRole('button', { name: /Export the annual report/ }));
    await waitFor(() => expect(annualReportPdf).toHaveBeenCalledWith(2026, 'psssp'));

    open.mockRestore();
    url.mockRestore();
  });

  it('counts students, not rows of the table', async () => {
    // A row is a beneficiary number. Two people can hold one, and reporting
    // the row count as "students funded" tells the funder the program reached
    // fewer people than it did.
    show();
    const tile = (await screen.findByText('Students funded'))
      .closest('.rkpi__tile') as HTMLElement;
    expect(within(tile).getByText('3')).toBeInTheDocument();
    expect(within(tile).queryByText('2')).not.toBeInTheDocument();
  });

  it('says when a beneficiary number covers more than one person', async () => {
    // Otherwise a row reading "225 applications" looks like bad data rather
    // than several students reported together.
    show();
    await settled();
    expect(screen.getByText(/counted inside a row above/)).toBeInTheDocument();
  });

  it('names the programmes on the chips the way the breakdown names them', async () => {
    // The chips are written here and the rows come from the server. When they
    // drift, one screen calls the same programme two things.
    show();
    await settled();
    const chips = [...document.querySelectorAll('.rfilter .chip')]
      .map((c) => c.textContent).slice(1);
    const rows = report().programmes.rows
      .filter((r) => r.stream !== 'shared').map((r) => r.label);
    expect(chips).toEqual(rows);
  });

  it('does not call a top-up a bursary', async () => {
    // A real programme with money but no applications of its own has topped up
    // somebody else's — which is what a filtered report is full of. Only the
    // shared row is bursaries, travel and scholarships.
    annualReport.mockResolvedValue(report({
      filter: { stream: 'ucepp' },
      programmes: {
        rows: [
          { stream: 'psssp', label: 'C-DFN PSSSP', applications: 0, students: 0,
            gross: '29400.00', repaid: '0.00', net: '29400.00' },
          { stream: 'ucepp', label: 'C-DFN UCEPP', applications: 3, students: 3,
            gross: '13400.00', repaid: '0.00', net: '13400.00' },
          { stream: 'shared', label: 'Not tied to one programme',
            applications: 0, students: 0, gross: '1000.00', repaid: '0.00',
            net: '1000.00' },
        ],
        note: 'Applications are counted against their primary programme.',
      },
    }));
    show();
    await settled();

    const card = (await screen.findByRole('heading',
      { name: 'Funding programme breakdown' })).closest('.card') as HTMLElement;
    const psssp = within(card).getByText('C-DFN PSSSP')
      .closest('li') as HTMLElement;
    expect(psssp).toHaveTextContent(/top-ups on other programmes/);
    expect(psssp).not.toHaveTextContent(/bursaries/);

    const shared = within(card).getByText('Not tied to one programme')
      .closest('li') as HTMLElement;
    expect(shared).toHaveTextContent(/bursaries, travel and scholarships/);
  });

  it('says office costs are not divided between programmes', async () => {
    // Otherwise the three filtered reports read as three sets of wages.
    annualReport.mockResolvedValue(report({ filter: { stream: 'dggr' } }));
    show();
    await settled();
    expect(screen.getByText(/not divided between programmes/))
      .toBeInTheDocument();
  });

  it('and says nothing of the kind when nothing is filtered', async () => {
    show();
    await settled();
    expect(screen.queryByText(/not divided between programmes/))
      .not.toBeInTheDocument();
  });

  it('offers the cost entry to an administrator only', async () => {
    show();
    expect(await screen.findByRole('button', { name: 'Record cost' })).toBeInTheDocument();
  });

  it('does not offer it to the Director', async () => {
    me.mockResolvedValue({ role: 'director' });
    show();
    await settled();
    expect(screen.queryByRole('button', { name: 'Record cost' })).not.toBeInTheDocument();
  });

  it('is not the report document', async () => {
    /* The office said the previous screen was too hard to read. The formal
       tables belong in the export; this screen answers questions. */
    show();
    await settled();
    expect(screen.queryByText(/Table 1/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Table 4/)).not.toBeInTheDocument();
  });
});
