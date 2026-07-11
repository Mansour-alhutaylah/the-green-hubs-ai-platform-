import { useNavigate } from 'react-router';
import { Button, Icon } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { ROUTES } from '@/app/navigation/routePaths';
import { AuthSplitLayout } from '../components/AuthSplitLayout';
import { AuthPageHeader } from '../components/AuthPageHeader';

/** Reached when a stored session has aged out — distinct from
 * `NoAccessPage` (an in-shell RBAC denial): this is a full auth-flow page,
 * shown before the shell mounts at all. */
export function SessionExpiredPage() {
  const { t } = useLocale();
  const navigate = useNavigate();

  return (
    <AuthSplitLayout>
      <div>
        <Icon name="circle-alert" size={28} className="mb-5 text-amber-700" />
        <AuthPageHeader
          eyebrow={t('auth.sessionExpired.eyebrow')}
          heading={t('auth.sessionExpired.heading')}
          supporting={t('auth.sessionExpired.supporting')}
        />
        <Button size="xl" className="w-full" onClick={() => navigate(ROUTES.login, { replace: true })}>
          {t('auth.sessionExpired.cta')}
        </Button>
      </div>
    </AuthSplitLayout>
  );
}
