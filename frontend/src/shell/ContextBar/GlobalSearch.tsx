import { useState } from 'react';
import { Icon } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';

export const GLOBAL_SEARCH_INPUT_ID = 'global-search-input';

/**
 * §3.2: structural stub — the "/" shortcut and the 280px input are real,
 * but the results overlay has no real entities to search yet (documents,
 * organizations, users, reports are all still stub pages). Wiring actual
 * search is a later phase's business logic.
 */
export function GlobalSearch() {
  const { t } = useLocale();
  const [isFocused, setIsFocused] = useState(false);

  return (
    <div className="relative">
      <div className="flex h-9 w-70 items-center gap-2 rounded-m border border-line-300 bg-surface-0 px-3">
        <Icon name="search" size={16} className="shrink-0 text-gray-400" />
        <input
          id={GLOBAL_SEARCH_INPUT_ID}
          type="text"
          placeholder={t('contextBar.search.placeholder')}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          className="w-full bg-transparent text-body outline-none placeholder:text-gray-400"
        />
        <kbd className="rounded-s border border-line-200 px-1.5 py-0.5 text-caption text-gray-400">
          /
        </kbd>
      </div>
      {isFocused && (
        <div className="absolute end-0 top-11 z-[var(--z-overlay)] w-70 rounded-m border border-line-200 bg-surface-0 p-4 shadow-float">
          <p className="text-caption text-gray-600">{t('contextBar.search.comingSoon')}</p>
        </div>
      )}
    </div>
  );
}
