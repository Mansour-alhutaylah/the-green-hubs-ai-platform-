import * as DialogPrimitive from '@radix-ui/react-dialog';
import { useAuth } from '@/features/auth/useAuth';
import { NAV_DOMAIN_ORDER, visibleNavItemsForDomain } from '@/app/navigation/navConfig';
import { useLocale } from '@/lib/i18n/useLocale';
import { BrandBlock } from '../CommandRail/BrandBlock';
import { RailGroup } from '../CommandRail/RailGroup';
import { SovereigntySeal } from '../CommandRail/SovereigntySeal';

/** §13 mobile behavior: below 768px the rail disappears entirely in favor
 * of a hamburger-triggered full-height Forest drawer carrying the same IA
 * in the same order, sliding from the rail's logical side (right in RTL). */
export function MobileDrawer({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { user } = useAuth();
  const { dir } = useLocale();

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-[var(--z-overlay)] bg-overlay [animation:overlay-fade-in_var(--motion-base)_var(--ease-out)]" />
        <DialogPrimitive.Content
          className="brand-rail rail-scrollbar fixed inset-y-0 start-0 z-[var(--z-rail)] flex w-66 max-w-[86vw] flex-col overflow-y-auto border-e border-rail-hairline focus:outline-none"
          style={{
            animation: `${dir === 'rtl' ? 'drawer-in-rtl' : 'drawer-in-ltr'} var(--motion-base) var(--ease-out)`,
          }}
        >
          <DialogPrimitive.Title className="sr-only">Navigation</DialogPrimitive.Title>
          <BrandBlock collapsed={false} />
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
