/**
 * A person's notices.
 *
 * The portal already emails what happens to an application; this is the same
 * record for someone who is already signed in and would rather not go to their
 * inbox.
 *
 * Two things here are for people who are not practised at this. A notice that
 * needs something from them is marked as such and sorted to the top, because
 * "more information needed" sitting fourth in a list of receipts is how a
 * semester's funding gets missed. And opening a notice marks it read on the way
 * through, so nobody has to understand that "read" is a separate act.
 */

import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import api, { type Notification, type NotificationKind } from '../../api/client';
import Icon, { type IconName } from '../../app/icons';
import { Alert, Button, Card } from '../../components/ui';
import './notifications.css';

/** The picture and tone that go with each kind the server records. */
const KINDS: Record<NotificationKind, { icon: IconName; tone: string; label: string }> = {
  received: { icon: 'applications', tone: 'info', label: 'Received' },
  action_needed: { icon: 'bell', tone: 'warn', label: 'Needs your reply' },
  approved: { icon: 'payments', tone: 'ok', label: 'Approved' },
  declined: { icon: 'help', tone: 'danger', label: 'Decided' },
  general: { icon: 'bell', tone: 'neutral', label: '' },
};

/** How long ago, in the words someone would use. */
function ago(value: string): string {
  const seconds = Math.floor((Date.now() - new Date(value).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return 'yesterday';
  if (days < 30) return `${days} days ago`;
  return new Date(value).toLocaleDateString(undefined, {
    year: 'numeric', month: 'long', day: 'numeric',
  });
}

/** Anything asking something of the person comes first, unread before read. */
function ordered(rows: Notification[]): Notification[] {
  const weight = (row: Notification) =>
    (row.kind === 'action_needed' && !row.is_read ? 0 : 2) + (row.is_read ? 1 : 0);
  return [...rows].sort(
    (a, b) =>
      weight(a) - weight(b) ||
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );
}

export default function Notifications() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<Notification[] | null>(null);
  const [unread, setUnread] = useState(0);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [reloads, setReloads] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .notifications(unreadOnly)
      .then((result) => {
        if (cancelled) return;
        setRows(result.results);
        setUnread(result.unread);
        setError('');
      })
      .catch(() => {
        if (!cancelled) setError('Your notifications could not be loaded.');
      });
    return () => { cancelled = true; };
  }, [unreadOnly, reloads]);

  const refresh = useCallback(() => setReloads((n) => n + 1), []);

  const markAll = async () => {
    setBusy(true);
    try {
      await api.markNotificationsRead();
      refresh();
    } catch {
      setError('They could not be marked read.');
    } finally {
      setBusy(false);
    }
  };

  /**
   * Marks one read without refetching the list.
   *
   * A refetch would reorder and, under "unread only", remove the row the
   * person just touched — the screen jumping out from under a click reads as a
   * fault. The count is corrected here rather than re-read for the same reason.
   */
  const markOne = async (id: number) => {
    setRows((current) =>
      (current ?? []).map((row) => (row.id === id ? { ...row, is_read: true } : row)),
    );
    setUnread((count) => Math.max(0, count - 1));
    try {
      await api.markNotificationsRead([id]);
    } catch {
      setError('That notice could not be marked read.');
      refresh();
    }
  };

  const open = (row: Notification) => {
    if (!row.is_read) void markOne(row.id);
    if (row.link) navigate(row.link);
  };

  if (error && !rows) {
    return <main className="page"><Alert tone="error">{error}</Alert></main>;
  }
  if (!rows) {
    return (
      <main className="page">
        <div className="spinner" role="status" aria-label="Loading notifications" />
      </main>
    );
  }

  const visible = ordered(rows);

  return (
    <main className="page stack stack--loose">
      <header className="page-head">
        <div>
          <h1>Notifications</h1>
          <p className="muted">
            {unread === 0
              ? 'You are up to date.'
              : `${unread} unread notice${unread === 1 ? '' : 's'}.`}
          </p>
        </div>
        <Button variant="primary" busy={busy} disabled={unread === 0}
                onClick={() => void markAll()}>
          Mark all read
        </Button>
      </header>

      {error && <Alert tone="error">{error}</Alert>}

      <div className="filters" role="group" aria-label="Filter notices">
        <button type="button" className={`chip ${!unreadOnly ? 'chip--on' : ''}`.trim()}
                aria-pressed={!unreadOnly} onClick={() => setUnreadOnly(false)}>
          All
        </button>
        <button type="button" className={`chip ${unreadOnly ? 'chip--on' : ''}`.trim()}
                aria-pressed={unreadOnly} onClick={() => setUnreadOnly(true)}>
          Unread{unread > 0 ? ` (${unread})` : ''}
        </button>
      </div>

      {visible.length === 0 ? (
        <Card>
          <div className="empty">
            <Icon name="bell" width="40" height="40" className="empty__icon" />
            <p className="empty__title">
              {unreadOnly ? 'Nothing unread' : 'No notices yet'}
            </p>
            <p className="empty__detail">
              {unreadOnly
                ? 'You have read everything. Choose All to see them again.'
                : 'When something happens to an application — a review, a request, a decision — it will appear here as well as by email.'}
            </p>
          </div>
        </Card>
      ) : (
        <ul className="notice-list">
          {visible.map((row) => {
            const kind = KINDS[row.kind] ?? KINDS.general;
            const actionable = Boolean(row.link);
            return (
              <li key={row.id}>
                {/* The whole notice is one target when it leads somewhere; a
                    row of small links is hard to hit and hard to explain. */}
                <div
                  className={[
                    'notice-card',
                    `notice-card--${kind.tone}`,
                    row.is_read ? 'notice-card--read' : 'notice-card--unread',
                    actionable ? 'notice-card--actionable' : '',
                  ].filter(Boolean).join(' ')}
                  role={actionable ? 'button' : undefined}
                  tabIndex={actionable ? 0 : undefined}
                  onClick={actionable ? () => open(row) : undefined}
                  onKeyDown={
                    actionable
                      ? (event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault();
                            open(row);
                          }
                        }
                      : undefined
                  }
                >
                  <span className="notice-card__icon" aria-hidden="true">
                    <Icon name={kind.icon} width="20" height="20" />
                  </span>

                  <div className="notice-card__body">
                    <div className="notice-card__head">
                      <span className="notice-card__title">{row.title}</span>
                      {!row.is_read && (
                        <span className="notice-card__dot" aria-label="Unread" />
                      )}
                    </div>
                    <p className="notice-card__message">{row.message}</p>
                    <div className="notice-card__foot">
                      <time dateTime={row.created_at}>{ago(row.created_at)}</time>
                      {kind.label && (
                        <span className={`notice-card__kind notice-card__kind--${kind.tone}`}>
                          {kind.label}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Only offered where opening it cannot do the job. */}
                  {!row.is_read && !actionable && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={(event) => {
                        event.stopPropagation();
                        void markOne(row.id);
                      }}
                    >
                      Mark read
                    </Button>
                  )}
                  {actionable && (
                    <Icon name="arrowRight" width="18" height="18"
                          className="notice-card__go" />
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
