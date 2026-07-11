import { useLocale } from '@/lib/i18n/useLocale';
import { PlaceholderModulePage } from '../components/PlaceholderModulePage';

export function TelemetryPage() {
  const { t } = useLocale();
  return (
    <PlaceholderModulePage
      title={t('nav.telemetry')}
      icon="telemetry"
      description={t('placeholder.telemetry.description')}
      unlock={t('placeholder.telemetry.unlock')}
    />
  );
}
