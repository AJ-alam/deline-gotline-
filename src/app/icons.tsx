/**
 * The navigation icons.
 *
 * Hand-drawn rather than a dependency: eleven glyphs do not justify an icon
 * package, and inlining them means no extra request and no version to keep in
 * step. They exist for recognition — someone who is not confident reading a
 * list of nine similar-looking labels can find "the one with the printer".
 *
 * All share a 24-unit box, a stroked outline and currentColor, so they sit at
 * one weight beside text at any size.
 */

import type { SVGProps } from 'react';

export type IconName =
  | 'home'
  | 'applications'
  | 'bell'
  | 'newApplication'
  | 'continuing'
  | 'travel'
  | 'payments'
  | 'rates'
  | 'people'
  | 'profile'
  | 'printer'
  | 'signOut'
  | 'help'
  | 'clock'
  | 'inbox'
  | 'arrowRight';

function Svg({ children, ...rest }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="20"
      height="20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  );
}

const PATHS: Record<IconName, React.ReactNode> = {
  home: <><path d="M3 10.5 12 3l9 7.5" /><path d="M5.5 9.5V20h13V9.5" /><path d="M9.75 20v-5.5h4.5V20" /></>,
  applications: <><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4" /><path d="M9 12h6M9 16h6" /></>,
  bell: <><path d="M6 9a6 6 0 0 1 12 0c0 4 1.5 5.5 1.5 5.5h-15S6 13 6 9Z" /><path d="M10 18a2 2 0 0 0 4 0" /></>,
  newApplication: <><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4" /><path d="M12 11v6M9 14h6" /></>,
  continuing: <><path d="M20 12a8 8 0 1 1-2.6-5.9" /><path d="M20 4v4h-4" /></>,
  travel: <><path d="M3 13.5 21 5l-4 8.5 2.5 5.5-3 1-3.5-4.5-4 1.5Z" /></>,
  payments: <><rect x="3" y="6" width="18" height="12" rx="2" /><circle cx="12" cy="12" r="2.5" /><path d="M6.5 12h.01M17.5 12h.01" /></>,
  rates: <><path d="M4 20V9M10 20V4M16 20v-7M22 20H2" /></>,
  profile: <><circle cx="12" cy="8" r="3.6" /><path d="M4.5 20c0-3.8 3.4-6.2 7.5-6.2s7.5 2.4 7.5 6.2" /></>,
  people: <><circle cx="9" cy="8" r="3.2" /><path d="M3 20c0-3.3 2.7-5.5 6-5.5s6 2.2 6 5.5" /><path d="M16 5.2A3.2 3.2 0 0 1 16 11" /><path d="M17.5 14.8c2 .7 3.5 2.5 3.5 5.2" /></>,
  printer: <><path d="M7 9V3h10v6" /><rect x="3" y="9" width="18" height="7" rx="2" /><path d="M7 14h10v7H7z" /></>,
  signOut: <><path d="M14 4H6v16h8" /><path d="M18 12H10" /><path d="m15 9 3 3-3 3" /></>,
  help: <><circle cx="12" cy="12" r="9" /><path d="M9.5 9.5a2.6 2.6 0 0 1 5 .9c0 1.7-2.5 2-2.5 3.6" /><path d="M12 17.5h.01" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5.2l3.2 2" /></>,
  inbox: <><path d="M3 13h5l1.5 3h5L16 13h5" /><path d="M5.6 5h12.8l2.6 8v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-5Z" /></>,
  arrowRight: <><path d="M4 12h15" /><path d="m13 6 6 6-6 6" /></>,
};

export default function Icon({ name, ...rest }: { name: IconName } & SVGProps<SVGSVGElement>) {
  return <Svg {...rest}>{PATHS[name]}</Svg>;
}
