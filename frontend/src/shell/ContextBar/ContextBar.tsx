import type { ReactNode } from 'react';
import { OrgSwitcher } from './OrgSwitcher';
import { Breadcrumb } from './Breadcrumb';
import { GlobalSearch } from './GlobalSearch';
import { LocaleToggle } from './LocaleToggle';
import { NotificationsBell } from './NotificationsBell';
import { ProfileMenu } from './ProfileMenu';

/** §3.2: the 64px white bar spanning the content area (never the rail),
 * left→right: org switcher, breadcrumb, spacer, global search, locale
 * toggle, notifications, profile.
 *
 * The leading group (menu button / org switcher / breadcrumb) is the only
 * one allowed to shrink (`min-w-0 flex-1`) — the trailing icon cluster
 * stays a fixed size (`shrink-0`) so it can never get pushed off-screen on
 * narrow viewports; the org name itself truncates within whatever space
 * that leaves it (§3.2's 320px org-switcher overlay is unaffected, this is
 * just the collapsed trigger's label width). */
export function ContextBar({ menuButton }: { menuButton?: ReactNode }) {
  return (
    <header
      data-testid="context-bar"
      className="sticky top-0 z-[var(--z-bar)] flex h-16 shrink-0 items-center gap-2 border-b border-line-200 bg-surface-0/95 px-3 backdrop-blur-sm sm:gap-4 sm:px-4 md:px-8"
    >
      <div className="flex min-w-0 flex-1 items-center gap-4">
        {menuButton}
        <OrgSwitcher />
        <div className="hidden md:block">
          <Breadcrumb />
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1 sm:gap-2">
        <div className="hidden items-center md:flex">
          <GlobalSearch />
        </div>
        <LocaleToggle />
        <NotificationsBell />
        <ProfileMenu />
      </div>
    </header>
  );
}
