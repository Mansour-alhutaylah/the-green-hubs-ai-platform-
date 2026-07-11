import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { EmptyState } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';

function RouteErrorFallback() {
  const { t } = useLocale();
  return (
    <EmptyState
      headingLevel={1}
      title={t('errors.routeCrash.title')}
      description={t('errors.routeCrash.body')}
    />
  );
}

interface RouteErrorBoundaryProps {
  children: ReactNode;
}

interface RouteErrorBoundaryState {
  error: Error | null;
}

/**
 * §14.9 "full failures" pattern applied per-route: a render error inside
 * one routed page (business-module logic, a bad lazy chunk, whatever)
 * shows the module's own failure state — inside the shell, rail and
 * context bar intact — instead of white-screening the whole app. Must be
 * a class component; React has no hook-based error boundary API.
 * AppShell remounts this per pathname (via a `key`) so navigating to a
 * fresh route always gets a clean boundary rather than a stuck error.
 */
export class RouteErrorBoundary extends Component<
  RouteErrorBoundaryProps,
  RouteErrorBoundaryState
> {
  state: RouteErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): RouteErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Phase 1 has no telemetry/error-reporting service wired up yet.
    console.error('Route render error:', error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return <RouteErrorFallback />;
    }
    return this.props.children;
  }
}
