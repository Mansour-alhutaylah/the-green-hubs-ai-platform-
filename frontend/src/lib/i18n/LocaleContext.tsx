import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { en, type StringKey } from './strings/en';
import { ar } from './strings/ar';
import { LocaleContext, type Locale, type LocaleContextValue, type Direction } from './context';

const DICTIONARIES: Record<Locale, Record<StringKey, string>> = { en, ar };
const STORAGE_KEY = 'ghp:locale';

function directionFor(locale: Locale): Direction {
  return locale === 'ar' ? 'rtl' : 'ltr';
}

function readInitialLocale(): Locale {
  if (typeof window === 'undefined') return 'en';
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === 'ar' || stored === 'en' ? stored : 'en';
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(readInitialLocale);
  const dir = directionFor(locale);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = dir;
  }, [locale, dir]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    window.localStorage.setItem(STORAGE_KEY, next);
  }, []);

  const toggleLocale = useCallback(() => {
    setLocale(locale === 'en' ? 'ar' : 'en');
  }, [locale, setLocale]);

  const t = useCallback<LocaleContextValue['t']>(
    (key, params) => {
      const template = DICTIONARIES[locale][key];
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
