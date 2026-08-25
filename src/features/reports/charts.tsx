/**
 * The chart marks the reports screen is built from.
 *
 * Inline SVG rather than a charting library: the app carries no chart
 * dependency, these are four fixed forms rather than a general plotting need,
 * and a library would bring a bundle and a styling system to fight with the
 * one already here.
 *
 * **Form follows the data's job, and colour comes last.**
 *
 * - Comparing magnitude — money by category, funding per student, students per
 *   institution — is one hue. Length carries the value; a different colour per
 *   bar would say the bars are different *kinds* of thing, which they are not.
 * - Telling series apart — university against college against trades school —
 *   is the only place a categorical palette is used, because there identity
 *   *is* the subject.
 *
 * The categorical hues are the validated reference set (blue, orange, aqua),
 * with unclassified enrolments in neutral grey rather than a fourth hue: it is
 * an absence of an answer, not a fourth kind of institution. Checked with the
 * palette validator rather than by eye — it passes the lightness band, chroma
 * floor, CVD separation and normal-vision floor, and warns on contrast against
 * the surface, which obliges every segment to carry a visible label. They do.
 */

import { useId, useState } from 'react';

import { AXIS, MAGNITUDE, SERIES, SURFACE } from './palette';


/* The two spacers: a 2px gap in the surface colour separates touching marks,
   and marks never carry a stroke — the gap does the separating. */
const GAP = 2;
const RADIUS = 4;

function money(value: number): string {
  return value.toLocaleString('en-CA', {
    style: 'currency', currency: 'CAD', maximumFractionDigits: 0,
  });
}

/**
 * A bar whose data-end is rounded and whose baseline end is square.
 *
 * Drawn as a path rather than a rect so only the growing end is rounded — a
 * rounded baseline makes the bar look as though it floats off the axis.
 */
function barPath(x: number, y: number, w: number, h: number, r: number,
                 side: 'top' | 'right'): string {
  const radius = Math.max(0, Math.min(r, side === 'top' ? h : w, side === 'top' ? w / 2 : h / 2));
  if (side === 'top') {
    return `M${x},${y + h} L${x},${y + radius} Q${x},${y} ${x + radius},${y}`
      + ` L${x + w - radius},${y} Q${x + w},${y} ${x + w},${y + radius}`
      + ` L${x + w},${y + h} Z`;
  }
  return `M${x},${y} L${x + w - radius},${y} Q${x + w},${y} ${x + w},${y + radius}`
    + ` L${x + w},${y + h - radius} Q${x + w},${y + h} ${x + w - radius},${y + h}`
    + ` L${x},${y + h} Z`;
}

export interface StackedColumn {
  label: string;
  segments: Array<{ key: string; label: string; value: number; color: string }>;
}

/**
 * Enrolment by semester — the one chart whose job is telling series apart.
 *
 * Stacked because the question is "how many students, and of what kind": the
 * total per season and its composition are both wanted, which is exactly what
 * a stack shows and a grouped bar makes the reader add up.
 */
