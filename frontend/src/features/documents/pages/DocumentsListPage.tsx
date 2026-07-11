import { useLocale } from '@/lib/i18n/useLocale';
import { StubModulePage } from '@/shell/StubModulePage';

export function DocumentsListPage() {
  const { t } = useLocale();
  return <StubModulePage title={t('nav.documents')} />;
}
