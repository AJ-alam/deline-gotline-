/**
 * What the payment run says is blocked.
 *
 * `finance.preview` blocks each award *line*, which is correct — a line is what
 * does or does not reach the file. The reason, though, is about the student, so
 * an application priced into five lines printed the same sentence five times and
 * the office was shown twenty-eight identical rows for nine students.
 *
 * On a money screen the count is the part that has to be right: "28 awards"
 * beside a list the reader cannot count is exactly the sort of figure this
 * project keeps having to correct.
 */

import { describe, expect, it } from 'vitest';

import { groupBlocked } from './blocked';

type Blocked = Parameters<typeof groupBlocked>[0];

const NO_ACCOUNT = 'Both Journey has no bank account on file.';
const RELEASE = 'Payment was requested to another person.';

function blocked(rows: Array<[number, number, string]>): Blocked {
  return rows.map(([award_id, application_id, reason]) => ({
    award_id,
    application_id,
    reason,
  })) as Blocked;
}

describe('groupBlocked', () => {
  it('says an application once however many award lines it was priced into', () => {
    const groups = groupBlocked(blocked([
      [1, 1, NO_ACCOUNT],
      [2, 1, NO_ACCOUNT],
      [3, 1, NO_ACCOUNT],
      [4, 1, NO_ACCOUNT],
      [5, 1, NO_ACCOUNT],
    ]));

    expect(groups).toHaveLength(1);
    expect(groups[0].application_id).toBe(1);
    expect(groups[0].awards).toBe(5);
  });

  it('keeps applications apart even when the reason reads identically', () => {
    /* The same student can hold two applications, and collapsing on the reason
       alone would hide one of them behind the other. */
    const groups = groupBlocked(blocked([
      [1, 1, NO_ACCOUNT],
      [2, 4, NO_ACCOUNT],
      [3, 6, NO_ACCOUNT],
    ]));

    expect(groups.map((g) => g.application_id)).toEqual([1, 4, 6]);
    expect(groups.every((g) => g.awards === 1)).toBe(true);
  });

  it('keeps two different reasons on the same application apart', () => {
    /* Grouping by application alone would drop one reason entirely, and the
       office would fix the bank account and not know why it was still stuck. */
    const groups = groupBlocked(blocked([
      [1, 1, NO_ACCOUNT],
      [2, 1, RELEASE],
    ]));

    expect(groups).toHaveLength(2);
    expect(groups.map((g) => g.reason)).toEqual([NO_ACCOUNT, RELEASE]);
  });

  it('preserves the order the server reported', () => {
    /* The service reports the awards with no decision behind them first,
       deliberately. Re-ordering here would bury that. */
    const groups = groupBlocked(blocked([
      [9, 31, RELEASE],
      [1, 1, NO_ACCOUNT],
      [2, 1, NO_ACCOUNT],
    ]));

    expect(groups.map((g) => g.application_id)).toEqual([31, 1]);
  });

  it('totals back to the number of award lines the server sent', () => {
    /* The grouped list is a different count from the headline, and the headline
       still speaks for award lines. If these ever disagree the screen is telling
       finance two different things about the same money. */
    const rows = blocked([
      [1, 1, NO_ACCOUNT],
      [2, 1, NO_ACCOUNT],
      [3, 4, NO_ACCOUNT],
      [4, 6, RELEASE],
    ]);

    const total = groupBlocked(rows).reduce((sum, g) => sum + g.awards, 0);

    expect(total).toBe(rows.length);
  });

  it('returns nothing when nothing is blocked', () => {
    expect(groupBlocked(blocked([]))).toEqual([]);
  });
});
