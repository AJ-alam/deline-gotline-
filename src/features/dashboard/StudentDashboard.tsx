/**
 * What a student sees on opening the portal.
 *
 * The screen this replaces showed three totals. For someone who had never
 * applied for anything — which is everyone, once — that is three zeros and no
 * way in. This leads with the next thing to do, and the server decides what
 * that is: "what comes next" depends on outstanding enrolment requests and
 * information requests, which is funding policy, not presentation.
 *
 * On the look: the header band is dark glass, matching the sidebar, and
 * everything below it sits on light solid surfaces. That is deliberate. Glass
 * behind a column of figures or a list of applications costs legibility for no
 * gain, and this is a screen people read money off. The decoration is confined
 * to the part carrying no data.
 *
 * Nothing here is invented. The deadline strip appears only when the office
 * has set deadlines, and the activity list says plainly when it is empty.
 */

import { Link } from 'react-router-dom';

import Icon, { type IconName } from '../../app/icons';
import type { DashboardSummary } from '../../api/client';
import { Alert, Badge, Card } from '../../components/ui';
import { formatMoney, statusTone } from '../../components/ui/format';

const SEMESTER_LABELS: Record<string, string> = {
  fall: 'Fall',
  winter: 'Winter',
  spring: 'Spring',
  summer: 'Summer',
};

/** The picture that goes with each thing the server may ask for next. */
const STEP_ICONS: Record<string, IconName> = {
  provide_information: 'bell',
  apply_admission: 'newApplication',
  awaiting_enrolment: 'clock',
  in_review: 'applications',
  apply_more: 'applications',
};

function shortDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function fullDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

/** How long until a deadline, in the words someone would use. */
function daysAway(value: string): string {
  const days = Math.ceil((new Date(value).getTime() - Date.now()) / 86_400_000);
  if (days <= 0) return 'today';
  if (days === 1) return 'tomorrow';
  if (days < 30) return `in ${days} days`;
  const months = Math.round(days / 30);
  return months === 1 ? 'in about a month' : `in about ${months} months`;
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="stat">
      <div className="stat__label">{label}</div>
      <div className="stat__value">{value}</div>
      {hint && <div className="stat__hint">{hint}</div>}
    </div>
  );
}

export default function StudentDashboard({ summary }: { summary: DashboardSummary }) {
  const student = summary.student;
  const step = summary.next_step;
  const recent = summary.recent ?? [];
  const deadlines = summary.deadlines ?? [];
  const next = deadlines[0];

  return (
    <main className="page stack stack--loose">
      {/* ── Header band ── */}
      <header className="hero">
        <div className="hero__body">
          <p className="hero__eyebrow">Student portal</p>
          <h1 className="hero__title">
            Welcome back{student?.name ? `, ${student.name}` : ''}
          </h1>
          {student?.reference && (
            <p className="hero__meta">
              Beneficiary number <span className="hero__chip">{student.reference}</span>
            </p>
          )}
        </div>

        {next && (
          <div className="hero__deadline">
            <span className="hero__deadline-label">Next deadline</span>
            <span className="hero__deadline-term">
              {SEMESTER_LABELS[next.semester] ?? next.semester} {next.academic_year}
            </span>
            <time dateTime={next.closes_at} className="hero__deadline-date">
              {fullDate(next.closes_at)}
            </time>
            <span className="hero__deadline-away">{daysAway(next.closes_at)}</span>
          </div>
        )}
      </header>

      {deadlines.length > 1 && (
        <div className="deadline-strip">
          <span className="deadline-strip__label">Also coming up</span>
          {deadlines.slice(1).map((deadline) => (
            <span key={`${deadline.semester}-${deadline.closes_at}`} className="deadline">
              <span className="deadline__term">
                {SEMESTER_LABELS[deadline.semester] ?? deadline.semester}
              </span>
              <time dateTime={deadline.closes_at} title={fullDate(deadline.closes_at)}>
                {shortDate(deadline.closes_at)}
              </time>
            </span>
          ))}
        </div>
      )}

      {summary.waiting_on_you ? (
        <Alert tone="error">
          {summary.waiting_on_you === 1
            ? 'One of your applications needs more information from you.'
            : `${summary.waiting_on_you} of your applications need more information from you.`}{' '}
          <Link to="/applications">Open them</Link>.
        </Alert>
      ) : null}

      {/* ── The one thing to do ── */}
      {step && (
        <section className="next-step">
          <span className="next-step__icon" aria-hidden="true">
            <Icon name={STEP_ICONS[step.key] ?? 'applications'} width="26" height="26" />
          </span>

          <div className="next-step__body">
            <span className="next-step__eyebrow">Your next step</span>
            <h2 className="next-step__title">{step.title}</h2>
            <p className="next-step__detail">{step.detail}</p>
          </div>

          {/* No action means there is nothing to do but wait, and a button
              would read as something they are failing to do. */}
          {step.action && step.href && (
            <Link to={step.href} className="next-step__action">
              {step.action}
              <Icon name="arrowRight" width="18" height="18" />
            </Link>
          )}
        </section>
      )}

      <div className="stats">
        <Stat
          label="Applications"
          value={String(summary.applications.total)}
          hint={
            summary.applications.total === 0
              ? 'None yet'
              : `${summary.applications.open} still open`
          }
        />
        <Stat
          label="Awarded"
          value={formatMoney(summary.money.awarded)}
          hint="Approved in your favour"
        />
        <Stat
          label="Paid"
          value={formatMoney(summary.money.paid)}
          hint="Already sent to you"
        />
      </div>

      <Card
        title="Recent activity"
        actions={
          recent.length > 0 ? (
            <Link to="/applications" className="small">See all</Link>
          ) : undefined
        }
      >
        {recent.length === 0 ? (
          <div className="empty">
            <Icon name="inbox" width="40" height="40" className="empty__icon" />
            <p className="empty__title">Nothing here yet</p>
            <p className="empty__detail">
              Once you submit an application it will appear here, and you can
              follow it all the way through review.
            </p>
          </div>
        ) : (
          <ul className="activity">
            {recent.map((application) => (
              <li key={application.id} className="activity__row">
                <Link to={`/applications/${application.id}`} className="activity__link">
                  <span className="activity__icon" aria-hidden="true">
                    <Icon name="applications" width="18" height="18" />
                  </span>
                  <span>
                    <span className="activity__type">{application.type_label}</span>
                    <span className="activity__when">
                      Submitted {fullDate(application.submitted_at)}
                    </span>
                  </span>
                </Link>
                <span className="activity__meta">
                  {Number(application.awarded_total) > 0 && (
                    <span className="activity__amount">
                      {formatMoney(application.awarded_total)}
                    </span>
                  )}
                  <Badge tone={statusTone(application.status)}>
                    {application.status_label}
                  </Badge>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Prefer to apply on paper?">
        <div className="paper">
          <Icon name="printer" width="28" height="28" className="paper__icon" />
          <div className="stack stack--tight">
            <p className="muted">
              Every form can be printed and filled in by hand, then dropped off
              or mailed to the DGG Education Department. Printed forms ask
              exactly the same questions as the ones here.
            </p>
            <p>
              <Link to="/forms">See the printable forms</Link>
            </p>
            <p className="small muted">
              Paper applications take longer to process than applying here.
            </p>
          </div>
        </div>
      </Card>
    </main>
  );
}
