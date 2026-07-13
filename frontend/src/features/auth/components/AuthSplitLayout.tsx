import type { ReactNode } from 'react';
import { Icon } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { en } from '@/lib/i18n/strings/en';
import { ar } from '@/lib/i18n/strings/ar';
import logoWhiteOnForest from '@/assets/brand/logo-lockup-white-on-forest.png';
import { BrandPatternAccent } from './BrandPatternAccent';

/**
 * The shared shell behind all 7 authentication pages (Login, OTP, Forgot/
 * Reset Password, Invite Acceptance, Session Expired, Access Denied):
 * 45% Forest brand panel (official logo lockup, bilingual mission line,
 * sovereignty trust line, sparse diamond accent) / 55% Paper panel
 * centering a 460px form column, with the locale toggle fixed to the
 * form panel's top-inline-end corner. Below ~900px the brand panel
 * collapses to a compact top band (logo only).
 *
 * The logo is the exact provided asset (`logo-lockup-white-on-forest.png`)
 * — no recolor, redraw, or effect ever applied to its pixels. The asset's
 * own canvas (1536×1024) carries the lockup on a large padded background
 * (measured content box: x 344–1262, y 296–694), which read as a "pasted
 * poster" when shown at its native crop. The frame below is a pure-CSS
 * windowed crop (an oversized `img` absolutely positioned inside an
 * `overflow-hidden` box) tightened to the lockup's own content with ~15%
 * breathing room — the same technique as a `background-position` crop,
 * just expressed with an `<img>`. No pixels are edited.
 *
 * The mission line is shown bilingually (English, then Arabic) regardless
 * of the current UI locale — a fixed sovereignty statement, not something
 * the locale toggle switches between.
 */
export function AuthSplitLayout({ children }: { children: ReactNode }) {
  const { t, toggleLocale } = useLocale();

  return (
    <div className="flex min-h-screen min-w-0 flex-col md:flex-row">
      <aside className="relative flex min-h-32 shrink-0 items-center overflow-hidden bg-forest-900 px-4 py-4 sm:px-6 md:min-h-screen md:w-[45%] md:flex-col md:items-start md:justify-between md:px-10 md:py-10 xl:px-14 xl:py-14">
        <BrandPatternAccent />

        {/* Logo + mission line as one tight brand lockup (rather than the
            logo sitting alone with a large gap below it) so the image
            reads as part of the panel's brand mark, not a separate block. */}
        <div className="relative z-10 flex min-w-0 items-center md:flex-col md:items-start">
          <div className="relative h-[52px] w-[120px] shrink-0 overflow-hidden md:h-[94px] md:w-[216px]">
            <img
              src={logoWhiteOnForest}
              alt="The Green Hubs"
              className="absolute left-[-21px] top-[-24px] h-[103px] w-[154px] max-w-none md:left-[-37px] md:top-[-43px] md:h-[185px] md:w-[278px]"
            />
          </div>

          <div className="ms-3 min-w-0 border-s border-rail-hairline ps-3 md:ms-0 md:mt-6 md:max-w-75 md:border-0 md:ps-0">
            <p lang="en" dir="ltr" className="text-caption font-light text-white sm:text-meta md:text-panel">
              {en['brand.mission']}
            </p>
            <p
              lang="ar"
              dir="rtl"
              className="mt-1 text-caption font-light text-white sm:text-meta md:text-panel"
              style={{ fontFamily: 'var(--font-arabic)' }}
            >
              {ar['brand.mission']}
            </p>
          </div>
        </div>

        <div className="relative z-10 hidden items-center gap-2.5 md:flex">
          <Icon name="shield-check" size={15} className="shrink-0 text-rail-muted" />
          <div className="text-micro leading-relaxed text-rail-muted">
            <p>{t('sovereignty.line1')}</p>
            <p>{t('sovereignty.line2')}</p>
          </div>
        </div>
      </aside>

      <main className="relative flex min-w-0 flex-1 items-center justify-center bg-paper-50 px-4 py-14 sm:px-6 sm:py-16">
        <button
          type="button"
          onClick={toggleLocale}
          aria-label={t('auth.localeToggle')}
          className="absolute end-4 top-4 rounded-m px-2 py-1 text-meta font-semibold text-leaf-700 hover:bg-leaf-100 sm:end-8 sm:top-8"
        >
          {t('auth.localeToggle')}
        </button>
        <div className="w-full max-w-115">{children}</div>
      </main>
    </div>
  );
}
