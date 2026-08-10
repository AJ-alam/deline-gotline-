import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';

import { tokens } from '../../api/client';

/**
 * Gates a route on having a token.
 *
 * This is a convenience, not a security boundary — every endpoint enforces its
 * own permissions server-side. A client-side check only decides what to render.
 */
export default function ProtectedRoute({ children }: { children: ReactNode }) {
  if (!tokens.access) return <Navigate to="/signin" replace />;
  return <>{children}</>;
}
