/**
 * The student's opening screen.
 *
 * The screen this replaces showed three totals, which for someone who had
 * never applied is three zeros and no way in. These pin the properties that
 * fixed that: the next step comes from the server and is shown, an empty file
 * says so rather than rendering an empty box, and nothing is invented — no
 * deadlines set means no deadline strip.
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import '@testing-library/jest-dom';

import type { DashboardSummary } from '../../api/client';
import StudentDashboard from './StudentDashboard';

function summary(overrides: Partial<DashboardSummary> = {}): DashboardSummary {
  return {
    scope: 'student',
    applications: { total: 0, open: 0, by_status: {} as never },
    money: { awarded: '0.00', paid: '0.00' },
    waiting_on_you: 0,
    student: { name: 'Sara', reference: 'B-1001' },
    next_step: {
      key: 'apply_admission',
      title: 'Start your admission application',
      detail: 'This is the first application.',
      action: 'Start application',
      href: '/apply/admission',
    },
    recent: [],
    deadlines: [],
    ...overrides,
  };
}

function show(data: DashboardSummary) {
  return render(
    <MemoryRouter>
      <StudentDashboard summary={data} />
    </MemoryRouter>,
  );
}

describe('StudentDashboard', () => {
  it('greets the student and shows their reference', () => {
    show(summary());
    expect(screen.getByRole('heading', { name: /Welcome back, Sara/ })).toBeInTheDocument();
    expect(screen.getByText('B-1001')).toBeInTheDocument();
  });

  it('leads with the next step the server decided', () => {
    show(summary());
    expect(screen.getByText('Start your admission application')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Start application/ }))
      .toHaveAttribute('href', '/apply/admission');
  });

  it('offers no action when there is nothing for the student to do but wait', () => {
    show(summary({
      next_step: {
        key: 'awaiting_enrolment',
        title: 'Waiting on your institution',
        detail: 'We have asked your registrar to confirm.',
        action: '',
        href: '',
      },
    }));

    expect(screen.getByText('Waiting on your institution')).toBeInTheDocument();
    // A button here would read as something they are failing to do.
    expect(screen.queryByRole('link', { name: /Start|Open|Track/ })).not.toBeInTheDocument();
  });

  it('says what will appear in the activity list rather than showing an empty box', () => {
    show(summary());
    expect(screen.getByText(/Nothing here yet/)).toBeInTheDocument();
    // An empty box tells a first-time user nothing except that something may
    // be broken; this says what will appear and when.
    expect(screen.getByText(/Once you submit an application/)).toBeInTheDocument();
  });

  it('lists recent applications with their status', () => {
    show(summary({
      applications: { total: 1, open: 1, by_status: {} as never },
      recent: [{
        id: 7,
        type: 'admission',
        type_label: 'Admission Application',
        status: 'under_review',
        status_label: 'Under Review',
        awarded_total: '0.00',
        submitted_at: '2026-09-01T00:00:00Z',
      }],
    }));

    expect(screen.getByText('Admission Application')).toBeInTheDocument();
    expect(screen.getByText('Under Review')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Admission Application/ }))
      .toHaveAttribute('href', '/applications/7');
  });

  it('shows no dates at all when the office has set none', () => {
    show(summary({ deadlines: [] }));
    expect(screen.queryByText('Next deadline')).not.toBeInTheDocument();
    expect(screen.queryByText('Also coming up')).not.toBeInTheDocument();
  });

  it('gives the soonest deadline its own place, since missing it costs a semester', () => {
    show(summary({
      deadlines: [
        { semester: 'fall', academic_year: '2026-2027', closes_at: '2099-08-01T23:59:00Z', late_allowed: true },
      ],
    }));

    expect(screen.getByText('Next deadline')).toBeInTheDocument();
    expect(screen.getByText('Fall 2026-2027')).toBeInTheDocument();
  });

  it('puts the deadlines after the soonest one in a strip below', () => {
    show(summary({
      deadlines: [
        { semester: 'fall', academic_year: '2026-2027', closes_at: '2099-08-01T23:59:00Z', late_allowed: true },
        { semester: 'winter', academic_year: '2026-2027', closes_at: '2099-12-01T23:59:00Z', late_allowed: true },
      ],
    }));

    expect(screen.getByText('Also coming up')).toBeInTheDocument();
    expect(screen.getByText('Winter')).toBeInTheDocument();
  });

  it('shows no strip when there is only one deadline to report', () => {
    show(summary({
      deadlines: [
        { semester: 'fall', academic_year: '2026-2027', closes_at: '2099-08-01T23:59:00Z', late_allowed: true },
      ],
    }));

    expect(screen.queryByText('Also coming up')).not.toBeInTheDocument();
  });

  it('names how many applications are waiting on the student', () => {
    show(summary({ waiting_on_you: 2 }));
    expect(screen.getByText(/2 of your applications need more information/))
      .toBeInTheDocument();
  });
});
