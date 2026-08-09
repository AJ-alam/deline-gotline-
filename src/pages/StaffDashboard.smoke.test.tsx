import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

/**
 * Render smoke tests for the staff dashboard.
 *
 * Every other test in this suite re-implements the component's logic and checks
 * the copy, so a crash during render ships unnoticed: the dashboard paints, the
 * first API responses land, and the tree throws on the second render pass. These
 * tests mount the real component against mocked API responses and fail on any
 * exception, including the ones React only surfaces asynchronously.
 */

// A student record with every field populated the way the backend sends it.
const STUDENT = {
  id: 7,
  full_name: 'Test Student',
  email: 'student@test.ca',
  phone: '(867) 000-0000',
  primary_stream: 'PSSSP',
  secondary_stream: 'DGGR',
  num_dependents: 0,
  enrollment_status: 'Full-Time',
  course_load: 100,
  province_of_residence: 'nwt',
};

const SUBMISSION = {
  id: 1,
  form: 1,
  form_title: 'Admission Application',
  form_type: 'Form A: Admission Application',
  student: 7,
  student_name: 'Test Student',
  student_details: STUDENT,
  submitted_at: '2026-01-15T10:00:00Z',
  status: 'pending',
  amount: '0.00',
  answers: [
    { id: 11, label: 'Tuition', answer_text: '5200' },
    { id: 12, label: 'City', answer_text: 'Deline' },
    { id: 13, label: 'Province', answer_text: 'NT' },
  ],
  notes: [],
  office_use_data: {},
  residency_flag: null,
};

const POLICY = {
  psssp_tuition: [{ id: 1, section: 'psssp_tuition', field_key: 'max_per_semester', field_label: 'Max', value: '5000', unit: '$', is_active: true }],
  psssp_living: [{ id: 2, section: 'psssp_living', field_key: 'fulltime_no_dependents', field_label: 'FT', value: '1200', unit: '$', is_active: true }],
};

const RESPONSES: Record<string, any> = {
  getApplications: [],
  getSubmissions: [SUBMISSION],
  getSubmission: SUBMISSION,
  getPolicySettings: POLICY,
  getMe: { id: 1, full_name: 'Staff User', email: 'staff@test.ca', role: 'admin' },
  getUsers: [],
  getPayments: [],
  getAppeals: [],
  getAuditLogs: [],
  getNotifications: [],
  getPolicyHistory: [],
  getReportStats: {},
  getUserDocuments: [],
  getFundingBreakdown: {
    categories: [
      { category: 'Tuition (PSSSP)', stream: 'PSSSP', amount: '5000', rule: 'PSSSP cap $5000 per semester' },
      { category: 'Tuition Top-Up (DGGR)', stream: 'DGGR', amount: '200', rule: 'Tops up unfunded tuition' },
      { category: 'Living Allowance (PSSSP)', stream: 'PSSSP', amount: '4800', rule: '$1200/month × 4 months' },
    ],
    total: '10000',
    stream: 'PSSSP + DGGR',
    enrollment: 'Full-Time',
    months: 4,
    has_dependents: false,
    tuition_confirmed: true,
    requested_tuition: '5200',
    unfunded_tuition: '0',
  },
};

// Any API method the dashboard calls resolves; unknown ones resolve to an empty
// list so a newly added call cannot fail the suite for the wrong reason.
vi.mock('../api/client', () => {
  const handler: ProxyHandler<any> = {
    get: (_target, prop: string) => {
      if (prop === 'then') return undefined; // never treat the mock as a thenable
      return vi.fn(() => Promise.resolve(RESPONSES[prop] ?? []));
    },
  };
  return { default: new Proxy({}, handler) };
});

vi.mock('jspdf', () => ({ jsPDF: class { text() {} save() {} } }));

import StaffDashboard from './StaffDashboard';

const renderDashboard = () =>
  render(
    <MemoryRouter initialEntries={['/staff/dashboard']}>
      <StaffDashboard />
    </MemoryRouter>,
  );

describe('StaffDashboard render smoke tests', () => {
  let consoleError: ReturnType<typeof vi.spyOn>;
  let errors: string[];

  beforeEach(() => {
    localStorage.setItem('dgg_token', 'test-token');
    localStorage.setItem('dgg_role', 'admin');
    errors = [];
    consoleError = vi.spyOn(console, 'error').mockImplementation((...args: any[]) => {
      errors.push(args.map(String).join(' '));
    });
  });

  afterEach(() => {
    consoleError.mockRestore();
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('mounts without throwing', () => {
    expect(() => renderDashboard()).not.toThrow();
  });

  it('still renders after the initial API responses land', async () => {
    renderDashboard();
    // The crash reported from the field appears a moment after first paint, once
    // the fetches resolve and the tree re-renders with real data.
    await waitFor(() => {
      expect(document.body.textContent).not.toBe('');
    });
    await new Promise(resolve => setTimeout(resolve, 50));
    expect(document.body.querySelector('.staff-portal-root')).toBeTruthy();
  });

  it('logs no React render errors', async () => {
    renderDashboard();
    await new Promise(resolve => setTimeout(resolve, 100));
    const renderErrors = errors.filter(e =>
      /Cannot read|is not a function|is not defined|undefined is not|Maximum update depth|Objects are not valid as a React child/i.test(e),
    );
    expect(renderErrors).toEqual([]);
  });

  it('does not fall into a render loop', async () => {
    renderDashboard();
    await new Promise(resolve => setTimeout(resolve, 200));
    expect(errors.filter(e => /Maximum update depth/i.test(e))).toEqual([]);
  });

  it('renders the sidebar navigation', async () => {
    renderDashboard();
    await waitFor(() => {
      expect(screen.getAllByText(/Applications/i).length).toBeGreaterThan(0);
    });
  });

  it('survives sparse and guest records', async () => {
    // Real rows are not as tidy as the happy-path fixture: guest submissions have
    // no student, legacy rows have no answers, and numbers arrive as strings.
    RESPONSES.getSubmissions = [
      { id: 2, status: 'pending', submitted_at: null, amount: null,
        student: null, student_details: null, answers: null, notes: null,
        form: null, form_title: null, office_use_data: null },
      { id: 3, status: 'accepted', submitted_at: '2026-02-01T00:00:00Z',
        amount: '1234.50', student_details: { full_name: null, email: null },
        answers: [{ id: 1, label: null, answer_text: null }], office_use_data: {} },
    ];
    RESPONSES.getApplications = [
      { id: 4, status: 'reviewed', student_details: {}, form_type: null, amount: '0' },
    ];

    renderDashboard();
    await new Promise(resolve => setTimeout(resolve, 150));

    const renderErrors = errors.filter(e =>
      /Cannot read|is not a function|is not iterable|undefined is not/i.test(e),
    );
    expect(renderErrors).toEqual([]);
    expect(document.body.querySelector('.staff-portal-root')).toBeTruthy();

    RESPONSES.getSubmissions = [SUBMISSION];
    RESPONSES.getApplications = [];
  });
});
