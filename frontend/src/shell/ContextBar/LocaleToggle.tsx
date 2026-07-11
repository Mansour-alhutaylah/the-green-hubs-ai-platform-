import { useLocale } from '@/lib/i18n/useLocale';

/** §3.2: instant locale + direction switch, preserving the current route. */
export function LocaleToggle() {
  const { locale, toggleLocale } = useLocale();
  return (
    <button
      type="button"
      onClick={toggleLocale}
      className="type-label shrink-0 whitespace-nowrap rounded-m px-2 py-1.5 text-gray-600 hover:bg-tint-100 hover:text-forest-900"
    >
      {locale === 'en' ? 'AR / EN' : 'EN / AR'}
    </button>
  );
}
