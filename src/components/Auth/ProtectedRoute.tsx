import React, { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import API from '../../api/client';

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: string[];
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, allowedRoles }) => {
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userRole, setUserRole] = useState<string | null>(null);
  const location = useLocation();

  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('dgg_token');
      if (!token) {
        setIsAuthenticated(false);
        setIsLoading(false);
        return;
      }

      try {
        const user = await API.getMe() as any;
        setIsAuthenticated(true);
        setUserRole(user.role);
        // Sync role to localStorage just in case
        localStorage.setItem('dgg_role', user.role);
      } catch (err) {
        console.error('Auth verification failed:', err);
        setIsAuthenticated(false);
        localStorage.removeItem('dgg_token');
        localStorage.removeItem('dgg_role');
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();
  }, []);

  if (isLoading) {
    return (
      <div style={{ 
          display: 'flex', 
          flexDirection: 'column',
          justifyContent: 'center', 
          alignItems: 'center', 
          height: '100vh', 
          background: '#f8fafc',
          gap: '16px'
      }}>
        <div className="admin-spinner" style={{ 
            width: '40px', 
            height: '40px', 
            border: '3px solid #e2e8f0', 
            borderTopColor: '#e5a662', 
            borderRadius: '50%',
            animation: 'admin-spin 1s linear infinite'
        }}></div>
        <div style={{ fontSize: '14px', color: '#64748b', fontWeight: '600' }}>Verifying security session...</div>
        <style>{`
          @keyframes admin-spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }

  if (!isAuthenticated) {
    // If it's a staff route, redirect to internal login
    const isStaffRoute = location.pathname.startsWith('/staff') || location.pathname.startsWith('/internal');
    return <Navigate to={isStaffRoute ? "/internal/login" : "/signin"} state={{ from: location }} replace />;
  }

  const normalizedUserRole = userRole?.toLowerCase();
  const normalizedAllowedRoles = allowedRoles?.map(role => role.toLowerCase());

  if (normalizedAllowedRoles && normalizedUserRole && !normalizedAllowedRoles.includes(normalizedUserRole)) {
    // Role not allowed - redirect to their native dashboard or sign in
    if (normalizedUserRole === 'student') return <Navigate to="/dashboard" replace />;
    if (['admin', 'director', 'ssw'].includes(normalizedUserRole)) return <Navigate to="/staff" replace />;
    return <Navigate to="/signin" replace />;
  }

  return <>{children}</>;
};

export default ProtectedRoute;
