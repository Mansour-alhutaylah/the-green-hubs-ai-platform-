import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { Avatar, Icon, PopoverMenu } from '@/design-system';
import { useAuth } from '@/features/auth/useAuth';
import { useLocale } from '@/lib/i18n/useLocale';
import { MOCK_ORGANIZATIONS, localizedOrgName } from '@/features/organizations/mockOrgs';
import { OrgSwitcherOverlay } from './OrgSwitcherOverlay';

/**
 * §3.2/§9.4: selecting an organization reloads the *current* route in the
 * new scope — it never navigates away. Business pages don't yet fetch
 * anything org-scoped, so "reload" here just updates the active-org
 * context; later phases' data hooks read `activeOrgId` and refetch.
 */
export function OrgSwitcher() {
  const { user, activeOrgId, setActiveOrg } = useAuth();
  const { locale, t } = useLocale();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  if (!user) return null;

  const myOrgs = MOCK_ORGANIZATIONS.filter((org) => user.orgIds.includes(org.id));
  const activeOrg = myOrgs.find((org) => org.id === activeOrgId) ?? myOrgs[0];
  if (!activeOrg) return null;

  function handleSelect(orgId: string) {
    setActiveOrg(orgId);
    setOpen(false);
    navigate(`${location.pathname}${location.search}`, { replace: true });
  }

  return (
    <PopoverMenu
      align="start"
      open={open}
      onOpenChange={setOpen}
      trigger={
        <button
          type="button"
          aria-label={t('contextBar.orgSwitcher.label')}
          className="flex min-h-10 min-w-0 items-center gap-2 rounded-m border border-line-200 bg-surface-0 px-2.5 py-1.5 shadow-card transition-colors hover:border-leaf-300 hover:bg-mist-50"
        >
          <Avatar
            name={activeOrg.name}
            shape="square"
            size={24}
            className="hidden ring-2 ring-leaf-100 sm:inline-flex"
          />
          <span
            className="min-w-0 max-w-20 truncate text-body font-bold text-forest-900 sm:max-w-30 md:max-w-45"
            data-user-content
          >
            {localizedOrgName(activeOrg, locale)}
          </span>
          <Icon name="chevron-down" size={16} className="shrink-0 text-gray-600" />
        </button>
      }
    >
      <OrgSwitcherOverlay
        organizations={myOrgs}
        activeOrgId={activeOrg.id}
        onSelect={handleSelect}
      />
    </PopoverMenu>
  );
}
