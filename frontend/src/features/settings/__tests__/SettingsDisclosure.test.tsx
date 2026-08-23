import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/renderWithProviders';
import { buildLiveAuthService, LIVE_USER_EMAIL, LIVE_USER_NAME } from '@/test/liveSession';
import { en } from '@/lib/i18n/strings/en';
import { SettingsPage } from '../pages/SettingsPage';

/**
 * Settings must not leak infrastructure.
 *
 * The route is reachable by any signed-in Admin, and a Settings screen is
 * exactly where a hostname, a project reference, or a key name gets added
 * "just so operations can see it" and then stays. So this test configures
 * the build with realistic, *distinctive* secret-shaped values and asserts
 * that none of them — nor any fragment of them — reaches the DOM.
 *
 * It also pins the two truthful absences the page must state rather than
 * fill in: data residency, which no product API exposes, and multi-factor
 * authentication, which is not implemented.
 */

vi.mock('@/lib/api/endpoints/organizations', () => ({
  listOrganizations: async () => ({
    items: [{ id: 'org-1', name: 'Authenticated Live Organization', created_at: null }],
    page: 1,
    page_size: 20,
    total: 1,
  }),
}));

const SUPABASE_URL = 'https://abcdefghijklmnop.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.super-secret-anon-key';
const API_BASE_URL = 'https://green-hubs-api-prod-7f3a.onrender.com';

/** Every fragment that would identify a host, project, account, or key. */
const FORBIDDEN_FRAGMENTS = [
  SUPABASE_URL,
  SUPABASE_ANON_KEY,
  API_BASE_URL,
  'abcdefghijklmnop',
  'supabase.co',
  'onrender.com',
  'eyJhbGciOi',
  'postgres',
  'postgresql://',
  'service_role',
  'SERVICE_ROLE',
  'VITE_SUPABASE_URL',
  'VITE_SUPABASE_ANON_KEY',
  'VITE_API_BASE_URL',
  'n8n',
];

function renderSettings() {
  vi.stubEnv('VITE_SUPABASE_URL', SUPABASE_URL);
  vi.stubEnv('VITE_SUPABASE_ANON_KEY', SUPABASE_ANON_KEY);
  vi.stubEnv('VITE_API_BASE_URL', API_BASE_URL);
  return renderWithProviders(<SettingsPage />, { authService: buildLiveAuthService() });
}

/**
 * Settings now renders one section at a time, so a disclosure assertion
 * has to open the section it is about. Every section label, in the order
 * the rail lists them.
 */
const SECTION_LABELS = [
  en['settings.section.overview'],
  en['settings.section.account'],
  en['settings.section.workspace'],
  en['settings.section.language'],
  en['settings.section.security'],
  en['settings.section.residency'],
  en['settings.section.integrations'],
  en['settings.section.about'],
] as const;

async function openSection(user: ReturnType<typeof userEvent.setup>, label: string) {
  const nav = await screen.findByRole('navigation', { name: en['settings.nav.label'] });
  await user.click(within(nav).getByRole('button', { name: label }));
}

