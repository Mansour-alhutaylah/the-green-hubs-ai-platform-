import { afterEach, describe, expect, it, vi } from 'vitest';

describe('supabase client configuration', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it('returns null and a clear, secret-free error when required env vars are absent', async () => {
    vi.stubEnv('VITE_SUPABASE_URL', '');
    vi.stubEnv('VITE_SUPABASE_ANON_KEY', '');

    const { getSupabaseClient, isSupabaseConfigured, getSupabaseConfigError } = await import(
      '../client'
    );

    expect(isSupabaseConfigured()).toBe(false);
    expect(getSupabaseClient()).toBeNull();
    expect(getSupabaseConfigError()).toMatch(/VITE_SUPABASE_URL/);
    expect(getSupabaseConfigError()).toMatch(/VITE_SUPABASE_ANON_KEY/);
  });

  it('builds a singleton client once configured, never requiring the service-role key', async () => {
    vi.stubEnv('VITE_SUPABASE_URL', 'https://example.supabase.co');
    vi.stubEnv('VITE_SUPABASE_ANON_KEY', 'anon-key-value');

    const { getSupabaseClient, isSupabaseConfigured } = await import('../client');

    expect(isSupabaseConfigured()).toBe(true);
    const first = getSupabaseClient();
    const second = getSupabaseClient();
    expect(first).not.toBeNull();
    expect(first).toBe(second);
  });

  it('Preview mode does not require Supabase configuration to be present', async () => {
    vi.stubEnv('VITE_SUPABASE_URL', '');
    vi.stubEnv('VITE_SUPABASE_ANON_KEY', '');
    vi.stubEnv('VITE_APP_MODE', 'preview');
    vi.stubEnv('VITE_APP_ENVIRONMENT', 'preview');

    const { getSupabaseClient } = await import('../client');
    const { isPreviewMode } = await import('@/lib/data/source');

    expect(isPreviewMode()).toBe(true);
    expect(getSupabaseClient()).toBeNull();
  });
});
