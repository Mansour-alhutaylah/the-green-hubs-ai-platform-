import { useParams } from 'react-router';
import { useLocale } from '@/lib/i18n/useLocale';
import { StubModulePage } from '@/shell/StubModulePage';

export function ReportDetailPage() {
  const { t } = useLocale();
  const { id } = useParams<{ id: string }>();
  return <StubModulePage title={t('nav.reports')} subtitle={id} />;
}
