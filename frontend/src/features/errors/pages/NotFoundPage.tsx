import { useNavigate } from 'react-router';
import { Button, EmptyState } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { ROUTES } from '@/app/navigation/routePaths';

/** §7: "404 / no-access render inside the shell with the standard
 * empty-state pattern and a 'Back to dashboard' primary action" — rendered
 * as an ordinary nested route, so the rail/context bar stay visible. */
export function NotFoundPage() {
  const { t } = useLocale();
  const navigate = useNavigate();

  return (
    <EmptyState
      headingLevel={1}
      title={t('errors.notFound.title')}
      description={t('errors.notFound.body')}
      action={
        <Button variant="ghost" onClick={() => navigate(ROUTES.dashboard)}>
          {t('errors.backToDashboard')}
        </Button>
      }
    />
  );
}
