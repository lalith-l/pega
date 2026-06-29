import React from 'react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null });
    // Reload the page to reset the app state
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          background: 'var(--bg-base)',
          color: 'var(--text-primary)',
          fontFamily: 'system-ui, sans-serif'
        }}>
          <div style={{
            background: 'var(--bg-surface)',
            padding: '40px',
            borderRadius: '16px',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5)',
            maxWidth: '500px',
            textAlign: 'center'
          }}>
            <h2 style={{ color: '#fca5a5', marginTop: 0 }}>An error occurred.</h2>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '30px' }}>
              The application encountered an unexpected rendering error. Your case data is still safe in the database.
            </p>
            <button
              onClick={this.handleReload}
              style={{
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.5)',
                color: '#fca5a5',
                padding: '10px 20px',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: 'bold',
                fontSize: '14px'
              }}
            >
              Click here to reload this case
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
