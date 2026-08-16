import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * Preview authentication must be inert.
 *
 * The audit's concern was a demo sign-in path sitting next to the real one,
 * where a mistyped branch could carry a demo user into real Supabase
 * traffic. In F1 the two services are chosen once, at build time, and share
 * nothing. These tests exercise the real modules (no component rendering)
 * so the assertions are about the services themselves.
 */
const supabaseSpy = vi.fn<() => void>();

vi.mock('@/lib/supabase/client', () => ({
  getSupabaseClient: () => {
    supabaseSpy();
    throw new Error('Supabase must not be reached by Preview authentication');
  },
  isSupabaseConfigured: () => false,
}));

const apiRequestSpy = vi.fn<(...args: unknown[]) => void>();

vi.mock('@/lib/api/client', () => ({
  apiRequest: (...args: unknown[]) => {
    apiRequestSpy(...args);
    throw new Error('apiRequest must not be reached by Preview authentication');
  },
}));

function usePreviewEnv() {
  vi.stubEnv('VITE_APP_MODE', 'preview');
  vi.stubEnv('VITE_APP_ENVIRONMENT', 'preview');
}

describe('Preview authentication isolation', () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.resetModules();
    supabaseSpy.mockClear();
    apiRequestSpy.mockClear();
    fetchSpy = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it('mints a local synthetic session without touching Supabase, apiRequest, or fetch', async () => {
    usePreviewEnv();
    const { previewAuthService } = await import('../services/previewAuthService');

    const session = await previewAuthService.enterPreviewWorkspace!();

    expect(session.kind).toBe('preview');
    expect(session.user.name).toBe('Demo Administrator');
    expect(supabaseSpy).not.toHaveBeenCalled();
    expect(apiRequestSpy).not.toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('has no credential sign-in to fall through to real authentication', async () => {
    usePreviewEnv();
    const { previewAuthService } = await import('../services/previewAuthService');

    await expect(
      previewAuthService.requestLogin('someone@example.test', 'whatever'),
    ).rejects.toThrow(/no credential sign-in/i);
    expect(supabaseSpy).not.toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('refuses to produce a Preview session in a Live build', async () => {
    const { previewAuthService } = await import('../services/previewAuthService');

    await expect(previewAuthService.enterPreviewWorkspace!()).rejects.toThrow(/Preview-only/);
  });

  it('is not the service a Live build resolves to', async () => {
    const { resolvedAuthService } = await import('../services/resolvedAuthService');
    const { liveAuthService } = await import('../services/liveAuthService');

    expect(resolvedAuthService).toBe(liveAuthService);
    expect(resolvedAuthService.enterPreviewWorkspace).toBeUndefined();
  });

  it('is the only service a Preview build resolves to', async () => {
    usePreviewEnv();
    const { resolvedAuthService } = await import('../services/resolvedAuthService');
    const { previewAuthService } = await import('../services/previewAuthService');

    expect(resolvedAuthService).toBe(previewAuthService);
  });

  it('does not adopt a persisted session that is not a Preview session', async () => {
    usePreviewEnv();
    const { previewAuthService } = await import('../services/previewAuthService');

    window.localStorage.setItem(
      'ghp:session',
      JSON.stringify({
        kind: 'live',
        user: { id: 'x', name: 'x', email: 'x', role: 'admin', orgIds: [] },
        token: 'forged',
        expiresAt: Date.now() + 60_000,
        activeOrgId: 'org-x',
      }),
    );

    expect(previewAuthService.getSession()).toBeNull();
  });

  it('exposes no multi-factor or verification-code capability at all', async () => {
    const authServiceModule = await import('../services/AuthService');
    const { previewAuthService } = await import('../services/previewAuthService');
    const { liveAuthService } = await import('../services/liveAuthService');

    for (const service of [previewAuthService, liveAuthService]) {
      expect('verifyOtp' in service).toBe(false);
      expect('resendOtp' in service).toBe(false);
      expect('getDevOtpHint' in service).toBe(false);
      expect('checkDevOtpCode' in service).toBe(false);
    }

    expect('ChallengeExpiredError' in authServiceModule).toBe(false);
    expect('InvalidOtpError' in authServiceModule).toBe(false);
  });
});
