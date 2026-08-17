import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { en, type StringKey } from './strings/en';
import { ar } from './strings/ar';
import { LocaleContext, type Locale, type LocaleContextValue, type Direction } from './context';
import { AUTHORITATIVE_LOCALE, resolveLocale } from './availability';

/**
 * English is the authoritative dictionary: it defines `StringKey`, and
 * every other locale is a `Partial` map over those keys. A missing entry
 * falls back to the English text rather than rendering a raw key, an empty
 * string, or `undefined` — which is what allows a future locale to be
 * landed incrementally without ever shipping a half-blank screen.
 */
const DICTIONARIES: Record<Locale, Partial<Record<StringKey, string>>> = { en, ar };

const STORAGE_KEY = 'ghp:locale';

function directionFor(locale: Locale): Direction {
  return locale === 'ar' ? 'rtl' : 'ltr';
}

/**
 * Reads the stored preference and resolves it against the locales this
 * build actually offers.
 *
 * `resolveLocale` is the fail-closed step: a stored `'ar'` — left by an
 * earlier build, hand-edited in devtools, or written by any other means —
 * resolves to English rather than putting the product into a language the
 * MVP does not ship. Storage is an input to be validated, never an
 * authority.
 */
function readInitialLocale(): Locale {
  if (typeof window === 'undefined') return AUTHORITATIVE_LOCALE;
  return resolveLocale(window.localStorage.getItem(STORAGE_KEY));
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(readInitialLocale);
  const dir = directionFor(locale);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = dir;
  }, [locale, dir]);

  /**
   * Every write goes through `resolveLocale`, so an unavailable locale
   * cannot be activated by a caller — not by the Settings control, not by
   * a component passing a forged value, not by anything else that reaches
   * this function. The *resolved* value is what gets persisted, so a
   * rejected choice does not linger in storage either.
   */
  const setLocale = useCallback((next: Locale) => {
    const resolved = resolveLocale(next);
    setLocaleState(resolved);
    window.localStorage.setItem(STORAGE_KEY, resolved);
  }, []);

  /** Retained for the future multi-language phase. With a single available
   * locale it resolves straight back to that locale, so it is inert rather
   * than a way around `setLocale`'s gate. */
  const toggleLocale = useCallback(() => {
    setLocale(locale === 'ar' ? 'en' : 'ar');
  }, [locale, setLocale]);

  const t = useCallback<LocaleContextValue['t']>(
    (key, params) => {
      // English is the authoritative source; a locale that does not carry
      // this key falls back to it rather than rendering nothing.
      const template = DICTIONARIES[locale][key] ?? en[key];
      if (!params) return template;
      return Object.entries(params).reduce<string>(
        (acc, [paramKey, value]) => acc.replaceAll(`{${paramKey}}`, String(value)),
        template,
      );
    },
    [locale],
  );

  const value = useMemo<LocaleContextValue>(
    () => ({ locale, dir, setLocale, toggleLocale, t }),
    [locale, dir, setLocale, toggleLocale, t],
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}
