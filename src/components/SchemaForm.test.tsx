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
    slug: 'admission',
    label: 'Admission Application',
    summary: 'Start here.',
    apply_in_portal: true,
    sections,
    fields,
  };
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

  it('lets a required yes/no be answered "no"', () => {
    // As a single checkbox, 'no' and 'not answered' were the same state, so a
    // required boolean could never be satisfied by answering no — the registrar
    // could not report a student as *not* enrolled, and an unanswered "do you
    // receive SFA?" would have read as "no" and picked the wrong funding stream.
    const onSubmit = vi.fn();
    render(
      <SchemaForm
        schema={schema([
          field({ key: 'receives_sfa', label: 'Receives SFA', type: 'boolean', required: true }),
        ])}
        onSubmit={onSubmit}
      />,
    );

    expect(screen.getByRole('button', { name: /Submit/ })).toBeDisabled();
    fireEvent.click(screen.getByRole('radio', { name: 'No' }));
    expect(screen.getByRole('button', { name: /Submit/ })).toBeEnabled();

    fireEvent.click(screen.getByRole('button', { name: /Submit/ }));
    expect(onSubmit).toHaveBeenCalledWith({ receives_sfa: false });
  });

  it('submits a required yes/no answered "yes" as true', () => {
    const onSubmit = vi.fn();
    render(
      <SchemaForm
        schema={schema([
          field({ key: 'receives_sfa', label: 'Receives SFA', type: 'boolean', required: true }),
        ])}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(screen.getByRole('radio', { name: 'Yes' }));
    fireEvent.click(screen.getByRole('button', { name: /Submit/ }));
    expect(onSubmit).toHaveBeenCalledWith({ receives_sfa: true });
  });

  it('shows the declaration being agreed to, and will not submit without it', () => {
    const onSubmit = vi.fn();
    render(
      <SchemaForm
        schema={schema([
          field({
            key: 'declaration_confirmed',
            label: 'Confirm declaration',
            type: 'confirm',
            required: true,
            help_text: 'I declare that all information given on this application is true and complete.',
          }),
        ])}
        onSubmit={onSubmit}
      />,
    );

    // The statement itself, not tucked under the box as a hint.
    expect(
      screen.getByText(/I declare that all information given on this application/),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Submit/ })).toBeDisabled();

    fireEvent.click(screen.getByLabelText(/Confirm declaration/));
    fireEvent.click(screen.getByRole('button', { name: /Submit/ }));
    expect(onSubmit).toHaveBeenCalledWith({ declaration_confirmed: true });
  });

  it('does not restate a one-section step as a heading over its own fields', () => {
    // The progress list names the step. Repeating it immediately above the
    // first question said the same thing twice before anything was asked.
    render(
      <SchemaForm
        schema={schema(
          [
            field({ key: 'full_name', section: 'Review your information' }),
            field({ key: 'doc_transcript', section: 'Upload required documents' }),
          ],
          ['Review your information', 'Upload required documents'],
        )}
        steps={[
          { title: 'Information review', sections: ['Review your information'] },
          { title: 'Documents', sections: ['Upload required documents'] },
        ]}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.queryByRole('heading', { name: /Review your information/ })).toBeNull();
    expect(screen.queryByRole('heading', { name: /Step 1/ })).toBeNull();
    // The step is still named once, in the progress list.
    expect(screen.getByRole('button', { name: /Information review/ })).toBeInTheDocument();
  });

  it('still separates a step that holds more than one section', () => {
    render(
      <SchemaForm
        schema={schema(
          [
            field({ key: 'doc_transcript', section: 'Upload required documents' }),
            field({ key: 'signature', section: 'Declaration' }),
          ],
          ['Upload required documents', 'Declaration'],
        )}
        steps={[
          {
            title: 'Documents & declaration',
            sections: ['Upload required documents', 'Declaration'],
          },
        ]}
        onSubmit={vi.fn()}
      />,
    );

    expect(
      screen.getByRole('heading', { name: 'Upload required documents' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Declaration' })).toBeInTheDocument();
  });

  it('opens with the answers already on file', () => {
    const onSubmit = vi.fn();
    render(
      <SchemaForm
        schema={schema([
          field({ key: 'full_name', label: 'Full name' }),
          field({ key: 'institution_name', label: 'Institution' }),
        ])}
        initial={{ full_name: 'Majid Khan', institution_name: 'Aurora College' }}
        onSubmit={onSubmit}
      />,
    );

    expect(screen.getByLabelText(/Full name/)).toHaveValue('Majid Khan');

    // Still editable: a renewal confirms what is held, it does not lock it.
    fireEvent.change(screen.getByLabelText(/Institution/), {
      target: { value: 'Yukon University' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Submit/ }));
    expect(onSubmit).toHaveBeenCalledWith({
      full_name: 'Majid Khan',
      institution_name: 'Yukon University',
    });
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

describe('editing an application that already exists', () => {
  /**
   * A SIN and a bank account are split off at submission and never returned, so
   * a form opened on a stored application opens with them blank. Required, they
   * held Save disabled on every edit of every form that asks for one — the
   * office could not correct such an application, and the student could not
   * answer a request for more information. The server accepting the edit made
   * no difference, because nobody could press the button.
   */
  const withPrivate = schema([
    field({ key: 'full_name', label: 'Full name', required: true }),
    field({ key: 'sin', label: 'Social Insurance Number', type: 'sin',
            required: true, private: true }),
    field({ key: 'account_number', label: 'Account number',
            required: true, private: true }),
  ]);

  it('does not demand an answer it was never given', () => {
    render(
      <SchemaForm schema={withPrivate} revising initial={{ full_name: 'Majid Khan' }}
                  submitLabel="Save changes" onSubmit={() => {}} />,
    );

    expect(screen.getByRole('button', { name: 'Save changes' })).toBeEnabled();
    expect(screen.queryByText(/left on this form/)).not.toBeInTheDocument();
  });

  it('still demands the answers the applicant can see', () => {
    render(
      <SchemaForm schema={withPrivate} revising initial={{ full_name: '' }}
                  submitLabel="Save changes" onSubmit={() => {}} />,
    );

    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled();
  });

  it('demands all of them on a first submission', () => {
    // Nothing is on file yet, so nothing may be left out.
    render(
      <SchemaForm schema={withPrivate} initial={{ full_name: 'Majid Khan' }}
                  onSubmit={() => {}} />,
    );

    expect(screen.getByRole('button', { name: 'Submit application' })).toBeDisabled();
  });

  it('says a blank will keep what is on file', () => {
    render(
      <SchemaForm schema={withPrivate} revising initial={{ full_name: 'Majid Khan' }}
                  onSubmit={() => {}} />,
    );

    expect(screen.getAllByText(/keep what is on file/).length).toBeGreaterThan(0);
  });
});
