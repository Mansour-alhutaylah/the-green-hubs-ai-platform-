import { useNavigate } from 'react-router';
import { Button } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { ROUTES } from '@/app/navigation/routePaths';
import { AuthSplitLayout } from '../components/AuthSplitLayout';
import { AuthPageHeader } from '../components/AuthPageHeader';
import { AuthStateMark } from '../components/AuthStateMark';

/** Reached when an unauthenticated/unauthorized visitor lands on a route
 * that requires a different account entirely — distinct from
 * `NoAccessPage` (an in-shell RBAC denial for an already-signed-in user
 * whose role tier is too low): this is a full auth-flow page. */
export function AccessDeniedPage() {
  const { t } = useLocale();
  const navigate = useNavigate();

  return (
    <AuthSplitLayout>
      <div>
        <AuthStateMark />
        <AuthPageHeader
          eyebrow={t('auth.accessDenied.eyebrow')}
          heading={t('auth.accessDenied.heading')}
          supporting={t('auth.accessDenied.supporting')}
        />
        <Button size="xl" className="w-full" onClick={() => navigate(ROUTES.login, { replace: true })}>
          {t('auth.accessDenied.cta')}
        </Button>
      </div>
    </AuthSplitLayout>
  );
}
