import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import API from '../api/client';
import '../styles/auth.css';

const ResetPassword: React.FC = () => {
  const [searchParams]            = useSearchParams();
  const navigate                  = useNavigate();
  const token                     = searchParams.get('token') || '';

  const [password, setPassword]   = useState('');
  const [confirm, setConfirm]     = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [step, setStep]           = useState<1 | 2>(1); // 1 = form, 2 = success

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
      setStep(2);
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
          {/* Left dark panel — identical to ForgotPassword */}
          <div className="left-panel">
            <div>
              <div className="brand-name">Deline Got'ine Government</div>
              <div className="brand-sub">Student Financial Support Program</div>
              <div className="left-headline">
                <h1>Welcome to your Education Portal</h1>
                <p>Apply for funding, track status, manage your support—all in one place.</p>
                <ul className="feature-list">
                  <li>No downloads required</li>
                  <li>Funding calculated automatically</li>
                  <li>Real-time application tracking</li>
                  <li>Progress never lost on disconnect</li>
                </ul>
              </div>
            </div>
            <div className="left-footer">
              <Link to="/signup">Apply for Student Funding</Link>
              <p>(867) 589-3515</p>
            </div>
          </div>

          {/* Right panel */}
          <div className="right-panel">
            {step === 1 ? (
              <div className="step-panel active">
                <div className="form-title">Reset Password</div>
                <div className="form-sub">
                  Enter your new password below. It must be at least 8 characters.
                </div>

                {error && (
                  <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b', padding: '10px 14px', borderRadius: '6px', fontSize: '13px', marginBottom: '12px' }}>
                    {error}
                  </div>
                )}

                <form onSubmit={handleSubmit}>
                  <div className="field-group">
                    <label className="field-label" htmlFor="rp-password">New Password</label>
                    <div style={{ position: 'relative' }}>
                      <input
                        id="rp-password"
                        className="field-input"
                        type={showPassword ? 'text' : 'password'}
                        placeholder="At least 8 characters"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        required
                        disabled={isLoading || !token}
                        autoFocus
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: '#64748b', fontSize: '12px' }}
                      >
                        {showPassword ? 'Hide' : 'Show'}
                      </button>
                    </div>
                  </div>

                  <div className="field-group">
                    <label className="field-label" htmlFor="rp-confirm">Confirm New Password</label>
                    <input
                      id="rp-confirm"
                      className="field-input"
                      type={showPassword ? 'text' : 'password'}
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
                  >
                    {isLoading ? 'Resetting…' : 'Reset Password \u00a0→'}
                  </button>
                </form>

                <Link to="/forgot-password" className="back-link">
                  ← Request a new link
                </Link>

                <div className="help-text" style={{ lineHeight: 1.5 }}>
                  Need help or can't access your account?<br />
                  <a href="mailto:education.support@gov.deline.ca">Contact Student Support Worker</a><br />
                  or call <strong>(867) 589-3515</strong> for manual verification.
                </div>
              </div>
            ) : (
              <div className="step-panel active">
                <div className="success-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#1a1a1a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>

                <div className="form-title">Password Reset!</div>
                <div className="form-sub">
                  Your password has been updated successfully.
                </div>

                <div className="info-box">
                  You will be redirected to Sign In automatically in a few seconds.
                </div>

                <Link to="/signin" className="btn-auth-primary" style={{ display: 'block', textAlign: 'center', textDecoration: 'none' }}>
                  Sign In Now &nbsp;→
                </Link>

                <div className="help-text" style={{ lineHeight: 1.5 }}>
                  Need help or can't access your phone/email?<br />
                  <a href="mailto:education.support@gov.deline.ca">Contact Student Support Worker</a><br />
                  or call <strong>(867) 589-3515</strong> for manual verification.
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ResetPassword;
