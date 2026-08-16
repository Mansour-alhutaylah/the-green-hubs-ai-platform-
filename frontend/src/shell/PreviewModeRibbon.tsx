import { DiamondGlyph } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { isPreviewMode } from '@/lib/data/source';

export const PREVIEW_RIBBON_TEST_ID = 'preview-mode-ribbon';

/**
 * The shell-level Preview disclosure.
 *
 * Rendered by `AppShell`, so it is present on every protected route and
 * survives navigation without each page having to remember it. It is
 * non-dismissible on purpose: a reviewer must never be able to reach a
 * state where synthetic data is on screen with nothing saying so.
 *
 * It renders nothing at all in Live mode — the check is the build-time
 * mode, not a prop, a query parameter, or a stored preference, so no
 * browser-controlled value can either summon it or suppress it.
 *
 * Styling stays inside the canonical token set (Forest surface, white text,
 * Leaf accent — the same treatment as the dashboard hero), so it reads as
 * part of the product rather than a foreign banner. White on `forest-900`
 * clears AA comfortably; `text-white/80` on the same surface is used only
 * for the secondary sentence, which still measures above 4.5:1.
 */
export function PreviewModeRibbon() {
  const { t } = useLocale();

  if (!isPreviewMode()) return null;

  return (
    <aside
      data-testid={PREVIEW_RIBBON_TEST_ID}
      aria-label={t('preview.ribbon.label')}
      className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-leaf-500/40 bg-forest-900 px-3 py-2 text-white sm:px-4 md:px-6 xl:px-8"
    >
      <span className="inline-flex shrink-0 items-center gap-2 rounded-full border border-leaf-300/40 bg-white/10 px-2.5 py-0.5 text-caption font-bold uppercase tracking-wide">
        <DiamondGlyph variant="filled" size={8} className="text-leaf-300" />
        {t('preview.ribbon.label')}
      </span>
      <p className="min-w-0 text-caption font-semibold text-white">
        {t('preview.ribbon.demonstration')}{' '}
        <span className="font-medium text-white/80">{t('preview.ribbon.notProduction')}</span>
      </p>
    </aside>
  );
}
