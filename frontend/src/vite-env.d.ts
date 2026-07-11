/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Dev-only shortcut that signs a visitor straight in as the Admin demo
   * account, skipping the credentials/OTP steps — see
   * `src/features/auth/devAuthBypass.ts` for the single place this is
   * read and enforced as dev-build-only regardless of its value. */
  readonly VITE_DEV_AUTH_BYPASS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
