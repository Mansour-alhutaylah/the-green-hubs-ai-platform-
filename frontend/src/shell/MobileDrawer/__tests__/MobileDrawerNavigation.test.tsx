import { beforeEach, describe, expect, it } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AppRoutes } from '@/app/router/routes';
import { Role } from '@/features/rbac/roles';
import { TEST_USERS } from '@/test/testUsers';
import { buildTestSession, renderWithProviders } from '@/test/renderWithProviders';
// Vite's `?raw` import — reads the real token file without pulling Node
// APIs (and their types) into the app tsconfig.
import tokensCss from '@/styles/tokens.css?raw';

/**
 * Regression cover for the real iPhone defect: the drawer's Content carried
 * `--z-rail` (40) while its own backdrop carried `--z-overlay` (50), so the
 * backdrop painted over the drawer and every tap on a nav item was routed
 * to the backdrop — which Radix treats as an outside-click and dismisses
 * on. The drawer closed instead of navigating.
 *
 * jsdom performs no layout or paint, so it CANNOT reproduce the hit-testing
 * failure itself — a click dispatched at a link in jsdom always reaches
 * that link regardless of what covers it. The stacking invariant is
 * therefore asserted directly (token order + which token each element
 * uses); the behavioral tests below cover everything else.
 */

const MOBILE_WIDTH = 390;

function setViewport(width: number) {
  Object.defineProperty(window, 'innerWidth', { value: width, configurable: true });
  window.dispatchEvent(new Event('resize'));
}

function renderShell(initialPath = '/dashboard') {
  const admin = TEST_USERS.find((user) => user.role === Role.Admin);
  if (!admin) throw new Error('No Admin demo user seeded');
  return renderWithProviders(<AppRoutes />, {
    initialEntries: [initialPath],
    session: buildTestSession(admin),
  });
}

async function openDrawer(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('button', { name: /open navigation/i }));
  return await screen.findByTestId('mobile-drawer');
}

describe('MobileDrawer — stacking invariant (the actual defect)', () => {
  it('keeps the drawer surface above its own backdrop in the token scale', () => {
    const read = (name: string) => {
      const match = new RegExp(`--z-${name}:\\s*(\\d+)`).exec(tokensCss);
      if (!match) throw new Error(`--z-${name} not found in tokens.css`);
      return Number(match[1]);
    };

    // The invariant that was violated: a surface rendered above a backdrop
    // must outrank the backdrop.
    expect(read('dialog')).toBeGreaterThan(read('overlay'));
    // ...and --z-rail must NOT be used for such a surface.
    expect(read('rail')).toBeLessThan(read('overlay'));
  });

  it('renders the drawer on the dialog token and the backdrop on the overlay token', async () => {
    setViewport(MOBILE_WIDTH);
    const user = userEvent.setup();
    renderShell();

    const drawer = await openDrawer(user);
    const overlay = screen.getByTestId('mobile-drawer-overlay');

    expect(drawer.className).toContain('z-[var(--z-dialog)]');
    expect(drawer.className).not.toContain('z-[var(--z-rail)]');
    expect(overlay.className).toContain('z-[var(--z-overlay)]');
  });
});

