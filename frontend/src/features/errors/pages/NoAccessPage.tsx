import { useNavigate } from 'react-router';
import { Button, EmptyState } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { ROUTES } from '@/app/navigation/routePaths';

/** RoleGuard's fallback for a route above the current user's tier (§19:
 * permissions are hidden at the nav level, but a direct URL still needs an
 * in-shell response rather than a raw redirect). */
export function NoAccessPage() {
  const { t } = useLocale();
  const navigate = useNavigate();

  return (
    <EmptyState
      headingLevel={1}
      title={t('errors.noAccess.title')}
      description={t('errors.noAccess.body')}
      action={
        <Button variant="ghost" onClick={() => navigate(ROUTES.dashboard)}>
          {t('errors.backToDashboard')}
        </Button>
      }
    />
  );
}
