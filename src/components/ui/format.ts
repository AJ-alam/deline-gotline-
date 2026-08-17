/**
 * Presentation helpers.
 *
 * Kept out of the component file so fast refresh works, and because formatting
 * is not a component. Money and dates are formatted in one place so they read
 * the same on every screen.
 */

export type Tone = 'ok' | 'warn' | 'danger' | 'info' | 'neutral';

/**
 * A policy rate, in whatever it is measured in.
 *
 * The rates screen formatted every one of them as money and ignored `unit`, so
 * an 80% achievement threshold read as "$80.00" — on the screen an
 * administrator changes what students are paid from.
 */
export function formatRate(value: string | number, unit: string): string {
  if (unit !== '%') return formatMoney(value);
  const number = typeof value === 'string' ? Number(value) : value;
  if (!Number.isFinite(number)) return '—';
  return `${number}%`;
}

export function formatMoney(amount: string | number): string {
  const value = typeof amount === 'string' ? Number(amount) : amount;
  if (!Number.isFinite(value)) return '—';
  return value.toLocaleString('en-CA', {
    style: 'currency',
    currency: 'CAD',
    minimumFractionDigits: 2,
  });
}

export function formatDate(iso: string | null): string {
  if (!iso) return '—';
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? '—'
    : date.toLocaleDateString('en-CA', { year: 'numeric', month: 'short', day: 'numeric' });
}

const STATUS_TONES: Record<string, Tone> = {
  draft: 'neutral',
  submitted: 'info',
  under_review: 'info',
  info_requested: 'warn',
  awaiting_decision: 'warn',
  approved: 'ok',
  declined: 'danger',
  sent_to_finance: 'ok',
};

export function statusTone(status: string): Tone {
  return STATUS_TONES[status] ?? 'neutral';
}
