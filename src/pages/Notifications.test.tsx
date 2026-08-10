/**
 * Notices.
 *
 * The unread count comes from the server and covers everything, not just what
 * is on screen — filtering the list must not change the number reported.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import '@testing-library/jest-dom';

import type { Notification, NotificationList } from '../api/client';

const notifications = vi.fn();
const markNotificationsRead = vi.fn();

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return {
    ...actual,
    default: { notifications, markNotificationsRead },
  };
});

const { default: Notifications } = await import('./Notifications');

function notice(overrides: Partial<Notification> = {}): Notification {
  return {
    id: 1,
    title: 'Application received',
    message: 'We received your admission application.',
    link: '/applications/1',
    is_read: false,
    created_at: '2026-09-01T00:00:00Z',
    ...overrides,
  };
}

function list(results: Notification[], unread = results.filter((n) => !n.is_read).length): NotificationList {
  return { unread, results };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <Notifications />
    </MemoryRouter>,
  );
}

describe('Notifications', () => {
  beforeEach(() => {
    notifications.mockReset();
    markNotificationsRead.mockReset();
  });

  it('shows the notices and how many are unread', async () => {
    notifications.mockResolvedValue(
      list([notice(), notice({ id: 2, title: 'Your application was approved', is_read: true })]),
    );
    renderPage();

    expect(await screen.findByText('Application received')).toBeInTheDocument();
    expect(screen.getByText('Your application was approved')).toBeInTheDocument();
    expect(screen.getByText('1 unread.')).toBeInTheDocument();
  });

  it('marks an unread notice with more than colour alone', async () => {
    notifications.mockResolvedValue(list([notice()]));
    renderPage();
    expect(await screen.findByText('New')).toBeInTheDocument();
  });

  it('asks the server for unread only rather than filtering on screen', async () => {
    notifications.mockResolvedValue(list([notice()]));
    renderPage();
    await screen.findByText('Application received');

    fireEvent.click(screen.getByRole('button', { name: 'Unread only' }));
    await waitFor(() => expect(notifications).toHaveBeenLastCalledWith(true));
  });

  it('keeps the unread count from the server when the list is filtered', async () => {
    // Three unread in total, one shown after filtering.
    notifications.mockResolvedValue(list([notice()], 3));
    renderPage();
    expect(await screen.findByText('3 unread.')).toBeInTheDocument();
  });

  it('marks everything read and reloads', async () => {
    notifications.mockResolvedValue(list([notice()]));
    markNotificationsRead.mockResolvedValue({ marked: 1, unread: 0 });
    renderPage();
    await screen.findByText('Application received');

    fireEvent.click(screen.getByRole('button', { name: 'Mark all read' }));

    await waitFor(() => expect(markNotificationsRead).toHaveBeenCalledWith());
    await waitFor(() => expect(notifications).toHaveBeenCalledTimes(2));
  });

  it('marks a single notice read by its id', async () => {
    notifications.mockResolvedValue(list([notice({ id: 7 })]));
    markNotificationsRead.mockResolvedValue({ marked: 1, unread: 0 });
    renderPage();
    await screen.findByText('Application received');

    fireEvent.click(screen.getByRole('button', { name: 'Mark read' }));
    await waitFor(() => expect(markNotificationsRead).toHaveBeenCalledWith([7]));
  });

  it('cannot mark all read when there is nothing unread', async () => {
    notifications.mockResolvedValue(list([notice({ is_read: true })], 0));
    renderPage();
    await screen.findByText('Application received');

    expect(screen.getByRole('button', { name: 'Mark all read' })).toBeDisabled();
  });

  it('says so plainly when there is nothing', async () => {
    notifications.mockResolvedValue(list([]));
    renderPage();
    expect(await screen.findByText('You have no notifications.')).toBeInTheDocument();
  });

  it('reports a failure rather than showing an empty list as if it were real', async () => {
    notifications.mockRejectedValue(new Error('network'));
    renderPage();
    expect(await screen.findByText(/could not be loaded/)).toBeInTheDocument();
  });
});
