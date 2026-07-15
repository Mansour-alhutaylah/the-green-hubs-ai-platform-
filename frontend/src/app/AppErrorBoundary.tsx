import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';

interface AppErrorBoundaryProps {
  children: ReactNode;
}

interface AppErrorBoundaryState {
  error: Error | null;
}

/**
 * Root-level safety net above `<App/>`. `RouteErrorBoundary` only wraps the
 * routed `<Outlet/>` inside `AppShell`, so any error thrown above that point
 * (providers, guards, the shell itself, or the public auth pages) had
 * nothing to catch it and white-screened the whole app. Deliberately
 * dependency-free (no design system imports, no i18n) so it can never
 * itself fail to render.
 */
export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('App render error:', error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            display: 'flex',
            minHeight: '100vh',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '24px',
            fontFamily: 'sans-serif',
            textAlign: 'center',
          }}
        >
          <div>
            <p style={{ fontSize: '18px', fontWeight: 700, color: '#122618' }}>
              Something went wrong.
            </p>
            <p style={{ marginTop: '8px', fontSize: '14px', color: '#66706b' }}>
              Please reload the page. If the problem continues, contact support.
            </p>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
