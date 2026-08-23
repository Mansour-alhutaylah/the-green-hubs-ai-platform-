import { useLocale } from '@/lib/i18n/useLocale';
import { hasSelectableLocales } from '@/lib/i18n/availability';

/**
 * §3.2: instant locale + direction switch, preserving the current route.
 *
 * Hidden for the MVP, which ships English only — a control offering a
 * language the product does not yet render in full would be a promise it
 * cannot keep. The component is kept, and kept mounted, rather than
 * deleted: the switch, the `dir` handling behind it, and the RTL layout
 * work are all intact and return the moment `AVAILABLE_LOCALES` gains a
 * second entry.
 */
export function LocaleToggle() {
  const { locale, toggleLocale } = useLocale();

  if (!hasSelectableLocales()) return null;

  return (
    <button
      type="button"
      onClick={toggleLocale}
      className="type-label min-h-10 shrink-0 whitespace-nowrap rounded-m px-2 text-gray-600 transition-colors hover:bg-mist-50 hover:text-forest-900"
    >
      {locale === 'en' ? 'AR / EN' : 'EN / AR'}
    </button>
  );
}
