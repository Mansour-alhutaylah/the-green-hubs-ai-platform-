import { useLocale } from '@/lib/i18n/useLocale';

/**
 * §17 keyboard operability: the Command Rail is the first focusable region
 * on every authenticated page (brand block, then every nav item) — without
 * this, a keyboard user re-tabs through the entire rail on every single
 * navigation before reaching page content. Visually hidden until focused,
 * per the standard skip-link pattern.
 */
export function SkipLink() {
  const { t } = useLocale();
  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:fixed focus:start-4 focus:top-4 focus:z-[var(--z-toast)] focus:rounded-m focus:bg-forest-900 focus:px-4 focus:py-2 focus:text-body focus:text-white"
    >
      {t('shell.skipToContent')}
    </a>
  );
}
