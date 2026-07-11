import { Link } from 'react-router';
import { EmptyState } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { ROUTES } from '@/app/navigation/routePaths';

/** Stub per Phase 1 scope — the Notifications module's real feed is a
 * later phase's business logic (Appendix D's event catalog). */
export function NotificationsPanel() {
  const { t } = useLocale();
  return (
    <div className="w-105 p-2">
      <EmptyState title={t('contextBar.notifications.empty')} />
      <Link
        to={ROUTES.notifications}
        className="block px-4 pb-2 text-center text-meta text-leaf-700 hover:underline"
      >
        {t('nav.notifications')}
      </Link>
    </div>
  );
}
