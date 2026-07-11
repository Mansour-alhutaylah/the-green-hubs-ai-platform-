import { useLocale } from '@/lib/i18n/useLocale';
import { PlaceholderModulePage } from '../components/PlaceholderModulePage';

export function CarbonPage() {
  const { t } = useLocale();
  return (
    <PlaceholderModulePage
      title={t('nav.carbon')}
      icon="carbon"
      description={t('placeholder.carbon.description')}
      unlock={t('placeholder.carbon.unlock')}
    />
  );
}