describe('MobileDrawer — navigation and dismissal', () => {
  beforeEach(() => {
    setViewport(MOBILE_WIDTH);
  });

  it('opens the drawer from the Context Bar trigger', async () => {
    const user = userEvent.setup();
    renderShell();

    const trigger = await screen.findByRole('button', { name: /open navigation/i });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');

    await user.click(trigger);
    expect(await screen.findByTestId('mobile-drawer')).toBeVisible();
  });

  it.each([
    ['Documents', /^documents$/i, /^documents$/i],
    ['Upload', /^upload$/i, /^upload$/i],
    ['Analysis', /^analysis$/i, /^analysis$/i],
  ])(
    'tapping %s navigates, closes the drawer, and leaves no overlay behind',
    async (_label, linkName, headingName) => {
      const user = userEvent.setup();
      renderShell();

      const drawer = await openDrawer(user);
      await user.click(within(drawer).getByRole('link', { name: linkName }));

      expect(
        await screen.findByRole('heading', { name: headingName }),
      ).toBeVisible();
      await waitFor(() => expect(screen.queryByTestId('mobile-drawer')).not.toBeInTheDocument());
      expect(screen.queryByTestId('mobile-drawer-overlay')).not.toBeInTheDocument();
      expect(screen.getByRole('main')).not.toBeEmptyDOMElement();
    },
  );

  it('tapping Dashboard from another page navigates and closes the drawer', async () => {
    const user = userEvent.setup();
    renderShell('/documents');

    const drawer = await openDrawer(user);
    await user.click(within(drawer).getByRole('link', { name: /^dashboard$/i }));

    expect(
      await screen.findByRole('heading', { name: /^dashboard$/i }),
    ).toBeVisible();
    await waitFor(() => expect(screen.queryByTestId('mobile-drawer')).not.toBeInTheDocument());
  });

  it('closes the drawer even when tapping the page already open', async () => {
    const user = userEvent.setup();
    renderShell('/dashboard');

    const drawer = await openDrawer(user);
    await user.click(within(drawer).getByRole('link', { name: /^dashboard$/i }));

    await waitFor(() => expect(screen.queryByTestId('mobile-drawer')).not.toBeInTheDocument());
    expect(screen.getByRole('heading', { name: /^dashboard$/i })).toBeVisible();
  });

  it('navigates to a Coming Soon route and closes the drawer', async () => {
    const user = userEvent.setup();
    renderShell();

    const drawer = await openDrawer(user);
    await user.click(within(drawer).getByRole('link', { name: /carbon intelligence/i }));

    expect(
      await screen.findByRole('heading', { name: /carbon intelligence/i }),
    ).toBeVisible();
    await waitFor(() => expect(screen.queryByTestId('mobile-drawer')).not.toBeInTheDocument());
    expect(screen.queryByTestId('mobile-drawer-overlay')).not.toBeInTheDocument();
  });

  it('closes when the backdrop is tapped', async () => {
    const user = userEvent.setup();
    renderShell();

    await openDrawer(user);
    await user.click(screen.getByTestId('mobile-drawer-overlay'));

    await waitFor(() => expect(screen.queryByTestId('mobile-drawer')).not.toBeInTheDocument());
    expect(screen.getByRole('heading', { name: /^dashboard$/i })).toBeVisible();
  });

  it('closes from the explicit close control', async () => {
    const user = userEvent.setup();
    renderShell();

    const drawer = await openDrawer(user);
    const close = within(drawer).getByRole('button', { name: /close navigation/i });
    expect(close).toBeVisible();

    await user.click(close);
    await waitFor(() => expect(screen.queryByTestId('mobile-drawer')).not.toBeInTheDocument());
  });

  it('closes on Escape', async () => {
    const user = userEvent.setup();
    renderShell();

    await openDrawer(user);
    await user.keyboard('{Escape}');

    await waitFor(() => expect(screen.queryByTestId('mobile-drawer')).not.toBeInTheDocument());
  });

  it('reopens normally after navigating through it', async () => {
    const user = userEvent.setup();
    renderShell();

    const drawer = await openDrawer(user);
    await user.click(within(drawer).getByRole('link', { name: /^documents$/i }));
    expect(
      await screen.findByRole('heading', { name: /^documents$/i }),
    ).toBeVisible();
    await waitFor(() => expect(screen.queryByTestId('mobile-drawer')).not.toBeInTheDocument());

    const reopened = await openDrawer(user);
    expect(reopened).toBeVisible();
    expect(within(reopened).getByRole('link', { name: /^analysis$/i })).toBeVisible();
  });

  it('gives the trigger and close control accessible names, and keeps the backdrop unfocusable', async () => {
    const user = userEvent.setup();
    renderShell();

    const drawer = await openDrawer(user);
    expect(within(drawer).getByRole('button', { name: /close navigation/i })).toBeInTheDocument();

    const overlay = screen.getByTestId('mobile-drawer-overlay');
    expect(overlay).not.toHaveAttribute('tabindex');
    expect(overlay.tagName).not.toBe('BUTTON');
  });
});

describe('responsive nav mode across target viewports', () => {
  // jsdom does no layout, so this cannot detect visual overflow or
  // clipping. It verifies the one thing that IS observable: which
  // navigation affordance the shell hands the user at each width, and that
  // the routed page still renders there.
  it.each([
    [360, 'drawer'],
    [375, 'drawer'],
    [390, 'drawer'],
    [430, 'drawer'],
    [767, 'drawer'],
    [768, 'rail'],
    [1024, 'rail'],
    [1280, 'rail'],
    [1440, 'rail'],
  ] as const)('offers the %s-px viewport the %s', async (width, affordance) => {
    setViewport(width);
    renderShell();

    expect(
      await screen.findByRole('heading', { name: /^dashboard$/i }),
    ).toBeVisible();

    const triggers = screen.queryAllByRole('button', { name: /open navigation/i });
    expect(triggers).toHaveLength(affordance === 'drawer' ? 1 : 0);
    // Queried by href, not by name: between 768px and 1279px the rail is in
    // its collapsed icon-only state, where the link carries no accessible
    // name (a pre-existing desktop-rail gap, out of scope for this mobile
    // fix — see the report).
    expect(document.querySelectorAll('a[href="/documents"]').length).toBeGreaterThan(
      affordance === 'rail' ? 0 : -1,
    );
    expect(screen.getByRole('main')).not.toBeEmptyDOMElement();
  });

  it.each(['/dashboard', '/documents', '/documents/upload', '/analysis', '/reports', '/settings'])(
    'renders %s at 390px with the drawer trigger reachable',
    async (path) => {
      setViewport(390);
      renderShell(path);

      expect(
        await screen.findByRole('button', { name: /open navigation/i }),
      ).toBeVisible();
      expect(screen.getByRole('main')).not.toBeEmptyDOMElement();
    },
  );
});

describe('MobileDrawer — desktop is unaffected', () => {
  it('renders no drawer trigger and no drawer at desktop width', async () => {
    setViewport(1440);
    renderShell();

    expect(
      await screen.findByRole('heading', { name: /^dashboard$/i }),
    ).toBeVisible();
    expect(screen.queryByRole('button', { name: /open navigation/i })).not.toBeInTheDocument();
    expect(screen.queryByTestId('mobile-drawer')).not.toBeInTheDocument();
    // The Command Rail still owns navigation on desktop.
    expect(screen.getByRole('link', { name: /^documents$/i })).toBeVisible();
  });
});
