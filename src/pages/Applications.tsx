/** A student's applications. */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import api, { type ApplicationSchema, type ApplicationSummary } from '../api/client';
import { Alert, Badge, Card } from '../components/ui';
import { formatDate, formatMoney, statusTone } from '../components/ui/format';

export default function Applications() {
  const [rows, setRows] = useState<ApplicationSummary[] | null>(null);
  const [schemas, setSchemas] = useState<ApplicationSchema[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    // Two requests, not seven: the queue and the list of things one can apply for.
    Promise.all([api.applications(), api.schemas()])
      .then(([page, available]) => { setRows(page.results); setSchemas(available); })
      .catch(() => setError('Your applications could not be loaded.'));
  }, []);

  if (error) return <main className="page"><Alert tone="error">{error}</Alert></main>;

  return (
    <main className="page stack stack--loose">
      <h1>My applications</h1>

      {rows === null ? (
        <div className="spinner" />
      ) : rows.length === 0 ? (
        <Card title="Nothing yet">
          <p className="muted">You have not submitted an application.</p>
        </Card>
      ) : (
        <Card>
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>Application</th><th>Status</th><th>Submitted</th><th>Awarded</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td><Link to={`/applications/${row.id}`}>{row.type_label}</Link></td>
                    <td><Badge tone={statusTone(row.status)}>{row.status_label}</Badge></td>
                    <td>{formatDate(row.submitted_at)}</td>
                    <td className="num">{formatMoney(row.awarded_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card title="Apply for funding">
        <ul className="stack stack--tight">
          {schemas.map((schema) => (
            <li key={schema.slug}><Link to={`/apply/${schema.slug}`}>{schema.label}</Link></li>
          ))}
        </ul>
      </Card>
    </main>
  );
}
