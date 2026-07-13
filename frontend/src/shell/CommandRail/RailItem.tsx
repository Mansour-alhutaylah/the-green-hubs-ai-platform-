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
  const { t, dir } = useLocale();
  const location = useLocation();
  const isActive = activeNavItemId(location.pathname) === item.id;
  const label = t(item.labelKey);

  const link = (
    <Link
      to={item.path}
      aria-current={isActive ? 'page' : undefined}
      className={cn(
        'focus-on-forest group relative mx-3 flex h-11 items-center gap-3 rounded-m border px-3 text-body font-semibold transition-all duration-[var(--motion-fast)]',
        isActive
          ? 'border-rail-hairline bg-rail-active text-white shadow-raise'
          : 'border-transparent text-rail-text hover:border-rail-hairline hover:bg-rail-hover hover:text-white',
        item.placeholder && !isActive && 'text-rail-muted',
        collapsed && 'mx-2 justify-center px-0',
      )}
    >
      {isActive && (
        <span
          className="absolute inset-y-2 start-0 w-[var(--size-active-bar)] rounded-e-full bg-leaf-500 shadow-signal"
          aria-hidden
        />
      )}

      <span
        className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-m bg-white/5 text-rail-text transition-colors group-hover:bg-white/10 group-hover:text-white',
          isActive && 'bg-leaf-500/20 text-leaf-300',
        )}
      >
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
      <Tooltip content={label} side={dir === 'rtl' ? 'left' : 'right'}>
      {link}
    </Tooltip>
  );
}
