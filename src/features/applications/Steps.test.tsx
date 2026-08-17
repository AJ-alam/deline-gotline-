/**
 * The step maps, checked against the schemas they group.
 *
 * Steps are built by naming sections. A section a step does not name is not
 * rendered at all — `SchemaForm` keeps only the sections its steps list — so a
 * section renamed in the backend, or added without being listed here, takes its
 * questions off the form silently. Everything still compiles, every test still
 * passes, and the office assesses an application that was never asked half of
 * what it needed.
 *
 * That is not hypothetical: the practicum step map went stale when its schema
 * was rewritten, and the only reason it surfaced was somebody opening the page.
 *
 * `APPLICATION_SECTIONS` is generated from the schemas by
 * `manage.py generate_types`, so these compare the client against the backend's
 * own definition rather than against a second copy of it.
 */

import { describe, expect, it } from 'vitest';

import { APPLICATION_SECTIONS, type ApplicationType } from '../../api/schema.generated';
import { STEPS } from './steps';

const stepped = Object.keys(STEPS) as ApplicationType[];

describe('every stepped form', () => {
  it('is a form that exists', () => {
    for (const type of stepped) {
      expect(APPLICATION_SECTIONS[type], `${type} has no schema`).toBeDefined();
    }
  });

  it.each(stepped)('%s names only sections its schema declares', (type) => {
    const declared = new Set(APPLICATION_SECTIONS[type]);
    const named = STEPS[type]!.flatMap((step) => step.sections);
    const unknown = named.filter((section) => !declared.has(section));

    expect(
      unknown,
      `${type} builds a step from ${JSON.stringify(unknown)}, which the schema `
      + `does not declare. Its sections are ${JSON.stringify([...declared])}.`,
    ).toEqual([]);
  });

  it.each(stepped)('%s leaves none of its sections off the form', (type) => {
    // The dangerous direction. An unnamed section is not rendered anywhere:
    // the questions are simply gone, and nothing says so.
    const named = new Set(STEPS[type]!.flatMap((step) => step.sections));
    const orphaned = APPLICATION_SECTIONS[type].filter((section) => !named.has(section));

    expect(
      orphaned,
      `${type} declares ${JSON.stringify(orphaned)} and no step names them, so `
      + 'those questions are never shown.',
    ).toEqual([]);
  });

  it.each(stepped)('%s does not ask for the same section twice', (type) => {
    const named = STEPS[type]!.flatMap((step) => step.sections);
    expect(named).toHaveLength(new Set(named).size);
  });

  it.each(stepped)('%s gives every step a title', (type) => {
    for (const step of STEPS[type]!) {
      expect(step.title.trim()).not.toBe('');
      expect(step.sections.length).toBeGreaterThan(0);
    }
  });
});
