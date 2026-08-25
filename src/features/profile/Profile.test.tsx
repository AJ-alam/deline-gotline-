/**
 * The profile screen.
 *
 * What is asserted here is mostly the arrangement rather than the rendering:
 * four sections that save independently, a screening whose verdict comes from
 * the server, and an account number that never appears on screen once it has
 * been stored.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import '@testing-library/jest-dom';

import type {
  BankAccountSummary,
  CurrentUser,
  EnrolmentProfile,
  ScreeningState,
} from '../../api/client';

const me = vi.fn();
const updateMe = vi.fn();
const screening = vi.fn();
const saveScreening = vi.fn();
const enrolmentProfile = vi.fn();
const saveEnrolmentProfile = vi.fn();
const banking = vi.fn();
const saveBanking = vi.fn();
const schema = vi.fn();

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client');
  return {
    ...actual,
    default: {
      me, updateMe, screening, saveScreening, enrolmentProfile,
      saveEnrolmentProfile, banking, saveBanking, schema,
    },
  };
});

// Imported after the mock: `vi.mock` is hoisted, so a value imported from the
// mocked module at the top of the file would run the factory before the spies
// above exist. Types are erased and can stay where they are.
const { ApiError } = await import('../../api/client');
const { default: Profile } = await import('./Profile');

const USER: CurrentUser = {
  id: 1,
  email: 'sara@student.test',
  first_name: 'Sara',
  last_name: 'Student',
  preferred_name: '',
  full_name: 'Sara Student',
  display_name: 'Sara',
  date_of_birth: '2001-04-12',
  pronouns: '',
  phone: '8675550100',
  alternate_phone: '',
  street_address: '12 Lakeview',
  city: 'Délı̨nę',
  province: 'NT',
  postal_code: 'X0E 0G0',
  role: 'student',
  role_label: 'Student',
  beneficiary_number: 'B-1',
  treaty_number: '',
  eligible_streams: ['psssp', 'dggr'],
  eligibility_assessed_at: '2026-08-01T00:00:00Z',
  bank_account: null,
};

const SCREENING: ScreeningState = {
  questions: [
    {
      key: 'indian_act_registered',
      text: 'Are you registered under the Indian Act with Délı̨nę First Nation affiliation?',
      help: '',
      choices: [{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }],
    },
    {
      key: 'receives_sfa',
      text: 'Are you currently receiving GNWT Student Financial Assistance (SFA)?',
      help: 'SFA affects C-DFN funding, but not the DGGR bursary.',
      choices: [{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }],
    },
  ],
  answers: { indian_act_registered: 'yes', receives_sfa: 'no' },
  streams: ['psssp', 'dggr'],
  assessed_at: '2026-08-01T00:00:00Z',
};

const STUDY: EnrolmentProfile = {
  institution_name: 'Aurora College',
  institution_location: '',
  institution_phone: '',
  registrar_email: 'registrar@aurora.test',
  student_number: 'A-4471',
  program: 'Nursing',
  credential_level: 'degree',
  learning_style: '',
  course_load: 'full_time',
  program_start: '2026-09-01',
  program_end: '2030-06-30',
  program_year: 1,
  program_length_years: 4,
  dependent_count: 0,
  updated_at: '2026-08-20T00:00:00Z',
};

const ACCOUNT: BankAccountSummary = {
  id: 3,
  account_holder: 'Sara Student',
  transit_number: '12345',
  institution_number: '001',
  account_number: '****3210',
  is_current: true,
  added_at: '2026-08-01T00:00:00Z',
};

const ADMISSION_SCHEMA = {
  slug: 'admission',
  fields: [
    {
      key: 'course_load',
      label: 'Enrollment status',
      type: 'choice',
      choices: [
        { value: 'full_time', label: 'Full-time' },
        { value: 'part_time', label: 'Part-time' },
      ],
    },
    {
      key: 'credential_level',
      label: 'Working towards',
      type: 'choice',
      choices: [{ value: 'degree', label: 'Degree' }],
    },
  ],
};

function renderPage() {
  return render(
    <MemoryRouter>
      <Profile />
    </MemoryRouter>,
  );
}

async function loaded() {
  renderPage();
  await screen.findByLabelText('First name');
}

describe('Profile', () => {
  beforeEach(() => {
    for (const mock of [me, updateMe, screening, saveScreening, enrolmentProfile,
      saveEnrolmentProfile, banking, saveBanking, schema]) {
      mock.mockReset();
    }
    me.mockResolvedValue(USER);
    updateMe.mockImplementation(async (patch: Partial<CurrentUser>) => ({ ...USER, ...patch }));
    screening.mockResolvedValue(SCREENING);
    enrolmentProfile.mockResolvedValue(STUDY);
    saveEnrolmentProfile.mockImplementation(async (patch: Partial<EnrolmentProfile>) => ({
      ...STUDY, ...patch,
    }));
    banking.mockResolvedValue(null);
    saveBanking.mockResolvedValue(ACCOUNT);
    schema.mockResolvedValue(ADMISSION_SCHEMA);
  });

  it('opens on what the portal already knows', async () => {
    await loaded();

    expect(screen.getByLabelText('First name')).toHaveValue('Sara');
    expect(screen.getByLabelText('Institution')).toHaveValue('Aurora College');
    expect(screen.getByLabelText(/Registrar/)).toHaveValue('registrar@aurora.test');
    expect(screen.getByText('C-DFN PSSSP')).toBeInTheDocument();
    expect(screen.getByText('DGGR Bursaries')).toBeInTheDocument();
  });

  it('posts an empty box as empty, for a student with nothing on file', async () => {
    // The section posts every box, and most are empty on a first visit —
    // registration collects no date of birth. The server reads '' as "nothing
    // on file"; sending `null` or omitting the key would be a different
    // contract, so this pins the one the server was given.
    me.mockResolvedValue({ ...USER, date_of_birth: null, city: '', pronouns: '' });
    enrolmentProfile.mockResolvedValue({
      ...STUDY, program_start: null, program_end: null,
      program_year: null, dependent_count: null,
    });
    await loaded();

    fireEvent.click(screen.getByRole('button', { name: 'Save details' }));
    await waitFor(() =>
      expect(updateMe).toHaveBeenCalledWith(expect.objectContaining({
        date_of_birth: '', city: '',
      })));

    fireEvent.click(screen.getByRole('button', { name: 'Save enrolment' }));
    await waitFor(() =>
      expect(saveEnrolmentProfile).toHaveBeenCalledWith(expect.objectContaining({
        program_start: '', dependent_count: '',
      })));
  });

  it('saves a corrected detail', async () => {
    await loaded();

    fireEvent.change(screen.getByLabelText('First name'), { target: { value: 'Sarah' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save details' }));

    await waitFor(() =>
      expect(updateMe).toHaveBeenCalledWith(expect.objectContaining({ first_name: 'Sarah' })));
    expect(await screen.findByText('Your details were saved.')).toBeInTheDocument();
  });

  it('sends all six screening answers, not the one that changed', async () => {
    // The outcome is decided by the answers together. A patch would re-screen
    // against a mixture of what is true now and what was true at sign-up.
    saveScreening.mockResolvedValue({
      ...SCREENING,
      answers: { indian_act_registered: 'yes', receives_sfa: 'yes' },
      streams: ['dggr'],
      outcome: { eligible: true, streams: ['dggr'], title: 'You can apply', message: 'DGGR.' },
      user: { ...USER, eligible_streams: ['dggr'] },
    });
    await loaded();

    fireEvent.change(screen.getByLabelText(/Student Financial Assistance/),
                     { target: { value: 'yes' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save answers' }));

    await waitFor(() => expect(saveScreening).toHaveBeenCalledWith({
      indian_act_registered: 'yes', receives_sfa: 'yes',
    }));
  });

  it('shows the screening its own verdict, including a bad one', async () => {
    saveScreening.mockResolvedValue({
      ...SCREENING,
      answers: { indian_act_registered: 'yes', receives_sfa: 'yes' },
      streams: [],
      outcome: {
        eligible: false,
        streams: [],
        title: 'Student Financial Assistance is active',
        message: 'Because you are currently receiving GNWT Student Financial Assistance…',
      },
      user: { ...USER, eligible_streams: [] },
    });
    await loaded();

    fireEvent.click(screen.getByRole('button', { name: 'Save answers' }));

    expect(await screen.findByText('Student Financial Assistance is active')).toBeInTheDocument();
    // And the streams on the page follow the server's answer rather than
    // staying at what they were before the save.
    expect(await screen.findByText('No funding stream')).toBeInTheDocument();
  });

  it('offers the schema’s own choices for a course load', async () => {
    await loaded();

    const select = screen.getByLabelText('Course load') as HTMLSelectElement;
    expect(select).toHaveValue('full_time');
    expect([...select.options].map((option) => option.value))
      .toEqual(['', 'full_time', 'part_time']);
  });

  it('still works when the schema cannot be fetched', async () => {
    // Only the choice values come from it. A failure there must not take the
    // page down with it.
    schema.mockRejectedValue(new Error('offline'));
    await loaded();

    expect(screen.getByLabelText('Institution')).toHaveValue('Aurora College');
  });

  it('puts a rejected field’s message under that field', async () => {
    saveEnrolmentProfile.mockRejectedValue(
      new ApiError(400, 'Bad request', {
        registrar_email: 'Enter a valid email address.',
      }));
    await loaded();

    fireEvent.click(screen.getByRole('button', { name: 'Save enrolment' }));

    expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument();
  });

  it('shows the masked account and never the digits', async () => {
    banking.mockResolvedValue(ACCOUNT);
    await loaded();

    expect(screen.getByText(/\*\*\*\*3210/)).toBeInTheDocument();
    expect(screen.getByLabelText('Account number')).toHaveValue('');
  });

  it('saves a payment account and clears the boxes afterwards', async () => {
    await loaded();

    for (const [label, value] of [
      ['Account holder', 'Sara Student'],
      ['Transit number', '12345'],
      ['Institution number', '001'],
      ['Account number', '9876543210'],
    ] as const) {
      fireEvent.change(screen.getByLabelText(label), { target: { value } });
    }
    fireEvent.click(screen.getByRole('button', { name: 'Save account' }));

    await waitFor(() => expect(saveBanking).toHaveBeenCalledWith({
      account_holder: 'Sara Student',
      transit_number: '12345',
      institution_number: '001',
      account_number: '9876543210',
    }));
    // The digits are never read back from the server, so leaving them in the
    // boxes would be the one place in the portal they can be read off a screen.
    await waitFor(() => expect(screen.getByLabelText('Account number')).toHaveValue(''));
  });

  it('keeps a refused account under its own box', async () => {
    saveBanking.mockRejectedValue(
      new ApiError(400, 'Bad request', {
        transit_number: 'The transit number is five digits.',
      }));
    await loaded();

    fireEvent.click(screen.getByRole('button', { name: 'Save account' }));

    expect(await screen.findByText('The transit number is five digits.')).toBeInTheDocument();
  });

  it('does not let one section’s failure discard another section’s work', async () => {
    // The reason there are four saves rather than one.
    saveBanking.mockRejectedValue(new ApiError(400, 'Bad request', {}));
    await loaded();

    fireEvent.change(screen.getByLabelText('First name'), { target: { value: 'Sarah' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save account' }));

    await screen.findByText('Bad request');
    expect(screen.getByLabelText('First name')).toHaveValue('Sarah');
    expect(updateMe).not.toHaveBeenCalled();
  });

  it('says so when the profile cannot be loaded at all', async () => {
    me.mockRejectedValue(new Error('offline'));
    renderPage();

    expect(await screen.findByText('Your profile could not be loaded.')).toBeInTheDocument();
  });
});
