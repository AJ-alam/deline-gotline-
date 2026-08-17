/**
 * The opening screen.
 *
 * One request, scoped to the role by the server. The screen this replaces
 * fetched seven endpoints every thirty seconds, pulled every application with
 * every answer, and counted them in the browser — so it grew slower with every
 * application the office received.
 *
 * A student and a support worker want entirely different things here, so they
 * get different components rather than one page threaded with `isStaff`.
 */

import { useEffect, useState } from 'react';

import api, { type DashboardSummary } from '../../api/client';
import { Alert } from '../../components/ui';
import StaffDashboard from './StaffDashboard';
import StudentDashboard from './StudentDashboard';
import './dashboard.css';

export default function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    api
      .dashboard()
      .then((result) => !cancelled && setSummary(result))
      .catch(() => !cancelled && setError('The summary could not be loaded.'));
    return () => { cancelled = true; };
  }, []);

  if (error) return <main className="page"><Alert tone="error">{error}</Alert></main>;
  if (!summary) {
    return (
      <main className="page">
        <div className="spinner" role="status" aria-label="Loading summary" />
      </main>
    );
  }

  return summary.scope === 'staff' ? (
    <StaffDashboard summary={summary} />
  ) : (
    <StudentDashboard summary={summary} />
  );
}
