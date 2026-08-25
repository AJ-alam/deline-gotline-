/**
 * The office's letterhead.
 *
 * The crest and wordmark are the supplied artwork. The ribbon to its right is
 * drawn here: it is in the templates as decoration and was not supplied as a
 * file, so it is four curved bands rather than a traced copy. It carries no
 * information, which is why approximating it is honest and approximating the
 * crest would not be.
 */

import logo from '../../assets/dgg-logo.svg';

export function Letterhead() {
  return (
    <header className="letterhead" aria-label="Délı̨nę Got’ı̨nę Government">
      <img className="letterhead__mark" src={logo} alt="Délı̨nę Got’ı̨nę Government" />
      <svg
        className="letterhead__ribbon"
        viewBox="0 0 520 150"
        preserveAspectRatio="none"
        role="presentation"
        aria-hidden="true"
      >
        <path d="M0 96 C 150 4, 330 4, 520 44 L 520 66 C 330 30, 150 30, 0 118 Z"
              fill="#9fc7d8" opacity="0.85" />
        <path d="M0 112 C 150 26, 340 22, 520 60 L 520 78 C 340 46, 150 50, 0 130 Z"
              fill="#e8a0b8" opacity="0.85" />
        <path d="M0 126 C 160 52, 350 44, 520 76 L 520 90 C 350 66, 160 74, 0 140 Z"
              fill="#7fb9a6" opacity="0.85" />
        <path d="M0 138 C 170 76, 360 66, 520 94 L 520 104 C 360 84, 170 94, 0 148 Z"
              fill="#c8d8b0" opacity="0.9" />
      </svg>
    </header>
  );
}

export function LetterFooter({ office }: {
  office: { address: string; phone: string; website: string };
}) {
  return (
    <footer className="letter__footer">
      {office.address} &nbsp;|&nbsp; Office: {office.phone} &nbsp;|&nbsp; {office.website}
    </footer>
  );
}
