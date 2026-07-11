import { useNavigate } from 'react-router';
import { Avatar, Icon, PopoverMenu } from '@/design-system';
import { useAuth } from '@/features/auth/useAuth';
import { useLocale } from '@/lib/i18n/useLocale';
import { ROUTES } from '@/app/navigation/routePaths';

export function ProfileMenu() {
  const { user, logout } = useAuth();
  const { t } = useLocale();
  const navigate = useNavigate();

  if (!user) return null;

  async function handleSignOut() {
    await logout();
    navigate(ROUTES.login, { replace: true });
  }

  return (
    <PopoverMenu
      contentClassName="w-50 py-1"
      trigger={
        <button type="button" aria-label={user.name} className="focus-on-forest rounded-full">
          <Avatar name={user.name} size={32} />
        </button>
      }
    >
      <MenuLink label={t('contextBar.profile.profile')} onClick={() => navigate(ROUTES.profile)} />
      <MenuLink
        label={t('contextBar.profile.settings')}
        onClick={() => navigate(ROUTES.settings)}
      />
      <MenuLink
        label={t('contextBar.profile.signOut')}
        onClick={() => void handleSignOut()}
        icon="log-out"
      />
    </PopoverMenu>
  );
}

function MenuLink({
  label,
  onClick,
  icon,
}: {
  label: string;
  onClick: () => void;
  icon?: 'log-out';
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-2 px-4 py-2 text-start text-body text-ink-900 hover:bg-tint-100"
    >
      {icon && <Icon name={icon} size={16} className="text-gray-600" />}
      {label}
    </button>
  );
}
