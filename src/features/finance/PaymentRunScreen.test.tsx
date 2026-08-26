/**
 * What the payment run puts in front of the person releasing the money.
 *
 * The table listed student, application, what it covers and how much — and not
 * one digit of where the money was going. The account lived in the dispatched
 * CSV and nowhere else, so the only way to check a transit number against a
 * student's file was to send the batch first; every award in a sent batch is
 * marked paid and drops off the run, so that check could only ever be made
 * after it was too late to act on.
 *
 * Rendered rather than asserted against the API shape. The backend tests
 * already prove the endpoint carries the account; what nothing checked is that
 * the screen shows it — which is the same gap that let dashboard tiles link to
 * a queue that ignored the link, through 809 passing tests.
 */

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../../api/client';
import PaymentRun from './PaymentRun';

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>(
    '../../api/client',
  );
  return {
    ...actual,
    default: { ...actual.default, paymentRun: vi.fn(), dispatchPaymentRun: vi.fn() },
  };
});

const RUN = {
  count: 1,
  total: '9800.00',
  blocked_total: '0.00',
  pending_total: '9800.00',
  awards: [
    {
      id: 42,
      student: 'Majid Khan',
      application_id: 42,
      category: 'Tuition; Living allowance',
      lines: 2,
      amount: '9800.00',
      account_holder: 'Majid Khan',
      account: '••••4321',
      transit_number: '12345',
      institution_number: '003',
    },
  ],
  blocked: [],
};

describe('the payment run table', () => {
  beforeEach(() => {
    vi.mocked(api.paymentRun).mockResolvedValue(RUN as never);
  });

  it('says which account each payment is going into', async () => {
    render(<PaymentRun />);
    expect(await screen.findByText('••••4321')).toBeInTheDocument();
  });

  it('and who that account belongs to', async () => {
    render(<PaymentRun />);
    await waitFor(() => expect(screen.getByText('••••4321')).toBeInTheDocument());
    // Twice: once as the student on the row, once as the account holder. They
    // are not always the same person, which is why both are shown.
    expect(screen.getAllByText('Majid Khan').length).toBeGreaterThanOrEqual(2);
  });

  it('and the numbers that identify the bank', async () => {
    render(<PaymentRun />);
    expect(await screen.findByText(/12345-003/)).toBeInTheDocument();
  });

  it('names the column so the reader knows what they are looking at', async () => {
    render(<PaymentRun />);
    expect(await screen.findByText('Paying into')).toBeInTheDocument();
  });

  it('never prints a whole account number', async () => {
    render(<PaymentRun />);
    await waitFor(() => expect(screen.getByText('••••4321')).toBeInTheDocument());
    // This screen lists everybody waiting to be paid. The file the bank acts
    // on carries the whole number; the screen carries enough to recognise it.
    expect(document.body.textContent).not.toContain('7654321');
  });

  it('still shows the amount beside the account it is going to', async () => {
    render(<PaymentRun />);
    expect(await screen.findByText('$9,800.00')).toBeInTheDocument();
  });
});
