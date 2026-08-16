/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Build-time data source: the exact string `preview` (paired with a
   * matching `VITE_APP_ENVIRONMENT`) selects Preview mode. Anything else,
   * including absent, fails closed to Live — see `src/lib/data/source.ts`,
   * the single place this is read. */
  readonly VITE_APP_MODE?: string;
  /** Build classification: `production` | `preview` | `development`.
   * Preview mode requires `preview` here as well, so a single mistyped
   * variable can never put a Production build into Preview. */
  readonly VITE_APP_ENVIRONMENT?: string;
  /** Preview-only: which state the Preview fixtures render —
   * `populated` (default) | `empty` | `loading` | `error` | `forbidden` |
   * `partial`. Ignored entirely in Live mode. */
  readonly VITE_PREVIEW_SCENARIO?: string;
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
