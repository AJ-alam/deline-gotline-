/**
 * The two list-shaped questions the travel claim introduced.
 *
 * An expense breakdown is rows of the same few questions, and its receipts are
 * several files answering one of them. Both were previously impossible to ask
 * for: a claim was a single amount typed into a box with one document behind
 * it, which is not something an office can check against anything.
 *
 * What these pin is that the rows and the files reach `onSubmit` as lists
 * keyed by the schema's own keys — the server does the arithmetic and the
 * validating, and it can only do either if the shape arrives intact.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';

import type { ApplicationSchema, SchemaField } from '../api/schema.generated';

const uploadDocument = vi.fn();

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return { ...actual, default: { uploadDocument }, api: { uploadDocument } };
});

const { default: SchemaForm } = await import('./SchemaForm');

function field(overrides: Partial<SchemaField> & { key: string }): SchemaField {
  return {
    label: overrides.key,
    type: 'text',
    required: false,
    help_text: '',
    section: 'Details',
    choices: [],
    columns: [],
    computed: false,
    private: false,
    max_items: 0,
    defaults_to_today: false,
    ...overrides,
  };
}

function schema(fields: SchemaField[], sections = ['Details']): ApplicationSchema {
  return {
    slug: 'travel',
    label: 'Travel & Emergency Assistance',
    summary: 'Claim back what you spent travelling.',
    apply_in_portal: true,
    sections,
    fields,
  };
}

const EXPENSES = field({
  key: 'expenses',
  label: 'Expenses claimed',
  type: 'table',
  required: true,
  max_items: 3,
  columns: [
    field({ key: 'description', label: 'Description', required: true }),
    field({ key: 'amount', label: 'Amount', type: 'money', required: true }),
    field({ key: 'receipt_attached', label: 'Receipt attached', type: 'boolean' }),
  ],
});

const RECEIPTS = field({
  key: 'doc_receipts', label: 'Receipts', type: 'files', required: true, max_items: 3,
});

/** The rows a person types into — not the header, and not the totals line. */
function entryRows() {
  // thead, tbody, tfoot are all rowgroups; the entry rows are the middle one.
  return within(screen.getAllByRole('rowgroup')[1]).getAllByRole('row');
}

/** Type into row `index`'s description and amount. */
function fillRow(index: number, description: string, amount: string) {
  const cells = within(entryRows()[index]).getAllByRole('textbox');
  fireEvent.change(cells[0], { target: { value: description } });
  fireEvent.change(cells[1], { target: { value: amount } });
}

describe('a table of rows', () => {
  it('opens with one empty line rather than behind an "add" button', () => {
    render(<SchemaForm schema={schema([EXPENSES])} onSubmit={vi.fn()} />);
    expect(entryRows()).toHaveLength(1);
  });

  it('names each column from the schema', () => {
    render(<SchemaForm schema={schema([EXPENSES])} onSubmit={vi.fn()} />);
    for (const heading of ['Description', 'Amount', 'Receipt attached']) {
      expect(screen.getByRole('columnheader', { name: new RegExp(heading) }))
        .toBeInTheDocument();
    }
  });

  it('submits the rows as a list keyed by the column keys', () => {
    const onSubmit = vi.fn();
    render(<SchemaForm schema={schema([EXPENSES])} onSubmit={onSubmit} />);

    fillRow(0, 'Flight', '812.50');
    fireEvent.click(screen.getByRole('button', { name: /Add a line/ }));
    fillRow(1, 'Hotel', '189.00');
    fireEvent.click(screen.getByRole('button', { name: /Submit/ }));

    expect(onSubmit).toHaveBeenCalledWith({
      expenses: [
        { description: 'Flight', amount: '812.50', receipt_attached: false },
        { description: 'Hotel', amount: '189.00', receipt_attached: false },
      ],
    });
  });

  it('does not send the blank line it opened with', () => {
    const onSubmit = vi.fn();
    render(<SchemaForm schema={schema([EXPENSES])} onSubmit={onSubmit} />);

    fillRow(0, 'Flight', '812.50');
    fireEvent.click(screen.getByRole('button', { name: /Add a line/ }));
    fireEvent.click(screen.getByRole('button', { name: /Submit/ }));

    expect(onSubmit.mock.calls[0][0].expenses).toHaveLength(1);
  });

  it('adds up the money column as the lines are typed', () => {
    render(<SchemaForm schema={schema([EXPENSES])} onSubmit={vi.fn()} />);

    fillRow(0, 'Flight', '812.50');
    fireEvent.click(screen.getByRole('button', { name: /Add a line/ }));
    fillRow(1, 'Hotel', '189.00');

    expect(screen.getByText('$1001.50')).toBeInTheDocument();
  });

  it('removes the line that was asked for, not the last one', () => {
    const onSubmit = vi.fn();
    render(<SchemaForm schema={schema([EXPENSES])} onSubmit={onSubmit} />);

    fillRow(0, 'Flight', '100');
    fireEvent.click(screen.getByRole('button', { name: /Add a line/ }));
    fillRow(1, 'Hotel', '200');
    fireEvent.click(screen.getByRole('button', { name: /Remove row 1/ }));
    fireEvent.click(screen.getByRole('button', { name: /Submit/ }));

    expect(onSubmit).toHaveBeenCalledWith({
      expenses: [{ description: 'Hotel', amount: '200', receipt_attached: false }],
    });
  });

  it('leaves a blank line behind when the only line is removed', () => {
    render(<SchemaForm schema={schema([EXPENSES])} onSubmit={vi.fn()} />);
    fillRow(0, 'Flight', '100');
    fireEvent.click(screen.getByRole('button', { name: /Remove row 1/ }));

    // Still one row to type into, rather than a table with no way back into it.
    expect(entryRows()).toHaveLength(1);
  });

  it('stops offering new lines at the cap the schema sets', () => {
    render(<SchemaForm schema={schema([EXPENSES])} onSubmit={vi.fn()} />);
    const add = screen.getByRole('button', { name: /Add a line/ });

    fireEvent.click(add);
    fireEvent.click(add);
    expect(add).toBeDisabled();
  });

  it('will not advance until a line has every column the schema requires', () => {
    render(<SchemaForm schema={schema([EXPENSES])} onSubmit={vi.fn()} />);
    const submit = screen.getByRole('button', { name: /Submit/ });
    expect(submit).toBeDisabled();

    // A description alone is not a claim: it has no amount.
    const cells = within(entryRows()[0]).getAllByRole('textbox');
    fireEvent.change(cells[0], { target: { value: 'Flight' } });
    expect(submit).toBeDisabled();

    fireEvent.change(cells[1], { target: { value: '812.50' } });
    expect(submit).toBeEnabled();
  });
});

