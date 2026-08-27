/**
 * A returning student, filing the form they file every semester.
 *
 * `account_number` is written once and read by nothing but the finance export.
 * `prefill` deliberately does not return it — the portal refuses to show a
 * student their own account number — and `Schema.clean(private_on_file=...)`
 * accepts a blank one when an account is already recorded. That pair is what
 * makes a second application possible at all.
 *
 * `revising` turns the requirement off in the renderer, and only the amend and
 * revise screens pass it. A *new* application does not, so the box sits
 * required and permanently empty, and the button that would submit the form is
 * disabled with no way for the student to satisfy it.
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import SchemaForm from './SchemaForm';
import type { ApplicationSchema } from '../api/schema.generated';

/** The banking block as `schemas.common.banking()` defines it. */
const BANKING = [
  { key: 'account_holder', label: 'Account holder name', type: 'text',
    required: true, private: true, section: 'Payment' },
  { key: 'transit_number', label: 'Transit number', type: 'text',
    required: true, private: true, section: 'Payment' },
  { key: 'institution_number', label: 'Bank institution number', type: 'text',
    required: true, private: true, section: 'Payment' },
  { key: 'account_number', label: 'Account number', type: 'text',
    required: true, private: true, section: 'Payment' },
];

const SCHEMA = {
  slug: 'continuing_funding',
  label: 'Continuing Funding',
  summary: 'Submit once each semester.',
  sections: ['Review your information', 'Payment'],
  fields: [
    { key: 'full_name', label: 'Full name', type: 'text', required: true,
      section: 'Review your information' },
    ...BANKING,
  ],
} as unknown as ApplicationSchema;

/** Exactly what `GET /api/form-prefill/continuing_funding/` returns for a
 *  student who already has a BankAccount: the three returnable fields, and
 *  never the account number. */
const PREFILL = {
  full_name: 'Majid Khan',
  account_holder: 'Majid Khan',
  transit_number: '12345',
  institution_number: '003',
};

/** What `private_on_file` reports for a student who has a BankAccount: the
 *  whole banking block, because `clean` will accept any of it blank. */
const ON_FILE = [
  'account_holder', 'transit_number', 'institution_number', 'account_number',
];

describe('a returning student filing a new application', () => {
  it('is not asked to retype the number the portal will not show them', () => {
    render(
      <SchemaForm
        schema={SCHEMA}
        initial={PREFILL}
        privateOnFile={ON_FILE}
        submitLabel="Submit application"
        onSubmit={() => {}}
      />,
    );

    const submit = screen.getByRole('button', { name: /Submit application/i });
    expect(
      submit,
      'the account number is required, blank, and unknowable to the student — '
        + 'the server accepts it blank when an account is on file, so the form '
        + 'must not hold the button shut on it',
    ).not.toBeDisabled();
  });

  it('and is not told answers are missing when only that one is', () => {
    render(
      <SchemaForm
        schema={SCHEMA}
        initial={PREFILL}
        privateOnFile={ON_FILE}
        submitLabel="Submit application"
        onSubmit={() => {}}
      />,
    );

    expect(screen.queryByText(/Please complete all required fields/i)).toBeNull();
  });

  it('still holds the button shut when a genuinely answerable field is blank', () => {
    // The guard above must not be bought by dropping the requirement wholesale.
    render(
      <SchemaForm
        schema={SCHEMA}
        initial={{ ...PREFILL, full_name: '' }}
        privateOnFile={ON_FILE}
        submitLabel="Submit application"
        onSubmit={() => {}}
      />,
    );

    expect(
      screen.getByRole('button', { name: /Submit application/i }),
    ).toBeDisabled();
  });

  it('a student with nothing on file is still asked for the account number', () => {
    // Nothing is pre-filled, so there is no account on file and the number is
    // the one thing that makes the award payable. Excusing it here would send
    // the application through with nowhere to pay it.
    render(
      <SchemaForm
        schema={SCHEMA}
        initial={{ full_name: 'New Comer' }}
        submitLabel="Submit application"
        onSubmit={() => {}}
      />,
    );

    expect(
      screen.getByRole('button', { name: /Submit application/i }),
    ).toBeDisabled();
  });
});
