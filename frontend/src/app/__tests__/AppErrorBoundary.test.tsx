import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AppErrorBoundary } from '../AppErrorBoundary';

function Bomb(): never {
  throw new Error('boom');
}

describe('AppErrorBoundary — root white-screen safety net', () => {
  it('renders children normally when nothing throws', () => {
    render(
      <AppErrorBoundary>
        <p>Everything is fine</p>
      </AppErrorBoundary>,
    );
    expect(screen.getByText('Everything is fine')).toBeInTheDocument();
  });

  it('catches a render error above the routed shell and shows a fallback instead of a blank page', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <AppErrorBoundary>
        <Bomb />
      </AppErrorBoundary>,
    );

    expect(screen.getByText('Something went wrong.')).toBeInTheDocument();
    expect(
      screen.getByText(/please reload the page/i),
    ).toBeInTheDocument();

    consoleSpy.mockRestore();
  });
});
