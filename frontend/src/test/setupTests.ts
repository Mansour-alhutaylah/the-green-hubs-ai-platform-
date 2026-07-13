import { afterEach, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';

Object.defineProperty(window, 'scrollTo', {
  configurable: true,
  writable: true,
  value: vi.fn<typeof window.scrollTo>(),
});

/** mockAuthService persists to real localStorage/sessionStorage — clear
 * both between tests so one test's session/lockout state can't leak into
 * the next. */
afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
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
