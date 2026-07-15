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
    <div className="mb-7 flex min-w-0 items-center gap-3 rounded-l border border-leaf-300 bg-mist-50 px-3.5 py-3 shadow-card">
      <Avatar name={organization.name} shape="square" size={32} />
      <div className="min-w-0">
        <p className="break-words text-meta font-bold text-ink-900" data-user-content>
          {localizedOrgName(organization, locale)}
        </p>
        <p className="mt-0.5 break-words text-caption text-gray-600" data-user-content>{organization.sector}</p>
      </div>
    </div>
  );
}
