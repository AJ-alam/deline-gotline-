import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import API from '../api/client';
import '../styles/auth.css';

const SignIn: React.FC = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [showGuestModal, setShowGuestModal] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleSignIn = async () => {
    setError(null);
    setIsLoading(true);
    try {
      const response = await API.login({ email, password }) as any;
      localStorage.setItem('dgg_token', response.access);
      localStorage.setItem('dgg_refresh', response.refresh);

      // Fetch user role
      const user = await API.getMe() as any;

      if (user.role !== 'student') {
        // Enforce role separation
        localStorage.removeItem('dgg_token');
        localStorage.removeItem('dgg_refresh');
        localStorage.removeItem('dgg_role');
        setError('PERMISSION DENIED: This portal is for students only. Please use the Internal Administration Access link below.');
        setIsLoading(false);
        return;
      }

      localStorage.setItem('dgg_role', user.role);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check your credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  const togglePassword = () => {
    setShowPassword(!showPassword);
  };

  return (
    <div className="auth-root">
      <div className="page-layout">
        {/* Left Branding Panel */}
        <div className="left-panel">
          <div>
            <div className="brand-name">Deline Got'ı̨nę Government</div>
            <div className="brand-sub">Student Financial Support Program</div>
            <div className="left-headline">
              <h1>Empowering your <br /><span style={{ color: 'var(--admin-accent, #e5a662)' }}>Academic Journey</span></h1>
              <p>Apply for student funding, track your application status, and manage your education future in one secure place.</p>

              <ul className="feature-list" style={{ marginTop: '32px' }}>
                <li>No software downloads required</li>
                <li>Real-time eligibility calculation</li>
                <li>Digital application tracking</li>
                <li>Persistent progress saving</li>
              </ul>
            </div>
          </div>

          <div className="left-footer">
            <div style={{ fontSize: '12px', color: '#e5a662', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>Support Center</div>
            <p style={{ color: 'rgba(255,255,255,0.6)', lineHeight: '1.5' }}>
              We're here to help you succeed. Contact your Student Support Worker if you have any questions.
            </p>
            <div style={{ marginTop: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '8px', height: '8px', background: '#38a169', borderRadius: '50%' }}></div>
              <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.4)' }}>Support Online: Mon–Fri, 9am–5pm</span>
            </div>
          </div>
        </div>

        {/* Right Form Card */}
        <div className="right-panel">
          <div className="form-title">Student Access</div>
          <div className="form-sub">New student? <Link to="/signup">Create your portal account →</Link></div>

          <div className="field-group">
            <label className="field-label" htmlFor="email" style={{ color: '#64748b' }}>Email or Phone</label>
            <input
              className="field-input"
              id="email"
              type="text"
              placeholder="e.g. marie.beaulieu@email.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              style={{ background: '#fff' }}
            />
          </div>

          <div className="field-group">
            <label className="field-label" htmlFor="password" style={{ color: '#64748b' }}>Password</label>
            <div className="password-wrap">
              <input
                className="field-input"
                id="password"
                type={showPassword ? "text" : "password"}
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                style={{ background: '#fff' }}
              />
              <button
                className="pw-toggle"
                onClick={togglePassword}
                type="button"
                aria-label={showPassword ? "Hide password" : "Show password"}
                style={{ color: '#64748b' }}
              >
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
            {error && <div style={{ color: '#ef4444', fontSize: '12px', marginTop: '8px', fontWeight: '600' }}>{error}</div>}
            <div style={{ textAlign: 'right', marginTop: '8px' }}>
              <Link to="/forgot-password" style={{ fontSize: '12px', color: '#64748b', textDecoration: 'none', fontWeight: '600' }}>Forgot password? →</Link>
            </div>
          </div>

          <button
            className="btn-auth-primary"
            type="button"
            disabled={isLoading}
            onClick={handleSignIn}
            style={{ marginTop: '24px', opacity: isLoading ? 0.7 : 1 }}
          >
            {isLoading ? 'SIGNING IN...' : 'SIGN IN TO PORTAL \u00a0\u2192'}
          </button>

          <div style={{ marginTop: '32px', textAlign: 'center', borderTop: '1px solid #f1f5f9', paddingTop: '24px' }}>
            <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '16px' }}>One-Off Applications</div>
            <button
              type="button"
              onClick={() => setShowGuestModal(true)}
              style={{ background: '#f8fafc', border: '1px solid #e2e8f0', color: '#1a1a1a', fontWeight: 700, cursor: 'pointer', fontSize: '12px', padding: '10px 16px', borderRadius: '8px', width: '100%' }}
            >
              Applying for a single award? Learn More →
            </button>
          </div>

          <div style={{ marginTop: '40px', textAlign: 'center' }}>
            <Link to="/internal/login" style={{ fontSize: '11px', color: '#94a3b8', textDecoration: 'none', fontWeight: '8400', opacity: 0.8, letterSpacing: '0.05em' }}>
              INTERNAL ADMINISTRATION ACCESS →
            </Link>
          </div>
        </div>
      </div>

      {/* ── Guest Application Modal ── */}
      {showGuestModal && (
        <div className="modal-overlay animate-fade-in" onClick={() => setShowGuestModal(false)}>
          <div className="modal-content animate-slide-in" onClick={e => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setShowGuestModal(false)}>✕</button>
            <div className="modal-header">
              <h3>One-Off Award Applications</h3>
              <p>Continue without an account for these specific short-term programs.</p>
            </div>

            <div className="guest-modal-options">
              <Link to="/forms/practicum" className="guest-modal-btn">
                <span className="btn-title">Working in Deline this summer?</span>
                <span className="btn-desc">Support for clinical placements or work experience.</span>
              </Link>
              <Link to="/forms/graduation" className="guest-modal-btn">
                <span className="btn-title">Completed high school or post-secondary/training program?</span>
                <span className="btn-desc">One-time recognition for successful program completion.</span>
              </Link>
            </div>

            <div className="modal-footer">
              <p>Guest records can be later merged to a full profile by staff using your SIN or Treaty/Beneficiary number.</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SignIn;
