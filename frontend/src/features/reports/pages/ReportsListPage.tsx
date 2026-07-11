import { useLocale } from '@/lib/i18n/useLocale';
import { StubModulePage } from '@/shell/StubModulePage';

export function ReportsListPage() {
  const { t } = useLocale();
  return <StubModulePage title={t('nav.reports')} />;
}
