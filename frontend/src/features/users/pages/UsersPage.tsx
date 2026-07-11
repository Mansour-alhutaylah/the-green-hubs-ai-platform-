import { useLocale } from '@/lib/i18n/useLocale';
import { StubModulePage } from '@/shell/StubModulePage';

/** Admin+ only (Appendix A) — RoleGuard covers the route itself. */
export function UsersPage() {
  const { t } = useLocale();
  return <StubModulePage title={t('nav.users')} />;
}
