import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import API from '../api/client';
import '../styles/auth.css';

const ResetPassword: React.FC = () => {
  const [searchParams]          = useSearchParams();
  const navigate                = useNavigate();
  const token                   = searchParams.get('token') || '';

  const [password, setPassword]   = useState('');
  const [confirm, setConfirm]     = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [success, setSuccess]     = useState(false);

  useEffect(() => {
    if (!token) {
      setError('Invalid reset link. Please request a new one.');
    }
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }

    setIsLoading(true);
    try {
      await API.resetPassword(token, password);
      setSuccess(true);
      // Redirect to sign-in after 3 seconds
      setTimeout(() => navigate('/signin'), 3000);
    } catch (err: any) {
      setError(err.message || 'Reset failed. The link may have expired. Please request a new one.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-root">
      <div className="browser-chrome">
        <div className="page-layout">

          {/* Left panel */}
          <div className="left-panel">
            <div>
              <div className="brand-name">Deline Got'ine Government</div>
              <div className="brand-sub">Student Financial Support Program</div>
              <div className="left-headline">
                <h1>Reset Your Password</h1>
                <p>Choose a new secure password for your DGG Student Portal account.</p>
              </div>
            </div>
            <div className="left-footer">
              <p>(867) 589-3515 ext. 1110</p>
            </div>
          </div>

          {/* Right panel */}
          <div className="right-panel">
            <div className="step-panel active">

              {success ? (
                <>
                  <div className="success-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
                      stroke="#1a1a1a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  </div>
                  <div className="form-title">Password Reset!</div>
                  <div className="form-sub">
                    Your password has been updated successfully. Redirecting you to sign in…
                  </div>
                  <Link to="/signin" className="btn-auth-primary" style={{ display: 'block', textAlign: 'center', textDecoration: 'none' }}>
                    Sign In Now →
                  </Link>
                </>
              ) : (
                <>
                  <div className="form-title">Set New Password</div>
                  <div className="form-sub">
                    Enter your new password below. It must be at least 8 characters.
                  </div>

                  {error && (
                    <div style={{
                      background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b',
                      padding: '12px 16px', borderRadius: '6px', fontSize: '13px', marginBottom: '16px'
                    }}>
                      {error}
                    </div>
                  )}

                  <form onSubmit={handleSubmit}>
                    <div className="field-group">
                      <label className="field-label">New Password</label>
                      <input
                        className="field-input"
                        type="password"
                        placeholder="At least 8 characters"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        required
                        disabled={isLoading || !token}
                        autoFocus
                      />
                    </div>

                    <div className="field-group">
                      <label className="field-label">Confirm New Password</label>
                      <input
                        className="field-input"
                        type="password"
                        placeholder="Repeat your new password"
                        value={confirm}
                        onChange={e => setConfirm(e.target.value)}
                        required
                        disabled={isLoading || !token}
                      />
                    </div>

                    <button
                      className="btn-auth-primary"
                      type="submit"
                      disabled={isLoading || !token || !password || !confirm}
                      style={{ opacity: isLoading ? 0.7 : 1 }}
                    >
                      {isLoading ? 'Resetting…' : 'Reset Password →'}
                    </button>
                  </form>

                  <Link to="/forgot-password" className="back-link">← Request a new link</Link>
                  <Link to="/signin" className="back-link">← Back to Sign In</Link>
                </>
              )}

            </div>
          </div>

        </div>
      </div>
    </div>
  );
};

export default ResetPassword;
