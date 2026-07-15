import { useLocale } from '@/lib/i18n/useLocale';

/** §3.2: instant locale + direction switch, preserving the current route. */
export function LocaleToggle() {
  const { locale, toggleLocale } = useLocale();
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
