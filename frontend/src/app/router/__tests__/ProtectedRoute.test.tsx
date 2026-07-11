import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '@/test/renderWithProviders';
import { AppRoutes } from '../routes';

describe('ProtectedRoute', () => {
  it('redirects an unauthenticated user hitting a protected deep link to /login', async () => {
    renderWithProviders(<AppRoutes />, { initialEntries: ['/documents'], session: null });

    expect(
      await screen.findByRole('heading', { name: /sign in to your hub/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/this module ships/i)).not.toBeInTheDocument();
  });
});
