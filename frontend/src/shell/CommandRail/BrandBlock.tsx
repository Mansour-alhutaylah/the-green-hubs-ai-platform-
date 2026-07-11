import { Link } from 'react-router';
import { useLocale } from '@/lib/i18n/useLocale';
import { ROUTES } from '@/app/navigation/routePaths';
import logoWhiteOnForest from '@/assets/brand/logo-lockup-white-on-forest.png';

/**
 * The official lockup, windowed via the same CSS-crop technique used on
 * the auth screens (see AuthSplitLayout's doc comment) — the source
 * asset's own 1536×1024 canvas carries generous background padding around
 * the mark (measured), so a native-crop display reads as a pasted
 * rectangle at rail scale. No pixels are edited; only the visible crop
 * window changes, via an oversized `img` absolutely positioned inside an
 * `overflow-hidden` frame.
 *
 * Expanded shows the full lockup (mark + wordmark, cropped tight to that
 * content box). Collapsed shows a mark-only crop — the measured divider
 * between the mark and "THE GREEN HUBS" sits at x 798–802 in the source,
 * so the mark's own content box (x 344–797) is windowed on its own rather
 * than squeezing the full lockup into the 72px collapsed rail.
 *
 * TODO(brand): replace with an official transparent SVG/PNG lockup when
 * available — this CSS crop is the best fidelity achievable from the
 * current opaque-background PNG.
 */
export function BrandBlock({ collapsed }: { collapsed: boolean }) {
  const { t } = useLocale();
  return (
    <Link
      to={ROUTES.dashboard}
      className="focus-on-forest flex h-18 shrink-0 items-center border-b border-rail-hairline px-6"
    >
      {collapsed ? (
        <div className="relative block h-8 w-9 shrink-0 grow-0 overflow-hidden border-0 bg-transparent outline-none">
          <img
            src={logoWhiteOnForest}
            alt={t('brand.name')}
            className="pointer-events-none absolute left-[-20px] top-[-17px] block h-[68px] w-[102px] max-w-none select-none border-0 bg-transparent outline-none"
          />
        </div>
      ) : (
        <div className="relative block h-8 w-[74px] shrink-0 grow-0 overflow-hidden border-0 bg-transparent outline-none">
          <img
            src={logoWhiteOnForest}
            alt={t('brand.name')}
            className="pointer-events-none absolute left-[-15px] top-[-16px] block h-[67px] w-[100px] max-w-none select-none border-0 bg-transparent outline-none"
          />
        </div>
      )}
    </Link>
  );
}
