import { getSupabaseClient } from '@/lib/supabase/client';
import { buildApiErrorFromResponse, NetworkError, RequestAbortedError } from './errors';
import { emitUnauthorizedResponse } from './sessionEvents';

export interface ApiRequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  /** JSON request body — mutually exclusive with `formData`. */
  json?: unknown;
  /** multipart/form-data body. The browser sets the `Content-Type`
   * (including the boundary) automatically; this client never sets it
   * manually for a `FormData` body. */
  formData?: FormData;
  query?: Record<string, string | number | boolean | undefined>;
  signal?: AbortSignal;
}

function readApiBaseUrl(): string {
  const base = import.meta.env.VITE_API_BASE_URL;
  if (!base) {
    throw new Error('VITE_API_BASE_URL is not configured.');
  }
  return base.replace(/\/+$/, '');
}

function buildUrl(path: string, query?: ApiRequestOptions['query']): string {
  const base = readApiBaseUrl();
  const url = new URL(`${base}${path.startsWith('/') ? path : `/${path}`}`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

/** Reads the current live Supabase access token fresh on every call — the
 * SDK refreshes it in the background, so this never caches a stale value.
 * Returns `null` (never throws) when no live session exists, e.g. in demo
 * mode, so nothing here ever fabricates or reuses a stale/fake token. */
async function getAccessToken(): Promise<string | null> {
  const supabase = getSupabaseClient();
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

async function safeParseJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/** The single seam every feature endpoint module calls through — no page
 * component issues a direct `fetch()`. Never logs the access token or
 * includes it in a thrown error message. */
export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const url = buildUrl(path, options.query);
  const headers: Record<string, string> = {};

  const token = await getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (options.formData) {
    body = options.formData;
  } else if (options.json !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(options.json);
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method ?? 'GET',
      headers,
      body,
      signal: options.signal,
    });
  } catch (cause) {
    if (options.signal?.aborted || (cause instanceof DOMException && cause.name === 'AbortError')) {
      throw new RequestAbortedError();
    }
    throw new NetworkError();
  }

  if (!response.ok) {
    if (response.status === 401) emitUnauthorizedResponse();
    const errorBody = await safeParseJson(response);
    throw buildApiErrorFromResponse(response.status, errorBody);
  }

  if (response.status === 204) return undefined as T;
  return (await safeParseJson(response)) as T;
}
