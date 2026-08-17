/**
 * How to reach the office, and the questions it is asked most.
 *
 * Both come from the API rather than from this file. An address written into a
 * component is an address the office cannot correct without a release, and the
 * one thing a help page must never be is out of date.
 *
 * The answers are disclosures rather than a hand-rolled accordion: a native
 * <details> is open to search-in-page, works before the JavaScript settles, and
 * is reachable from a keyboard without anyone writing the key handling.
 */

import { useEffect, useState } from 'react';

import api, { type Help as HelpContent } from '../../api/client';
import { Alert, Card } from '../../components/ui';

export default function Help() {
  const [content, setContent] = useState<HelpContent | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.help()
      .then((help) => !cancelled && setContent(help))
      .catch(() => !cancelled && setFailed(true));
    return () => { cancelled = true; };
  }, []);

  if (failed) {
    return (
      <main className="page stack stack--loose">
        <h1>Help &amp; FAQ</h1>
        {/* The address is the thing being asked for, so a failure that hides it
            is the worst possible one. It is repeated here rather than left to a
            retry, because somebody reading this may have no other way to ask. */}
        <Alert tone="error">
          The help page could not be loaded. You can still reach the Education
          Department by post at P.O. Box 156, Délı̨nę, NT X0E 0G0.
        </Alert>
      </main>
    );
  }

  if (!content) {
    return <main className="page"><div className="spinner" /></main>;
  }

  const { contact, faq } = content;

  return (
    <main className="page stack stack--loose">
      <h1>Help &amp; FAQ</h1>

      <Card title="Contact support">
        <div className="stack">
          <dl className="contact">
            <div className="contact__row">
              <dt>Email support</dt>
              <dd><a href={`mailto:${contact.email}`}>{contact.email}</a></dd>
            </div>
            <div className="contact__row">
              <dt>Phone</dt>
              {/* Tel link on the number as given: somebody reading this on a
                  phone should be able to press it. */}
              <dd><a href={`tel:${contact.phone.replace(/[^\d+]/g, '')}`}>{contact.phone}</a></dd>
            </div>
            <div className="contact__row contact__row--wide">
              <dt>Mailing address</dt>
              <dd>{contact.address}</dd>
            </div>
          </dl>
        </div>
      </Card>

      <Card title="Frequently asked questions">
        <div className="stack">
          {faq.length === 0 ? (
            <p className="muted">No questions have been published yet.</p>
          ) : (
            <div className="faq">
              {faq.map((entry) => (
                <details key={entry.question} className="faq__item">
                  <summary className="faq__question">{entry.question}</summary>
                  <p className="faq__answer">{entry.answer}</p>
                </details>
              ))}
            </div>
          )}
        </div>
      </Card>
    </main>
  );
}
