import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
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

describe('Settings exposes no infrastructure identifier', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('renders none of the configured hosts, projects, or keys', async () => {
    const { container } = renderSettings();
    await screen.findByRole('heading', { name: en['settings.about.title'] });

    const markup = container.innerHTML;
    for (const fragment of FORBIDDEN_FRAGMENTS) {
      expect(markup, `Settings must not render "${fragment}"`).not.toContain(fragment);
    }
  });

  it('reports configuration as a boolean rather than a value', async () => {
    renderSettings();
    await screen.findByRole('heading', { name: en['settings.about.title'] });

    expect(screen.getByText(en['settings.about.api'])).toBeVisible();
    expect(screen.getByText(en['settings.about.auth'])).toBeVisible();
    // "Configured" — never the thing that was configured.
    expect(screen.getAllByText(en['settings.about.configured']).length).toBeGreaterThan(0);
  });

  it('states that residency metadata is not published, rather than naming a region', async () => {
    renderSettings();

    expect(await screen.findByText(en['settings.residency.unavailable.title'])).toBeVisible();
    expect(screen.getByText(en['settings.residency.unavailable.description'])).toBeVisible();

    // No region, jurisdiction, or provider is claimed anywhere on the page.
    for (const pattern of [/riyadh/i, /eu-west/i, /us-east/i, /frankfurt/i, /aws\b/i, /gcp\b/i]) {
      expect(screen.queryByText(pattern)).toBeNull();
    }
  });

  it('states plainly that multi-factor authentication is not implemented, with no control', async () => {
    renderSettings();

    expect(await screen.findByText(en['settings.security.mfa.description'])).toBeVisible();

    // The mock OTP flow a previous audit removed is not restored.
    expect(screen.queryByRole('button', { name: /enable.*(mfa|two-factor|2fa)/i })).toBeNull();
    expect(screen.queryByRole('switch')).toBeNull();
    expect(screen.queryByText(/verification code/i)).toBeNull();
  });

  it('shows the real authenticated identity and the existing sign-out action', async () => {
    renderSettings();

    expect(await screen.findByText(LIVE_USER_NAME, undefined)).toBeVisible();
    expect(screen.getAllByText(LIVE_USER_EMAIL).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: en['settings.security.signOut'] })).toBeVisible();
  });

  it('describes integrations as capabilities, with nothing configurable and no provider named', async () => {
    renderSettings();

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
    renderSettings();
    await screen.findByRole('heading', { name: en['settings.about.title'] });

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
    renderSettings();

    expect(await screen.findByText(en['settings.about.version.unstamped'])).toBeVisible();
  });
});
