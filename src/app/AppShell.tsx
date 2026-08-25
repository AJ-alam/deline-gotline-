/**
 * The frame around every signed-in page.
 *
 * A sidebar of grouped sections, and a slim bar on narrow screens. The portal
 * this replaces had a top navigation and a sidebar listing overlapping
 * destinations, so half the entries appeared twice and neither told you where
 * you were.
 *
 * Two things here are for the people using it rather than for looks. Every
 * destination carries an icon, because a student who is not confident reading
 * nine similar labels can still find the printer. And students see a support
 * contact at the foot of the sidebar on every page, so being stuck never
 * requires knowing where "help" lives.
 *
 * Which destinations exist is decided by role here and enforced by the API
 * there; this list only decides what is worth showing.
 */

import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';

import api, { type CurrentUser } from '../api/client';
import Icon, { type IconName } from './icons';
import './app-shell.css';

interface Destination {
  to: string;
  label: string;
  icon: IconName;
  /** One line under the label. Only where the name alone is not enough. */
  hint?: string;
  /** Who this is for. Mirrors what the API will allow. */
  when: (user: CurrentUser) => boolean;
}

interface Group {
  heading: string;
  items: Destination[];
}

const isStudent = (user: CurrentUser) => user.role === 'student';
const reviews = (user: CurrentUser) => ['support_worker', 'admin'].includes(user.role);
const decides = (user: CurrentUser) => ['director', 'admin'].includes(user.role);
const staff = (user: CurrentUser) => !isStudent(user);
const pays = (user: CurrentUser) => ['finance', 'admin'].includes(user.role);

const GROUPS: Group[] = [
  {
    heading: 'Main',
    items: [
      { to: '/dashboard', label: 'Home', icon: 'home', when: () => true },
      { to: '/applications', label: 'My applications', icon: 'applications', when: isStudent },
      {
        to: '/review', label: 'Applications', icon: 'applications',
        when: (u) => reviews(u) || decides(u),
      },
      {
        // Students only. Staff have no eligibility screening, no enrolment and
        // no bank account here, and the API refuses all three for them — a
        // destination that 403s on arrival is worse than one that is absent.
        to: '/profile', label: 'Your profile', icon: 'profile',
        hint: 'Details we fill your applications in from', when: isStudent,
      },
      { to: '/notifications', label: 'Notifications', icon: 'bell', when: () => true },
    ],
  },
  {
    heading: 'Apply for funding',
    items: [
      {
        to: '/apply/admission', label: 'Admission application', icon: 'newApplication',
        hint: 'Start here — it sets what you qualify for', when: isStudent,
      },
      {
        to: '/apply/continuing_funding', label: 'Continuing funding', icon: 'continuing',
        hint: 'For a semester after your first', when: isStudent,
      },
      {
        to: '/apply/travel', label: 'Travel & emergency', icon: 'travel', when: isStudent,
      },
      {
        to: '/forms', label: 'Printable forms', icon: 'printer',
        hint: 'Fill in by hand instead', when: isStudent,
      },
    ],
  },
  {
    heading: 'Office',
    items: [
      { to: '/payments', label: 'Payments', icon: 'payments', when: pays },
      // The roles that already see money. A support worker assesses
      // applications and does not need the year's expenditure.
      { to: '/reports', label: 'Reports', icon: 'rates',
        when: (u) => pays(u) || decides(u) },
      { to: '/policy', label: 'Policy rates', icon: 'rates', when: staff },
      { to: '/people', label: 'People', icon: 'people', when: staff },
      { to: '/forms', label: 'Printable forms', icon: 'printer', when: staff },
    ],
  },
  {
    // Last, and for everybody. The office's screen puts it directly above Sign
    // out, which is where a person looks once they have stopped finding what
    // they came for.
    heading: 'Other',
    items: [
      {
        to: '/help', label: 'Help & FAQ', icon: 'help',
        hint: 'How to reach the office', when: () => true,
      },
    ],
  },
];

function initials(user: CurrentUser) {
  return (user.display_name || '?')
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');
}

export default function AppShell() {
  const navigate = useNavigate();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [unread, setUnread] = useState(0);
  const [failed, setFailed] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

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

  const groups = user
    ? GROUPS.map((group) => ({
        ...group,
        items: group.items.filter((item) => item.when(user)),
      })).filter((group) => group.items.length > 0)
    : [];

  return (
    <div className={`shell ${menuOpen ? 'shell--menu-open' : ''}`.trim()}>
      <a className="sr-only" href="#main">Skip to content</a>

      <aside className="shell__side" aria-label="Sections">
        <div className="shell__side-inner">
          <Link to="/dashboard" className="shell__brand" onClick={() => setMenuOpen(false)}>
            <span className="shell__brand-name">Deline Got&rsquo;ı̨nę Government</span>
            <span className="shell__brand-sub">Student Funding</span>
          </Link>

          {user && (
            <div className="shell__identity">
              <span className="shell__avatar" aria-hidden="true">{initials(user)}</span>
              <span className="shell__identity-text">
                <span className="shell__who">{user.display_name}</span>
                <span className="shell__role">{user.role.replace(/_/g, ' ')}</span>
              </span>
            </div>
          )}

          <nav className="shell__nav">
            {groups.map((group) => (
              <div key={group.heading} className="shell__group">
                <div className="shell__group-heading">{group.heading}</div>
                {group.items.map((item) => (
                  <NavLink
                    key={`${group.heading}-${item.to}`}
                    to={item.to}
                    end={item.to === '/dashboard'}
                    onClick={() => setMenuOpen(false)}
                    className={({ isActive }) =>
                      isActive ? 'shell__link shell__link--current' : 'shell__link'
                    }
                  >
                    <Icon name={item.icon} className="shell__icon" />
                    <span className="shell__link-text">
                      <span className="shell__link-label">{item.label}</span>
                      {item.hint && <span className="shell__link-hint">{item.hint}</span>}
                    </span>
                    {item.to === '/notifications' && unread > 0 && (
                      <span className="shell__count">{unread}</span>
                    )}
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>

          {/* Being stuck should never require knowing where help lives. */}
          {user && isStudent(user) && (
            <div className="shell__help">
              <Icon name="help" className="shell__icon" />
              <span>
                <strong>Stuck?</strong> Your Student Support Worker at the DGG
                Education Department can walk you through any application.
              </span>
            </div>
          )}

          <button type="button" className="shell__signout" onClick={signOut}>
            <Icon name="signOut" className="shell__icon" />
            Sign out
          </button>
        </div>
      </aside>

      <div className="shell__main">
        <header className="shell__bar">
          <button
            type="button"
            className="shell__menu"
            aria-expanded={menuOpen}
            aria-label="Sections"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            ☰
          </button>
          <span className="shell__bar-title">Student Funding</span>
          <NavLink
            to="/notifications"
            className="shell__bar-link"
            aria-label={unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'}
          >
            <Icon name="bell" className="shell__icon" />
            {unread > 0 && <span className="shell__count">{unread}</span>}
          </NavLink>
        </header>

        <div id="main">
          <Outlet />
        </div>
      </div>

      {/* Closes the drawer on small screens without trapping anything. */}
      {menuOpen && (
        <button
          type="button"
          className="shell__scrim"
          aria-label="Close sections"
          onClick={() => setMenuOpen(false)}
        />
      )}
    </div>
  );
}
