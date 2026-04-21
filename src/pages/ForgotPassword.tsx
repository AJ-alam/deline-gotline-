import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import '../styles/auth.css';

const ForgotPassword: React.FC = () => {
  const [step, setStep] = useState(1);
  const [contactInfo, setContactInfo] = useState('');

  const handleSendLink = (e: React.FormEvent) => {
    e.preventDefault();
    if (contactInfo.trim()) {
      setStep(2);
    }
  };

  return (
    <div className="auth-root">
      <div className="browser-chrome">
        <div className="page-layout">
          {/* Left dark panel */}
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
              <p>(867) 589-3515 ext. 1110</p>
            </div>
          </div>

          {/* Right panel */}
          <div className="right-panel">
            {step === 1 ? (
              <div className="step-panel active">
                <div className="form-title">Forgot Password</div>
                <div className="form-sub">
                  Enter the email or phone number linked to your account and we'll send you a reset link.
                </div>

                <form onSubmit={handleSendLink}>
                  <div className="field-group">
                    <label className="field-label">Email or Phone Number</label>
                    <input
                      className="field-input"
                      type="text"
                      placeholder="Enter email or phone number"
                      value={contactInfo}
                      onChange={(e) => setContactInfo(e.target.value)}
                      required
                    />
                  </div>

                  <button className="btn-auth-primary" type="submit">
                    Send Reset Link &nbsp;→
                  </button>
                </form>

                <Link to="/signin" className="back-link">
                  ← Back to Sign In
                </Link>

                <div className="help-text" style={{ lineHeight: 1.5 }}>
                  Need help or can't access your phone/email?<br />
                  <a href="mailto:education.support@gov.deline.ca">Contact Student Support Worker</a><br />
                  or call <strong>(867) 589-3515 ext. 1110</strong> for manual verification.
                </div>
              </div>
            ) : (
              <div className="step-panel active">
                <div className="success-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#1a1a1a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>

                <div className="form-title">Check your inbox</div>
                <div className="form-sub">
                  We've sent a password reset link to <strong>{contactInfo}</strong>
                </div>

                <div className="info-box">
                  Didn't receive it? Check your spam folder, or make sure the email or phone number matches what's on your account.
                  The link expires in <strong>30 minutes</strong>.
                </div>

                <button className="btn-auth-primary" onClick={() => setStep(1)} type="button">
                  Try a Different Address &nbsp;→
                </button>

                <Link to="/signin" className="back-link">
                  ← Back to Sign In
                </Link>

                <div className="help-text" style={{ lineHeight: 1.5 }}>
                  Need help or can't access your phone/email?<br />
                  <a href="mailto:education.support@gov.deline.ca">Contact Student Support Worker</a><br />
                  or call <strong>(867) 589-3515 ext. 1110</strong> for manual verification.
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ForgotPassword;
