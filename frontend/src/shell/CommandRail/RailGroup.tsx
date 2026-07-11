import { useLocale } from '@/lib/i18n/useLocale';
import type { NavDomain, NavItem } from '@/app/navigation/navConfig';
import { NAV_DOMAIN_LABEL_KEYS } from '@/app/navigation/navConfig';
import { RailItem } from './RailItem';

export function RailGroup({
  domain,
  items,
  collapsed,
}: {
  domain: NavDomain;
  items: NavItem[];
  collapsed: boolean;
}) {
  const { t } = useLocale();
  if (items.length === 0) return null;

  return (
    <div className="mt-7 first:mt-0">
      {!collapsed && (
        <p className="type-label mb-2.5 px-6 text-rail-muted">{t(NAV_DOMAIN_LABEL_KEYS[domain])}</p>
      )}
      {collapsed && <div className="mx-6 mb-2 border-t border-rail-hairline" aria-hidden />}
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            <RailItem item={item} collapsed={collapsed} />
          </li>
        ))}
      </ul>
    </div>
  );
}
