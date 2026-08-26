/**
 * The approval letter, as the office sends it.
 *
 * Every word and every figure comes from the server. This lays them out and
 * decides nothing: the same letter goes out by email, and a component that
 * composed its own version would be a second document able to disagree with
 * the first about what somebody was awarded.
 *
 * Printing is the browser's job, as it is for the blank forms — "Save as PDF"
 * is in every print dialogue, and a PDF generator would be a second
 * description of the letter to keep in step.
 */

import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import api, { ApiError, type ApprovalLetter as Letter } from '../../api/client';
import { Alert, Button } from '../../components/ui';
import { Letterhead, LetterFooter } from './Letterhead';
import './letter.css';

function Breakdown({ letter }: { letter: Letter }) {
  return (
    <table className="letter__table">
      <thead>
        <tr>
          <th>Semester</th>
          <th>Type of Assistance</th>
          <th>Amount</th>
        </tr>
      </thead>
      <tbody>
        {letter.rows.map((row, index) => (
          <tr key={row.label}>
            {index === 0 && (
              <td rowSpan={letter.rows.length + (letter.total_label ? 1 : 0)}>
                {letter.semester}
              </td>
            )}
            <td>{row.label}</td>
            <td className="num">
              {row.amount}
              {row.note && <span className="letter__note">{row.note}</span>}
            </td>
          </tr>
        ))}
        {letter.total_label && (
          <tr>
            <td className="letter__total-label">{letter.total_label}</td>
            <td className="num letter__total-label">{letter.total}</td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

function OneLetter({ letter }: { letter: Letter }) {
  return (
    <article className="letter">
      <Letterhead />

      {/* Only the DGGR template carries a date; the server sends none for the
          other two rather than this deciding where a date belongs. */}
      {letter.date && <p className="letter__date">Date: {letter.date}</p>}

      <p className="letter__identifier">
        {letter.identifier.label} {letter.identifier.value}
      </p>

      <p className="letter__re">
        <strong>RE: {letter.title} {letter.term}</strong>
      </p>

      <p>Dear {letter.recipient}</p>
      <p>{letter.opening}</p>
      <p>{letter.breakdown_lead}</p>

      <Breakdown letter={letter} />
      {letter.footnote && <p className="letter__footnote">*{letter.footnote}</p>}

      {letter.paragraphs.map((text) => <p key={text.slice(0, 40)}>{text}</p>)}

      <p className="letter__closing">{letter.closing}</p>
      <p className="letter__signature">
        {letter.signatory.name}<br />
        {letter.signatory.title}<br />
        {letter.signatory.organisation}<br />
        Email: <a href={`mailto:${letter.signatory.email}`}>{letter.signatory.email}</a>
      </p>

      <LetterFooter office={letter.office} />
    </article>
  );
}

export default function ApprovalLetter() {
  const { id } = useParams();
  const [letters, setLetters] = useState<Letter[] | null>(null);
  const [error, setError] = useState('');
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    // Awaited inside the effect rather than chained onto the promise. Either
    // catches the failure; only this one is seen to catch it by the test
    // runner, which otherwise reports a rejection the component has already
    // handled and fails the test that proves the handling works.
    (async () => {
      try {
        const result = await api.approvalLetter(Number(id));
        if (!cancelled) setLetters(result);
      } catch (problem) {
        if (cancelled) return;
        // The server says *why* there is no letter — not approved, not priced,
        // the pricing awards nothing, or a one-off award the office has supplied
        // no letter for. Its wording is what tells somebody what to do next, so
        // it is shown rather than replaced with a generic failure.
        //
        // Read from `ApiError.message`, which is where `toApiError` puts the
        // body's `detail`. This reached for `problem.response.data.detail` —
        // the shape axios throws, not the shape the client re-throws — so it
        // was always `undefined` and every one of the four reasons showed as
        // "The approval letter could not be loaded." A student whose award is
        // a travel claim was told the page was broken rather than that their
        // award has no letter.
        setError(
          problem instanceof ApiError && problem.message
            ? problem.message
            : 'The approval letter could not be loaded.',
        );
      }
    })();

    return () => { cancelled = true; };
  }, [id]);

  /**
   * Hand the PDF to a new tab as a blob.
   *
   * The tab is opened before the request, not after: a browser blocks
   * `window.open` that is not the direct result of a click, so opening it in
   * the promise's `then` gets it swallowed by the popup blocker on exactly the
   * button people press.
   */
  const openPdf = async () => {
    const tab = window.open('', '_blank');
    setDownloading(true);
    try {
      const blob = await api.approvalLetterPdf(Number(id));
      const href = URL.createObjectURL(blob);
      if (tab) tab.location.href = href;
      else window.location.href = href;
    } catch (problem) {
      tab?.close();
      setError(problem instanceof ApiError
        ? problem.message
        : 'The PDF could not be produced.');
    } finally {
      setDownloading(false);
    }
  };

  if (error) return <main className="page"><Alert tone="error">{error}</Alert></main>;
  if (!letters) {
    return (
      <main className="page">
        <div className="spinner" role="status" aria-label="Loading the letter" />
      </main>
    );
  }

  return (
    <main className="page stack stack--loose letter-page">
      <header className="row row--between letter-page__bar">
        <h1>
          {letters.length > 1 ? 'Your approval letters' : 'Your approval letter'}
        </h1>
        <div className="row">
          <Button onClick={() => window.print()}>Print</Button>
          <Button variant="primary" busy={downloading} onClick={() => void openPdf()}>
            Download PDF
          </Button>
        </div>
      </header>

      {letters.length > 1 && (
        <p className="small muted letter-page__bar">
          Your semester was funded by more than one programme, so there is a
          letter for each.
        </p>
      )}

      {letters.map((letter) => (
        <OneLetter key={letter.programme_code} letter={letter} />
      ))}
    </main>
  );
}
