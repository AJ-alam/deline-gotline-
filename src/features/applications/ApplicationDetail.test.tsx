/**
 * The screen a reviewer decides from.
 *
 * Every answer on it is rendered from the schema, so the question shows as it
 * was asked while the stored answer stays keyed by its stable key. That is the
 * whole arrangement — but it means a field type the renderer does not know
 * about does not fail: it renders `String(value)`, which for a list of expense
 * rows is `[object Object]`. The reviewer is then looking at a claim whose
 * itemisation is on file and unreadable, which is the same as not having it.
 *
 * These pin what the office actually sees: the lines, the receipts, the total,
 * and the answers whose raw form means something different from their reading.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import '@testing-library/jest-dom';

import type { Application, ApplicationSchema, SchemaField } from '../../api/client';

const application = vi.fn();
const schema = vi.fn();
const me = vi.fn();
const openDocument = vi.fn();
const transition = vi.fn();
const amend = vi.fn();
const requestEnrolment = vi.fn();
const setAward = vi.fn();
const awardCategories = vi.fn().mockResolvedValue([]);

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client');
  return {
    ...actual,
    default: { application, schema, me, openDocument, transition, amend, requestEnrolment, setAward, awardCategories },
    api: { application, schema, me, openDocument, transition, amend, requestEnrolment, setAward, awardCategories },
  };
});

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useParams: () => ({ id: '7' }) };
});

const { default: ApplicationDetail } = await import('./ApplicationDetail');

// Call counts, not implementations: "was this ever sent?" is a question about
// this test, and a mock that remembers the last one answers it wrongly.
beforeEach(() => { vi.clearAllMocks(); });

function field(overrides: Partial<SchemaField> & { key: string }): SchemaField {
  return {
    label: overrides.key,
    type: 'text',
    required: false,
    help_text: '',
    section: 'Expenses',
    choices: [],
    columns: [],
    computed: false,
    private: false,
    max_items: 0,
    defaults_to_today: false,
    ...overrides,
  };
}

const TRAVEL_SCHEMA: ApplicationSchema = {
  slug: 'travel',
  label: 'Travel & Emergency Assistance',
  summary: 'Claim back what you spent travelling.',
  apply_in_portal: true,
  sections: ['Expenses', 'Travel', 'Declaration'],
  fields: [
    field({
      key: 'expenses', label: 'Expenses claimed', type: 'table',
      columns: [
        field({ key: 'description', label: 'Description' }),
        field({ key: 'amount', label: 'Amount', type: 'money' }),
        field({ key: 'receipt_attached', label: 'Receipt attached', type: 'boolean' }),
      ],
    }),
    field({ key: 'amount_requested', label: 'Total claimed', type: 'money', computed: true }),
    field({ key: 'doc_receipts', label: 'Receipts', type: 'files' }),
    field({
      key: 'travel_purpose', label: 'Purpose of travel', type: 'choice',
      section: 'Travel',
      choices: [
        { value: 'graduation', label: 'Graduation ceremony' },
        { value: 'compassionate', label: 'Compassionate or emergency travel' },
      ],
    }),
    field({ key: 'return_date', label: 'Return date', type: 'date', section: 'Travel' }),
    field({
      key: 'declaration_confirmed', label: 'I confirm the declaration',
      type: 'confirm', section: 'Declaration',
    }),
  ],
};

/** A travel claim as the API returns it, after the round trip through JSON. */
const CLAIM: Application = {
  id: 7,
  type: 'travel',
  type_label: 'Travel & Emergency Assistance',
  stream: 'dggr',
  status: 'submitted',
  status_label: 'Submitted',
  student_name: 'Majid Khan',
  awarded_total: '0.00',
  submitted_at: '2026-09-01T00:00:00Z',
  submitted_after_deadline: false,
  residency_flag: '',
  enrolment: { required: false, status: 'not_required', label: 'Not required' },
  schema_slug: 'travel',
  answers: {
    expenses: [
      { description: 'Air North YZF–YEG', amount: '812.50', receipt_attached: true },
      { description: 'Hotel, one night', amount: '189.00', receipt_attached: false },
    ],
    amount_requested: '1001.50',
    doc_receipts: ['document:1', 'document:2', 'document:3'],
    travel_purpose: 'graduation',
    declaration_confirmed: true,
  },
  office_notes: {},
  events: [],
  decision: null,
  enrolment_answers: null,
  identifiers: {},
  documents: [],
  can_revise: false,
  information_requested: null,
  banking: { on_file: false, account: '', holder: '', held: false },
};

