import React from 'react';

export default class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error) {
    // Avoid logging props, user-entered keys, or request payloads.
    console.error('Dashboard rendering failed', { name: error?.name || 'Error' });
  }
  render() {
    if (this.state.failed) {
      return React.createElement('main', { role: 'alert', style: { maxWidth: 640, margin: '12vh auto', padding: 24, fontFamily: 'system-ui' } },
        React.createElement('h1', null, 'The dashboard encountered a problem'),
        React.createElement('p', null, 'Your data has not been confirmed as changed. Reload the dashboard to try again.'),
        React.createElement('button', { onClick: () => window.location.reload() }, 'Reload dashboard'));
    }
    return this.props.children;
  }
}
