/**
 * The frame around every signed-in page.
 *
 * What matters here is not how it looks but who is shown what: this list is a
 * mirror of the API's permissions, and an entry offered to someone the API
 * will refuse is a dead end presented as a destination. These pin the mirror.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import '@testing-library/jest-dom';

import type { CurrentUser } from '../api/client';

const me = vi.fn();
const notifications = vi.fn();
const signOut = vi.fn();

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return {
    ...actual,
    default: { me, notifications, signOut },
    api: { me, notifications, signOut },
  };
});

const { default: AppShell } = await import('./AppShell');

function user(role: CurrentUser['role'], overrides: Partial<CurrentUser> = {}): CurrentUser {
  return {
    id: 1,
    email: `${role}@dgg.test`,
    first_name: 'Sara',
    last_name: 'Doe',
    display_name: 'Sara Doe',
    role,
    ...overrides,
  } as CurrentUser;
}

async function show(as: CurrentUser, unread = 0) {
  me.mockResolvedValue(as);
  notifications.mockResolvedValue({ unread, results: [] });
  render(
    <MemoryRouter>
      <AppShell />
    </MemoryRouter>,
  );
  await waitFor(() => expect(screen.getByText('Sara Doe')).toBeInTheDocument());
}

describe('AppShell', () => {
  beforeEach(() => {
    me.mockReset();
    notifications.mockReset();
  });

  it('offers a student the places a student may go', async () => {
    await show(user('student'));

    expect(screen.getByRole('link', { name: /Home/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /My applications/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Admission application/ })).toBeInTheDocument();
  });

  it('offers a student nothing the API would refuse them', async () => {
    await show(user('student'));

    for (const forbidden of [/Policy rates/, /People/, /Payments/]) {
      expect(screen.queryByRole('link', { name: forbidden })).not.toBeInTheDocument();
    }
  });

  it('does not offer staff the student application forms', async () => {
    await show(user('support_worker'));

    expect(screen.queryByRole('link', { name: /Admission application/ }))
      .not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Policy rates/ })).toBeInTheDocument();
  });

  it('shows payments only to those who run them', async () => {
    await show(user('director'));
    expect(screen.queryByRole('link', { name: /Payments/ })).not.toBeInTheDocument();
  });

  it('keeps help in reach of a student from every page', async () => {
    await show(user('student'));
    expect(screen.getByText(/Student Support Worker/)).toBeInTheDocument();
  });

  it('does not clutter a staff sidebar with the student help notice', async () => {
    await show(user('admin'));
    expect(screen.queryByText(/Student Support Worker/)).not.toBeInTheDocument();
  });

  it('counts unread notices where the notices live', async () => {
    await show(user('student'), 3);
    expect(screen.getByRole('link', { name: /Notifications, 3 unread/ }))
      .toBeInTheDocument();
  });

  it('names the signed-in person and their role', async () => {
    await show(user('support_worker'));
    expect(screen.getByText('Sara Doe')).toBeInTheDocument();
    // Underscores are storage, not something to show a person.
    expect(screen.getByText('support worker')).toBeInTheDocument();
  });
});
