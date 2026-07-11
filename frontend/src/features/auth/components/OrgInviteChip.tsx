import { Avatar } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { localizedOrgName, type MockOrganization } from '@/features/organizations/mockOrgs';

export interface OrgInviteChipProps {
  organization: MockOrganization;
}

/** Invitation Acceptance shows which organization/hub the invite belongs
 * to before the user commits to a password — the same square-avatar
 * pattern the Context Bar's org switcher already uses. */
export function OrgInviteChip({ organization }: OrgInviteChipProps) {
  const { locale } = useLocale();
  return (
    <div className="mb-7 flex items-center gap-3 rounded-m border border-line-200 bg-surface-0 px-3.5 py-2.5">
      <Avatar name={organization.name} shape="square" size={32} />
      <div>
        <p className="text-meta font-bold text-ink-900" data-user-content>
          {localizedOrgName(organization, locale)}
        </p>
        <p className="text-caption text-gray-600">{organization.sector}</p>
      </div>
    </div>
  );
}
