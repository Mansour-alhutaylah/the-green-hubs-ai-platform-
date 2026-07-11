import { useLocale } from '@/lib/i18n/useLocale';
import { StubModulePage } from '@/shell/StubModulePage';

export function AnalysisListPage() {
  const { t } = useLocale();
  return <StubModulePage title={t('nav.analysis')} />;
}
