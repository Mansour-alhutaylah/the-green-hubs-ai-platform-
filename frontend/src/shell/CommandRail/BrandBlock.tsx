import { Link } from 'react-router';
import { BrandLogo } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { ROUTES } from '@/app/navigation/routePaths';

/**
 * Sidebar placement for the single approved company lockup. Collapsed and
 * expanded states use the same source artwork with its aspect ratio intact.
 */
export function BrandBlock({ collapsed }: { collapsed: boolean }) {
  const { t } = useLocale();
  return (
    <Link
      to={ROUTES.dashboard}
      className="focus-on-forest relative z-10 flex h-24 shrink-0 items-center border-b border-rail-hairline px-5"
    >
      {collapsed ? (
        <BrandLogo size="compact" alt={t('brand.name')} className="mx-auto" />
      ) : (
        <div className="min-w-0">
          <BrandLogo size="standard" alt={t('brand.name')} />
          <p
            lang="en"
            className="mt-1 text-micro font-bold uppercase tracking-wider text-rail-muted"
          >
            Sustainability intelligence
          </p>
        </div>
      )}
    </Link>
  );
}
