import { useNavigate } from 'react-router';
import { Button, Icon } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { ROUTES } from '@/app/navigation/routePaths';
import { AuthSplitLayout } from '../components/AuthSplitLayout';
import { AuthPageHeader } from '../components/AuthPageHeader';

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
        <Icon name="circle-alert" size={28} className="mb-5 text-amber-700" />
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
