/**
 * The Social Insurance Number field.
 *
 * A SIN carries a Luhn check digit, so most made-up numbers are invalid — which
 * is correct, because a wrong-but-accepted number is filed against a real
 * person who is not the applicant. What was wrong was *when* the applicant
 * found out: the form said nothing until it was submitted at the end of four
 * steps, and the only signal was a rejected application.
 *
 * These pin that the same rule the server applies is applied here too, at the
 * moment the number is entered.
 */

import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

import type { ApplicationSchema, SchemaField } from '../api/schema.generated';
import SchemaForm from './SchemaForm';

const SCHEMA: ApplicationSchema = {
  slug: 'admission',
  label: 'Admission Application',
  summary: 'Start here.',
  apply_in_portal: true,
  sections: ['Applicant'],
  fields: [
    {
      key: 'sin',
      label: 'Social Insurance Number',
      type: 'sin',
      required: true,
      help_text: '',
      section: 'Applicant',
      choices: [],
      columns: [],
      computed: false,
    private: false,
      max_items: 0,
      defaults_to_today: false,
    } as SchemaField,
  ],
};

function enter(digits: string) {
  render(<SchemaForm schema={SCHEMA} onSubmit={vi.fn()} />);
  const input = screen.getByLabelText(/Social Insurance Number/);
  fireEvent.change(input, { target: { value: digits } });
  fireEvent.blur(input);
  return input;
}

describe('the Social Insurance Number field', () => {
  it('accepts a number that satisfies the check digit', () => {
    enter('130692544');
    expect(screen.getByText(/looks right/)).toBeInTheDocument();
  });

  it('says so immediately when the check digit does not add up', () => {
    // The commonest real mistake: two digits swapped.
    enter('130692454');
    expect(screen.getByText(/not a valid number/)).toBeInTheDocument();
  });

  it('explains that no number starts with zero', () => {
    enter('046454286');
    expect(screen.getByText(/starts with 0/)).toBeInTheDocument();
  });

  it('counts down rather than calling a half-typed number wrong', () => {
    enter('1306');
    expect(screen.getByText(/5 more digits to go/)).toBeInTheDocument();
  });

  it('says nothing at all before anything is typed', () => {
    render(<SchemaForm schema={SCHEMA} onSubmit={vi.fn()} />);
    expect(screen.queryByText(/not a valid number/)).not.toBeInTheDocument();
    expect(screen.queryByText(/looks right/)).not.toBeInTheDocument();
  });

  it('keeps only digits, so spaces and dashes can be typed or pasted', () => {
    const input = enter('130-692 544');
    expect(input).toHaveValue('130692544');
    expect(screen.getByText(/looks right/)).toBeInTheDocument();
  });

  it('stops at nine digits', () => {
    const input = enter('1306925441234');
    expect(input).toHaveValue('130692544');
  });

  it('is masked until revealed', () => {
    const input = enter('130692544');
    expect(input).toHaveAttribute('type', 'password');

    fireEvent.click(screen.getByRole('button', { name: 'Show' }));
    expect(screen.getByLabelText(/Social Insurance Number/)).toHaveAttribute('type', 'text');
  });
});
