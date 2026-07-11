import { useLocale } from '@/lib/i18n/useLocale';
import { StubModulePage } from '@/shell/StubModulePage';

/** Editor+ only — RoleGuard keeps this unreachable (and its rail item
 * absent) below that tier (§11.3). */
export function DocumentUploadPage() {
  const { t } = useLocale();
  return <StubModulePage title={t('nav.upload')} />;
}