describe('several files answering one question', () => {
  beforeEach(() => {
    uploadDocument.mockReset();
  });

  function upload(...names: string[]) {
    let next = 0;
    uploadDocument.mockImplementation((file: File) => {
      next += 1;
      return Promise.resolve({
        id: next, field_key: 'doc_receipts', original_name: file.name,
        uploaded_at: '2026-09-01T00:00:00Z', reference: `document:${next}`,
      });
    });
    return names.map((name) => new File(['%PDF'], name, { type: 'application/pdf' }));
  }

  it('accepts more than one file at a time', () => {
    render(<SchemaForm schema={schema([RECEIPTS])} onSubmit={vi.fn()} />);
    expect(screen.getByLabelText(/Receipts/)).toHaveAttribute('multiple');
  });

  it('uploads every file chosen and keeps all of their references', async () => {
    const onSubmit = vi.fn();
    render(<SchemaForm schema={schema([RECEIPTS])} onSubmit={onSubmit} />);

    const files = upload('boarding-pass.pdf', 'hotel.pdf');
    fireEvent.change(screen.getByLabelText(/Receipts/), { target: { files } });

    await waitFor(() => expect(uploadDocument).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/hotel\.pdf/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Submit/ }));
    expect(onSubmit).toHaveBeenCalledWith({
      doc_receipts: ['document:1', 'document:2'],
    });
  });

  it('adds to what is already attached rather than replacing it', async () => {
    const onSubmit = vi.fn();
    render(<SchemaForm schema={schema([RECEIPTS])} onSubmit={onSubmit} />);
    const input = screen.getByLabelText(/Receipts/);

    fireEvent.change(input, { target: { files: upload('boarding-pass.pdf') } });
    await screen.findByText(/boarding-pass\.pdf/);
    fireEvent.change(input, { target: { files: [new File(['%PDF'], 'taxi.pdf', { type: 'application/pdf' })] } });
    await screen.findByText(/taxi\.pdf/);

    fireEvent.click(screen.getByRole('button', { name: /Submit/ }));
    expect(onSubmit.mock.calls[0][0].doc_receipts).toHaveLength(2);
  });

  it('removes the one file asked about and keeps the rest', async () => {
    const onSubmit = vi.fn();
    render(<SchemaForm schema={schema([RECEIPTS])} onSubmit={onSubmit} />);

    const files = upload('boarding-pass.pdf', 'hotel.pdf');
    fireEvent.change(screen.getByLabelText(/Receipts/), { target: { files } });
    await screen.findByText(/hotel\.pdf/);

    const attached = screen.getByText('boarding-pass.pdf').closest('li')!;
    fireEvent.click(within(attached).getByRole('button', { name: /Remove/ }));

    fireEvent.click(screen.getByRole('button', { name: /Submit/ }));
    expect(onSubmit).toHaveBeenCalledWith({ doc_receipts: ['document:2'] });
  });

  it('will not submit until at least one receipt is attached', () => {
    render(<SchemaForm schema={schema([RECEIPTS])} onSubmit={vi.fn()} />);
    expect(screen.getByRole('button', { name: /Submit/ })).toBeDisabled();
  });
});

