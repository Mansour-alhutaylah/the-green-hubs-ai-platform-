import { createClient, type Session as SupabaseSession, type SupabaseClient } from '@supabase/supabase-js';

/**
 * Singleton Supabase client — browser-safe: only the public anon key is
 * ever read here. `VITE_SUPABASE_SERVICE_ROLE_KEY` must never exist as a
 * frontend env var and this module never reads one.
 */
let client: SupabaseClient | null = null;
let configError: string | null = null;

function readConfig(): { url: string; anonKey: string } | null {
  const url = import.meta.env.VITE_SUPABASE_URL;
  const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;
  if (!url || !anonKey) {
    configError =
      'Supabase is not configured: set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.';
    return null;
  }
  return { url, anonKey };
}

/** Returns the singleton client, or `null` when required env vars are
 * absent — callers decide how to surface that (never thrown at import
 * time, so demo mode can boot without any Supabase configuration). */
export function getSupabaseClient(): SupabaseClient | null {
  if (client) return client;
  const config = readConfig();
  if (!config) return null;
  client = createClient(config.url, config.anonKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: false,
    },
  });
  return client;
}

export function isSupabaseConfigured(): boolean {
  return readConfig() !== null;
}

/** Human-readable configuration error, set only after a failed
 * `getSupabaseClient()`/`readConfig()` call. Never includes any secret. */
export function getSupabaseConfigError(): string | null {
  return configError;
}

export type { SupabaseSession };
