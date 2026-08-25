/**
 * The approval letter as the student reads it.
 *
 * The letter's words and figures are the server's. These pin that the page
 * renders what it was given rather than composing anything, that a letter per
 * programme means a page with both on it, and that the server's reason for
 * there being no letter is what the reader is shown — "not approved yet" tells
 * somebody what is happening; "could not be loaded" does not.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import '@testing-library/jest-dom';

import type { ApprovalLetter as Letter } from '../../api/client';

const approvalLetter = vi.fn();

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client');
  return { ...actual, default: { approvalLetter }, api: { approvalLetter } };
});

const { default: ApprovalLetter } = await import('./ApprovalLetter');

function letter(overrides: Partial<Letter> = {}): Letter {
  return {
    application_id: 7,
    stream: 'psssp',
    programme_code: 'DGG-CDFN',
    title: 'Approval of the Canada Dèlı̨nę First Nation Student Bursary for the',
    term: 'Fall 2026-2027',
    date: '2026-08-24',
    identifier: { label: 'Treaty #', value: 'T-9001' },
    recipient: 'Sara Student',
    opening: 'The Department of Education have reviewed your application.',
    breakdown_lead: 'The following is a breakdown of the funds that you have been approved:',
    semester: 'Fall',
    rows: [
      { label: 'Program Costs (Tuition, books, fees, etc.)*', amount: '$5,000.00', note: '' },
      { label: 'Monthly Allowance', amount: '$4,800.00', note: '$1,200.00/month × 4 months' },
    ],
    total_label: 'Total Allotted',
    total: '$9,800.00',
    footnote: 'Students may not receive the entire allotted amount…',
    paragraphs: ['You must inform the Education Department of any changes.'],
    closing: 'Kind regards,',
    signatory: {
      name: 'Wajiha Shah',
      title: 'Director of Education',
      organisation: 'Délı̨nę Got’ı̨nę Government',
      email: 'director.education@gov.deline.ca',
    },
    office: {
      address: 'P.O. Box 156, Délı̨nę, NT X0E 0G0',
      phone: '(867) 589.3515',
      website: 'www.deline.ca',
    },
    ...overrides,
  };
}

function show() {
  return render(
    <MemoryRouter initialEntries={['/applications/7/approval-letter']}>
      <Routes>
        <Route path="/applications/:id/approval-letter" element={<ApprovalLetter />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ApprovalLetter', () => {
  beforeEach(() => {
    // Braces, not a concise arrow body. `mockReset()` returns the mock, and a
    // value returned from `beforeEach` is treated as a teardown function — so
    // the concise form had the runner *calling the mock* after each test, with
    // nobody awaiting it. Against a rejecting implementation that is an
    // unhandled rejection, and it failed the two tests that prove rejections
    // are handled while the component was catching them correctly all along.
    approvalLetter.mockReset();
  });

  it('prints the letter the office wrote, word for word', async () => {
    approvalLetter.mockResolvedValue([letter()]);
    show();

    expect(await screen.findByText(/Dear Sara Student/)).toBeInTheDocument();
    expect(screen.getByText(/Treaty # T-9001/)).toBeInTheDocument();
    expect(screen.getByText(/reviewed your application/)).toBeInTheDocument();
    expect(screen.getByText('Wajiha Shah', { exact: false })).toBeInTheDocument();
    expect(screen.getByText(/P.O. Box 156/)).toBeInTheDocument();
  });

  it('shows the breakdown, with the monthly rate under the amount', async () => {
    approvalLetter.mockResolvedValue([letter()]);
    show();

    const table = (await screen.findByRole('table'));
    expect(within(table).getByText('$5,000.00')).toBeInTheDocument();
    expect(within(table).getByText('$1,200.00/month × 4 months')).toBeInTheDocument();
    expect(within(table).getByText('Total Allotted')).toBeInTheDocument();
    expect(within(table).getByText('$9,800.00')).toBeInTheDocument();
  });

  it('leaves out the total row where the office\'s template has none', async () => {
    // The UCEPP letter carries no total. Inventing one would be this portal
    // deciding what the office's letter says.
    approvalLetter.mockResolvedValue([
      letter({ programme_code: 'DGG-UCEPP', total_label: '', total: '$4,000.00' }),
    ]);
    show();

    const table = await screen.findByRole('table');
    expect(within(table).queryByText('Total Allotted')).not.toBeInTheDocument();
    expect(within(table).queryByText('$4,000.00')).not.toBeInTheDocument();
  });

  it('shows both letters when two programmes funded the semester', async () => {
    approvalLetter.mockResolvedValue([
      letter(),
      letter({
        programme_code: 'DGGR-SFSP',
        identifier: { label: 'Beneficiary #', value: 'B-1001' },
        rows: [{ label: 'Semester Stipend', amount: '$1,500.00', note: '' }],
        total_label: 'Total',
        total: '$1,500.00',
      }),
    ]);
    show();

    expect(await screen.findByText(/Treaty # T-9001/)).toBeInTheDocument();
    expect(screen.getByText(/Beneficiary # B-1001/)).toBeInTheDocument();
    expect(screen.getByText('Semester Stipend')).toBeInTheDocument();
    expect(screen.getAllByRole('table')).toHaveLength(2);
    expect(screen.getByRole('heading', { name: /approval letters/i })).toBeInTheDocument();
  });

  it('prints the date only where the letter carries one', async () => {
    // Two of the three templates have no line for a date. The server decides
    // which; a component that stamped today's date on every letter would be
    // putting a date on a document the office's template has no line for.
    approvalLetter.mockResolvedValue([letter({ date: '' })]);
    const { unmount } = show();
    expect(await screen.findByText(/Dear Sara Student/)).toBeInTheDocument();
    expect(screen.queryByText(/^Date:/)).not.toBeInTheDocument();
    unmount();

    approvalLetter.mockResolvedValue([letter({ date: '2026-08-24' })]);
    show();
    expect(await screen.findByText(/Date: 2026-08-24/)).toBeInTheDocument();
  });

  it('gives the server\'s reason when there is no letter', async () => {
    // "Not approved yet" tells somebody what is happening. A generic failure
    // sends them to the office to ask what went wrong with the website.
    // Rejected lazily. `mockRejectedValue` builds the rejected promise at setup
    // time, before the component has attached a handler, and the runner reports
    // that as an unhandled rejection even though the component catches it.
    approvalLetter.mockImplementation(() => Promise.reject({
      response: { data: { detail: 'This application has not been approved.' } },
    }));
    show();
    expect(await screen.findByText('This application has not been approved.'))
      .toBeInTheDocument();
  });

  it('still says something when the failure carries no reason', async () => {
    approvalLetter.mockImplementation(() => Promise.reject(new Error('network')));
    show();
    expect(await screen.findByText(/could not be loaded/)).toBeInTheDocument();
  });
});
