/**
 * Catches unreadable hover states caused by CSS specificity.
 *
 * `.chip:hover` is (0,2,0); `.chip--on` is (0,1,0). So an unscoped hover rule
 * that sets `color` beats the modifier's `color` while leaving the modifier's
 * `background` in place — dark text on a black chip, unreadable exactly when
 * the pointer is on it. Order in the file does not save you; specificity wins.
 *
 * This flags the shape rather than the symptom: a `.x:hover` that changes
 * `color` without also settling `background`, where some `.x--modifier` sets a
 * background of its own. The fix is either `.x:not(.x--modifier):hover` or an
 * explicit `.x--modifier:hover`.
 *
 *     node scripts/check-hover-contrast.mjs
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = 'src';

function cssFiles(dir) {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) return cssFiles(path);
    return path.endsWith('.css') ? [path] : [];
  });
}

/** Top-level `selector { declarations }` pairs, comments and at-rules removed. */
function rules(css) {
  const withoutComments = css.replace(/\/\*[\s\S]*?\*\//g, '');
  const found = [];
  const pattern = /([^{}]+)\{([^{}]*)\}/g;
  let match;
  while ((match = pattern.exec(withoutComments)) !== null) {
    const selector = match[1].trim().replace(/\s+/g, ' ');
    if (!selector || selector.startsWith('@')) continue;
    found.push({ selector, body: match[2] });
  }
  return found;
}

const sets = (body, property) =>
  new RegExp(`(^|[;{\\s])${property}\\s*:`, 'i').test(body);

const problems = [];

for (const file of cssFiles(ROOT)) {
  const parsed = rules(readFileSync(file, 'utf8'));

  // Which base classes have a modifier that paints its own background.
  const modifierBackgrounds = new Map();
  for (const { selector, body } of parsed) {
    if (!sets(body, 'background')) continue;
    for (const part of selector.split(',')) {
      const simple = part.trim().match(/^\.([a-z0-9_]+(?:__[a-z0-9_]+)?)--([a-z0-9_-]+)$/i);
      if (!simple) continue;
      const base = `.${simple[1]}`;
      modifierBackgrounds.set(base, [...(modifierBackgrounds.get(base) ?? []), part.trim()]);
    }
  }

  for (const { selector, body } of parsed) {
    for (const part of selector.split(',')) {
      const one = part.trim();
      // Only bare `.x:hover` — anything already carrying :not() has been
      // thought about.
      const hover = one.match(/^\.([a-z0-9_]+(?:__[a-z0-9_]+)?):hover$/i);
      if (!hover) continue;
      const base = `.${hover[1]}`;
      const modifiers = modifierBackgrounds.get(base);
      if (!modifiers) continue;
      if (!sets(body, 'color')) continue;
      if (sets(body, 'background')) continue;

      problems.push(
        `${file}\n    ${one} sets color but not background, and ` +
          `${modifiers.join(', ')} sets a background.\n` +
          `    The hover wins on colour and loses on background — the text can ` +
          `land on the wrong fill.\n` +
          `    Fix: .${hover[1]}:not(${modifiers[0]}):hover { ... } ` +
          `plus an explicit ${modifiers[0]}:hover.`,
      );
    }
  }
}

if (problems.length > 0) {
  console.error(`\nUnreadable hover states (${problems.length}):\n`);
  for (const problem of problems) console.error(`  ${problem}\n`);
  process.exit(1);
}

console.log('No hover states are overridden into unreadable combinations.');
