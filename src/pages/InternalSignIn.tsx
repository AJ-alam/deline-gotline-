import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import API from '../api/client';
import '../styles/auth.css';

const InternalSignIn: React.FC = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [showPassword, setShowPassword] = useState(false);
    const navigate = useNavigate();

    const handleLogin = async () => {
        if (!email || !password) {
            setError('Please enter both email and password.');
            return;
        }

        setIsLoading(true);
        setError(null);

        try {
            const response = await API.login({ email, password }) as any;
            localStorage.setItem('dgg_token', response.access);
            localStorage.setItem('dgg_refresh', response.refresh);
            
            // Fetch profile to verify organizational role
            const user = await API.getMe() as any;
            localStorage.setItem('dgg_role', user.role);

            // Allowed roles for internal portal
            const staffRoles = ['admin', 'staff', 'director'];
            
            if (staffRoles.includes(user.role)) {
                navigate('/staff');
            } else {
                setError('PERMISSION DENIED: This account is registered as a student. Use the Student Portal login instead.');
                localStorage.removeItem('dgg_token');
                localStorage.removeItem('dgg_role');
            }
        } catch (err: any) {
            console.error('Login error:', err);
            const status = err.status || 0;
            if (status === 401) {
                setError('INVALID CREDENTIALS: The email or password provided is incorrect.');
            } else if (status === 403) {
                setError('ACCOUNT INACTIVE: Your administrative access has been suspended.');
            } else {
                setError(err.message || 'SERVER ERROR: Could not connect to authentication services.');
            }
        } finally {
            setIsLoading(false);
        }
    };

    return (
    <div className="auth-root">
      <div className="page-layout">
        <div className="left-panel">
          <div>
            <div className="brand-name">Deline Got'ı̨nę Government</div>
            <div className="brand-sub">Internal Administration Portal</div>
            <div className="left-headline" style={{ marginTop: '56px' }}>
              <h1>Governing with <br/><span style={{ color: 'var(--admin-accent, #e5a662)' }}>Integrity & Vision</span></h1>
              <p>Access the secure administrative suite to manage student financial applications, policy rates, and government reporting.</p>
            </div>
          </div>

          <div className="left-footer">
            <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.5)', textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: '700', marginBottom: '8px' }}>Security Notice</div>
            <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.6)', lineHeight: '1.5' }}>
              This portal is for authorized DGG personnel only. All access and actions are strictly monitored and logged for audit compliance.
            </p>
          </div>
        </div>

        <div className="right-panel">
          <div className="form-title">Internal Access</div>
          <div className="form-sub">Authorized Personnel Only</div>

          {error && (
            <div style={{ background: '#fff2f2', border: '1px solid #ffcccc', color: '#cc0000', padding: '12px', borderRadius: '8px', marginBottom: '24px', fontSize: '12px', fontWeight: '600' }}>
              {error}
            </div>
          )}

          <div className="field-group">
            <label className="field-label" style={{ color: '#64748b' }}>Government ID / Email</label>
            <input 
                className="field-input" 
                type="text" 
                placeholder="e.g. admin@deline.ca" 
                style={{ background: '#fff' }} 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="field-group">
            <label className="field-label" style={{ color: '#64748b' }}>Password</label>
            <div className="password-wrap">
              <input 
                className="field-input" 
                type={showPassword ? "text" : "password"} 
                placeholder="••••••••••••"
                style={{ background: '#fff' }}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button className="pw-toggle" type="button" onClick={() => setShowPassword(!showPassword)} style={{ color: '#64748b' }}>
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
          </div>

          <div style={{ padding: '16px', background: '#f8fafc', borderRadius: '12px', marginBottom: '24px', border: '1px solid #e2e8f0' }}>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              <div style={{ width: '8px', height: '8px', background: '#1a6b3a', borderRadius: '50%' }}></div>
              <span style={{ fontSize: '11px', fontWeight: '800', color: '#1e293b' }}>RSA TOKEN REQUIRED</span>
            </div>
            <p style={{ fontSize: '10px', color: '#64748b', marginTop: '6px', lineHeight: '1.4' }}>Multi-factor authentication (MFA) will be requested on the next step via your government-issued token.</p>
          </div>

          <button 
            className="btn-auth-primary" 
            style={{ background: 'var(--admin-accent, #e5a662)', color: '#111', opacity: isLoading ? 0.7 : 1 }}
            onClick={handleLogin}
            disabled={isLoading}
          >
            {isLoading ? 'VERIFYING...' : 'SECURE ACCESS \u00a0→'}
          </button>

          <Link to="/signin" style={{ display: 'block', textAlign: 'center', marginTop: '24px', fontSize: '12px', color: '#64748b', textDecoration: 'none', fontWeight: '600' }}>
            ← Back to Student Portal
          </Link>
        </div>
      </div>
    </div>
    );
};

export default InternalSignIn;
