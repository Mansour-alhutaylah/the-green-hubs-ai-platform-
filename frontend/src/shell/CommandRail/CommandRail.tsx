import { useRef, type KeyboardEvent } from 'react';
import { Icon } from '@/design-system';
import { useAuth } from '@/features/auth/useAuth';
import { NAV_DOMAIN_ORDER, visibleNavItemsForDomain } from '@/app/navigation/navConfig';
import { BrandBlock } from './BrandBlock';
import { RailGroup } from './RailGroup';
import { SovereigntySeal } from './SovereigntySeal';

export interface CommandRailProps {
  isCollapsed: boolean;
  onToggle: () => void;
}

/**
 * §3.1: the fixed, single dark surface of the product. Filters every nav
 * item by the signed-in user's tier before rendering — items are simply
 * absent below their `minTier`, never shown-but-disabled (§4/§19). Collapse
 * state is owned by AppShell (via useRailPreference) since the content
 * area's start-margin must stay in sync with the rail's rendered width.
 */
export function CommandRail({ isCollapsed, onToggle }: CommandRailProps) {
  const navRef = useRef<HTMLElement | null>(null);

  function handleArrowKeys(event: KeyboardEvent<HTMLElement>) {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    const focusable = Array.from(navRef.current?.querySelectorAll<HTMLElement>('a[href]') ?? []);
    const currentIndex = focusable.indexOf(document.activeElement as HTMLElement);
    if (currentIndex === -1) return;
    event.preventDefault();
    const delta = event.key === 'ArrowDown' ? 1 : -1;
    const nextIndex = (currentIndex + delta + focusable.length) % focusable.length;
    focusable[nextIndex]?.focus();
  }

  return (
    <nav
      ref={navRef}
      aria-label="Primary"
      onKeyDown={handleArrowKeys}
      style={{ width: isCollapsed ? 'var(--size-rail-collapsed)' : 'var(--size-rail)' }}
      className="brand-rail rail-scrollbar fixed inset-y-0 start-0 z-[var(--z-rail)] flex h-full shrink-0 flex-col overflow-y-auto border-e border-rail-hairline transition-[width] duration-[var(--motion-base)]"
    >
      <BrandBlock collapsed={isCollapsed} />

      <div className="relative z-10 flex-1 py-3">
        {NAV_DOMAIN_ORDER.map((domain) => (
          <VisibleRailGroup key={domain} domain={domain} collapsed={isCollapsed} />
        ))}
      </div>

      <button
        type="button"
        onClick={onToggle}
        aria-pressed={isCollapsed}
        aria-label={isCollapsed ? 'Expand navigation' : 'Collapse navigation'}
        className="focus-on-forest relative z-10 mx-3 mb-2 flex h-9 items-center justify-center rounded-m border border-rail-hairline bg-white/5 text-rail-muted transition-colors hover:bg-rail-hover hover:text-white"
      >
        <Icon
          name="chevron-right"
          size={16}
          className={isCollapsed ? undefined : 'rotate-180'}
        />
      </button>

      <SovereigntySeal collapsed={isCollapsed} />
    </nav>
  );
}

function VisibleRailGroup({
  domain,
  collapsed,
}: {
  domain: (typeof NAV_DOMAIN_ORDER)[number];
  collapsed: boolean;
}) {
  const { user } = useAuth();
  const items = visibleNavItemsForDomain(domain, user?.role ?? null);
  return <RailGroup domain={domain} items={items} collapsed={collapsed} />;
}
