import { Role, meetsMinTier } from '@/features/rbac/roles';
import type { IconName } from '@/design-system';
import type { StringKey } from '@/lib/i18n/strings/en';
import { ROUTES } from './routePaths';

export type NavDomain = 'oversight' | 'operations' | 'intelligence' | 'administration';

export interface NavItem {
  id: string;
  path: string;
  labelKey: StringKey;
  icon: IconName;
  domain: NavDomain;
  /** Appendix A minimum tier to see this item/route at all — render-time
   * hidden below this tier, never disabled (§4/§19). */
  minTier: Role;
  /** Phase-2/3 modules (§0.3, §11.8): hollow diamond + "SOON" tag, but
   * still a real, clickable route. */
  placeholder?: boolean;
}

export const NAV_DOMAIN_ORDER: NavDomain[] = [
  'oversight',
  'operations',
  'intelligence',
  'administration',
];

export const NAV_DOMAIN_LABEL_KEYS: Record<NavDomain, StringKey> = {
  oversight: 'nav.domain.oversight',
  operations: 'nav.domain.operations',
  intelligence: 'nav.domain.intelligence',
  administration: 'nav.domain.administration',
};

/**
 * Single source of truth for both the Command Rail's items and each
 * gated route's minimum tier (Appendix A) — RoleGuard reads `minTier` from
 * here via `findNavItem`, so the permission table is only ever encoded
 * once.
 */
export const NAV_ITEMS: NavItem[] = [
  {
    id: 'dashboard',
    path: ROUTES.dashboard,
    labelKey: 'nav.dashboard',
    icon: 'dashboard',
    domain: 'oversight',
    minTier: Role.Viewer,
  },
  {
    id: 'reports',
    path: ROUTES.reports,
    labelKey: 'nav.reports',
    icon: 'reports',
    domain: 'oversight',
    minTier: Role.Viewer,
  },

  {
    id: 'documents',
    path: ROUTES.documents,
    labelKey: 'nav.documents',
    icon: 'documents',
    domain: 'operations',
    minTier: Role.Viewer,
  },
  {
    id: 'upload',
    path: ROUTES.documentUpload,
    labelKey: 'nav.upload',
    icon: 'upload',
    domain: 'operations',
    minTier: Role.Editor,
  },
  {
    id: 'analysis',
    path: ROUTES.analysis,
    labelKey: 'nav.analysis',
    icon: 'analysis',
    domain: 'operations',
    minTier: Role.Viewer,
  },

  {
    id: 'hub-zero',
    path: ROUTES.hubZero,
    labelKey: 'nav.hubZero',
    icon: 'hub-diamond',
    domain: 'intelligence',
    minTier: Role.Viewer,
    placeholder: true,
  },
  {
    id: 'carbon',
    path: ROUTES.carbon,
    labelKey: 'nav.carbon',
    icon: 'carbon',
    domain: 'intelligence',
    minTier: Role.Viewer,
    placeholder: true,
  },
  {
    id: 'telemetry',
    path: ROUTES.telemetry,
    labelKey: 'nav.telemetry',
    icon: 'telemetry',
    domain: 'intelligence',
    minTier: Role.Viewer,
    placeholder: true,
  },

  {
    id: 'organizations',
    path: ROUTES.organizations,
    labelKey: 'nav.organizations',
    icon: 'organizations',
    domain: 'administration',
    minTier: Role.Viewer,
  },
  {
    id: 'users',
    path: ROUTES.users,
    labelKey: 'nav.users',
    icon: 'users',
    domain: 'administration',
    minTier: Role.Admin,
  },
  {
    id: 'frameworks',
    path: ROUTES.frameworks,
    labelKey: 'nav.frameworks',
    icon: 'frameworks',
    domain: 'administration',
    minTier: Role.Viewer,
    placeholder: true,
  },
  {
    id: 'audit',
    path: ROUTES.audit,
    labelKey: 'nav.audit',
    icon: 'audit',
    domain: 'administration',
    minTier: Role.Viewer,
    placeholder: true,
  },
  {
    id: 'settings',
    path: ROUTES.settings,
    labelKey: 'nav.settings',
    icon: 'settings',
    domain: 'administration',
    minTier: Role.Admin,
  },
];

export function findNavItem(id: string): NavItem {
  const item = NAV_ITEMS.find((navItem) => navItem.id === id);
  if (!item) throw new Error(`Unknown nav item id: ${id}`);
  return item;
}

export function navItemsForDomain(domain: NavDomain): NavItem[] {
  return NAV_ITEMS.filter((item) => item.domain === domain);
}

/**
 * The single RBAC nav-filtering rule (§4/§19: items are absent below their
 * `minTier`, never disabled) — both CommandRail and MobileDrawer render the
 * same domain groups and must apply this identically, so it lives here
 * once rather than being re-implemented per surface. Takes a plain
 * `Role | null` (not a hook) so it can be called from a `.map()` without
 * violating the rules of hooks; callers read `user` via `useAuth()` once
 * and pass `user?.role ?? null`.
 */
export function visibleNavItemsForDomain(domain: NavDomain, userRole: Role | null): NavItem[] {
  return navItemsForDomain(domain).filter(
    (item) => userRole != null && meetsMinTier(userRole, item.minTier),
  );
}

/**
 * Resolves which single nav item should render "active" for a given
 * pathname. Plain prefix matching would make Documents falsely light up
 * for /documents/upload (whose own item's path is a longer, more specific
 * prefix) — so a match only wins if no sibling item matches a longer path.
 */
export function activeNavItemId(pathname: string): string | undefined {
  const matches = (path: string) => pathname === path || pathname.startsWith(`${path}/`);
  const candidates = NAV_ITEMS.filter((item) => matches(item.path));
  const mostSpecific = candidates.reduce<NavItem | undefined>((best, item) => {
    if (!best || item.path.length > best.path.length) return item;
    return best;
  }, undefined);
  return mostSpecific?.id;
}
