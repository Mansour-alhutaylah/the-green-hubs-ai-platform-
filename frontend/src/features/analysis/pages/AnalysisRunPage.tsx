import { useParams } from 'react-router';
import { useLocale } from '@/lib/i18n/useLocale';
import { StubModulePage } from '@/shell/StubModulePage';

export function AnalysisRunPage() {
  const { t } = useLocale();
  const { runId } = useParams<{ runId: string }>();
  return <StubModulePage title={t('nav.analysis')} subtitle={runId} />;
}