describe('Settings exposes no infrastructure identifier', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  /* Stronger than the version this replaced. The page used to render every
     section at once, so one snapshot covered all of them; now that only
     one panel is mounted at a time, the sweep opens all eight in turn and
     checks each. A leak confined to a single section can no longer hide
     behind a section that happens to be closed. */
  it('renders none of the configured hosts, projects, or keys, in any section', async () => {
    const user = userEvent.setup();
    const { container } = renderSettings();
    await screen.findByRole('navigation', { name: en['settings.nav.label'] });

    for (const label of SECTION_LABELS) {
      await openSection(user, label);
      const markup = container.innerHTML;
      for (const fragment of FORBIDDEN_FRAGMENTS) {
        expect(
          markup,
          `Settings section "${label}" must not render "${fragment}"`,
        ).not.toContain(fragment);
      }
    }
  });

  it('reports configuration as a boolean rather than a value', async () => {
    const user = userEvent.setup();
    renderSettings();
    await openSection(user, en['settings.section.about']);

    expect(screen.getByText(en['settings.about.api'])).toBeVisible();
    expect(screen.getByText(en['settings.about.auth'])).toBeVisible();
    // "Configured" — never the thing that was configured.
    expect(screen.getAllByText(en['settings.about.configured']).length).toBeGreaterThan(0);
  });

  it('states that residency metadata is not published, rather than naming a region', async () => {
    const user = userEvent.setup();
    renderSettings();
    await openSection(user, en['settings.section.residency']);

    expect(await screen.findByText(en['settings.residency.unavailable.title'])).toBeVisible();
    expect(screen.getByText(en['settings.residency.unavailable.description'])).toBeVisible();

    // No region, jurisdiction, or provider is claimed anywhere on the page.
    for (const pattern of [/riyadh/i, /eu-west/i, /us-east/i, /frankfurt/i, /aws\b/i, /gcp\b/i]) {
      expect(screen.queryByText(pattern)).toBeNull();
    }
  });

  it('states plainly that multi-factor authentication is not implemented, with no control', async () => {
    const user = userEvent.setup();
    renderSettings();
    await openSection(user, en['settings.section.security']);

    expect(await screen.findByText(en['settings.security.mfa.description'])).toBeVisible();

    // The mock OTP flow a previous audit removed is not restored.
    expect(screen.queryByRole('button', { name: /enable.*(mfa|two-factor|2fa)/i })).toBeNull();
    expect(screen.queryByRole('switch')).toBeNull();
    expect(screen.queryByText(/verification code/i)).toBeNull();
  });

  it('shows the real authenticated identity and the existing sign-out action', async () => {
    const user = userEvent.setup();
    renderSettings();

    await openSection(user, en['settings.section.account']);
    expect(await screen.findByText(LIVE_USER_NAME, undefined)).toBeVisible();
    expect(screen.getAllByText(LIVE_USER_EMAIL).length).toBeGreaterThan(0);

    await openSection(user, en['settings.section.security']);
    expect(screen.getByRole('button', { name: en['settings.security.signOut'] })).toBeVisible();
  });

  it('describes integrations as capabilities, with nothing configurable and no provider named', async () => {
    const user = userEvent.setup();
    renderSettings();
    await openSection(user, en['settings.section.integrations']);

    expect(
      await screen.findByRole(
        'heading',
        { name: en['settings.integrations.title'] },
      ),
    ).toBeVisible();
    expect(screen.getByText(en['settings.integrations.documentStorage'])).toBeVisible();
    expect(
      screen.getAllByText(en['settings.integrations.state.notConfigurable']).length,
    ).toBe(3);

    // No provider name, and nothing that would contact or configure one.
    for (const pattern of [/openai/i, /anthropic/i, /n8n/i, /webhook/i, /api key/i]) {
      expect(screen.queryByText(pattern)).toBeNull();
    }
  });

  it('makes no certification, uptime, or compliance claim', async () => {
    const user = userEvent.setup();
    renderSettings();
    await openSection(user, en['settings.section.about']);

    expect(screen.getByText(en['settings.about.claims'])).toBeVisible();
    // `/uptime/i` alone would match the disclaimer itself, which denies the
    // claim rather than making one — so the patterns below look for an
    // actual assertion.
    for (const pattern of [
      /iso ?27001/i,
      /soc ?2/i,
      /\d+(\.\d+)? ?% uptime/i,
      /gdpr certified/i,
      /certified/i,
    ]) {
      expect(screen.queryByText(pattern)).toBeNull();
    }
  });

  it('states that the build carries no version stamp rather than inventing one', async () => {
    const user = userEvent.setup();
    renderSettings();
    await openSection(user, en['settings.section.about']);

    expect(await screen.findByText(en['settings.about.version.unstamped'])).toBeVisible();
  });
});
