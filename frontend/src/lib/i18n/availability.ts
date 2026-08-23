import type { Locale } from './context';

/**
 * Which languages this build actually offers.
 *
 * The MVP ships **English only**. Arabic is deferred to a dedicated later
 * phase: the dictionary, the `dir` handling, the logical CSS properties,
 * and the RTL layout work all remain in the codebase and are not to be
 * removed — but a partially translated Arabic interface is worse than an
 * honest English one, so Arabic is not selectable until a completeness
 * gate is passed.
 *
 * This module is the single gate. It is deliberately a *build-time
 * constant list*, not a preference, a feature flag read from storage, or a
 * query parameter — the same fail-closed shape as `data/source.ts`. That
 * matters because the failure mode being prevented is a user (or a stale
 * `localStorage` entry, or a forged URL) putting the product into a
 * half-translated state that no reviewer ever signed off.
 *
 * **Re-enabling Arabic is not a one-line change.** Adding `'ar'` here is
 * the last step, not the only one. The `dir`/RTL machinery is genuinely
 * intact and `LocaleProvider` already resolves through `resolveLocale`, so
 * no re-implementation is needed — but the dictionary is typed
 * `Partial<Record<StringKey, string>>`, which means a missing translation
 * is no longer a compile error. It silently renders the English text
 * instead. That is what makes an incremental translation phase possible,
 * and it is also why enabling the locale without a completeness check would
 * ship exactly the half-translated interface this gate exists to prevent.
 * As of F2A, `ar.ts` is already missing the four `settings.language.*`
 * keys added by the English-only decision itself.
 *
 * All four of the following are required, in order:
 *
 * 1. Complete, reviewed Arabic translations for every active `StringKey`,
 *    including every key F2A added — not machine translation, and not
 *    English text wearing an Arabic label.
 * 2. Restore the completeness gate that the `Partial` type gave up: either
 *    type `ar` as an exhaustive `Record<StringKey, string>` again, or add a
 *    test asserting EN/AR key parity. Without one of these, nothing fails
 *    when a future key goes untranslated.
 * 3. Add `'ar'` to `AVAILABLE_LOCALES` below.
 * 4. Real-browser RTL visual QA across every supported route at 360px,
 *    768px, and 1280px. jsdom performs no layout and cannot stand in for
 *    this step.
 *
 * See `project-governance/05-delivery/Deferred_Arabic_Localization_And_RTL.md`.
 */

export const AUTHORITATIVE_LOCALE: Locale = 'en';

/** Every locale this build will render. English only for the MVP. */
export const AVAILABLE_LOCALES: readonly Locale[] = ['en'];

export function isLocaleAvailable(value: unknown): value is Locale {
  return typeof value === 'string' && AVAILABLE_LOCALES.includes(value as Locale);
}

/** True only when there is a genuine choice to offer. Every language
 * selector in the UI is hidden while this is false, rather than shown with
 * a single option or shown with an option that would not work. */
export function hasSelectableLocales(): boolean {
  return AVAILABLE_LOCALES.length > 1;
}

/**
 * The fail-closed resolution every entry point goes through.
 *
 * A stored `'ar'` from a build where Arabic *was* selectable, a
 * hand-edited `localStorage` value, a forged query parameter, a value
 * injected into React state — all resolve to English. There is no input to
 * this function that yields an unavailable locale.
 */
export function resolveLocale(value: unknown): Locale {
  return isLocaleAvailable(value) ? value : AUTHORITATIVE_LOCALE;
}
