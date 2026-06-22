import React from 'react';
import { useNavigate } from 'react-router-dom';
import '../../styles/auth.css';

interface StandaloneFormWrapperProps {
  children: (props: { onBack: () => void; onComplete: () => void }) => React.ReactNode;
}

const StandaloneFormWrapper: React.FC<StandaloneFormWrapperProps> = ({ children }) => {
  const navigate = useNavigate();

  const handleBack = () => {
    navigate('/signin');
  };

  const handleComplete = () => {
    // In a real app, this would submit to the backend.
    // For now, we'll redirect to a generic success message or back to signin.
    alert('Application submitted successfully! Our staff will review your request.');
    navigate('/signin');
  };

  return (
    <div className="auth-root" style={{ background: '#f8fafc' }}>
      <div className="browser-chrome" style={{ maxWidth: '900px', margin: '0 auto' }}>
        <div className="page-layout" style={{ minHeight: 'auto' }}>
          <div className="right-panel" style={{ padding: '0' }}>
            {children({ onBack: handleBack, onComplete: handleComplete })}
          </div>
        </div>
      </div>
      
      {/* Simple footer for guest forms */}
      <div style={{ position: 'fixed', bottom: '20px', left: 0, right: 0, textAlign: 'center', pointerEvents: 'none' }}>
        <div style={{ display: 'inline-block', padding: '8px 16px', background: 'rgba(255,255,255,0.9)', backdropFilter: 'blur(8px)', borderRadius: '20px', fontSize: '11px', color: '#64748b', border: '1px solid #e2e8f0', boxShadow: '0 4px 12px rgba(0,0,0,0.05)', pointerEvents: 'auto' }}>
          Guest Portal · Deline Got'ı̨nę Government · <button onClick={() => navigate('/signin')} style={{ background: 'none', border: 'none', color: '#e5a662', fontWeight: 600, cursor: 'pointer', padding: 0 }}>Return to Sign In</button>
        </div>
      </div>
    </div>
  );
};

export default StandaloneFormWrapper;
