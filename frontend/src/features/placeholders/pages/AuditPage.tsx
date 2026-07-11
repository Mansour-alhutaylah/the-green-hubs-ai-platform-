import { useLocale } from '@/lib/i18n/useLocale';
import { PlaceholderModulePage } from '../components/PlaceholderModulePage';

export function AuditPage() {
  const { t } = useLocale();
  return (
    <PlaceholderModulePage
      title={t('nav.audit')}
      icon="audit"
      description={t('placeholder.audit.description')}
      unlock={t('placeholder.audit.unlock')}
    />
  );
}