describe('a date that opens on today', () => {
  /**
   * The date a declaration is signed is the day it is being filled in. The
   * employer's practicum report is the case: it is filed by a supervisor with
   * no account, so `services/prefill` — which returns nothing for a guest —
   * cannot be the thing that fills it.
   */
  const SIGNED_ON = field({
    key: 'report_completed_on', label: 'Date', type: 'date',
    required: true, defaults_to_today: true,
  });

  function todayISO() {
    const now = new Date();
    return [
      now.getFullYear(),
      String(now.getMonth() + 1).padStart(2, '0'),
      String(now.getDate()).padStart(2, '0'),
    ].join('-');
  }

  it('opens filled in', () => {
    render(<SchemaForm schema={schema([SIGNED_ON])} onSubmit={vi.fn()} />);
    expect(screen.getByLabelText(/Date/)).toHaveValue(todayISO());
  });

  it('is the local date, not the one `toISOString` would give', () => {
    /**
     * `toISOString()` converts to UTC first, and for part of every day that is
     * a different date. Delyne is seven hours behind UTC, so a report signed
     * there after 5pm would be dated tomorrow.
     *
     * The clock is moved to a moment where the two genuinely disagree, so the
     * assertion has something to catch. On a machine running at UTC they never
     * do, and there is nothing here to test.
     */
    const offset = new Date().getTimezoneOffset();
    if (offset === 0) return;
    const straddling = offset > 0
      ? new Date(2026, 7, 20, 23, 30)   // west of UTC: UTC is already the 21st
      : new Date(2026, 7, 20, 0, 30);   // east of it: UTC is still the 19th

    vi.useFakeTimers();
    vi.setSystemTime(straddling);
    try {
      render(<SchemaForm schema={schema([SIGNED_ON])} onSubmit={vi.fn()} />);
      // The trap this exists for: the two disagree right now.
      expect(new Date().toISOString().slice(0, 10)).not.toBe('2026-08-20');
      expect(screen.getByLabelText(/Date/)).toHaveValue('2026-08-20');
    } finally {
      vi.useRealTimers();
    }
  });

  it('satisfies the required question without anyone typing', () => {
    render(<SchemaForm schema={schema([SIGNED_ON])} onSubmit={vi.fn()} />);
    expect(screen.getByRole('button', { name: /Submit/ })).toBeEnabled();
  });

  it('stays editable', () => {
    const onSubmit = vi.fn();
    render(<SchemaForm schema={schema([SIGNED_ON])} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText(/Date/), { target: { value: '2026-08-20' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit/ }));

    expect(onSubmit).toHaveBeenCalledWith({ report_completed_on: '2026-08-20' });
  });

  it('is what gets sent when it is left alone', () => {
    const onSubmit = vi.fn();
    render(<SchemaForm schema={schema([SIGNED_ON])} onSubmit={onSubmit} />);

    fireEvent.click(screen.getByRole('button', { name: /Submit/ }));

    expect(onSubmit).toHaveBeenCalledWith({ report_completed_on: todayISO() });
  });
});

describe('an answer the server works out', () => {
  const TOTAL = field({
    key: 'amount_requested', label: 'Total claimed', type: 'money', computed: true,
  });

  it('is not asked as a question', () => {
    render(<SchemaForm schema={schema([EXPENSES, TOTAL])} onSubmit={vi.fn()} />);
    expect(screen.queryByLabelText(/Total claimed/)).not.toBeInTheDocument();
  });

  it('is not sent, so it cannot disagree with the lines it is the sum of', () => {
    const onSubmit = vi.fn();
    render(<SchemaForm schema={schema([EXPENSES, TOTAL])} onSubmit={onSubmit} />);

    fillRow(0, 'Flight', '812.50');
    fireEvent.click(screen.getByRole('button', { name: /Submit/ }));

    expect(onSubmit.mock.calls[0][0]).not.toHaveProperty('amount_requested');
  });

  it('is not sent even when it arrives pre-filled', () => {
    /**
     * The path that makes the check worth having. Applying opens the form with
     * `api.formPrefill`, which answers from the most recent application of the
     * same type — so last term's total would be carried into this claim and
     * submitted alongside a set of expense lines that do not add up to it.
     */
    const onSubmit = vi.fn();
    render(
      <SchemaForm
        schema={schema([EXPENSES, TOTAL])}
        initial={{ amount_requested: '99999.00' }}
        onSubmit={onSubmit}
      />,
    );

    fillRow(0, 'Flight', '812.50');
    fireEvent.click(screen.getByRole('button', { name: /Submit/ }));

    expect(onSubmit.mock.calls[0][0]).not.toHaveProperty('amount_requested');
  });
});
