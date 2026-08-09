/**
 * Routes.
 *
 * Every route is lazy: the previous App.tsx imported all thirty eagerly, which
 * is why one 1.2MB chunk was downloaded before anything rendered.
 */
import { Suspense, lazy } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import ProtectedRoute from './components/Auth/ProtectedRoute';
import './styles/tokens.css';
import './styles/app.css';

const SignIn = lazy(() => import('./pages/SignIn'));
const Register = lazy(() => import('./pages/Register'));
const Applications = lazy(() => import('./pages/Applications'));
const Apply = lazy(() => import('./pages/Apply'));

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
          <Route path="/" element={<Navigate to="/signin" replace />} />
          <Route path="/signin" element={<SignIn />} />
          <Route path="/register" element={<Register />} />

          <Route
            path="/applications"
            element={<ProtectedRoute><Applications /></ProtectedRoute>}
          />
          <Route
            path="/apply/:type"
            element={<ProtectedRoute><Apply /></ProtectedRoute>}
          />

          <Route path="*" element={<Navigate to="/signin" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
