import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class AdminErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    // Update state so the next render will show the fallback UI.
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error in Admin Dashboard:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div style={{ 
            display: 'flex', 
            flexDirection: 'column', 
            alignItems: 'center', 
            justifyContent: 'center', 
            height: '100vh', 
            padding: '24px',
            textAlign: 'center',
            background: '#fff',
            fontFamily: 'system-ui, -apple-system, sans-serif'
        }}>
          <div style={{ 
              fontSize: '48px', 
              marginBottom: '16px' 
          }}>⚠️</div>
          <h2 style={{ 
              fontSize: '20px', 
              fontWeight: '800', 
              color: '#d32f2f', 
              marginBottom: '12px' 
          }}>
            Dashboard Rendering Error
          </h2>
          <p style={{ 
              fontSize: '14px', 
              color: '#64748b', 
              maxWidth: '400px', 
              lineHeight: '1.6',
              marginBottom: '24px'
          }}>
            The administrative dashboard encountered a runtime error. This is often caused by missing profile data or a role mismatch.
          </p>
          
          <div style={{ 
              padding: '16px', 
              background: '#f8fafc', 
              borderRadius: '8px', 
              border: '1px solid #e2e8f0',
              fontFamily: 'monospace',
              fontSize: '12px',
              color: '#1e293b',
              marginBottom: '32px',
              width: '100%',
              maxWidth: '500px',
              overflow: 'auto'
          }}>
             {this.state.error?.toString()}
          </div>

          <button 
            onClick={() => window.location.href = '/internal/login'}
            style={{ 
                background: '#1e293b', 
                color: '#fff', 
                border: 'none', 
                padding: '10px 24px', 
                borderRadius: '6px', 
                fontWeight: '600', 
                cursor: 'pointer' 
            }}
          >
            Return to Login
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default AdminErrorBoundary;
