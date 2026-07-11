import { Link, useLocation } from 'react-router';
import { cn } from '@/lib/utils/cn';
import { Icon, DiamondGlyph, Tooltip } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { activeNavItemId, type NavItem } from '@/app/navigation/navConfig';

/** §3.1: icon identifies the module; the diamond glyph is the status
 * language layered alongside it — filled bullet for active, hollow outline
 * in place of the object icon for a not-yet-shipped placeholder module
 * (§14.4: "status is never an icon... icons identify objects and actions
 * only"). */
export function RailItem({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const { t } = useLocale();
  const location = useLocation();
  const isActive = activeNavItemId(location.pathname) === item.id;
  const label = t(item.labelKey);

  const link = (
    <Link
      to={item.path}
      aria-current={isActive ? 'page' : undefined}
      className={cn(
        'focus-on-forest relative flex h-11 items-center gap-3 px-6 text-body font-semibold transition-colors duration-[var(--motion-fast)]',
        isActive
          ? 'bg-rail-active text-white'
          : 'text-rail-text hover:bg-rail-hover hover:text-white',
        item.placeholder && !isActive && 'text-rail-muted',
        collapsed && 'justify-center px-0',
      )}
    >
      {isActive && (
        <span
          className="absolute inset-y-0 start-0 w-[var(--size-active-bar)] bg-leaf-500"
          aria-hidden
        />
      )}

      <span className="flex w-5 shrink-0 items-center justify-center">
        {item.placeholder ? (
          <DiamondGlyph variant="hollow" size={14} />
        ) : (
          <Icon name={item.icon} size={20} />
        )}
      </span>

      {!collapsed && (
        <>
          {isActive && (
            <DiamondGlyph variant="filled" size={8} className="shrink-0 text-leaf-500" />
          )}
          <span className="truncate">{label}</span>
          {item.placeholder && (
            <span className="type-label ms-auto shrink-0 text-leaf-500">{t('nav.soon')}</span>
          )}
        </>
      )}
    </Link>
  );

  if (!collapsed) return link;

  return (
    <Tooltip content={label} side="right">
      {link}
    </Tooltip>
  );
}
