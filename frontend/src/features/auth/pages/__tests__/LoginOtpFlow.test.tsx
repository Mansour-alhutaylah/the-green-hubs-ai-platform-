import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/renderWithProviders';
import { mockAuthService, DEV_OTP_CODE } from '@/features/auth/services/mockAuthService';
import { DEMO_PASSWORD, DEMO_USERS } from '@/features/auth/services/demoUsers';
import { Role } from '@/features/rbac/roles';
import { AppRoutes } from '@/app/router/routes';

describe('Login -> OTP -> Dashboard flow', () => {
  it('signs a demo user in end to end and lands on the dashboard', async () => {
    const user = userEvent.setup();
    const viewer = DEMO_USERS.find((demoUser) => demoUser.role === Role.Viewer);
    if (!viewer) throw new Error('No Viewer demo user seeded');

    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/login'],
      authService: mockAuthService,
    });

    await screen.findByRole('heading', { name: /welcome back/i });
    expect(screen.getByRole('checkbox', { name: /remember me/i })).toBeChecked();

    await user.type(screen.getByLabelText(/work email/i), viewer.email);
    await user.type(screen.getByLabelText(/^password$/i), DEMO_PASSWORD);
    await user.click(screen.getByRole('button', { name: /^sign in$/i }));

    const otpCells = await screen.findAllByLabelText(/Digit \d of 6/);
    expect(otpCells).toHaveLength(6);
    for (let i = 0; i < DEV_OTP_CODE.length; i += 1) {
      await user.type(otpCells[i]!, DEV_OTP_CODE[i]!);
    }

    // DashboardPage is a lazy-loaded chunk (§7 business modules are
    // code-split) — its dynamic import needs more than the default 1s.
    expect(
      await screen.findByRole('heading', { name: /^dashboard$/i }, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(screen.getByText(new RegExp(viewer.email))).toBeInTheDocument();
  }, 10_000);
});
