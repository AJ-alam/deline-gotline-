/**
 * Applying for a one-off award without an account.
 *
 * What these pin: only the two offered awards can be reached this way, the
 * form is the schema the server sent rather than a hand-written copy, and a
 * successful submission leaves the applicant holding the reference number —
 * which, having no account, is the only thing they can come back with.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import '@testing-library/jest-dom';

import type { ApplicationSchema, SchemaField } from '../../api/schema.generated';

const guestSchemas = vi.fn();
const submitGuest = vi.fn();

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client');
  return {
    ...actual,
    default: { guestSchemas, submitGuest },
    api: { guestSchemas, submitGuest },
  };
});

const { default: GuestApply } = await import('./GuestApply');

function field(overrides: Partial<SchemaField> & { key: string }): SchemaField {
  return {
    label: overrides.key,
    type: 'text',
    required: false,
    help_text: '',
    section: 'Applicant',
    choices: [],
    columns: [],
    computed: false,
    private: false,
    max_items: 0,
    defaults_to_today: false,
    ...overrides,
  };
}

const BURSARY: ApplicationSchema = {
  slug: 'graduation_bursary',
  label: 'Graduation Bursary',
  summary: 'A one-time award for finishing a credential.',
  apply_in_portal: true,
  sections: ['Applicant'],
  fields: [
    field({ key: 'first_name', label: 'First name', required: true }),
    field({ key: 'email', label: 'Email', type: 'email', required: true }),
  ],
};

function renderAt(type: string) {
  return render(
    <MemoryRouter initialEntries={[`/apply-once/${type}`]}>
      <Routes>
        <Route path="/apply-once/:type" element={<GuestApply />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('GuestApply', () => {
  beforeEach(() => {
    guestSchemas.mockReset().mockResolvedValue([BURSARY]);
    submitGuest.mockReset().mockResolvedValue({
      reference: 'DGG-000042',
      detail: 'Your application has been received.',
    });
  });

  it('renders the form the server described', async () => {
    renderAt('graduation_bursary');

    expect(await screen.findByRole('heading', { name: /Graduation Bursary/ }))
      .toBeInTheDocument();
    expect(screen.getByLabelText(/First name/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Email/)).toBeInTheDocument();
  });

  it('refuses an award that is not offered without an account', async () => {
    renderAt('admission');

    expect(await screen.findByText(/cannot be applied for without an account/))
      .toBeInTheDocument();
    // Not merely hidden: the schema is never even asked for.
    expect(guestSchemas).not.toHaveBeenCalled();
  });

  it('shows the reference number after submitting, because nothing else is kept', async () => {
    renderAt('graduation_bursary');

    fireEvent.change(await screen.findByLabelText(/First name/),
                     { target: { value: 'Guest' } });
    fireEvent.change(screen.getByLabelText(/Email/),
                     { target: { value: 'guest@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /submit application/i }));

    await waitFor(() =>
      expect(submitGuest).toHaveBeenCalledWith(
        'graduation_bursary',
        expect.objectContaining({ first_name: 'Guest', email: 'guest@example.com' }),
      ),
    );
    expect(await screen.findByText('DGG-000042')).toBeInTheDocument();
  });

  it('shows a field error against the field it belongs to', async () => {
    const { ApiError } = await import('../../api/client');
    submitGuest.mockRejectedValue(
      new ApiError(400, 'Invalid', { email: 'Enter a valid email address.' }),
    );

    renderAt('graduation_bursary');

    fireEvent.change(await screen.findByLabelText(/First name/),
                     { target: { value: 'Guest' } });
    fireEvent.change(screen.getByLabelText(/Email/), { target: { value: 'nope' } });
    fireEvent.click(screen.getByRole('button', { name: /submit application/i }));

    expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument();
    expect(screen.queryByText('DGG-000042')).not.toBeInTheDocument();
  });
});
