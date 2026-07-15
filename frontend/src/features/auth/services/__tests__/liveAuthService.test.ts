import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ForbiddenError, NotFoundApiError } from '@/lib/api/errors';
import { InvalidCredentialsError, ProfileNotProvisionedError, RateLimitedError } from '../AuthService';

const getSupabaseClient = vi.fn<() => unknown>();
const getMe = vi.fn<() => Promise<unknown>>();

vi.mock('@/lib/supabase/client', () => ({
  getSupabaseClient: () => getSupabaseClient(),
}));

vi.mock('@/lib/api/endpoints/auth', () => ({
  getMe: () => getMe(),
}));

function buildSupabaseMock({
  signInError,
  session,
}: {
  signInError?: { status: number };
  session?: { access_token: string; expires_at: number } | null;
} = {}) {
  const signOut = vi.fn<() => Promise<{ error: null }>>().mockResolvedValue({ error: null });
  return {
    signOut,
    client: {
      auth: {
        signInWithPassword: vi
          .fn<() => Promise<{ error: { status: number } | null }>>()
          .mockResolvedValue({ error: signInError ?? null }),
        getSession: vi
          .fn<() => Promise<{ data: { session: unknown } }>>()
          .mockResolvedValue({ data: { session: session ?? null } }),
        signOut,
        onAuthStateChange: vi
          .fn<() => { data: { subscription: { unsubscribe: () => void } } }>()
          .mockReturnValue({ data: { subscription: { unsubscribe: vi.fn<() => void>() } } }),
      },
    },
  };
}

describe('liveAuthService', () => {
  beforeEach(() => {
    getSupabaseClient.mockReset();
    getMe.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('signs in and resolves the backend profile into a live session', async () => {
    const { client } = buildSupabaseMock({
      session: { access_token: 'token-abc', expires_at: Math.floor(Date.now() / 1000) + 3600 },
    });
    getSupabaseClient.mockReturnValue(client);
    getMe.mockResolvedValue({
      id: 'user-1',
      organization_id: 'org-1',
      full_name: 'Reem Al-Harbi',
      email: 'reem@example.com',
      role: 'admin',
    });

    const { liveAuthService } = await import('../liveAuthService');
    const result = await liveAuthService.requestLogin('reem@example.com', 'correct-password');

    expect(result.kind).toBe('authenticated');
    if (result.kind !== 'authenticated') throw new Error('expected authenticated result');
    expect(result.session.kind).toBe('live');
    expect(result.session.user.email).toBe('reem@example.com');
    expect(result.session.activeOrgId).toBe('org-1');
    // The real access token is never carried on the app-level Session.
    expect(result.session.token).not.toBe('token-abc');
  });

  it('throws InvalidCredentialsError on a rejected sign-in', async () => {
    const { client } = buildSupabaseMock({ signInError: { status: 400 } });
    getSupabaseClient.mockReturnValue(client);

    const { liveAuthService } = await import('../liveAuthService');
    await expect(liveAuthService.requestLogin('reem@example.com', 'wrong')).rejects.toThrow(
      InvalidCredentialsError,
    );
  });

  it('throws RateLimitedError when Supabase reports 429', async () => {
    const { client } = buildSupabaseMock({ signInError: { status: 429 } });
    getSupabaseClient.mockReturnValue(client);

    const { liveAuthService } = await import('../liveAuthService');
    await expect(liveAuthService.requestLogin('reem@example.com', 'x')).rejects.toThrow(
      RateLimitedError,
    );
  });

  it('signs out and surfaces ProfileNotProvisionedError to an active login attempt', async () => {
    const { client, signOut } = buildSupabaseMock({
      session: { access_token: 'token-abc', expires_at: Math.floor(Date.now() / 1000) + 3600 },
    });
    getSupabaseClient.mockReturnValue(client);
    getMe.mockRejectedValue(new ForbiddenError('User has no organization'));

    const { liveAuthService } = await import('../liveAuthService');
    await expect(liveAuthService.requestLogin('reem@example.com', 'x')).rejects.toThrow(
      ProfileNotProvisionedError,
    );
    expect(signOut).toHaveBeenCalledTimes(1);
  });

  it('restoreSession resolves to null (never throws) for the same not-provisioned case, so bootstrap never loops', async () => {
    const { client, signOut } = buildSupabaseMock({
      session: { access_token: 'token-abc', expires_at: Math.floor(Date.now() / 1000) + 3600 },
    });
    getSupabaseClient.mockReturnValue(client);
    getMe.mockRejectedValue(new ForbiddenError('User has no organization'));

    const { liveAuthService } = await import('../liveAuthService');
    await expect(liveAuthService.restoreSession!()).resolves.toBeNull();
    expect(signOut).toHaveBeenCalledTimes(1);
  });

  it('restoreSession resolves to null (not an error) for an unrelated backend failure', async () => {
    const { client } = buildSupabaseMock({
      session: { access_token: 'token-abc', expires_at: Math.floor(Date.now() / 1000) + 3600 },
    });
    getSupabaseClient.mockReturnValue(client);
    getMe.mockRejectedValue(new NotFoundApiError('not found'));

    const { liveAuthService } = await import('../liveAuthService');
    await expect(liveAuthService.restoreSession!()).resolves.toBeNull();
  });

  it('restoreSession resolves to null when there is no Supabase session', async () => {
    const { client } = buildSupabaseMock({ session: null });
    getSupabaseClient.mockReturnValue(client);

    const { liveAuthService } = await import('../liveAuthService');
    await expect(liveAuthService.restoreSession!()).resolves.toBeNull();
    expect(getMe).not.toHaveBeenCalled();
  });

  it('logout signs out of Supabase', async () => {
    const { client, signOut } = buildSupabaseMock();
    getSupabaseClient.mockReturnValue(client);

    const { liveAuthService } = await import('../liveAuthService');
    await liveAuthService.logout();
    expect(signOut).toHaveBeenCalledTimes(1);
  });

  it('requestLogin throws a clear configuration error when Supabase is not configured', async () => {
    getSupabaseClient.mockReturnValue(null);

    const { liveAuthService } = await import('../liveAuthService');
    await expect(liveAuthService.requestLogin('reem@example.com', 'x')).rejects.toThrow(
      /not configured/i,
    );
  });
});