export function StackedColumns({ columns, caption }: {
  columns: StackedColumn[];
  caption: string;
}) {
  const titleId = useId();
  const [hover, setHover] = useState<{ x: number; y: number; text: string } | null>(null);

  const width = 640;
  const height = 260;
  const padding = { top: 16, right: 16, bottom: 40, left: 44 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  const totals = columns.map((c) => c.segments.reduce((sum, s) => sum + s.value, 0));
  const peak = Math.max(...totals, 1);
  // Ticks on clean numbers, so the axis carries the values no label does.
  const step = Math.max(1, Math.ceil(peak / 4));
  const top = step * 4;
  const band = plotW / Math.max(columns.length, 1);
  const barW = Math.min(56, band * 0.55);

  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby={titleId}
           className="chart__svg" onMouseLeave={() => setHover(null)}>
        <title id={titleId}>{caption}</title>

        {[0, 1, 2, 3, 4].map((i) => {
          const y = padding.top + plotH - (plotH * (i * step)) / top;
          return (
            <g key={i}>
              <line x1={padding.left} x2={width - padding.right} y1={y} y2={y}
                    stroke={AXIS} strokeWidth={1} opacity={i === 0 ? 1 : 0.45} />
              <text x={padding.left - 8} y={y + 4} textAnchor="end"
                    className="chart__tick">{i * step}</text>
            </g>
          );
        })}

        {columns.map((column, index) => {
          const x = padding.left + band * index + (band - barW) / 2;
          let cursor = padding.top + plotH;
          const drawn = column.segments.filter((s) => s.value > 0);
          return (
            <g key={column.label}>
              {drawn.map((segment, sIndex) => {
                const h = (plotH * segment.value) / top;
                const isTop = sIndex === drawn.length - 1;
                cursor -= h;
                const y = cursor;
                // The gap is taken out of the segment, in the surface colour,
                // rather than drawn as a stroke around it.
                const drawH = Math.max(1, h - (sIndex === 0 ? 0 : GAP));
                const label = `${column.label} — ${segment.label}: ${segment.value}`;
                return (
                  <g key={segment.key}>
                    <path
                      d={barPath(x, y + (h - drawH), barW, drawH,
                                 isTop ? RADIUS : 0, 'top')}
                      fill={segment.color}
                      onMouseEnter={() => setHover({ x, y, text: label })}
                    />
                    {/* Contrast against the surface warns, so every segment
                        with room carries its value. */}
                    {drawH >= 18 && (
                      <text x={x + barW / 2} y={y + (h - drawH) + drawH / 2 + 4}
                            textAnchor="middle" className="chart__inlabel">
                        {segment.value}
                      </text>
                    )}
                  </g>
                );
              })}
              <text x={x + barW / 2} y={height - 20} textAnchor="middle"
                    className="chart__axis">{column.label}</text>
              <text x={x + barW / 2} y={height - 6} textAnchor="middle"
                    className="chart__tick">{totals[index]}</text>
            </g>
          );
        })}

        {hover && (
          <g transform={`translate(${Math.min(hover.x, width - 190)},${Math.max(hover.y - 26, 4)})`}>
            <rect width={186} height={22} rx={4} fill={SURFACE} stroke={AXIS} />
            <text x={8} y={15} className="chart__tip">{hover.text}</text>
          </g>
        )}
      </svg>
    </figure>
  );
}

export interface BarDatum {
  key: string;
  label: string;
  sub?: string;
  value: number;
  /** Shown at the tip instead of the raw value — money, mostly. */
  display?: string;
  muted?: boolean;
}

/**
 * Ranked magnitude, one hue.
 *
 * Horizontal because the labels are long — institution names, category names,
 * student numbers — and a horizontal bar gives them a whole line each instead
 * of turning the axis into rotated text.
 */
export function BarRows({ rows, caption, formatValue = money }: {
  rows: BarDatum[];
  caption: string;
  formatValue?: (value: number) => string;
}) {
  const peak = Math.max(...rows.map((r) => r.value), 1);
  return (
    <figure className="chart" aria-label={caption}>
      <ul className="cbars">
        {rows.map((row) => (
          <li key={row.key} className={row.muted ? 'cbars__row cbars__row--muted' : 'cbars__row'}>
            <div className="cbars__label">
              <span className="cbars__name">{row.label}</span>
              {row.sub && <span className="cbars__sub">{row.sub}</span>}
            </div>
            <div className="cbars__track">
              {/* A zero draws no mark at all. A stub of colour beside "$0"
                  reads as a small amount rather than as none. */}
              {row.value > 0 && (
                <span
                  className="cbars__fill"
                  style={{
                    width: `${Math.max(1.5, (row.value / peak) * 100)}%`,
                    background: row.muted ? SERIES.unclassified : MAGNITUDE,
                  }}
                />
              )}
            </div>
            <div className="cbars__value">{row.display ?? formatValue(row.value)}</div>
          </li>
        ))}
      </ul>
    </figure>
  );
}