function show(overrides: Partial<Application> = {}, role = 'support_worker') {
  application.mockResolvedValue({ ...CLAIM, ...overrides });
  schema.mockResolvedValue(TRAVEL_SCHEMA);
  me.mockResolvedValue({
    id: 2, email: `${role}@dgg.test`, full_name: 'Wanda Worker',
    role, beneficiary_number: '',
  });
  render(
    <MemoryRouter>
      <ApplicationDetail />
    </MemoryRouter>,
  );
}

describe('the answers a reviewer is shown', () => {
  it('renders an expense breakdown as its rows, not as [object Object]', async () => {
    show();
    const heading = await screen.findByText('Expenses claimed');
    const table = heading.closest('.answers__row')!.querySelector('table')!;

    expect(within(table).getByText('Air North YZF–YEG')).toBeInTheDocument();
    expect(within(table).getByText('$812.50')).toBeInTheDocument();
    expect(screen.queryByText(/\[object Object\]/)).not.toBeInTheDocument();
  });

  it('labels the columns from the schema', async () => {
    show();
    await screen.findByText('Expenses claimed');
    for (const label of ['Description', 'Amount', 'Receipt attached']) {
      expect(screen.getByRole('columnheader', { name: label })).toBeInTheDocument();
    }
  });

  it('reads a cell that is false as "No", not as blank', async () => {
    /**
     * The row where the student said a receipt was not attached. Rendered as
     * an empty cell it looks like a question nobody answered, and a reviewer
     * has no reason to ask about it.
     */
    show();
    await screen.findByText('Expenses claimed');
    const rows = screen.getAllByRole('row');
    const hotel = rows.find((row) => within(row).queryByText('Hotel, one night'))!;
    expect(within(hotel).getByText('No')).toBeInTheDocument();
  });

  it('counts the receipts rather than printing their references', async () => {
    show();
    expect(await screen.findByText('3 files attached')).toBeInTheDocument();
    expect(screen.queryByText(/document:1/)).not.toBeInTheDocument();
  });

  it('says "1 file" when there is one', async () => {
    show({ answers: { ...CLAIM.answers, doc_receipts: ['document:1'] } });
    expect(await screen.findByText('1 file attached')).toBeInTheDocument();
  });

  it('shows the total the server worked out', async () => {
    show();
    await screen.findByText('Total claimed');
    expect(screen.getByText('$1001.50')).toBeInTheDocument();
  });

  it('shows a choice by its label, never by its stored value', async () => {
    // The stored value is what the award is calculated from; the label is what
    // a person reads. Showing 'graduation' to a reviewer is showing them the
    // database.
    show();
    expect(await screen.findByText('Graduation ceremony')).toBeInTheDocument();
    expect(screen.queryByText('graduation')).not.toBeInTheDocument();
  });

  it('reads a declaration as confirmed rather than as the word true', async () => {
    show();
    expect(await screen.findByText('Confirmed')).toBeInTheDocument();
  });

  it('leaves an unanswered optional question off the list entirely', async () => {
    /**
     * `return_date` is in the schema and absent from the answers: a one-way
     * trip. The list shows what was answered, so an optional question nobody
     * answered is not a row — a screen of empty rows is one a reviewer stops
     * reading.
     */
    show();
    await screen.findByText('Expenses claimed');
    expect(screen.queryByText('Return date')).not.toBeInTheDocument();
  });

  it('marks a missing cell inside a row rather than leaving it blank', async () => {
    /**
     * A cell can be absent where the whole answer cannot: the schema drops a
     * blank optional value before writing, so a row can arrive short. Blank, it
     * reads as a column that failed to render.
     */
    show({
      answers: {
        ...CLAIM.answers,
        expenses: [{ description: 'Taxi from airport', amount: '48.25' }],
      },
    });
    await screen.findByText('Expenses claimed');
    const row = screen.getAllByRole('row')
      .find((candidate) => within(candidate).queryByText('Taxi from airport'))!;
    expect(within(row).getByText('—')).toBeInTheDocument();
  });
});

