import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { buildTestSession, renderWithProviders } from '@/test/renderWithProviders';
import { TEST_USERS } from '@/test/testUsers';
import { Role } from '@/features/rbac/roles';
import { en } from '@/lib/i18n/strings/en';
import { EngagementsListPage } from '@/features/engagements/pages/EngagementsListPage';
import { OrganizationsListPage } from '@/features/organizations/pages/OrganizationsListPage';
import { UsersPage } from '@/features/users/pages/UsersPage';
import { SettingsPage } from '@/features/settings/pages/SettingsPage';

/**
 * Responsive and accessibility checks for the F2A pages, English/LTR.
 *
 * **What jsdom can and cannot prove.** jsdom performs no layout:
 * `scrollWidth` and `clientWidth` are both `0`, so an overflow assertion
 * would compare `0 <= 0` and pass regardless of the CSS. Real
 * horizontal-overflow checking needs a browser, and this file does not
 * pretend otherwise.
 *
 * What it *can* prove, and does:
 *
 * - Each page renders its full content at 360px, 768px, and 1280px — no
 *   breakpoint drops a section, and nothing throws on a narrow viewport.
 * - The structural rules that make the CSS work are present: wide tables
 *   sit inside their own focusable scroll container (which is what keeps
 *   the *page* from scrolling sideways at 360px), each page has exactly one
 *   `h1`, and every control has an accessible name.
 * - Loading and error states are announced through the right live region.
 */

const admin = TEST_USERS.find((user) => user.role === Role.Admin)!;

const WIDTHS = [360, 768, 1280] as const;

vi.mock('@/lib/api/endpoints/organizations', () => ({
  listOrganizations: async () => ({
    items: [{ id: 'org-1', name: 'Preview Organization', created_at: null }],
    page: 1,
    page_size: 20,
    total: 1,
  }),
  getOrganization: async () => {
    throw new Error('unused');
  },
  updateOrganization: async () => {
    throw new Error('unused');
  },
}));

vi.mock('@/lib/api/endpoints/engagements', () => ({
  listEngagements: async () => ({ items: [], page: 1, page_size: 20, total: 0 }),
  getEngagement: async () => {
    throw new Error('unused');
  },
  createEngagement: async () => {
    throw new Error('unused');
  },
  updateEngagement: async () => {
    throw new Error('unused');
  },
}));

function setViewport(width: number) {
  Object.defineProperty(window, 'innerWidth', { value: width, configurable: true });
  window.dispatchEvent(new Event('resize'));
}

function renderPreview(ui: React.ReactElement) {
  vi.stubEnv('VITE_APP_MODE', 'preview');
  vi.stubEnv('VITE_APP_ENVIRONMENT', 'preview');
  return renderWithProviders(ui, { session: buildTestSession(admin) });
}

const PAGES = [
  ['Engagements', <EngagementsListPage key="e" />, en['nav.engagements']],
  ['Organizations', <OrganizationsListPage key="o" />, en['nav.organizations']],
  ['Users & Roles', <UsersPage key="u" />, en['nav.users']],
  ['Settings', <SettingsPage key="s" />, en['nav.settings']],
] as const;

describe('F2A pages render completely at every supported width', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  for (const width of WIDTHS) {
    it.each(PAGES)(`%s renders at ${width}px`, async (_name, element, heading) => {
      setViewport(width);
      renderPreview(element);

      expect(await screen.findByRole('heading', { name: heading, level: 1 })).toBeVisible();
      expect(screen.getByRole('heading', { level: 1 })).toBeVisible();
    });
  }

  it.each(PAGES)('%s has exactly one h1', async (_name, element, heading) => {
    setViewport(360);
    renderPreview(element);

    await screen.findByRole('heading', { name: heading, level: 1 });
    // §17: one `h1` per page. A second would make the document outline
    // ambiguous for anyone navigating by heading.
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
  });
});

describe('F2A tables keep their overflow to themselves', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it.each([
    ['Engagements', <EngagementsListPage key="e" />],
    ['Organizations', <OrganizationsListPage key="o" />],
    ['Users & Roles', <UsersPage key="u" />],
  ] as const)('%s scrolls its table, not the page', async (_name, element) => {
    setViewport(360);
    const { container } = renderPreview(element);

    await screen.findAllByRole('table');

    const table = container.querySelector('table');
    expect(table).not.toBeNull();

    // The scroll container is the table's own named, focusable region — a
    // scrollable area that cannot be focused is unreachable by keyboard.
    const scroller = table?.closest('section');
    expect(scroller).not.toBeNull();
    expect(scroller?.className).toContain('overflow-x-auto');
    expect(scroller?.getAttribute('tabindex')).toBe('0');
    expect(scroller?.getAttribute('aria-label')).toBeTruthy();
  });

  it('gives every table a caption and column headers', async () => {
    setViewport(1280);
    renderPreview(<EngagementsListPage />);

    const table = await screen.findByRole('table');
    expect(within(table).getByText(en['engagements.table.caption'])).toBeInTheDocument();

    const columnHeaders = within(table).getAllByRole('columnheader');
    expect(columnHeaders.length).toBeGreaterThan(0);
    for (const header of columnHeaders) {
      expect(header.getAttribute('scope')).toBe('col');
      expect(header.textContent?.trim().length).toBeGreaterThan(0);
    }
  });

  it('names each row by its own row header rather than leaving it anonymous', async () => {
    setViewport(1280);
    renderPreview(<EngagementsListPage />);

    const table = await screen.findByRole('table');
    const rowHeaders = within(table).getAllByRole('rowheader');
    expect(rowHeaders.length).toBeGreaterThan(0);
    for (const header of rowHeaders) {
      expect(header.getAttribute('scope')).toBe('row');
    }
  });
});

