import { createContext } from 'react';
import type { StringKey } from './strings/en';

export type Locale = 'en' | 'ar';
export type Direction = 'ltr' | 'rtl';

export interface LocaleContextValue {
  locale: Locale;
  dir: Direction;
  setLocale: (locale: Locale) => void;
  toggleLocale: () => void;
  /** Translate a key, optionally interpolating `{param}` placeholders. */
  t: (key: StringKey, params?: Record<string, string | number>) => string;
}

/**
 * Kept in its own module (not alongside LocaleProvider) so
 * LocaleContext.tsx only ever exports the component — mixing a plain
 * `createContext()` value into a component file breaks React Fast Refresh.
 */
export const LocaleContext = createContext<LocaleContextValue | null>(null);
