/**
 * The renderer that replaced nine hand-written form pages.
 *
 * These assert it renders whatever the API describes without knowing anything
 * about any particular form — which is the property that makes the nine pages
 * unnecessary.
 */

import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

import SchemaForm from './SchemaForm';
import type { ApplicationSchema, SchemaField } from '../api/schema.generated';

function field(overrides: Partial<SchemaField> & { key: string }): SchemaField {
  return {
    label: overrides.key,
    type: 'text',
    required: false,
    help_text: '',
    section: 'Details',
    choices: [],
    ...overrides,
  };
}

function schema(fields: SchemaField[], sections = ['Details']): ApplicationSchema {
  return { slug: 'admission', label: 'Admission Application', sections, fields };
}

describe('SchemaForm', () => {
  it('renders a control for every field the schema describes', () => {
    render(
      <SchemaForm
        schema={schema([
          field({ key: 'first_name', label: 'First name' }),
          field({ key: 'email', label: 'Email', type: 'email' }),
        ])}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByLabelText(/First name/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Email/)).toBeInTheDocument();
  });

  it('renders a choice field as a select with exactly the offered options', () => {
    render(
      <SchemaForm
        schema={schema([
          field({
            key: 'course_load',
            label: 'Enrollment status',
            type: 'choice',
            choices: [
              { value: 'full_time', label: 'Full-time' },
              { value: 'part_time', label: 'Part-time' },
            ],
          }),
        ])}
        onSubmit={vi.fn()}
      />,
    );

    const select = screen.getByLabelText(/Enrollment status/) as HTMLSelectElement;
    // A free-text answer is what let 'BSc' fall through to the cheapest tier.
    expect([...select.options].map((o) => o.value)).toEqual(['', 'full_time', 'part_time']);
  });

  it('groups fields under the sections the schema declares', () => {
    render(
      <SchemaForm
        schema={schema(
          [
            field({ key: 'first_name', section: 'Applicant' }),
            field({ key: 'institution_name', section: 'Study' }),
          ],
          ['Applicant', 'Study'],
        )}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByRole('heading', { name: 'Applicant' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Study' })).toBeInTheDocument();
  });

  it('submits answers keyed by the schema field keys', () => {
    const onSubmit = vi.fn();
    render(
      <SchemaForm
        schema={schema([field({ key: 'first_name', label: 'First name' })])}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.change(screen.getByLabelText(/First name/), { target: { value: 'Jane' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit/ }));

    expect(onSubmit).toHaveBeenCalledWith({ first_name: 'Jane' });
  });

  it('omits blank optional answers rather than sending empty strings', () => {
    const onSubmit = vi.fn();
    render(
      <SchemaForm
        schema={schema([
          field({ key: 'first_name', label: 'First name' }),
          field({ key: 'preferred_name', label: 'Preferred name' }),
        ])}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.change(screen.getByLabelText(/First name/), { target: { value: 'Jane' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit/ }));

    expect(onSubmit).toHaveBeenCalledWith({ first_name: 'Jane' });
    expect(onSubmit.mock.calls[0][0]).not.toHaveProperty('preferred_name');
  });

  it('keeps a false checkbox, because false is an answer', () => {
    const onSubmit = vi.fn();
    render(
      <SchemaForm
        schema={schema([field({ key: 'receives_sfa', label: 'Receives SFA', type: 'boolean' })])}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /Submit/ }));
    expect(onSubmit).toHaveBeenCalledWith({ receives_sfa: false });
  });

  it('shows an API error against the question it belongs to', () => {
    render(
      <SchemaForm
        schema={schema([
          field({ key: 'course_load', label: 'Enrollment status' }),
          field({ key: 'first_name', label: 'First name' }),
        ])}
        errors={{ course_load: 'Enrollment status must be one of: Full-time, Part-time.' }}
        onSubmit={vi.fn()}
      />,
    );

    const message = screen.getByText(/Enrollment status must be one of/);
    // Announced, not merely coloured: a red border alone is invisible to a
    // screen reader.
    expect(message).toHaveAttribute('role', 'alert');
    expect(screen.getByLabelText(/Enrollment status/)).toHaveAttribute('aria-invalid', 'true');
    // The error belongs to one question; the other must not be marked invalid.
    expect(screen.getByLabelText(/First name/)).not.toHaveAttribute('aria-invalid');
  });

  it('marks required fields for assistive technology', () => {
    render(
      <SchemaForm
        schema={schema([field({ key: 'first_name', label: 'First name', required: true })])}
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByText('First name').textContent).toContain('*');
  });

  it('shows help text from the schema', () => {
    render(
      <SchemaForm
        schema={schema([
          field({
            key: 'course_load',
            label: 'Enrollment status',
            help_text: 'Full-time and part-time draw different rates.',
          }),
        ])}
        onSubmit={vi.fn()}
      />,
    );
    expect(
      screen.getByText('Full-time and part-time draw different rates.'),
    ).toBeInTheDocument();
  });

  it('disables submission while a request is in flight', () => {
    render(
      <SchemaForm
        schema={schema([field({ key: 'first_name' })])}
        busy
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: /Submit/ })).toBeDisabled();
  });
});
