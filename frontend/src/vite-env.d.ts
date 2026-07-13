/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Dev-only flag that exposes an explicit local demo-session action — see
   * `src/features/auth/devAuthBypass.ts` for the single place this is
   * read and enforced as dev-build-only regardless of its value. */
  readonly VITE_DEV_AUTH_BYPASS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
