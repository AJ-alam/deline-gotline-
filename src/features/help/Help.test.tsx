/**
 * The help page.
 *
 * What it must do is narrow and unforgiving: show a way to reach the office.
 * Someone opens this because something has already gone wrong, so the failure
 * path matters as much as the happy one — a page that answers a failed request
 * with a spinner has left them with nothing.
 */

import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';

import type { Help as HelpContent } from '../../api/client';

const help = vi.fn();

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client');
  return { ...actual, default: { help }, api: { help } };
});

const { default: Help } = await import('./Help');

const CONTENT: HelpContent = {
  contact: {
    email: 'education.support@gov.deline.ca',
    phone: '(867) 589-3515',
    address: 'P.O. Box 156, Délı̨nę, NT X0E 0G0',
  },
  faq: [
    {
      question: 'How is my enrollment verified?',
      answer: 'We email your registrar a single-use link.',
    },
    {
      question: 'How do I claim travel?',
      answer: 'List each expense on its own line and attach every receipt.',
    },
  ],
};

function show(content: HelpContent | null = CONTENT) {
  if (content) help.mockResolvedValue(content);
  else help.mockRejectedValue(new Error('offline'));
  render(<Help />);
}

describe('contact details', () => {
  it('shows the address, the phone number and the email', async () => {
    show();
    expect(await screen.findByText('education.support@gov.deline.ca')).toBeInTheDocument();
    expect(screen.getByText('(867) 589-3515')).toBeInTheDocument();
    expect(screen.getByText(/P\.O\. Box 156/)).toBeInTheDocument();
  });

  it('makes the email something you can press', async () => {
    show();
    const link = await screen.findByRole('link', { name: 'education.support@gov.deline.ca' });
    expect(link).toHaveAttribute('href', 'mailto:education.support@gov.deline.ca');
  });

  it('makes the phone number dialable, punctuation stripped', async () => {
    // Read on a phone, which is where somebody stuck is most likely reading it.
    show();
    const link = await screen.findByRole('link', { name: '(867) 589-3515' });
    expect(link).toHaveAttribute('href', 'tel:8675893515');
  });

  it('takes them from the API, not from this file', async () => {
    // The reason the office can correct an address without a release.
    show({
      ...CONTENT,
      contact: { email: 'new@example.ca', phone: '(111) 222-3333', address: 'Elsewhere' },
    });
    expect(await screen.findByText('new@example.ca')).toBeInTheDocument();
    expect(screen.queryByText('education.support@gov.deline.ca')).not.toBeInTheDocument();
  });
});

describe('the questions', () => {
  it('lists every one it is given', async () => {
    show();
    expect(await screen.findByText('How is my enrollment verified?')).toBeInTheDocument();
    expect(screen.getByText('How do I claim travel?')).toBeInTheDocument();
  });

  it('opens an answer when its question is pressed', async () => {
    show();
    const question = await screen.findByText('How is my enrollment verified?');
    const item = question.closest('details')!;

    expect(item.open).toBe(false);
    fireEvent.click(question);
    expect(item.open).toBe(true);
    expect(within(item).getByText(/single-use link/)).toBeInTheDocument();
  });

  it('keeps the answers in the page even while closed', async () => {
    /**
     * A native <details> is what makes search-in-page work: somebody looking
     * for the word "receipt" finds it without opening anything first. A
     * hand-rolled accordion that unmounts its answer cannot do that.
     */
    show();
    await screen.findByText('How do I claim travel?');
    expect(screen.getByText(/attach every receipt/)).toBeInTheDocument();
  });

  it('says so plainly when there are none', async () => {
    show({ ...CONTENT, faq: [] });
    expect(await screen.findByText(/No questions have been published/)).toBeInTheDocument();
  });
});

describe('when the API is unreachable', () => {
  it('still gives them somewhere to write', async () => {
    // The failure that matters. Somebody reading this may have no other way to
    // ask, so a bare error message would be the page failing at its one job.
    show(null);
    expect(await screen.findByText(/P\.O\. Box 156/)).toBeInTheDocument();
  });

  it('does not sit on a spinner forever', async () => {
    show(null);
    await waitFor(() =>
      expect(document.querySelector('.spinner')).not.toBeInTheDocument());
  });
});
