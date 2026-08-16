import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { listDocuments, uploadDocument, getDocument, processDocument, generateEmbeddings } from '../endpoints/documents';
import { listEngagements } from '../endpoints/engagements';
import { listOrganizations } from '../endpoints/organizations';
import { getMe } from '../endpoints/auth';

vi.mock('@/lib/supabase/client', () => ({
  getSupabaseClient: () => null,
  isSupabaseConfigured: () => false,
}));

/**
 * Tenant scope is derived by the Backend from the bearer token. The
 * Frontend must never assert which organization a request belongs to — a
 * client-supplied `organization_id` would turn a display value into an
 * authorization claim.
 *
 * This drives every endpoint module through the real `apiRequest` with a
 * stubbed `fetch`, then inspects what actually went on the wire.
 */
const FORBIDDEN_KEYS = ['organization_id', 'organizationId', 'org_id', 'orgId', 'tenant_id', 'tenantId'];

describe('no request carries a client-supplied tenant identifier', () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.test.invalid');
    fetchSpy = vi.fn<typeof fetch>(async () => new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it('sends none of the tenant keys in any URL or body', async () => {
    const file = new File(['pdf'], 'report.pdf', { type: 'application/pdf' });

    await listDocuments({ engagement_id: 'eng-1', limit: 5, offset: 0 });
    await getDocument('doc-1');
    await uploadDocument({ engagementId: 'eng-1', file });
    await processDocument('doc-1');
    await generateEmbeddings('doc-1');
    await listEngagements({ page_size: 100 });
    await listOrganizations();
    await getMe();

    expect(fetchSpy.mock.calls.length).toBeGreaterThan(0);

    for (const [url, init] of fetchSpy.mock.calls as Array<[string, RequestInit]>) {
      for (const key of FORBIDDEN_KEYS) {
        expect(url, `${url} must not carry ${key}`).not.toContain(key);
      }

      const body = init?.body;
      const bodyText = typeof body === 'string' ? body : '';
      const formKeys = body instanceof FormData ? [...body.keys()] : [];

      for (const key of FORBIDDEN_KEYS) {
        expect(bodyText, `request body must not carry ${key}`).not.toContain(key);
        expect(formKeys, `form data must not carry ${key}`).not.toContain(key);
      }
    }
  });

  it('sends no Authorization header when there is no live session, rather than a fabricated one', async () => {
    await listOrganizations();

    const [, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    const headers = (init.headers ?? {}) as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });
});
