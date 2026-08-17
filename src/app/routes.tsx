/**
 * Every route in the portal.
 *
 * Signed-in pages render inside AppShell, so navigation and identity are
 * defined once rather than repeated per page. Sign-in, registration and the
 * registrar's enrolment form sit outside it: none of them have a session.
 *
 * Every page is lazy. The previous App.tsx imported all thirty eagerly, which
 * is why one 1.2MB chunk downloaded before anything rendered.
 */
import { Suspense, lazy } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import ProtectedRoute from '../features/auth/ProtectedRoute';
import AppShell from './AppShell';
import '../styles/tokens.css';
import '../styles/app.css';

const SignIn = lazy(() => import('../features/auth/SignIn'));
const Register = lazy(() => import('../features/auth/Register'));
const GuestApply = lazy(() => import('../features/auth/GuestApply'));
const EnrollmentVerification = lazy(() => import('../features/enrolment/EnrollmentVerification'));

const Dashboard = lazy(() => import('../features/dashboard/Dashboard'));
const Applications = lazy(() => import('../features/applications/Applications'));
const Apply = lazy(() => import('../features/applications/Apply'));
const ApplicationDetail = lazy(() => import('../features/applications/ApplicationDetail'));
const ReviewQueue = lazy(() => import('../features/review/ReviewQueue'));
const PaymentRun = lazy(() => import('../features/finance/PaymentRun'));
const PolicyRates = lazy(() => import('../features/policy/PolicyRates'));
const People = lazy(() => import('../features/people/People'));
const Notifications = lazy(() => import('../features/notifications/Notifications'));
const Help = lazy(() => import('../features/help/Help'));
const PrintableForms = lazy(() => import('../features/forms/PrintableForms'));

function Loading() {
  return (
    <div className="page" aria-busy="true">
      <div className="spinner" />
      <span className="sr-only">Loading</span>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<Loading />}>
        <Routes>
          {/* No session: an applicant before they have an account, and the
              registrar, who never has one. */}
          <Route path="/" element={<Navigate to="/signin" replace />} />
          <Route path="/signin" element={<SignIn />} />
          <Route path="/register" element={<Register />} />
          {/* One-off awards, claimed without an account. */}
          <Route path="/apply-once/:type" element={<GuestApply />} />
          <Route path="/enrolment/:token" element={<EnrollmentVerification />} />

          <Route element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/applications" element={<Applications />} />
            <Route path="/applications/:id" element={<ApplicationDetail />} />
            <Route path="/apply/:type" element={<Apply />} />
            <Route path="/review" element={<ReviewQueue />} />
            <Route path="/review/:id" element={<ApplicationDetail />} />
            <Route path="/payments" element={<PaymentRun />} />
            <Route path="/policy" element={<PolicyRates />} />
            <Route path="/people" element={<People />} />
            <Route path="/notifications" element={<Notifications />} />
            <Route path="/help" element={<Help />} />
            <Route path="/forms" element={<PrintableForms />} />
            <Route path="/forms/:type" element={<PrintableForms />} />
          </Route>

          <Route path="*" element={<Navigate to="/signin" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
