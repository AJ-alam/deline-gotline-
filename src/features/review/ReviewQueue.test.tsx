/**
 * The staff queue.
 *
 * These pin the properties that replaced the old dashboard's behaviour: one
 * request rather than seven, filtering done server-side, and a stale response
 * unable to overwrite a newer one.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import '@testing-library/jest-dom';

import type { ApplicationSummary, Page } from '../../api/client';

const applications = vi.fn();

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client');
  return { ...actual, default: { applications }, api: { applications } };
});

const { default: ReviewQueue } = await import('./ReviewQueue');

function row(overrides: Partial<ApplicationSummary> = {}): ApplicationSummary {
  return {
    id: 1,
    type: 'admission',
    type_label: 'Admission Application',
    stream: 'psssp',
    status: 'submitted',
    status_label: 'Submitted',
    student_name: 'Jane Doe',
    awarded_total: '0.00',
    submitted_at: '2026-09-01T00:00:00Z',
    submitted_after_deadline: false,
    residency_flag: '',
    enrolment: { required: false, status: 'not_required', label: 'Not required' },
    ...overrides,
  };
}

function page(rows: ApplicationSummary[], count = rows.length): Page<ApplicationSummary> {
  return { count, next: null, previous: null, results: rows };
}

function renderQueue(url = '/review') {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <ReviewQueue />
    </MemoryRouter>,
  );
}

describe('ReviewQueue', () => {
  beforeEach(() => {
    applications.mockReset();
  });

  it('loads the queue with a single request', async () => {
    applications.mockResolvedValue(page([row()]));
    renderQueue();

    await screen.findByText('Jane Doe');
    // The old dashboard fired seven every thirty seconds.
    expect(applications).toHaveBeenCalledTimes(1);
  });

  it('asks the server to filter rather than filtering in the browser', async () => {
    applications.mockResolvedValue(page([row()]));
    renderQueue();
    await screen.findByText('Jane Doe');

    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'approved' } });

    await waitFor(() =>
      expect(applications).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: 'approved' }),
      ),
    );
  });

  it('returns to the first page when a filter changes', async () => {
    // More than one page of results, otherwise Next is correctly disabled.
    applications.mockResolvedValue(page([row()], 120));
    renderQueue();
    await screen.findByText('Jane Doe');

    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() =>
      expect(applications).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })),
    );

    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'declined' } });
    await waitFor(() =>
      expect(applications).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1 })),
    );
  });

  it('does not let a slow response for old filters overwrite a newer one', async () => {
    let resolveSlow: (value: Page<ApplicationSummary>) => void = () => {};
    applications
      .mockImplementationOnce(
        () => new Promise<Page<ApplicationSummary>>((resolve) => { resolveSlow = resolve; }),
      )
      .mockResolvedValue(page([row({ student_name: 'Newer Result' })]));

    renderQueue();
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'approved' } });
    await screen.findByText('Newer Result');

    // The first request finishes last. Its result belongs to filters the user
    // has already moved past.
    resolveSlow(page([row({ student_name: 'Stale Result' })]));

    await waitFor(() => expect(screen.queryByText('Stale Result')).not.toBeInTheDocument());
    expect(screen.getByText('Newer Result')).toBeInTheDocument();
  });

  it('marks a late application and a residency mismatch', async () => {
    applications.mockResolvedValue(
      page([row({ submitted_after_deadline: true, residency_flag: 'Declared outside NWT' })]),
    );
    renderQueue();

    expect(await screen.findByText('Late')).toBeInTheDocument();
    expect(screen.getByText('Residency')).toBeInTheDocument();
  });

  it('arrives filtered when the dashboard links in filtered', async () => {
    // The dashboard's queue tiles link to /review?status=submitted. While the
    // filters were component state every one of those links landed on the whole
    // list, filtered by nothing, with no sign the filter had been dropped.
    applications.mockResolvedValue(page([row()]));
    renderQueue('/review?status=submitted');

    await waitFor(() =>
      expect(applications).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: 'submitted' }),
      ),
    );
    expect(screen.getByLabelText('Status')).toHaveValue('submitted');
  });

  it('arrives filtered to a funding stream the same way', async () => {
    applications.mockResolvedValue(page([row()]));
    renderQueue('/review?stream=dggr');

    await waitFor(() =>
      expect(applications).toHaveBeenLastCalledWith(
        expect.objectContaining({ stream: 'dggr' }),
      ),
    );
    expect(screen.getByLabelText('Funding stream')).toHaveValue('dggr');
  });

  it('filters by stream on the server rather than in the browser', async () => {
    applications.mockResolvedValue(page([row()]));
    renderQueue();
    await screen.findByText('Jane Doe');

    fireEvent.change(screen.getByLabelText('Funding stream'), {
      target: { value: 'psssp' },
    });

    await waitFor(() =>
      expect(applications).toHaveBeenLastCalledWith(
        expect.objectContaining({ stream: 'psssp' }),
      ),
    );
  });

  it('ignores a filter value nobody offered rather than passing it on', async () => {
    // The server filters on a choice field, so a junk value is a 400 and the
    // queue reports itself as unloadable. Reading an unoffered value as though
    // somebody had chosen it is the fault that let a screening answer nobody
    // offered decide a funding stream.
    applications.mockResolvedValue(page([row()]));
    renderQueue('/review?stream=not-a-stream&status=invented');

    await screen.findByText('Jane Doe');
    const sent = applications.mock.calls[0][0];
    expect(sent).not.toHaveProperty('stream');
    expect(sent).not.toHaveProperty('status');
  });

  it('says so plainly when nothing matches', async () => {
    applications.mockResolvedValue(page([]));
    renderQueue();
    expect(await screen.findByText(/No applications match/)).toBeInTheDocument();
  });

  it('reports a failure instead of showing an empty queue as if it were real', async () => {
    applications.mockRejectedValue(new Error('network'));
    renderQueue();
    expect(await screen.findByText(/could not be loaded/)).toBeInTheDocument();
  });
});
