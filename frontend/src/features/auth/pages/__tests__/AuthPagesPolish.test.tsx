import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '@/test/renderWithProviders';
import { SessionExpiredPage } from '../SessionExpiredPage';
import { AccessDeniedPage } from '../AccessDeniedPage';
import { ForgotPasswordPage } from '../ForgotPasswordPage';

describe('authentication page polish', () => {
  it.each([
    ['session expired', <SessionExpiredPage key="session" />, /sign in again/i],
    ['access denied', <AccessDeniedPage key="access" />, /back to sign in/i],
  ])(
    'renders the %s state with mission context and a named action',
    async (_name, page, action) => {
      renderWithProviders(page);

      expect(screen.getByText('The operating system for sustainability.')).toBeVisible();
      expect(screen.getByRole('img', { name: 'The Green Hubs' })).toHaveAttribute(
        'src',
        '/brand/logo-lockup-white-on-forest.png',
      );
      expect(screen.getByRole('button', { name: action })).toBeVisible();
    },
  );

  it('renders the recovery form with labeled controls', () => {
    renderWithProviders(<ForgotPasswordPage />);

    expect(screen.getByRole('heading', { name: /reset your password/i })).toBeVisible();
    expect(screen.getByLabelText(/work email/i)).toHaveAttribute('type', 'email');
    expect(screen.getByRole('button', { name: /send reset link/i })).toBeVisible();
  });
});
