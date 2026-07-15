/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Dev-only flag that exposes an explicit local demo-session action — see
   * `src/features/auth/devAuthBypass.ts` for the single place this is
   * read and enforced as dev-build-only regardless of its value. */
  readonly VITE_DEV_AUTH_BYPASS?: string;
  /** Base URL of the backend API, no trailing slash — see
   * `src/lib/api/client.ts`. */
  readonly VITE_API_BASE_URL?: string;
  /** Supabase project URL — see `src/lib/supabase/client.ts`. */
  readonly VITE_SUPABASE_URL?: string;
  /** Supabase anon (public) key — never the service-role key. */
  readonly VITE_SUPABASE_ANON_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
