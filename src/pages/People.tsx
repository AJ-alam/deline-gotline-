/**
 * Who has an account, and what they may do.
 *
 * Staff can find someone. Only an administrator can change what they may do,
 * because a role grants or removes the power to decide funding and release
 * money. The server refuses changes that would leave the office unable to
 * administer itself; this page shows the reason it gives rather than a generic
 * failure, because the reason tells you what to do instead.
 */

import { useEffect, useState } from 'react';

import api, {
  ApiError,
  type CurrentUser,
  type Directory,
  type DirectoryPerson,
  type UserRole,
} from '../api/client';
import { Alert, Badge, Button, Card, Field, Input, Select } from '../components/ui';
import { formatDate } from '../components/ui/format';

export default function People() {
  const [directory, setDirectory] = useState<Directory | null>(null);
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [search, setSearch] = useState('');
  const [role, setRole] = useState('');
  const [includeInactive, setIncludeInactive] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [reloads, setReloads] = useState(0);

  useEffect(() => {
    let cancelled = false;
    // Debounced, so typing a name does not fire a request per keystroke.
    const timer = setTimeout(() => {
      Promise.all([
        api.directory({ search, role, include_inactive: includeInactive }),
        api.me(),
      ])
        .then(([people, user]) => {
          if (cancelled) return;
          setDirectory(people);
          setMe(user);
          setError('');
        })
        .catch((err) => {
          if (cancelled) return;
          setError(
            err instanceof ApiError && err.status === 403
              ? 'Only staff can view the directory.'
              : 'The directory could not be loaded.',
          );
        });
    }, 250);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [search, role, includeInactive, reloads]);

  const apply = async (action: Promise<DirectoryPerson>, message: string) => {
    setError('');
    setNotice('');
    try {
      await action;
      setNotice(message);
      setReloads((n) => n + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'That change could not be made.');
    }
  };

  if (error && !directory) {
    return (
      <main className="page">
        <Alert tone="error">{error}</Alert>
      </main>
    );
  }
  if (!directory || !me) {
    return (
      <main className="page">
        <div className="spinner" role="status" aria-label="Loading directory" />
      </main>
    );
  }

  const canManage = me.role === 'admin';

  return (
    <main className="page stack stack--loose">
      <header className="stack stack--tight">
        <h1>People</h1>
        <p className="muted">
          {canManage
            ? 'Change what someone may do, or close an account.'
            : 'Find someone with an account. Only an administrator can change a role.'}
        </p>
      </header>

      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="ok">{notice}</Alert>}

      <Card>
        <div className="grid-2">
          <Field id="people-search" label="Search" hint="Name, email or beneficiary number.">
            <Input
              id="people-search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </Field>
          <Field id="people-role" label="Role">
            <Select
              id="people-role"
              value={role}
              onChange={(event) => setRole(event.target.value)}
            >
              <option value="">Any role</option>
              {directory.roles.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <label className="checkbox" style={{ marginTop: 'var(--s-3)' }}>
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(event) => setIncludeInactive(event.target.checked)}
          />
          <span>Include closed accounts</span>
        </label>
      </Card>

      <Card>
        {directory.results.length === 0 ? (
          <p className="muted">Nobody matches.</p>
        ) : (
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Joined</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {directory.results.map((person) => (
                  <tr key={person.id}>
                    <td>
                      {person.full_name}
                      {!person.is_active && (
                        <>
                          {' '}
                          <Badge tone="neutral">Closed</Badge>
                        </>
                      )}
                      {person.id === me.id && (
                        <>
                          {' '}
                          <Badge tone="info">You</Badge>
                        </>
                      )}
                      {person.beneficiary_number && (
                        <div className="small muted">{person.beneficiary_number}</div>
                      )}
                    </td>
                    <td className="small">{person.email}</td>
                    <td>
                      {canManage ? (
                        <Select
                          aria-label={`Role for ${person.full_name}`}
                          value={person.role}
                          onChange={(event) =>
                            void apply(
                              api.changeRole(person.id, event.target.value as UserRole),
                              `${person.full_name} is now ${event.target.selectedOptions[0].label}.`,
                            )
                          }
                        >
                          {directory.roles.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </Select>
                      ) : (
                        <Badge tone="neutral">{person.role_label}</Badge>
                      )}
                    </td>
                    <td className="small">{formatDate(person.date_joined)}</td>
                    <td>
                      {canManage && (
                        <Button
                          size="sm"
                          variant={person.is_active ? 'danger' : 'secondary'}
                          onClick={() =>
                            void apply(
                              api.setAccountActive(person.id, !person.is_active),
                              person.is_active
                                ? `Closed the account for ${person.full_name}.`
                                : `Reopened the account for ${person.full_name}.`,
                            )
                          }
                        >
                          {person.is_active ? 'Close account' : 'Reopen'}
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </main>
  );
}
