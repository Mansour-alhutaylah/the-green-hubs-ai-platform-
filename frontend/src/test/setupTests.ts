import { afterEach, vi } from 'vitest';
import { configure } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

/**
 * How long a `findBy*`/`waitFor` may wait, defined once.
 *
 * Testing Library's 1s default is too short for this suite: many tests
 * mount the whole route tree in jsdom, which resolves a `React.lazy` chunk
 * and pulls in the design system, the data layer, and the i18n dictionary
 * on demand. This replaced the `{ timeout: 5000 }` literals that were
 * scattered across the suite — **112 of them**, in 14 files. (An earlier
 * note here said ~130; the measured count was 112.)
 *
 * The value is set from measurement, not estimate. Across two full runs of
 * the suite, the slowest single test was **7.2s** (`DocumentDetailPage`
 * polling, and the equivalent `AnalysisRunPage` polling test — both wait on
 * real timers by design), and no test exceeded 10s. 10s therefore clears
 * the observed worst case with roughly 40% headroom while staying tight
 * enough that a genuinely hung wait fails quickly rather than stalling the
 * run.
 *
 * This is a *timeout*, not a delay: a test that never resolves still fails,
 * just unambiguously, and a fast machine is unaffected because every wait
 * ends as soon as the assertion passes. Keeping the value here rather than
 * at each call site means there is one number to revisit, not 112.
 *
 * If this needs raising, identify the specific test and say why — a broad
 * increase would hide exactly the hangs, duplicate fetches, and missing
 * cleanup this budget is meant to expose.
 */
configure({ asyncUtilTimeout: 10_000 });

Object.defineProperty(window, 'scrollTo', {
  configurable: true,
  writable: true,
  value: vi.fn<typeof window.scrollTo>(),
});

Object.defineProperty(window.history, 'scrollRestoration', {
  configurable: true,
  writable: true,
  value: 'auto',
});

/** mockAuthService persists to real localStorage/sessionStorage — clear
 * both between tests so one test's session/lockout state can't leak into
 * the next. */
afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  window.history.scrollRestoration = 'auto';
  vi.mocked(window.scrollTo).mockClear();
});

/** jsdom doesn't implement matchMedia — polyfill it so useReducedMotion
 * and any other matchMedia-based hooks don't throw during tests. */
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList;
}
