/**
 * The office's opening screen.
 *
 * These pin the stream split: every pot present even at nought, each tile a way
 * into the queue filtered to it, and no money on it. An award line carries no
 * stream and could not be given one — the rules gate against every stream an
 * applicant qualifies for, and DGGR tops up rather than replaces — so a figure
 * here labelled DGGR would be read as what DGGR paid, and it is not.
 *
 * The tiles are tested by clicking them and watching what the queue then asks
 * the server. Asserting the `href` instead is how a link that opened the API's
 * 401 page on every document, for every role, survived 809 unit tests: the
 * attribute was there and nothing had ever followed it.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import '@testing-library/jest-dom';

import type { ApplicationSummary, DashboardSummary, Page } from '../../api/client';

const applications = vi.fn();

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client');
  return { ...actual, default: { applications }, api: { applications } };
});

const { default: StaffDashboard } = await import('./StaffDashboard');
const { default: ReviewQueue } = await import('../review/ReviewQueue');

function summary(overrides: Partial<DashboardSummary> = {}): DashboardSummary {
  return {
    scope: 'staff',
    applications: { total: 3, open: 2, by_status: {} as never },
    money: { awarded: '0.00', awaiting_payment: '0.00', paid: '0.00' },
    queues: { to_review: 1, awaiting_decision: 0, awaiting_enrolment_confirmation: 0 },
    attention: { submitted_late: 0, residency_mismatch: 0 },
    streams: [
      { stream: 'psssp', label: 'C-DFN PSSSP', total: 2, open: 1 },
      { stream: 'ucepp', label: 'C-DFN UCEPP', total: 0, open: 0 },
      { stream: 'dggr', label: 'DGGR Bursaries', total: 1, open: 1 },
    ],
    ...overrides,
  };
}

function show(data: DashboardSummary) {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<StaffDashboard summary={data} />} />
        <Route path="/review" element={<ReviewQueue />} />
      </Routes>
    </MemoryRouter>,
  );
}

function split() {
  return screen.getByRole('heading', { name: 'By funding stream' })
    .closest('.card') as HTMLElement;
}

function emptyPage(): Page<ApplicationSummary> {
  return { count: 0, next: null, previous: null, results: [] };
}

describe('StaffDashboard stream split', () => {
  beforeEach(() => {
    applications.mockReset();
    applications.mockResolvedValue(emptyPage());
  });

  it('names each stream as the office does and counts its applications', () => {
    show(summary());
    const section = within(split());
    expect(section.getByText('C-DFN PSSSP')).toBeInTheDocument();
    expect(section.getByText('2')).toBeInTheDocument();
    expect(section.getByText('DGGR Bursaries')).toBeInTheDocument();
  });

  it('shows a stream with nothing in it rather than leaving it out', () => {
    // UCEPP is assigned by nothing, so it is always nought. A split that omits
    // the empty pots is a list of what happens to exist.
    show(summary());
    expect(within(split()).getByText('C-DFN UCEPP')).toBeInTheDocument();
  });

  it('says how many of each are still open', () => {
    show(summary());
    const psssp = within(split()).getByRole('link', { name: /C-DFN PSSSP/ });
    expect(within(psssp).getByText('1 still open')).toBeInTheDocument();
  });

  it('opens the queue actually filtered to the stream that was clicked', async () => {
    show(summary());
    fireEvent.click(within(split()).getByRole('link', { name: /DGGR Bursaries/ }));

    // The queue is what proves the tile: it has to ask the server for that
    // stream, not merely be reachable.
    await waitFor(() =>
      expect(applications).toHaveBeenLastCalledWith(
        expect.objectContaining({ stream: 'dggr' }),
      ),
    );
    expect(await screen.findByRole('heading', { name: 'Applications' }))
      .toBeInTheDocument();
    expect(screen.getByLabelText('Funding stream')).toHaveValue('dggr');
  });

  it('puts no money in the split, and says why', () => {
    show(summary({
      money: { awarded: '9999.00', awaiting_payment: '9999.00', paid: '9999.00' },
    }));
    expect(within(split()).queryByText(/\$/)).not.toBeInTheDocument();
    expect(within(split()).getByText(/not amounts of money/)).toBeInTheDocument();
  });

  it('renders nothing where the server sent no split', () => {
    // Not an empty section: every stream is present even at nought, so a
    // missing key means the server did not send one.
    show(summary({ streams: undefined }));
    expect(screen.queryByRole('heading', { name: 'By funding stream' }))
      .not.toBeInTheDocument();
  });

  it('counts a stream outside the three but does not offer it as a way in', async () => {
    // `stream` is a CharField with choices and no database constraint, so the
    // server carries an unknown value through rather than losing applications
    // out of the total. The queue filters on the choice set and answers 400 to
    // anything else — so a link here would drop its filter and open every
    // application in the office under a tile that says four.
    show(summary({
      applications: { total: 4, open: 4, by_status: {} as never },
      streams: [{ stream: 'ncep', label: 'ncep', total: 4, open: 4 }],
    }));

    const section = within(split());
    expect(section.getByText('ncep')).toBeInTheDocument();
    expect(section.getByText('4')).toBeInTheDocument();
    expect(section.queryByRole('link')).not.toBeInTheDocument();
  });
});
