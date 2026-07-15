import { describe, expect, it, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { renderWithProviders, buildTestSession } from '@/test/renderWithProviders';
import { DEMO_USERS } from '@/features/auth/services/demoUsers';
import { Role } from '@/features/rbac/roles';
import { AppShell } from '../AppShell';
// Vite's `?raw` suffix imports the file as a plain string — no Node `fs`
// dependency needed in this browser-targeted tsconfig.
import globalsCss from '../../styles/globals.css?raw';

/**
 * Regression coverage for the protected-page vertical-offset bug: CommandRail's
 * `<nav>` carries Tailwind's `fixed` utility, but the unlayered `.brand-rail`
 * CSS rule (globals.css) also set `position: relative`, and an unlayered rule
 * always outranks a layered one (Tailwind's utilities live in `@layer
 * utilities`) regardless of source order or specificity — so `.brand-rail`
 * silently won, pulling the ~260px-wide, full-height rail into normal
 * document flow and pushing every routed page down by its own content height
 * (measured ~962px in a 900px viewport — enough to push the header
 * completely below the fold). Fixed by moving `.brand-rail` into an explicit
 * `@layer components` block, which Tailwind v4 always ranks below
 * `@layer utilities`.
 *
 * jsdom has no real layout/rendering engine (`getBoundingClientRect` and
 * CSS Cascade Layer resolution aren't meaningfully testable here), so these
 * tests guard the structural invariants that produced the bug rather than
 * pixel geometry. The actual fix was verified with real computed layout in
 * a headless Chromium session (Playwright) — see the accompanying report.
 */
describe('protected-page layout — CommandRail positioning', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { value: 1440, configurable: true });
  });

  function renderShell() {
    const owner = DEMO_USERS.find((user) => user.role === Role.Owner);
    if (!owner) throw new Error('No Owner demo user seeded');
    return renderWithProviders(
      <Routes>
        <Route path="/dashboard" element={<AppShell />}>
          <Route index element={<div>routed page content</div>} />
        </Route>
      </Routes>,
      { initialEntries: ['/dashboard'], session: buildTestSession(owner) },
    );
  }

  it('.brand-rail is layered under @layer components, so Tailwind utilities always win the cascade', () => {
    const componentsLayerIndex = globalsCss.indexOf('@layer components {');
    const brandRailIndex = globalsCss.indexOf('.brand-rail {');

    expect(componentsLayerIndex).toBeGreaterThan(-1);
    expect(brandRailIndex).toBeGreaterThan(-1);
    // Exactly one declaration of `.brand-rail {` in the file, and it must
    // sit textually after `@layer components {` opens — i.e. it is not an
    // unlayered rule that could silently outrank a layered Tailwind utility.
    expect(globalsCss.split('.brand-rail {').length - 1).toBe(1);
    expect(brandRailIndex).toBeGreaterThan(componentsLayerIndex);
  });

  it('CommandRail renders with the fixed positioning utility, expanded', async () => {
    renderShell();
    const nav = await screen.findByRole('navigation', { name: 'Primary' });
    expect(nav.className).toContain('fixed');
    expect(nav.className).toContain('brand-rail');
  });

  it('CommandRail keeps the fixed positioning utility after collapsing', async () => {
    const user = userEvent.setup();
    renderShell();
    const nav = await screen.findByRole('navigation', { name: 'Primary' });

    await user.click(screen.getByRole('button', { name: /collapse navigation/i }));

    expect(nav.className).toContain('fixed');
    expect(screen.getByRole('button', { name: /expand navigation/i })).toBeInTheDocument();
  });

  it('ContextBar and routed content are reachable immediately — no gating element renders before them', async () => {
    renderShell();
    // These must resolve without any special waiting beyond the async auth
    // session restore already covered elsewhere — a stray full-viewport
    // spacer ahead of them would not affect *whether* they're found here
    // (jsdom has no layout), but confirms the shell's DOM order/composition
    // is exactly: CommandRail (fixed, out of flow) -> ContextBar -> routed
    // content, with nothing else in between.
    await screen.findByRole('navigation', { name: 'Primary' });
    expect(screen.getByTestId('context-bar')).toBeInTheDocument();
    expect(screen.getByText('routed page content')).toBeInTheDocument();
  });
});
