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

  // Inert in a production build regardless (isDevAuthBypassEnabled() is
  // gated on import.meta.env.DEV), but a `true` here signals that
  // production is being configured from a development env file.
  if (env.VITE_DEV_AUTH_BYPASS === 'true') {
    warn('VITE_DEV_AUTH_BYPASS is "true" in a production build — it has no effect, but set it to false.');
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
    },
  };
});
