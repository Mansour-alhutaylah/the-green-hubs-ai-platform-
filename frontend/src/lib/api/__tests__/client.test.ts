import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  ConflictError,
  ForbiddenError,
  NetworkError,
  NotFoundApiError,
  RequestAbortedError,
  UnauthorizedError,
  ValidationApiError,
} from '../errors';
import { onUnauthorizedResponse } from '../sessionEvents';

const getSupabaseClient = vi.fn<() => unknown>();

vi.mock('@/lib/supabase/client', () => ({
  getSupabaseClient: () => getSupabaseClient(),
}));

const SECRET_TOKEN = 'super-secret-access-token';

function mockSupabaseSession(accessToken: string | null) {
  getSupabaseClient.mockReturnValue({
    auth: {
      getSession: vi.fn<() => Promise<{ data: { session: unknown } }>>().mockResolvedValue({
        data: { session: accessToken ? { access_token: accessToken } : null },
      }),
    },
  });
}

describe('apiRequest', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
    getSupabaseClient.mockReset();
    getSupabaseClient.mockReturnValue(null);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it('attaches the live Supabase access token as a Bearer header', async () => {
    mockSupabaseSession(SECRET_TOKEN);
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );

    const { apiRequest } = await import('../client');
    await apiRequest('/api/v1/auth/me');

    const [, init] = fetchSpy.mock.calls[0]!;
    const headers = init?.headers as Record<string, string>;
    expect(headers.Authorization).toBe(`Bearer ${SECRET_TOKEN}`);
  });

  it('sends no Authorization header when there is no live session (demo mode)', async () => {
    mockSupabaseSession(null);
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );

    const { apiRequest } = await import('../client');
    await apiRequest('/api/v1/organizations');

    const [, init] = fetchSpy.mock.calls[0]!;
    const headers = init?.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });

  it('serializes a JSON body with a Content-Type header', async () => {
    mockSupabaseSession(null);
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );

    const { apiRequest } = await import('../client');
    await apiRequest('/api/v1/organizations/123', { method: 'PATCH', json: { name: 'Acme' } });

    const [, init] = fetchSpy.mock.calls[0]!;
    const headers = init?.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
    expect(init?.body).toBe(JSON.stringify({ name: 'Acme' }));
  });

  it('sends a FormData body for multipart uploads without setting Content-Type itself', async () => {
    mockSupabaseSession(null);
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ id: 'doc-1' }), { status: 201 }),
    );

    const { apiRequest } = await import('../client');
    const formData = new FormData();
    formData.append('engagement_id', 'eng-1');
    await apiRequest('/api/v1/documents', { method: 'POST', formData });

    const [, init] = fetchSpy.mock.calls[0]!;
    const headers = init?.headers as Record<string, string>;
    expect(headers['Content-Type']).toBeUndefined();
    expect(init?.body).toBe(formData);
  });

  it.each([
    [401, UnauthorizedError],
    [403, ForbiddenError],
    [404, NotFoundApiError],
    [409, ConflictError],
    [422, ValidationApiError],
  ])('maps a %i response to the matching error class', async (status, ErrorClass) => {
    mockSupabaseSession(null);
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Something specific happened' }), { status }),
    );

    const { apiRequest } = await import('../client');
    await expect(apiRequest('/api/v1/documents')).rejects.toThrow(ErrorClass);
  });

  it('joins FastAPI-shaped validation error arrays into one readable message', async () => {
    mockSupabaseSession(null);
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ detail: [{ msg: 'field required', loc: ['body', 'engagement_id'] }] }),
        { status: 422 },
      ),
    );

    const { apiRequest } = await import('../client');
    await expect(apiRequest('/api/v1/documents')).rejects.toThrow('field required');
  });

  it('distinguishes a network failure from a backend error response', async () => {
    mockSupabaseSession(null);
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));

    const { apiRequest } = await import('../client');
    await expect(apiRequest('/api/v1/documents')).rejects.toThrow(NetworkError);
  });

  it('rejects with RequestAbortedError when the caller cancels the request', async () => {
    mockSupabaseSession(null);
    const controller = new AbortController();
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => {
      controller.abort();
      return Promise.reject(new DOMException('Aborted', 'AbortError'));
    });

    const { apiRequest } = await import('../client');
    await expect(apiRequest('/api/v1/documents', { signal: controller.signal })).rejects.toThrow(
      RequestAbortedError,
    );
  });

  it('never includes the access token in a thrown error message', async () => {
    mockSupabaseSession(SECRET_TOKEN);
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Invalid authentication credentials' }), { status: 401 }),
    );

    const { apiRequest } = await import('../client');
    await expect(apiRequest('/api/v1/documents')).rejects.not.toThrow(
      expect.stringContaining(SECRET_TOKEN),
    );
  });

  it('emits a session-expired signal on a 401 response', async () => {
    mockSupabaseSession(SECRET_TOKEN);
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Invalid authentication credentials' }), { status: 401 }),
    );

    const { apiRequest } = await import('../client');
    const handler = vi.fn<() => void>();
    const unsubscribe = onUnauthorizedResponse(handler);
    try {
      await expect(apiRequest('/api/v1/documents')).rejects.toThrow(UnauthorizedError);
      expect(handler).toHaveBeenCalledTimes(1);
    } finally {
      unsubscribe();
    }
  });
});
