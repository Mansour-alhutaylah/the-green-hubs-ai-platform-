import { useLocale } from '@/lib/i18n/useLocale';
import { PlaceholderModulePage } from '../components/PlaceholderModulePage';

export function HubZeroPage() {
  const { t } = useLocale();
  return (
    <PlaceholderModulePage
      title={t('nav.hubZero')}
      icon="hub-diamond"
      description={t('placeholder.hubZero.description')}
      unlock={t('placeholder.hubZero.unlock')}
    />
  );
}
