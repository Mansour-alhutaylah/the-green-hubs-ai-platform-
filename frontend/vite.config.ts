/// <reference types="vitest/config" />
import path from 'node:path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

/**
 * Warns — never fails — about production env configuration that would build
 * cleanly but leave the deployed app broken. Deliberately warning-only:
 * CI runs `npm run build` with no VITE_* variables at all
 * (.github/workflows/ci.yml), so erroring here would break the pipeline.
 * On Vercel these lines land in the visible build log, which is where a
 * stale or missing variable is cheapest to catch.
 *
 * Only ever reports whether a variable is set and, for the API base URL,
 * its shape. No value is ever printed.
 */
function warnAboutProductionEnv(env: Record<string, string>): void {
  const warn = (message: string) => console.warn(`[env-check] ${message}`);

  // Preview is a separate build: it contacts nothing, so the Live service
  // variables below are not required (and warning about them would be
  // noise). The app resolves the mode itself in src/lib/data/source.ts;
  // this only decides which warnings are worth printing.
  const isPreviewBuild = env.VITE_APP_MODE === 'preview' && env.VITE_APP_ENVIRONMENT === 'preview';

  if (env.VITE_APP_MODE && !isPreviewBuild) {
    warn(
      'VITE_APP_MODE is set but does not pair with VITE_APP_ENVIRONMENT=preview — this build resolves to Live mode.',
    );
  }

  if (isPreviewBuild) {
    warn('Building in PREVIEW mode: the app will render synthetic fixtures and contact no service.');
    return;
  }

  for (const key of ['VITE_API_BASE_URL', 'VITE_SUPABASE_URL', 'VITE_SUPABASE_ANON_KEY']) {
    if (!env[key]) warn(`${key} is not set — the deployed app cannot sign in or call the API.`);
  }

  const base = env.VITE_API_BASE_URL;
  if (base) {
    if (/localhost|127\.0\.0\.1/.test(base)) {
      warn('VITE_API_BASE_URL points at localhost — a browser cannot reach that from a hosted deployment.');
    }
    // Every endpoint module already includes the /api/v1 prefix
    // (src/lib/api/endpoints/*.ts), so a prefixed base URL yields
    // /api/v1/api/v1/... and 404s on every call.
    if (/\/api\/v1\/?$/.test(base)) {
      warn('VITE_API_BASE_URL ends with /api/v1 — it must be the backend origin only.');
    }
  }
}

// https://vite.dev/config/
export default defineConfig(({ command, mode }) => {
  if (command === 'build' && mode === 'production') {
    // `__dirname`, not `process.cwd()`: the frontend directory stays the
    // authoritative env directory even when a host invokes the build from a
    // different working directory. Matches the `@` alias resolution below.
    warnAboutProductionEnv(loadEnv(mode, __dirname, 'VITE_'));
  }

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setupTests.ts'],
      globals: true,
      css: true,
      /**
       * Vitest's 5s default is not enough for this suite's slowest cases.
       * Several tests mount the whole route tree in jsdom, which pulls in
       * lazy route chunks, the design system, and both i18n dictionaries;
       * under full parallelism on a modest machine that alone can exceed
       * 5s, and the resulting failures are pure scheduling noise — the same
       * tests pass in isolation and at a longer limit.
       *
       * This is a timeout, not a delay: a genuinely hanging test still
       * fails, just less ambiguously.
       */
      testTimeout: 20_000,
    },
  };
});