describe('when the office has asked for more information', () => {
  const ASKED = {
    note: 'Please attach your transcript for the Fall term.',
    asked_by: 'Wanda Worker',
    asked_at: '2026-09-02T00:00:00Z',
  };

  it('shows the student what was asked, in the reviewer’s own words', async () => {
    show({ information_requested: ASKED, can_revise: true });
    expect(await screen.findByText(/attach your transcript for the Fall term/))
      .toBeInTheDocument();
  });

  it('says who asked', async () => {
    // Without it the student is told something is needed and not by whom.
    show({ information_requested: ASKED, can_revise: true });
    expect(await screen.findByText(/Wanda Worker/)).toBeInTheDocument();
  });

  it('opens the application for editing', async () => {
    show({ information_requested: ASKED, can_revise: true });
    expect(await screen.findByText('Update your application')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Send back to the office/ }))
      .toBeInTheDocument();
  });

  it('opens it on the answers already stored, so nothing is retyped', async () => {
    show({ information_requested: ASKED, can_revise: true });
    await screen.findByText('Update your application');
    const purpose = screen.getByLabelText(/Purpose of travel/) as HTMLSelectElement;
    expect(purpose.value).toBe('graduation');
  });

  it('offers a file control, so a document can be replaced', async () => {
    show({ information_requested: ASKED, can_revise: true });
    await screen.findByText('Update your application');
    expect(screen.getByLabelText(/Receipts/)).toHaveAttribute('type', 'file');
  });

  it('does not offer the form when the office is not waiting', async () => {
    // An application under review must not change under the reviewer.
    show({ information_requested: ASKED, can_revise: false });
    await screen.findByText(/attach your transcript/);
    expect(screen.queryByText('Update your application')).not.toBeInTheDocument();
  });

  it('says nothing about it when nothing was asked', async () => {
    show();
    await screen.findByText('Expenses claimed');
    expect(screen.queryByText('More information needed')).not.toBeInTheDocument();
  });
});

describe('documents the office can open', () => {
  const DOCUMENTS = [
    {
      id: 12, field_key: 'doc_receipts', original_name: 'boarding-pass.pdf',
      uploaded_at: '2026-09-01T00:00:00Z', url: '/api/documents/12/',
    },
    {
      id: 13, field_key: 'doc_receipts', original_name: 'hotel.pdf',
      uploaded_at: '2026-09-01T00:00:00Z', url: '/api/documents/13/',
    },
  ];

  it('lists every attached document by the name it was uploaded under', async () => {
    show({ documents: DOCUMENTS });
    expect(await screen.findByText('boarding-pass.pdf')).toBeInTheDocument();
    expect(screen.getByText('hotel.pdf')).toBeInTheDocument();
  });

  it('opens one through the client, so the token goes with the request', async () => {
    /**
     * The whole point. A reviewer was shown `document:12` and could do nothing
     * with it, which is the same as the document never having been attached.
     *
     * This asserted an `href` for a while, and passed for a year while the
     * feature was broken: the endpoint is authorised by the bearer token, a
     * navigation carries none, and every click opened the API's 401 page. An
     * href is the shape of working, not working — so what is pinned here is
     * that the click *fetches*, and that there is no bare link to the API for
     * a browser to navigate to.
     */
    const opened = vi.fn().mockResolvedValue(new Blob(['%PDF-1.4'], { type: 'application/pdf' }));
    openDocument.mockImplementation(opened);
    const tab = { location: { href: '' }, close: vi.fn() };
    vi.spyOn(window, 'open').mockReturnValue(tab as unknown as Window);
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:document');

    show({ documents: DOCUMENTS });
    const control = await screen.findByRole('button', { name: 'boarding-pass.pdf' });
    expect(screen.queryByRole('link', { name: 'boarding-pass.pdf' })).not.toBeInTheDocument();

    fireEvent.click(control);
    await waitFor(() => expect(opened).toHaveBeenCalledWith('/api/documents/12/'));
    await waitFor(() => expect(tab.location.href).toBe('blob:document'));
  });

  it('says which question each one answers', async () => {
    show({ documents: DOCUMENTS });
    await screen.findByText('boarding-pass.pdf');
    expect(screen.getAllByText(/Receipts/).length).toBeGreaterThan(0);
  });

  it('shows no card when nothing is attached', async () => {
    show({ documents: [] });
    await screen.findByText('Expenses claimed');
    expect(screen.queryByText('Documents')).not.toBeInTheDocument();
  });
});