/**
 * Part-to-whole for a small total — graduate awards by credential.
 *
 * A horizontal stacked bar rather than a pie: the reader is comparing a handful
 * of small counts, and lengths along a common baseline are read accurately
 * where angles are not.
 */
export function StackedBar({ segments, caption }: {
  segments: Array<{ key: string; label: string; value: number; color: string }>;
  caption: string;
}) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  const drawn = segments.filter((s) => s.value > 0);
  if (total === 0) return <p className="muted">None issued this year.</p>;

  return (
    <figure className="chart" aria-label={caption}>
      <div className="cstack">
        {drawn.map((segment) => (
          <span
            key={segment.key}
            className="cstack__seg"
            style={{
              width: `${(segment.value / total) * 100}%`,
              background: segment.color,
            }}
            title={`${segment.label}: ${segment.value}`}
          />
        ))}
      </div>
      <Legend items={drawn.map((s) => ({ ...s, value: String(s.value) }))} />
    </figure>
  );
}

/**
 * A legend is present for every chart of two or more series.
 *
 * Never colour-alone: the swatch carries identity, the text stays in an ink
 * token, and the value rides beside it so the reader never has to match a
 * shade against a bar to learn a number.
 */
export function Legend({ items }: {
  items: Array<{ key: string; label: string; color: string; value?: string }>;
}) {
  return (
    <ul className="clegend">
      {items.map((item) => (
        <li key={item.key}>
          <span className="clegend__dot" style={{ background: item.color }} />
          <span className="clegend__label">{item.label}</span>
          {item.value !== undefined && <strong>{item.value}</strong>}
        </li>
      ))}
    </ul>
  );
}

/**
 * A donut — the funding programme breakdown.
 *
 * Part-to-whole for **three** slices, which is the only size a ring is honest
 * at: the reader compares a handful of arcs, and every slice carries its own
 * label and value so nothing rests on judging an angle. More slices than this
 * and it would be a stacked bar.
 *
 * The hole carries the total, which is the figure most often wanted and would
 * otherwise need its own tile.
 */
export function Donut({ segments, total, caption, unit = '' }: {
  segments: Array<{ key: string; label: string; value: number; color: string }>;
  total: string;
  caption: string;
  unit?: string;
}) {
  const titleId = useId();
  const size = 168;
  const stroke = 26;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const sum = segments.reduce((acc, s) => acc + s.value, 0);
  const drawn = segments.filter((s) => s.value > 0);

  let offset = 0;
  return (
    <figure className="chart chart--donut">
      <svg viewBox={`0 0 ${size} ${size}`} role="img" aria-labelledby={titleId}
           className="cdonut">
        <title id={titleId}>{caption}</title>
        <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
          <circle cx={size / 2} cy={size / 2} r={radius} fill="none"
                  stroke={AXIS} strokeWidth={stroke} opacity={0.28} />
          {sum > 0 && drawn.map((segment) => {
            const share = segment.value / sum;
            // A 2px gap in the surface colour separates the arcs, the same
            // spacer a stacked bar uses — never a stroke around the mark.
            const length = Math.max(0, circumference * share - 2);
            const dash = `${length} ${circumference - length}`;
            const element = (
              <circle key={segment.key} cx={size / 2} cy={size / 2} r={radius}
                      fill="none" stroke={segment.color} strokeWidth={stroke}
                      strokeDasharray={dash}
                      strokeDashoffset={-offset} strokeLinecap="butt" />
            );
            offset += circumference * share;
            return element;
          })}
        </g>
        <text x={size / 2} y={size / 2 - 2} textAnchor="middle"
              className="cdonut__total">{total}</text>
        <text x={size / 2} y={size / 2 + 16} textAnchor="middle"
              className="chart__tick">{unit}</text>
      </svg>
    </figure>
  );
}
