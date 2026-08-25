/**
 * The letter's route sits under the application detail route.
 *
 * `/applications/:id` is declared before `/applications/:id/approval-letter`,
 * and a router that matched in declaration order would send every request for
 * a letter to the application screen instead — with the id read as `:id` and
 * "approval-letter" silently dropped. React Router ranks by specificity rather
 * than order, which is the behaviour this depends on; it is worth one test
 * rather than an assumption, because the failure is a page nobody can reach.
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import '@testing-library/jest-dom';

describe('approval letter routing', () => {
  function resolve(path: string) {
    render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          {/* Declared in the same order as app/routes.tsx. */}
          <Route path="/applications/:id" element={<p>detail</p>} />
          <Route path="/applications/:id/approval-letter" element={<p>letter</p>} />
        </Routes>
      </MemoryRouter>,
    );
  }

  it('sends the letter path to the letter, not to the application', () => {
    resolve('/applications/7/approval-letter');
    expect(screen.getByText('letter')).toBeInTheDocument();
  });

  it('still sends the application path to the application', () => {
    resolve('/applications/7');
    expect(screen.getByText('detail')).toBeInTheDocument();
  });
});
