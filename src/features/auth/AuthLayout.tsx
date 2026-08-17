/**
 * The frame both signed-out screens sit in.
 *
 * Sign in and registration used to be a bare centred card each, which meant a
 * student's first sight of the service said nothing about what it was for.
 * The left panel carries that; the right carries whatever form was passed in.
 */

import type { ReactNode } from 'react';

import './auth.css';

const PROMISES = [
  'Nothing to download',
  'Eligibility checked before you apply',
  'Every application tracked as it moves',
  'Awards show the rules behind the amount',
];

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="auth-shell">
      <div className="auth-layout">
        <aside className="auth-brand">
          <div>
            <div className="auth-brand__mark">Deline Got&rsquo;ı̨nę Government</div>
            <div className="auth-brand__sub">Student Financial Support Program</div>
          </div>

          <h1 className="auth-brand__headline">
            Empowering your <em>Academic Journey</em>
          </h1>

          <p className="auth-brand__blurb">
            Apply for student funding, track your application status, and manage
            your education future in one secure place.
          </p>

          <ul className="auth-brand__list">
            {PROMISES.map((promise) => (
              <li key={promise}>{promise}</li>
            ))}
          </ul>

          <div className="auth-brand__support">
            <h2>Support</h2>
            <p>
              Contact your Student Support Worker at the DGG Education
              Department if you have questions.
            </p>
            <p className="auth-brand__hours">Monday to Friday, 9am&ndash;5pm</p>
          </div>
        </aside>

        <section className="auth-panel">{children}</section>
      </div>
    </main>
  );
}