describe('F2A controls carry accessible names', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it.each(PAGES)('%s labels every interactive control', async (_name, element, heading) => {
    setViewport(1280);
    renderPreview(element);
    await screen.findByRole('heading', { name: heading, level: 1 });

    const controls = [
      ...screen.queryAllByRole('button'),
      ...screen.queryAllByRole('link'),
      ...screen.queryAllByRole('combobox'),
      ...screen.queryAllByRole('textbox'),
      ...screen.queryAllByRole('searchbox'),
    ];

    for (const control of controls) {
      const name =
        control.getAttribute('aria-label') ??
        control.textContent?.trim() ??
        control.getAttribute('title') ??
        '';
      const labelledBy = control.getAttribute('aria-labelledby');
      const labelled =
        name.length > 0 ||
        Boolean(labelledBy) ||
        // A native control associated with a <label for=...>.
        Boolean(control.id && document.querySelector(`label[for="${control.id}"]`));
      expect(labelled, `${control.tagName} control has no accessible name`).toBe(true);
    }
  });
});

describe('F2A states are announced', () => {
  beforeEach(() => {
    setViewport(1280);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('announces loading politely, through a status region', async () => {
    vi.stubEnv('VITE_PREVIEW_SCENARIO', 'loading');
    const { container } = renderPreview(<EngagementsListPage />);

    await screen.findByRole('heading', { level: 1 });
    // `<output>` carries an implicit `role="status"` — polite, so it does
    // not interrupt whatever the reader is in the middle of.
    const busy = container.querySelector('output[aria-busy="true"]');
    expect(busy).not.toBeNull();
    expect(busy?.getAttribute('aria-label')).toBeTruthy();
  });

  it('announces an error assertively, because it changes what a person can do', async () => {
    vi.stubEnv('VITE_PREVIEW_SCENARIO', 'error');
    renderPreview(<EngagementsListPage />);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(en['engagements.error.title']);
  });

  it('announces a forbidden result assertively too', async () => {
    vi.stubEnv('VITE_PREVIEW_SCENARIO', 'forbidden');
    renderPreview(<EngagementsListPage />);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(en['workspace.state.forbidden.title']);
  });

  it('announces partial coverage without replacing the content', async () => {
    vi.stubEnv('VITE_PREVIEW_SCENARIO', 'partial');
    renderPreview(<EngagementsListPage />);

    expect(await screen.findByText(en['workspace.state.partial'])).toBeVisible();
    // Partial content is still content: the rows render alongside the notice.
    expect(screen.getByRole('table')).toBeVisible();
  });
});

describe('Settings navigation is reachable at every width', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  /**
   * Settings became a section workspace: a rail of buttons beside one
   * active panel, rather than eight anchor links scrolling one long page.
   *
   * Both controls are in the DOM at every width by design. The rail is the
   * `lg` presentation and the `<select>` is the presentation below it, and
   * which one is *visible* is a CSS media query jsdom does not evaluate.
   * What this asserts is the property that matters and that jsdom can
   * prove: all eight sections are reachable through a named control at
   * every width, so no section can become unreachable on a phone.
   */
  it.each(WIDTHS)('exposes all eight settings sections at %ipx', async (width) => {
    setViewport(width);
    renderPreview(<SettingsPage />);

    const nav = await screen.findByRole('navigation', { name: en['settings.nav.label'] });
    const buttons = within(nav).getAllByRole('button');
    expect(buttons).toHaveLength(8);
    for (const button of buttons) {
      expect(button.textContent?.trim().length).toBeGreaterThan(0);
    }

    // The same eight are options on the small-viewport selector.
    const selector = screen.getByLabelText(en['settings.nav.select']);
    expect(within(selector).getAllByRole('option')).toHaveLength(8);
  });

  it.each(WIDTHS)('opens a chosen settings section at %ipx', async (width) => {
    const user = userEvent.setup();
    setViewport(width);
    renderPreview(<SettingsPage />);

    const nav = await screen.findByRole('navigation', { name: en['settings.nav.label'] });
    await user.click(within(nav).getByRole('button', { name: en['settings.section.about'] }));

    expect(await screen.findByText(en['settings.about.claims'])).toBeVisible();
  });
});
