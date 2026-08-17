import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  createEngagement,
  getEngagement,
  listEngagements,
  updateEngagement,
} from '../endpoints/engagements';
import { getOrganization, listOrganizations, updateOrganization } from '../endpoints/organizations';
import * as organizationEndpoints from '../endpoints/organizations';

vi.mock('@/lib/supabase/client', () => ({
  getSupabaseClient: () => null,
  isSupabaseConfigured: () => false,
}));

/**
 * Tenant-scope safety for the endpoints F2A added.
 *
 * The rule the existing `tenantScope.test.ts` established still holds: the
 * Frontend never asserts which organization a request belongs to, because
 * that would turn a display value into an authorization claim.
 *
 * F2A adds one deliberate, contract-mandated exception —
 * `POST /engagements` requires `organization_id` in its body — so this file
 * pins down its exact shape rather than waiving the rule. Everything else
 * stays clean, and the create request is proven to send *only* the value it
 * was handed, with no filter, query parameter, or header carrying a scope
 * alongside it.
 */
const FORBIDDEN_KEYS = [
  'organization_id',
  'organizationId',
  'org_id',
  'orgId',
  'tenant_id',
  'tenantId',
];

type FetchCall = [string, RequestInit];

describe('F2A endpoints and tenant scope', () => {
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

  it('sends no tenant identifier on any read or update', async () => {
    await listOrganizations();
    await getOrganization('org-1');
    await updateOrganization('org-1', { name: 'Renamed' });
    await listEngagements({ page: 2, page_size: 20 });
    await getEngagement('eng-1');
    await updateEngagement('eng-1', { title: 'Retitled', status: 'active' });

    expect(fetchSpy.mock.calls.length).toBe(6);

    for (const [url, init] of fetchSpy.mock.calls as FetchCall[]) {
      for (const key of FORBIDDEN_KEYS) {
        expect(url, `${url} must not carry ${key}`).not.toContain(key);
        const body = typeof init?.body === 'string' ? init.body : '';
        expect(body, `request body must not carry ${key}`).not.toContain(key);
      }
    }
  });

  it('never sends the engagements list route its optional organization filter', async () => {
    await listEngagements({ page: 1, page_size: 50 });

    const [url] = fetchSpy.mock.calls[0] as FetchCall;
    // The route accepts `organization_id` as a filter. Sending one would
    // narrow a scope the server already decided, while making the request
    // read as a tenancy assertion — so the client has no parameter for it.
    expect(url).toContain('page=1');
    expect(url).toContain('page_size=50');
    expect(url).not.toContain('organization_id');
  });

  it('sends exactly the create body the contract requires, and nothing more', async () => {
    await createEngagement({ organization_id: 'org-caller-own', title: 'Annual disclosure' });

    const [url, init] = fetchSpy.mock.calls[0] as FetchCall;
    expect(url).toBe('https://api.test.invalid/api/v1/engagements');
    expect(init.method).toBe('POST');

    const body = JSON.parse(String(init.body)) as Record<string, unknown>;
    // `organization_id` is required by `EngagementCreateRequest`, and the
    // service answers 403 for any value but the caller's own. It is passed
    // through verbatim; the safety property is *where the caller got it*,
    // which `EngagementCreateOrgScope.test.tsx` proves.
    expect(body).toEqual({ organization_id: 'org-caller-own', title: 'Annual disclosure' });
    // No scope smuggled into the URL alongside the body.
    expect(url).not.toContain('organization_id');
  });

  it('omits status entirely rather than sending an explicit null', async () => {
    await createEngagement({ organization_id: 'org-caller-own', title: 'No status chosen' });

    const [, init] = fetchSpy.mock.calls[0] as FetchCall;
    const body = JSON.parse(String(init.body)) as Record<string, unknown>;
    // The schema types `status` as a plain `str` with a server default, so
    // an explicit null is a 422 while an omission uses the default.
    expect('status' in body).toBe(false);
  });

  it('omits an unchanged field on update rather than resending or nulling it', async () => {
    await updateEngagement('eng-1', { title: 'Only the title changed' });

    const [, init] = fetchSpy.mock.calls[0] as FetchCall;
    const body = JSON.parse(String(init.body)) as Record<string, unknown>;
    expect(body).toEqual({ title: 'Only the title changed' });
    expect('status' in body).toBe(false);
    expect('organization_id' in body).toBe(false);
  });

  it('exposes no organization-creation client at all', () => {
    // `POST /organizations` exists but `OrganizationService.create` raises
    // unconditionally, so shipping a client for it would only ever invite a
    // Live affordance guaranteed to 403.
    expect(Object.keys(organizationEndpoints)).not.toContain('createOrganization');
    expect(Object.keys(organizationEndpoints)).not.toContain('deleteOrganization');
  });
});
