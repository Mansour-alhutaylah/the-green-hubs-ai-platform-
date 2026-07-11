import { useLocale } from '@/lib/i18n/useLocale';
import { useAuth } from '@/features/auth/useAuth';
import { Avatar, RoleBadge } from '@/design-system';
import { PageHeader } from '@/shell/PageHeader';
import { ModulePendingNotice } from '@/shell/ModulePendingNotice';

export function ProfilePage() {
  const { t } = useLocale();
  const { user } = useAuth();

  return (
    <div>
      <PageHeader title={t('nav.profile')} />
      <div className="flex max-w-160 flex-col gap-6">
        {user && (
          <div className="flex items-center gap-4 rounded-l border border-line-200 bg-surface-0 p-6">
            <Avatar name={user.name} size={40} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-panel text-forest-900" data-user-content>
                {user.name}
              </p>
              <p className="truncate text-body text-gray-600">{user.email}</p>
            </div>
            <RoleBadge role={user.role} className="shrink-0" />
          </div>
        )}
        <ModulePendingNotice />
      </div>
    </div>
  );
}
