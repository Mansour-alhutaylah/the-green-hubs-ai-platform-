import { useLocale } from '@/lib/i18n/useLocale';
import { PlaceholderModulePage } from '../components/PlaceholderModulePage';

export function FrameworksPage() {
  const { t } = useLocale();
  return (
    <PlaceholderModulePage
      title={t('nav.frameworks')}
      icon="frameworks"
      description={t('placeholder.frameworks.description')}
      unlock={t('placeholder.frameworks.unlock')}
    />
  );
}
