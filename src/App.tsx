import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import SignIn from './pages/SignIn';
import SignUp from './pages/SignUp';
import ForgotPassword from './pages/ForgotPassword';
import Dashboard from './pages/Dashboard';
import StaffDashboard from './pages/StaffDashboard';
import InternalSignIn from './pages/InternalSignIn';
import HardshipBursary from './pages/Forms/HardshipBursary';
import FormF from './pages/Forms/FormF';
import FormG from './pages/Forms/FormG';
import StandaloneFormWrapper from './components/Forms/StandaloneFormWrapper';
import ProtectedRoute from './components/Auth/ProtectedRoute';

import AdminErrorBoundary from './components/Auth/AdminErrorBoundary';

function App() {
  return (
    <Router>
      <Routes>
        {/* Public Auth Routes */}
        <Route path="/" element={<SignIn />} />
        <Route path="/signin" element={<SignIn />} />
        <Route path="/signup" element={<SignUp />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/internal/login" element={<InternalSignIn />} />

        {/* Protected Student Routes */}
        <Route path="/dashboard/*" element={
          <ProtectedRoute allowedRoles={['student']}>
            <Dashboard />
          </ProtectedRoute>
        } />

        {/* Protected Staff/Director Routes */}
        <Route path="/staff/*" element={
          <ProtectedRoute allowedRoles={['admin', 'director', 'ssw']}>
            <AdminErrorBoundary>
              <StaffDashboard />
            </AdminErrorBoundary>
          </ProtectedRoute>
        } />

        {/* Catch-all for /staff to ensure it maps to the dashboard */}
        <Route path="/staff" element={<Navigate to="/staff/dashboard" replace />} />

        {/* Guest Application Routes (Semi-protected or Public based on requirements) */}
        <Route path="/forms/hardship" element={
          <StandaloneFormWrapper>
            {(props) => <HardshipBursary {...props} />}
          </StandaloneFormWrapper>
        } />
        <Route path="/forms/practicum" element={
          <StandaloneFormWrapper>
            {(props) => <FormF {...props} />}
          </StandaloneFormWrapper>
        } />
        <Route path="/forms/graduation" element={
          <StandaloneFormWrapper>
            {(props) => <FormG {...props} />}
          </StandaloneFormWrapper>
        } />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
