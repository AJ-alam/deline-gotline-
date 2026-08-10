/**
 * A person's notices.
 *
 * The portal already emails what happens to an application; this is the same
 * record for someone who is already signed in and would rather not go to their
 * inbox.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import api, { type Notification } from '../api/client';
import { Alert, Badge, Button, Card } from '../components/ui';
import { formatDate } from '../components/ui/format';

export default function Notifications() {
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

  const markOne = async (id: number) => {
    try {
      await api.markNotificationsRead([id]);
      refresh();
    } catch {
      setError('That notice could not be marked read.');
    }
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

  return (
    <main className="page stack stack--loose">
      <header className="row row--between">
        <div className="stack stack--tight">
          <h1>Notifications</h1>
          <p className="muted">
            {unread === 0 ? 'Nothing unread.' : `${unread} unread.`}
          </p>
        </div>
        <div className="row">
          <Button size="sm" onClick={() => setUnreadOnly((v) => !v)}>
            {unreadOnly ? 'Show all' : 'Unread only'}
          </Button>
          <Button size="sm" variant="primary" busy={busy} disabled={unread === 0}
                  onClick={() => void markAll()}>
            Mark all read
          </Button>
        </div>
      </header>

      {error && <Alert tone="error">{error}</Alert>}

      {rows.length === 0 ? (
        <Card>
          <p className="muted">
            {unreadOnly ? 'Nothing unread.' : 'You have no notifications.'}
          </p>
        </Card>
      ) : (
        <Card>
          <ul className="notices">
            {rows.map((row) => (
              <li key={row.id} className={row.is_read ? 'notice' : 'notice notice--unread'}>
                <div className="stack stack--tight">
                  <div className="row">
                    {!row.is_read && <Badge tone="info">New</Badge>}
                    <strong>{row.title}</strong>
                  </div>
                  <p className="small">{row.message}</p>
                  <div className="row small muted">
                    <span>{formatDate(row.created_at)}</span>
                    {row.link && <Link to={row.link}>Open</Link>}
                    {!row.is_read && (
                      <Button size="sm" variant="ghost" onClick={() => void markOne(row.id)}>
                        Mark read
                      </Button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </main>
  );
}
