/**
 * Stepping through a long form, and attaching documents.
 *
 * The admission application is forty-five questions. On one page that is where
 * people give up; split into four it is four short pages. The split is
 * presentation only — the schema still decides what is asked and the server
 * still decides what is valid — so what these pin is that nothing can be
 * skipped, nothing gets hidden, and a document actually uploads.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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
    section: 'One',
    choices: [],
    columns: [],
    computed: false,
    private: false,
    max_items: 0,
    defaults_to_today: false,
    ...overrides,
  };
}

const SCHEMA: ApplicationSchema = {
  slug: 'admission',
  label: 'Admission Application',
  summary: 'Start here.',
  apply_in_portal: true,
  sections: ['One', 'Two', 'Docs'],
  fields: [
    field({ key: 'first_name', label: 'First name', required: true, section: 'One' }),
    field({ key: 'program', label: 'Program', required: true, section: 'Two' }),
    field({ key: 'doc_transcript', label: 'Transcript', type: 'file', section: 'Docs' }),
  ],
};

const STEPS = [
  { title: 'Student information', sections: ['One'] },
  { title: 'Program', sections: ['Two'] },
  { title: 'Documents', sections: ['Docs'] },
];

function show(props: Partial<React.ComponentProps<typeof SchemaForm>> = {}) {
  return render(
    <SchemaForm schema={SCHEMA} steps={STEPS} onSubmit={vi.fn()} {...props} />,
  );
}

describe('SchemaForm steps', () => {
  beforeEach(() => uploadDocument.mockReset());

  it('shows only the current step', () => {
    show();
    expect(screen.getByLabelText(/First name/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Program/)).not.toBeInTheDocument();
  });

  it('will not advance while a required answer on this step is blank', () => {
    show();
    expect(screen.getByRole('button', { name: /Next step/ })).toBeDisabled();
  });

  it('advances once the step is complete', () => {
    show();
    fireEvent.change(screen.getByLabelText(/First name/), { target: { value: 'Majid' } });

    fireEvent.click(screen.getByRole('button', { name: /Next step/ }));

    expect(screen.getByLabelText(/Program/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/First name/)).not.toBeInTheDocument();
  });

  it('keeps answers when stepping back and forth', () => {
    show();
    fireEvent.change(screen.getByLabelText(/First name/), { target: { value: 'Majid' } });
    fireEvent.click(screen.getByRole('button', { name: /Next step/ }));
    fireEvent.click(screen.getByRole('button', { name: /Back/ }));

    expect(screen.getByLabelText(/First name/)).toHaveValue('Majid');
  });

  it('offers submit only on the last step', () => {
    show();
    expect(screen.queryByRole('button', { name: /Submit/ })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/First name/), { target: { value: 'Majid' } });
    fireEvent.click(screen.getByRole('button', { name: /Next step/ }));
    fireEvent.change(screen.getByLabelText(/Program/), { target: { value: 'Nursing' } });
    fireEvent.click(screen.getByRole('button', { name: /Next step/ }));

    expect(screen.getByRole('button', { name: /Submit/ })).toBeInTheDocument();
  });

  it('does not let a step be skipped by clicking ahead in the progress bar', () => {
    show();
    expect(screen.getByRole('button', { name: /Documents/ })).toBeDisabled();
  });

  it('jumps to the step holding a rejected answer', () => {
    // Otherwise the person is told something is wrong and shown nothing: the
    // offending field is two steps away.
    const { rerender } = show();
    rerender(
      <SchemaForm schema={SCHEMA} steps={STEPS} onSubmit={vi.fn()}
                  errors={{ program: 'Enter your programme.' }} />,
    );

    expect(screen.getByText('Enter your programme.')).toBeInTheDocument();
    expect(screen.getByLabelText(/Program/)).toBeInTheDocument();
  });

  it('renders the footer only on the last step', () => {
    show({ footer: <p>Form B preview</p> });
    expect(screen.queryByText('Form B preview')).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/First name/), { target: { value: 'M' } });
    fireEvent.click(screen.getByRole('button', { name: /Next step/ }));
    fireEvent.change(screen.getByLabelText(/Program/), { target: { value: 'N' } });
    fireEvent.click(screen.getByRole('button', { name: /Next step/ }));

    expect(screen.getByText('Form B preview')).toBeInTheDocument();
  });

  it('renders as one page when no steps are given', () => {
    render(<SchemaForm schema={SCHEMA} onSubmit={vi.fn()} />);
    expect(screen.getByLabelText(/First name/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Program/)).toBeInTheDocument();
  });
});

describe('document upload', () => {
  beforeEach(() => uploadDocument.mockReset());

  function toDocuments() {
    show();
    fireEvent.change(screen.getByLabelText(/First name/), { target: { value: 'M' } });
    fireEvent.click(screen.getByRole('button', { name: /Next step/ }));
    fireEvent.change(screen.getByLabelText(/Program/), { target: { value: 'N' } });
    fireEvent.click(screen.getByRole('button', { name: /Next step/ }));
  }

  it('offers a file chooser rather than a text box', () => {
    toDocuments();
    expect(screen.getByLabelText(/Transcript/)).toHaveAttribute('type', 'file');
  });

  it('uploads as soon as a file is chosen', async () => {
    uploadDocument.mockResolvedValue({
      id: 3, field_key: 'doc_transcript', original_name: 'transcript.pdf',
      uploaded_at: '2026-09-01T00:00:00Z', reference: 'document:3',
    });
    toDocuments();

    const file = new File(['%PDF'], 'transcript.pdf', { type: 'application/pdf' });
    fireEvent.change(screen.getByLabelText(/Transcript/), { target: { files: [file] } });

    await waitFor(() =>
      expect(uploadDocument).toHaveBeenCalledWith(file, 'doc_transcript'),
    );
    expect(await screen.findByText(/transcript\.pdf/)).toBeInTheDocument();
  });

  // Not covered here: the failure path. The component catches the rejection
  // and renders the message — verified by hand and visible in the DOM — but
  // vitest reports the rejection as an unhandled error regardless of the
  // catch, and I would rather leave the gap stated than write a test that
  // passes by asserting nothing. The messages themselves are covered by
  // funding.test_documents on the server side.
});
