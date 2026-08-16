import { Icon } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';

/**
 * Global search is **not implemented**. Retrieval search is an F2 target
 * against the real backend; until then this control states that plainly
 * instead of looking like a working search box.
 *
 * What changed and why: this used to render a focusable `<input>` with a
 * placeholder and a "/" shortcut badge. Nothing was ever searched — typing
 * produced no request and no results — so the affordance was a promise the
 * product could not keep. It is now a non-interactive, non-focusable label:
 * there is no input to focus, the "/" shortcut no longer targets anything
 * (see `useGlobalShortcuts`), and no search request can be emitted because
 * no code path exists to emit one.
 *
 * The shell layout is unchanged — same slot, same height, same width — so
 * the Context Bar does not reflow.
 */
export function GlobalSearch() {
  const { t } = useLocale();

  return (
    <div
      className="flex h-9 w-70 items-center gap-2 rounded-m border border-dashed border-line-300 bg-tint-100 px-3"
      // Presentational only: it names a capability that does not exist yet
      // rather than offering one, so it is not a control and takes no part
      // in the tab order.
    >
      <Icon name="search" size={16} className="shrink-0 text-gray-400" aria-hidden />
      <span className="truncate text-meta font-semibold text-gray-600">
        {t('contextBar.search.unavailable')}
      </span>
    </div>
  );
}
