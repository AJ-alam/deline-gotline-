/**
 * The chart palette, kept apart from the components that use it.
 *
 * Its own module because a file that exports both components and constants
 * breaks fast refresh — and because the palette is a decision in its own
 * right, checked by the validator rather than by eye.
 *
 * **Categorical, for the one chart whose job is telling series apart.** The
 * validated reference hues: blue, orange, aqua. Unclassified enrolments take a
 * neutral grey rather than a fourth hue, because an absent answer is not a
 * fourth kind of institution.
 *
 * Verified against the light surface — lightness band, chroma floor, CVD
 * separation (worst adjacent ΔE 9.1, target ≥8) and normal-vision floor
 * (worst 22.9, floor ≥15) all pass. Contrast against the surface *warns*,
 * which is not dismissable: it obliges a visible label on every segment, and
 * every segment with room carries its value.
 */
export const SERIES = {
  university: '#2a78d6',
  college: '#eb6834',
  trades: '#1baf7a',
  unclassified: '#9a9384',
} as const;

/**
 * One hue for magnitude.
 *
 * Money by category, funding per student, students per institution — these
 * compare amounts of the same kind of thing, so length carries the value and
 * the colour is just ink. A different hue per bar would claim the bars are
 * different kinds of thing, which they are not.
 */
export const MAGNITUDE = '#b8823c';

/** Recessive furniture: gridlines, axes, the tooltip's edge. */
export const AXIS = '#cbc0aa';
export const SURFACE = '#ffffff';
