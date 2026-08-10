import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';

import api, { type CurrentUser } from '../api/client';
import './app-shell.css';

interface Destination {
  to: string;
  label: string;
  /** Who this is for. Mirrors what the API will allow. */
  when: (user: CurrentUser) => boolean;
}

const isStudent = (user: CurrentUser) => user.role === 'student';
const reviews = (user: CurrentUser) => ['support_worker', 'admin'].includes(user.role);
const decides = (user: CurrentUser) => ['director', 'admin'].includes(user.role);
const staff = (user: CurrentUser) => !isStudent(user);

const DESTINATIONS: Destination[] = [
  { to: '/dashboard', label: 'Overview', when: () => true },
  { to: '/applications', label: 'My applications', when: isStudent },
  { to: '/review', label: 'Applications', when: (u) => reviews(u) || decides(u) },
  { to: '/payments', label: 'Payments', when: (u) => ['finance', 'admin'].includes(u.role) },
  { to: '/policy', label: 'Funding rates', when: staff },
  { to: '/people', label: 'People', when: staff },
];

export default function AppShell() {
  const navigate = useNavigate();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [unread, setUnread] = useState(0);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.me(), api.notifications().catch(() => ({ unread: 0, results: [] }))])
      .then(([me, notices]) => {
        if (cancelled) return;
        setUser(me);
        setUnread(notices.unread);
      })
      .catch(() => !cancelled && setFailed(true));
    return () => { cancelled = true; };
  }, []);

  const signOut = () => {
    api.signOut();
    navigate('/signin', { replace: true });
  };

  // A failed /me means the session is gone; sending them to sign in is more
  // use than an error on a page they cannot read anyway.
  useEffect(() => {
    if (failed) navigate('/signin', { replace: true });
  }, [failed, navigate]);

  return (
    <div className="shell">
      <a className="sr-only" href="#main">Skip to content</a>

      <header className="shell__bar">
        <div className="shell__inner">
          <Link to="/dashboard" className="shell__brand">
            <span className="shell__brand-name">Deline Got&rsquo;ı̨nę Government</span>
            <span className="shell__brand-sub">Student Funding</span>
          </Link>

          <nav className="shell__nav" aria-label="Sections">
            {user &&
              DESTINATIONS.filter((item) => item.when(user)).map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    isActive ? 'shell__link shell__link--current' : 'shell__link'
                  }
                >
                  {item.label}
                </NavLink>
              ))}
          </nav>

          <div className="shell__account">
            <NavLink to="/notifications" className="shell__link" aria-label={
              unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'
            }>
              Notices
              {unread > 0 && <span className="shell__count">{unread}</span>}
            </NavLink>
            {user && <span className="shell__who">{user.display_name}</span>}
            <button type="button" className="shell__signout" onClick={signOut}>
              Sign out
            </button>
          </div>
        </div>
      </header>

      <div id="main">
        <Outlet />
      </div>
    </div>
  );
}
