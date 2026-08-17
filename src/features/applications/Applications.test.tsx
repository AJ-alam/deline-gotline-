/**
 * The student's own list of applications.
 *
 * Staff have a queue of everybody's at /review, which is where their navigation
 * points — but nothing stopped one arriving here, and what they got was the
 * student's page: "My applications", "Everything you have submitted", and a
 * catalogue inviting them to apply for funding. On a database with rows in it
 * that read as a plausible queue; on an empty one it told a support worker to
 * start their own admission application.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import '@testing-library/jest-dom';

const applications = vi.fn();
const schemas = vi.fn();
const me = vi.fn();

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client');
  return {
    ...actual,
    default: { applications, schemas, me },
    api: { applications, schemas, me },
  };
});

const { default: Applications } = await import('./Applications');

beforeEach(() => {
  vi.clearAllMocks();
  applications.mockResolvedValue({ results: [], count: 0 });
  schemas.mockResolvedValue([]);
});

function show(role: string) {
  me.mockResolvedValue({
    id: 1, email: `${role}@dgg.test`, full_name: 'Somebody', role,
    beneficiary_number: '',
  });
  render(
    <MemoryRouter initialEntries={['/applications']}>
      <Routes>
        <Route path="/applications" element={<Applications />} />
        <Route path="/review" element={<h1>Applications to review</h1>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('who this list is for', () => {
  it('shows a student their own applications', async () => {
    show('student');
    expect(await screen.findByRole('heading', { name: 'My applications' }))
      .toBeInTheDocument();
  });

  it.each(['support_worker', 'director', 'finance', 'admin'])(
    'sends %s to the queue instead', async (role) => {
      show(role);
      expect(await screen.findByRole('heading', { name: 'Applications to review' }))
        .toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: 'My applications' }))
        .not.toBeInTheDocument();
    });

  it('never invites a member of staff to apply for funding', async () => {
    show('support_worker');
    await screen.findByRole('heading', { name: 'Applications to review' });
    await waitFor(() => {
      expect(screen.queryByText(/Start an application/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Apply for funding/)).not.toBeInTheDocument();
    });
  });
});
