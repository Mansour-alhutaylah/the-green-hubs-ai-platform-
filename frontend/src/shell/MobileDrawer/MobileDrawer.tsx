import * as DialogPrimitive from '@radix-ui/react-dialog';
import { Icon } from '@/design-system';
import { useAuth } from '@/features/auth/useAuth';
import { NAV_DOMAIN_ORDER, visibleNavItemsForDomain } from '@/app/navigation/navConfig';
import { useLocale } from '@/lib/i18n/useLocale';
import { BrandBlock } from '../CommandRail/BrandBlock';
import { RailGroup } from '../CommandRail/RailGroup';
import { SovereigntySeal } from '../CommandRail/SovereigntySeal';

/** §13 mobile behavior: below 768px the rail disappears entirely in favor
 * of a hamburger-triggered full-height Forest drawer carrying the same IA
 * in the same order, sliding from the rail's logical side (right in RTL).
 *
 * The drawer is a dialog surface, so its Content sits on `--z-dialog` (60)
 * above the `--z-overlay` (50) backdrop — the same pairing the Dialog
 * primitive uses. It previously carried `--z-rail` (40), which put the
 * full-viewport backdrop *over* the drawer: every tap on a nav item landed
 * on the backdrop, which Radix reads as a click outside the Content and
 * dismisses on, so the drawer closed instead of navigating.
 */
export function MobileDrawer({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { user } = useAuth();
  const { t, dir } = useLocale();

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay
          data-testid="mobile-drawer-overlay"
          className="fixed inset-0 z-[var(--z-overlay)] bg-overlay [animation:overlay-fade-in_var(--motion-base)_var(--ease-out)]"
        />
        <DialogPrimitive.Content
          data-testid="mobile-drawer"
          aria-label={t('shell.nav.title')}
          // `h-[100dvh]` rather than `inset-y-0` alone: on iOS Safari the
          // dynamic browser chrome otherwise leaves the drawer's last items
          // and the seal underneath the toolbar.
          className="brand-rail rail-scrollbar fixed inset-y-0 start-0 z-[var(--z-dialog)] flex h-[100dvh] w-66 max-w-[85vw] flex-col overflow-y-auto overscroll-contain border-e border-rail-hairline focus:outline-none"
          style={{
            animation: `${dir === 'rtl' ? 'drawer-in-rtl' : 'drawer-in-ltr'} var(--motion-base) var(--ease-out)`,
            paddingTop: 'env(safe-area-inset-top)',
            paddingBottom: 'env(safe-area-inset-bottom)',
            paddingInlineStart: dir === 'rtl' ? undefined : 'env(safe-area-inset-left)',
            paddingInlineEnd: dir === 'rtl' ? 'env(safe-area-inset-right)' : undefined,
          }}
        >
          <DialogPrimitive.Title className="sr-only">{t('shell.nav.title')}</DialogPrimitive.Title>

          <div className="relative z-10 flex shrink-0 items-center gap-2 pe-3">
            <div className="min-w-0 flex-1">
              <BrandBlock collapsed={false} />
            </div>
            <DialogPrimitive.Close
              aria-label={t('shell.nav.close')}
              className="focus-on-forest flex h-11 w-11 shrink-0 items-center justify-center rounded-m border border-rail-hairline text-rail-text transition-colors hover:bg-rail-hover hover:text-white"
            >
              <Icon name="x" size={20} />
            </DialogPrimitive.Close>
          </div>

          <div className="relative z-10 flex-1 py-3">
            {NAV_DOMAIN_ORDER.map((domain) => (
              <RailGroup
                key={domain}
                domain={domain}
                items={visibleNavItemsForDomain(domain, user?.role ?? null)}
                collapsed={false}
              />
            ))}
          </div>
          <SovereigntySeal collapsed={false} />
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
