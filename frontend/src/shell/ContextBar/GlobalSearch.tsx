import { useId, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { Icon } from '@/design-system';
import { NAV_ITEMS } from '@/app/navigation/navConfig';
import { meetsMinTier } from '@/features/rbac/roles';
import { useAuth } from '@/features/auth/useAuth';
import { isPreviewMode } from '@/lib/data/source';
import { useLocale } from '@/lib/i18n/useLocale';

/**
 * Global search.
 *
 * Two behaviours, chosen at build time, because only one of them can be
 * honest in each mode.
 *
 * **Preview** gets a real, working navigator. It searches the registered
 * navigation destinations this user's tier can actually reach and jumps to
 * the one they pick. Every result is a route the router declares, so
 * nothing here can navigate into a page that does not exist, and a
 * destination the tier cannot open is filtered out rather than offered and
 * then refused.
 *
 * It is entirely local: the matching is `Array.filter` over `NAV_ITEMS`, a
 * module constant. There is no `fetch`, no `apiRequest`, and no Supabase
 * call in this file, so the zero-network property is structural rather
 * than a promise.
 *
 * It deliberately does **not** search documents, engagements, or reports.
 * Retrieval search across records needs a backend query endpoint that does
 * not exist, and a box that searched only the fixtures currently in memory
 * would quietly answer "no matches" for a record that exists on another
 * page.
 *
 * **Live** gets a disabled control with a stated reason, not a focusable
 * input. Typing into a box that cannot search is a promise the product
 * cannot keep; an earlier version made exactly that mistake with a
 * placeholder and a "/" shortcut badge that targeted nothing.
 */
export function GlobalSearch() {
  return isPreviewMode() ? <PreviewNavigatorSearch /> : <LiveSearchUnavailable />;
}

/** Live: names the capability instead of offering it. Not focusable and
 * not a control, so it takes no part in the tab order. */
function LiveSearchUnavailable() {
  const { t } = useLocale();

  return (
    <div className="flex h-9 w-70 items-center gap-2 rounded-m border border-dashed border-line-300 bg-tint-100 px-3">
      <Icon name="search" size={16} className="shrink-0 text-gray-400" aria-hidden />
      <span className="truncate text-meta font-semibold text-gray-600">
        {t('contextBar.search.unavailable')}
      </span>
    </div>
  );
}

function PreviewNavigatorSearch() {
  const { t } = useLocale();
  const navigate = useNavigate();
  const { user } = useAuth();
  const listId = useId();

  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const blurTimer = useRef<number | null>(null);

  const role = user?.role;

  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (needle.length === 0) return [];
    return NAV_ITEMS.filter((item) => {
      // Never offer a destination this tier cannot open. A result that
      // bounces to Access Denied is worse than no result.
      if (role && !meetsMinTier(role, item.minTier)) return false;
      return t(item.labelKey).toLowerCase().includes(needle);
    }).slice(0, 6);
  }, [query, role, t]);

  function choose(path: string) {
    setOpen(false);
    setQuery('');
    navigate(path);
  }

  return (
    <div className="relative w-70">
      <div className="flex h-9 items-center gap-2 rounded-m border border-line-300 bg-surface-0 px-3 focus-within:border-forest-700">
        <Icon name="search" size={16} className="shrink-0 text-gray-400" aria-hidden />
        {/* Deliberately not an ARIA combobox. The results are real
            `<button>` elements: natively focusable, natively named, and
            reachable by Tab as well as by the arrow keys handled below. A
            listbox role over non-native elements would add ARIA the
            browser already provides and would misreport the widget if the
            keyboard contract ever drifted. */}
        <input
          type="search"
          value={query}
          aria-controls={listId}
          aria-label={t('contextBar.search.preview.label')}
          placeholder={t('contextBar.search.preview.placeholder')}
          className="min-w-0 flex-1 bg-transparent text-meta text-ink-900 outline-none placeholder:text-gray-500"
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
            setActiveIndex(0);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => {
            // Deferred so a click on a result lands before the list closes.
            blurTimer.current = window.setTimeout(() => setOpen(false), 120);
          }}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              setOpen(false);
              return;
            }
            if (results.length === 0) return;
            if (event.key === 'ArrowDown') {
              event.preventDefault();
              setActiveIndex((index) => (index + 1) % results.length);
            } else if (event.key === 'ArrowUp') {
              event.preventDefault();
              setActiveIndex((index) => (index - 1 + results.length) % results.length);
            } else if (event.key === 'Enter') {
              event.preventDefault();
              const target = results[activeIndex];
              if (target) choose(target.path);
            }
          }}
        />
      </div>

      {open && query.trim().length > 0 && (
        <div className="absolute inset-x-0 top-11 z-[var(--z-overlay)] overflow-hidden rounded-m border border-line-200 bg-surface-0 shadow-float">
          {results.length > 0 ? (
            <div id={listId} aria-label={t('contextBar.search.preview.results')}>
              {results.map((item, index) => (
                <button
                  key={item.id}
                  type="button"
                  className={
                    index === activeIndex
                      ? 'flex w-full items-center gap-2 bg-tint-100 px-3 py-2 text-start text-meta font-semibold text-forest-900'
                      : 'flex w-full items-center gap-2 px-3 py-2 text-start text-meta text-ink-900 hover:bg-tint-100'
                  }
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => {
                    if (blurTimer.current) window.clearTimeout(blurTimer.current);
                    choose(item.path);
                  }}
                >
                  <Icon name={item.icon} size={15} className="shrink-0 text-gray-500" />
                  <span className="truncate">{t(item.labelKey)}</span>
                </button>
              ))}
            </div>
          ) : (
            <p className="px-3 py-2.5 text-meta text-gray-600">
              {t('contextBar.search.preview.noResults')}
            </p>
          )}
          <p className="border-t border-line-200 bg-tint-100/60 px-3 py-2 text-caption text-gray-600">
            {t('contextBar.search.preview.scope')}
          </p>
        </div>
      )}
    </div>
  );
}
