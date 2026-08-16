import { afterEach, describe, expect, it, vi } from 'vitest';
import { getAppMode, isLiveMode, isPreviewMode, resolveAppMode } from '../source';
import {
  DEFAULT_PREVIEW_SCENARIO,
  getPreviewScenario,
  resolvePreviewScenario,
} from '../scenarios';

/**
 * The fail-closed contract for Live/Preview selection.
 *
 * Two properties are asserted here and nowhere else:
 *
 * 1. Preview requires an exact, agreeing pair of build-time variables.
 *    Everything else — missing, blank, misspelled, mis-cased, truthy-looking,
 *    or inconsistent — is Live.
 * 2. Nothing a browser or a user controls participates in the decision.
 */
describe('app mode resolution', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('selects Preview only when both build-time variables say preview', () => {
    expect(resolveAppMode({ VITE_APP_MODE: 'preview', VITE_APP_ENVIRONMENT: 'preview' })).toBe(
      'preview',
    );
  });

  it.each([
    ['both missing', {}],
    ['mode only', { VITE_APP_MODE: 'preview' }],
    ['environment only', { VITE_APP_ENVIRONMENT: 'preview' }],
    ['blank values', { VITE_APP_MODE: '', VITE_APP_ENVIRONMENT: '' }],
    ['production environment', { VITE_APP_MODE: 'preview', VITE_APP_ENVIRONMENT: 'production' }],
    ['development environment', { VITE_APP_MODE: 'preview', VITE_APP_ENVIRONMENT: 'development' }],
    ['wrong case', { VITE_APP_MODE: 'Preview', VITE_APP_ENVIRONMENT: 'Preview' }],
    ['padded', { VITE_APP_MODE: ' preview ', VITE_APP_ENVIRONMENT: ' preview ' }],
    ['truthy string', { VITE_APP_MODE: 'true', VITE_APP_ENVIRONMENT: 'true' }],
    ['numeric', { VITE_APP_MODE: '1', VITE_APP_ENVIRONMENT: '1' }],
    ['unknown word', { VITE_APP_MODE: 'demo', VITE_APP_ENVIRONMENT: 'demo' }],
    ['non-string', { VITE_APP_MODE: true, VITE_APP_ENVIRONMENT: 1 }],
    ['null', { VITE_APP_MODE: null, VITE_APP_ENVIRONMENT: null }],
  ])('fails closed to Live for %s', (_case, env) => {
    expect(resolveAppMode(env)).toBe('live');
  });

  it('reads the mode from build-time configuration', () => {
    vi.stubEnv('VITE_APP_MODE', 'preview');
    vi.stubEnv('VITE_APP_ENVIRONMENT', 'preview');
    expect(getAppMode()).toBe('preview');
    expect(isPreviewMode()).toBe(true);
    expect(isLiveMode()).toBe(false);
  });

  it('defaults to Live with no configuration at all', () => {
    expect(getAppMode()).toBe('live');
    expect(isLiveMode()).toBe(true);
  });

  /**
   * The core security property. Every one of these is a surface an attacker
   * or a curious user can set from a browser; none of them may promote a
   * Live build into Preview, where fixtures would replace real data.
   */
  it('cannot be switched to Preview by anything the browser controls', () => {
    window.history.replaceState({}, '', '/dashboard?mode=preview&preview=true#preview');
    window.localStorage.setItem('VITE_APP_MODE', 'preview');
    window.localStorage.setItem('ghp:mode', 'preview');
    window.sessionStorage.setItem('VITE_APP_MODE', 'preview');
    window.sessionStorage.setItem('ghp:mode', 'preview');
    document.cookie = 'VITE_APP_MODE=preview';
    document.cookie = 'ghp_mode=preview';

    expect(getAppMode()).toBe('live');
    expect(isPreviewMode()).toBe(false);

    // Also as explicit inputs to the pure rule: a value that arrived from a
    // query string, a route param, or a request body is still just a
    // string, and only the two build-time names are ever consulted.
    expect(
      resolveAppMode({
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        ...({ mode: 'preview', preview: 'true', organization_id: 'x' } as any),
      }),
    ).toBe('live');

    window.history.replaceState({}, '', '/');
  });
});

describe('preview scenario resolution', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('accepts each known scenario', () => {
    expect(resolvePreviewScenario({ VITE_PREVIEW_SCENARIO: 'forbidden' })).toBe('forbidden');
    expect(resolvePreviewScenario({ VITE_PREVIEW_SCENARIO: 'partial' })).toBe('partial');
  });

  it('falls back to the default for unknown or malformed values', () => {
    expect(resolvePreviewScenario({})).toBe(DEFAULT_PREVIEW_SCENARIO);
    expect(resolvePreviewScenario({ VITE_PREVIEW_SCENARIO: 'nonsense' })).toBe(
      DEFAULT_PREVIEW_SCENARIO,
    );
    expect(resolvePreviewScenario({ VITE_PREVIEW_SCENARIO: 42 })).toBe(DEFAULT_PREVIEW_SCENARIO);
  });

  it('is inert in Live mode even when a scenario is configured', () => {
    vi.stubEnv('VITE_PREVIEW_SCENARIO', 'error');
    expect(getPreviewScenario()).toBe(DEFAULT_PREVIEW_SCENARIO);
  });

  it('applies in Preview mode', () => {
    vi.stubEnv('VITE_APP_MODE', 'preview');
    vi.stubEnv('VITE_APP_ENVIRONMENT', 'preview');
    vi.stubEnv('VITE_PREVIEW_SCENARIO', 'error');
    expect(getPreviewScenario()).toBe('error');
  });
});
