import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  stack: string;
}

/**
 * Catches any render error anywhere in the app.
 *
 * Only the staff dashboard was wrapped before, so a crash in the student
 * dashboard, a form, or the router itself unmounted the whole tree and left a
 * white page with the reason visible only in the browser console. This boundary
 * puts the error on screen where the person hitting it can read it out.
 */
class RootErrorBoundary extends Component<Props, State> {
  public state: State = { hasError: false, error: null, stack: '' };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, stack: '' };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught application error:', error, errorInfo);
    this.setState({ stack: errorInfo.componentStack || '' });
  }

  public render() {
    if (!this.state.hasError) return this.props.children;

    const details = [
      this.state.error?.toString() || 'Unknown error',
      '',
      (this.state.stack || '').split('\n').slice(0, 12).join('\n').trim(),
    ].join('\n');

    return (
      <div style={{
        minHeight: '100vh', padding: '32px 24px', background: '#fff',
        fontFamily: 'system-ui, -apple-system, sans-serif', color: '#1e293b',
      }}>
        <h2 style={{ fontSize: '20px', fontWeight: 800, color: '#b91c1c', marginBottom: '8px' }}>
          Something broke on this page
        </h2>
        <p style={{ fontSize: '14px', color: '#64748b', marginBottom: '20px', maxWidth: '640px', lineHeight: 1.6 }}>
          The page stopped rendering. Copy the details below when reporting this — they name the
          exact component and line that failed.
        </p>
        <pre style={{
          padding: '16px', background: '#f8fafc', border: '1px solid #e2e8f0',
          borderRadius: '8px', fontSize: '12px', lineHeight: 1.5,
          whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          maxWidth: '860px', maxHeight: '40vh', overflow: 'auto', marginBottom: '24px',
        }}>{details}</pre>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <button
            onClick={() => { navigator.clipboard?.writeText(details); }}
            style={{ background: '#fff', color: '#1e293b', border: '1px solid #cbd5e1', padding: '10px 20px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}
          >Copy details</button>
          <button
            onClick={() => window.location.reload()}
            style={{ background: '#1e293b', color: '#fff', border: 'none', padding: '10px 20px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}
          >Reload page</button>
        </div>
      </div>
    );
  }
}

export default RootErrorBoundary;
