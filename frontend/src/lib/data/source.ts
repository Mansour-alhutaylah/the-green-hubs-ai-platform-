/**
 * The application's data source selector — the single place that decides
 * whether this build talks to real services (Live) or renders clearly
 * labelled synthetic fixtures (Preview).
 *
 * Fail-closed by construction:
 *
 * - The decision reads **only** build-time environment values. `location`,
 *   `document.cookie`, `localStorage`, `sessionStorage`, route params,
 *   request bodies and headers are never consulted, so no browser-, user-,
 *   or tenant-controlled value can flip a deployed build into Preview.
 * - Two independent variables must agree. `VITE_APP_MODE` states the
 *   intent, `VITE_APP_ENVIRONMENT` states which build classification is
 *   being produced. A blank, malformed, unknown, or inconsistent pair
 *   resolves to `'live'` — a Production build can therefore never fall into
 *   Preview by omission or by a single mistyped variable.
 * - `'live'` is the default in every ambiguous case, and Live never renders
 *   Preview fixtures: a capability the Backend does not implement yet shows
 *   a truthful unavailable state instead (see `DataState`).
 *
 * `import.meta.env` reads are intentionally not cached: Vite statically
 * replaces them at build time, so there is nothing to memoize in a real
 * build, and tests can exercise the genuine code path with `vi.stubEnv`
 * instead of mocking this module.
 */

export type AppMode = 'live' | 'preview';

/** Build classification. `preview` is the only one that may pair with
 * Preview mode; anything else (including `production`) forces Live. */
export type AppEnvironment = 'production' | 'preview' | 'development';

const PREVIEW = 'preview';

/** The exact build-time inputs the decision is allowed to depend on. */
export interface AppModeEnv {
  readonly VITE_APP_MODE?: unknown;
  readonly VITE_APP_ENVIRONMENT?: unknown;
}

/**
 * Pure resolution rule, exported so the fail-closed behavior is testable
 * against arbitrary (including hostile) input without touching a build.
 *
 * Preview requires an exact, lowercase, whitespace-free `'preview'` in
 * *both* variables. No trimming, no case folding, no truthy coercion — a
 * value that merely looks like an opt-in ("Preview", "true", "1", " preview")
 * is treated as malformed configuration and yields Live.
 */
export function resolveAppMode(env: AppModeEnv): AppMode {
  const mode = env.VITE_APP_MODE;
  const environment = env.VITE_APP_ENVIRONMENT;

  if (typeof mode !== 'string' || typeof environment !== 'string') return 'live';
  if (mode !== PREVIEW) return 'live';
  if (environment !== PREVIEW) return 'live';

  return 'preview';
}

export function getAppMode(): AppMode {
  return resolveAppMode({
    VITE_APP_MODE: import.meta.env.VITE_APP_MODE,
    VITE_APP_ENVIRONMENT: import.meta.env.VITE_APP_ENVIRONMENT,
  });
}

export function isPreviewMode(): boolean {
  return getAppMode() === PREVIEW;
}

export function isLiveMode(): boolean {
  return getAppMode() === 'live';
}

/**
 * Guard for the few modules that must never execute outside Preview
 * (the Preview auth service, the Preview data sources). Calling one of them
 * in a Live build is a programming error, not a recoverable condition, so
 * it throws rather than silently degrading into fabricated data.
 */
export function assertPreviewMode(context: string): void {
  if (!isPreviewMode()) {
    throw new Error(`${context} is Preview-only and must never run in Live mode.`);
  }
}
