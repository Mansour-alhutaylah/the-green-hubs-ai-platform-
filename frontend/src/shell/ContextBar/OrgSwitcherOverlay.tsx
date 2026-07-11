import { cn } from '@/lib/utils/cn';
import { Avatar, DiamondGlyph } from '@/design-system';
import { localizedOrgName, type MockOrganization } from '@/features/organizations/mockOrgs';
import { useLocale } from '@/lib/i18n/useLocale';

export function OrgSwitcherOverlay({
  organizations,
  activeOrgId,
  onSelect,
}: {
  organizations: MockOrganization[];
  activeOrgId: string | null;
  onSelect: (orgId: string) => void;
}) {
  const { locale } = useLocale();

  return (
    <ul className="w-80 py-1">
      {organizations.map((org) => {
        const isActive = org.id === activeOrgId;
        return (
          <li key={org.id}>
            <button
              type="button"
              onClick={() => onSelect(org.id)}
              className={cn(
                'flex w-full items-center gap-3 px-4 py-2.5 text-start text-body hover:bg-tint-100',
                isActive && 'bg-leaf-100',
              )}
            >
              <Avatar name={org.name} shape="square" size={24} />
              <span className="flex-1 truncate" data-user-content>
                {localizedOrgName(org, locale)}
              </span>
              {isActive && <DiamondGlyph variant="filled" size={8} className="text-leaf-700" />}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