describe('the actions the office is offered', () => {
  /**
   * The screen used to carry its own copy of the workflow table. The server
   * gained the ability to approve a reviewed application without forwarding it
   * to the director first — the office asked for exactly that — and the copy
   * here was never updated, so the feature existed over HTTP and not in a
   * browser. The table is generated from the backend now.
   */
  it('offers an administrator Approve on a reviewed application', async () => {
    show({ status: 'under_review' }, 'admin');
    expect(await screen.findByRole('button', { name: 'Approve' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Forward to Director' })).toBeInTheDocument();
  });

  it('offers a director the same', async () => {
    show({ status: 'under_review' }, 'director');
    expect(await screen.findByRole('button', { name: 'Approve' })).toBeInTheDocument();
  });

  it('does not offer a support worker anything that decides', async () => {
    show({ status: 'under_review' }, 'support_worker');
    await screen.findByRole('button', { name: 'Forward to Director' });
    for (const deciding of ['Approve', 'Decline']) {
      expect(screen.queryByRole('button', { name: deciding })).not.toBeInTheDocument();
    }
  });

  it('offers nothing at all once an application is decided', async () => {
    for (const status of ['approved', 'declined', 'sent_to_finance'] as const) {
      show({ status }, 'admin');
      await screen.findByRole('heading', { name: 'Admission Application' })
        .catch(() => undefined);
      for (const gone of ['Approve', 'Decline', 'Mark reviewed', 'Forward to Director']) {
        expect(
          screen.queryByRole('button', { name: gone }),
          `${status} offered ${gone}`,
        ).not.toBeInTheDocument();
      }
      cleanup();
    }
  });
});

describe('asking the applicant for something', () => {
  /**
   * The server has carried a note on this transition since the path existed:
   * it goes into the email and into the portal notice. The screen posted the
   * action with nothing attached, so every student was told "Please review your
   * application" — a request to guess what the office wanted.
   */
  it('will not send a request for information with no words in it', async () => {
    show({ status: 'submitted' }, 'support_worker');

    fireEvent.click(await screen.findByRole('button', { name: 'Request more information' }));

    expect(screen.getByRole('button', { name: 'Send request' })).toBeDisabled();
    expect(transition).not.toHaveBeenCalled();
  });

  it('sends what the reviewer typed', async () => {
    transition.mockResolvedValue({ ...CLAIM, status: 'info_requested' });
    show({ status: 'submitted' }, 'support_worker');

    fireEvent.click(await screen.findByRole('button', { name: 'Request more information' }));
    fireEvent.change(screen.getByLabelText('What do you need from the applicant?'), {
      target: { value: 'Please attach your transcript for the Fall term.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send request' }));

    await waitFor(() => expect(transition).toHaveBeenCalledWith(
      7, 'info_requested', 'Please attach your transcript for the Fall term.'));
  });

  it('asks a reason before declining', async () => {
    // Declining is a decision, so it belongs to the director — a support
    // worker is never offered it at all.
    show({ status: 'submitted' }, 'director');

    fireEvent.click(await screen.findByRole('button', { name: 'Decline' }));
    expect(screen.getByLabelText('Why is this being declined?')).toBeInTheDocument();
    expect(transition).not.toHaveBeenCalled();
  });
});

describe('the office editing a filed application', () => {
  it('offers an administrator the edit', async () => {
    show({ status: 'submitted' }, 'admin');
    expect(await screen.findByRole('button', { name: 'Edit application' })).toBeInTheDocument();
  });

  it('does not offer it to the people who assess applications', async () => {
    /**
     * Someone who can both rewrite the answers and advance the application can
     * price whatever they like without a second person seeing it. The server
     * refuses them; the button must not be there either.
     */
    for (const role of ['support_worker', 'director', 'finance', 'student']) {
      show({ status: 'submitted' }, role);
      await screen.findByText('Expenses claimed');
      expect(
        screen.queryByRole('button', { name: 'Edit application' }),
        `${role} was offered the edit`,
      ).not.toBeInTheDocument();
      cleanup();
    }
  });

  it('does not offer it once the application has been decided', async () => {
    // Its answers are the record the decision was made from.
    show({ status: 'approved' }, 'admin');
    await screen.findByText('Expenses claimed');
    expect(screen.queryByRole('button', { name: 'Edit application' })).not.toBeInTheDocument();
  });

  it('warns that the applicant will be told', async () => {
    show({ status: 'submitted' }, 'admin');
    fireEvent.click(await screen.findByRole('button', { name: 'Edit application' }));

    expect(screen.getByText(/They will be\s+told what changed/)).toBeInTheDocument();
    expect(screen.getByLabelText('What are you changing, and why?')).toBeInTheDocument();
  });
});

describe('an enrolment nobody has asked about', () => {
  /**
   * The request goes out at submission — but only when a registrar address is
   * already known, and a renewal carries one from the student's last
   * application. Somebody whose admission was on paper has nothing to carry, so
   * the request was skipped in silence and the application could never be
   * forwarded by anybody. The screen said "Not required".
   */
  const NEEDS_ASKING = {
    required: true, status: 'not_requested' as const,
    label: 'No confirmation requested yet', confirmed: false,
  };

  it('says plainly that nothing has been requested', async () => {
    show({ type: 'admission', enrolment: NEEDS_ASKING }, 'support_worker');
    expect(await screen.findByText(/No confirmation has been requested/))
      .toBeInTheDocument();
  });

  it('lets staff ask, once they give an address', async () => {
    show({ type: 'admission', enrolment: NEEDS_ASKING }, 'support_worker');
    const ask = await screen.findByRole('button', { name: 'Request confirmation' });
    expect(ask).toBeDisabled();

    fireEvent.change(screen.getByLabelText('Registrar’s email address'), {
      target: { value: 'registrar@aurora.test' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Request confirmation' }));

    await waitFor(() => expect(requestEnrolment)
      .toHaveBeenCalledWith(7, 'registrar@aurora.test'));
  });

  it('offers to send again when one already went out', async () => {
    show({
      type: 'admission',
      enrolment: { required: true, status: 'requested', label: 'Awaiting institution',
                   confirmed: false, registrar_email: 'registrar@aurora.test' },
    }, 'support_worker');

    expect(await screen.findByRole('button', { name: 'Send the request again' }))
      .toBeEnabled();
  });

  it('does not offer it to the student', async () => {
    show({ type: 'admission', enrolment: NEEDS_ASKING }, 'student');
    await screen.findByText('Expenses claimed');
    expect(screen.queryByRole('button', { name: 'Request confirmation' }))
      .not.toBeInTheDocument();
  });

  it('stops offering it once the institution has confirmed', async () => {
    show({
      type: 'admission',
      enrolment: { required: true, status: 'completed', label: 'Confirmed by institution',
                   confirmed: true, registrar_email: 'registrar@aurora.test' },
    }, 'support_worker');
    await screen.findByText('Expenses claimed');
    expect(screen.queryByRole('button', { name: /Request confirmation|Send the request again/ }))
      .not.toBeInTheDocument();
  });
});

describe('setting the funding breakdown by hand', () => {
  const PRICED = {
    id: 4, total: '9600.00', rule_set_version: 1, priced_on: '2026-09-01',
    is_complete: true, is_current: true, created_at: '2026-09-01T00:00:00Z',
    lines: [
      { id: 1, category: 'living', category_label: 'Living Allowance',
        amount: '9600.00', status: 'pending', rule_code: 'psssp_living',
        reference: null, created_at: '2026-09-01T00:00:00Z' },
    ],
    trace: {
      rule_set: 'DGG Student Funding Policy v1', priced_on: '2026-09-01',
      total: '9600.00', missing_rates: [],
      rules: [{ code: 'psssp_living', description: 'Living allowance',
                category: 'living', applied: true, amount: '9600.00',
                reason: '$2400.00/month x 4 month(s)' }],
    },
  };

  it('offers the edit to an administrator', async () => {
    show({ status: 'submitted', decision: PRICED }, 'admin');
    expect(await screen.findByRole('button', { name: 'Edit breakdown' }))
      .toBeInTheDocument();
  });

  it('does not offer it to a director or a support worker', async () => {
    for (const role of ['director', 'support_worker', 'finance', 'student']) {
      show({ status: 'submitted', decision: PRICED }, role);
      await screen.findByText('Expenses claimed');
      expect(
        screen.queryByRole('button', { name: 'Edit breakdown' }),
        `${role} was offered it`,
      ).not.toBeInTheDocument();
      cleanup();
    }
  });

  it('opens on what is already awarded rather than empty', async () => {
    show({ status: 'submitted', decision: PRICED }, 'admin');
    fireEvent.click(await screen.findByRole('button', { name: 'Edit breakdown' }));

    expect(screen.getByLabelText('What line 1 is for')).toHaveValue('Living allowance');
    expect(screen.getByLabelText('Amount for line 1')).toHaveValue('9600.00');
  });

  it('adds a line, and sends every line to the server', async () => {
    /** The office's case: a fee the rules have no rate for. */
    setAward.mockResolvedValue(PRICED);
    awardCategories.mockResolvedValue([
      { value: 'living', label: 'Living Allowance' },
      { value: 'travel', label: 'Travel' },
    ]);
    show({ status: 'submitted', decision: PRICED }, 'admin');
    fireEvent.click(await screen.findByRole('button', { name: 'Edit breakdown' }));
    // The categories are fetched. Without waiting for them the test drives an
    // editor that has not finished loading, which no person ever does.
    await screen.findByRole('option', { name: 'Travel' });

    fireEvent.click(screen.getByRole('button', { name: 'Add a line' }));
    fireEvent.change(screen.getByLabelText('What line 2 is for'),
      { target: { value: 'Flight home at term end' } });
    // Chosen, not assumed. The category the new line is filed under is the
    // office's decision, and a test that leaves the select alone is asserting
    // whatever the component happened to default to.
    fireEvent.change(screen.getByLabelText('Category for line 2'),
      { target: { value: 'travel' } });
    fireEvent.change(screen.getByLabelText('Amount for line 2'),
      { target: { value: '1200' } });
    fireEvent.change(screen.getByLabelText('Why is it being set by hand?'),
      { target: { value: 'Agreed at the counter.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save this breakdown' }));

    await waitFor(() => expect(setAward).toHaveBeenCalledWith(
      7,
      [
        { category: 'living', description: 'Living allowance', amount: '9600.00' },
        { category: 'travel', description: 'Flight home at term end', amount: '1200' },
      ],
      'Agreed at the counter.',
    ));
  });

  it('files a new line under a category the office actually offers', async () => {
    /**
     * The select and the value saved must agree.
     *
     * A `<select>` given a value none of its options carries displays the first
     * option instead. The blank line was created with `'tuition'` written into
     * the component, so on an office whose list does not start with tuition the
     * screen said one thing and the save posted another — with nobody having
     * touched the control.
     */
    setAward.mockResolvedValue(PRICED);
    awardCategories.mockResolvedValue([
      { value: 'bursary', label: 'Bursary' },
      { value: 'travel', label: 'Travel' },
    ]);
    show({ status: 'submitted', decision: PRICED }, 'admin');
    fireEvent.click(await screen.findByRole('button', { name: 'Edit breakdown' }));
    await screen.findByRole('option', { name: 'Bursary' });

    fireEvent.click(screen.getByRole('button', { name: 'Add a line' }));
    fireEvent.change(screen.getByLabelText('Amount for line 2'),
      { target: { value: '250' } });
    fireEvent.change(screen.getByLabelText('Why is it being set by hand?'),
      { target: { value: 'Counter agreement.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save this breakdown' }));

    await waitFor(() => expect(setAward).toHaveBeenCalled());
    const [, lines] = setAward.mock.calls[0];
    expect(lines[1].category).toBe('bursary');
    expect(screen.queryByDisplayValue('tuition')).not.toBeInTheDocument();
  });

  it('warns that re-pricing will discard what was typed', async () => {
    show({ status: 'submitted', decision: PRICED }, 'admin');
    fireEvent.click(await screen.findByRole('button', { name: 'Edit breakdown' }));

    expect(screen.getByText(/prices the application from the rules again/))
      .toBeInTheDocument();
  });

  it('will not save a line with no amount', async () => {
    show({ status: 'submitted', decision: PRICED }, 'admin');
    fireEvent.click(await screen.findByRole('button', { name: 'Edit breakdown' }));
    fireEvent.click(screen.getByRole('button', { name: 'Add a line' }));

    expect(screen.getByRole('button', { name: 'Save this breakdown' })).toBeDisabled();
  });
});
