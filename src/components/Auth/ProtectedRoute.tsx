import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: string[];
}

function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return Date.now() >= payload.exp * 1000;
  } catch {
    return true;
  }
}

// Validates the JWT locally — no network round-trip, no spinner.
// Token expiry is encoded in the payload so we decode it in-browser.
const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, allowedRoles }) => {
  const location = useLocation();

  const token = localStorage.getItem('dgg_token');
  const role  = localStorage.getItem('dgg_role');

  if (!token || isTokenExpired(token)) {
    localStorage.removeItem('dgg_token');
    localStorage.removeItem('dgg_refresh');
    localStorage.removeItem('dgg_role');
    localStorage.removeItem('dgg_profile_cache');
    const isStaff = location.pathname.startsWith('/staff') || location.pathname.startsWith('/internal');
    return <Navigate to={isStaff ? '/internal/login' : '/signin'} state={{ from: location }} replace />;
  }

  if (allowedRoles && role) {
    const norm = role.toLowerCase();
    if (!allowedRoles.map(r => r.toLowerCase()).includes(norm)) {
      if (norm === 'student') return <Navigate to="/dashboard" replace />;
      if (['admin', 'director', 'ssw'].includes(norm)) return <Navigate to="/staff" replace />;
      return <Navigate to="/signin" replace />;
    }
  }

  return <>{children}</>;
};

export default ProtectedRoute;
