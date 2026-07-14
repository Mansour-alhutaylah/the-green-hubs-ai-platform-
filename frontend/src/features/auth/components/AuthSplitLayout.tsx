import type { ReactNode } from 'react';
import { BrandLogo, Icon } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { en } from '@/lib/i18n/strings/en';
import { ar } from '@/lib/i18n/strings/ar';
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
 * The logo is the approved supplied company asset, rendered without any
 * crop, recolor, transform, or distortion through the shared BrandLogo.
 *
 * The mission line is shown bilingually (English, then Arabic) regardless
 * of the current UI locale — a fixed sovereignty statement, not something
 * the locale toggle switches between.
 */
export function AuthSplitLayout({
  children,
  variant = 'default',
}: {
  children: ReactNode;
  variant?: 'default' | 'login';
}) {
  const { t, toggleLocale } = useLocale();
  const isLogin = variant === 'login';

  return (
    <div className="flex min-h-dvh min-w-0 flex-col lg:flex-row">
      <aside className="auth-brand-panel relative flex min-h-40 shrink-0 items-center overflow-hidden px-4 py-5 sm:min-h-44 sm:px-6 lg:min-h-dvh lg:w-[44%] lg:flex-col lg:items-start lg:px-10 lg:py-10 xl:px-14 xl:py-14">
        <BrandPatternAccent />

        {/* Logo + mission line as one tight brand lockup (rather than the
            logo sitting alone with a large gap below it) so the image
            reads as part of the panel's brand mark, not a separate block. */}
        <div className="relative z-10 flex min-w-0 items-center lg:flex-col lg:items-start">
          <BrandLogo size="hero" />

          {!isLogin && (
            <div className="ms-3 min-w-0 border-s border-rail-hairline ps-3 lg:ms-0 lg:mt-6 lg:max-w-80 lg:border-0 lg:ps-0">
              <p
                lang="en"
                dir="ltr"
                className="text-caption font-medium text-white sm:text-meta lg:text-title"
              >
                {en['brand.mission']}
              </p>
              <p
                lang="ar"
                dir="rtl"
                className="mt-1 text-caption font-medium text-white sm:text-meta lg:text-title"
                style={{ fontFamily: 'var(--font-arabic)' }}
              >
                {ar['brand.mission']}
              </p>
            </div>
          )}
        </div>

        {isLogin && (
          <div className="relative z-10 mt-auto hidden max-w-96 pb-32 lg:block xl:pb-40">
            <p lang="en" dir="ltr" className="text-display text-white xl:text-hero">
              {en['auth.welcome.title']}
            </p>
            <p lang="en" dir="ltr" className="mt-3 max-w-[36ch] text-body leading-6 text-rail-text">
              {en['auth.welcome.supporting']}
            </p>
            <div className="my-7 h-px w-12 bg-leaf-500" aria-hidden />
            <p
              lang="ar"
              dir="rtl"
              className="text-display text-white xl:text-hero"
              style={{ fontFamily: 'var(--font-arabic)' }}
            >
              {ar['auth.welcome.title']}
            </p>
            <p
              lang="ar"
              dir="rtl"
              className="mt-3 max-w-[36ch] text-body leading-7 text-rail-text"
              style={{ fontFamily: 'var(--font-arabic)' }}
            >
              {ar['auth.welcome.supporting']}
            </p>
          </div>
        )}

        <div className="relative z-10 hidden items-center gap-3 rounded-l border border-rail-hairline bg-white/5 px-4 py-3 lg:flex">
          <span className="flex h-8 w-8 items-center justify-center rounded-m bg-leaf-500/15 text-leaf-300">
            <Icon name="shield-check" size={16} />
          </span>
          <div className="text-micro leading-relaxed text-rail-muted">
            <p>{t('sovereignty.line1')}</p>
            <p>{t('sovereignty.line2')}</p>
          </div>
        </div>
      </aside>

      <main className="auth-form-panel relative flex min-w-0 flex-1 items-center justify-center px-3 py-12 sm:px-6 sm:py-16 lg:px-10">
        <button
          type="button"
          onClick={toggleLocale}
          aria-label={t('auth.localeToggle')}
          className="absolute end-4 top-4 inline-flex min-h-11 items-center rounded-m border border-leaf-300 bg-surface-0/80 px-3 text-meta font-semibold text-leaf-700 shadow-card transition-colors hover:bg-leaf-100 sm:end-8 sm:top-8"
        >
          {t('auth.localeToggle')}
        </button>
        <div className="auth-card panel-enter w-full max-w-115 rounded-xl border border-white/80 p-3 min-[390px]:p-5 sm:p-7 lg:p-8">
          {children}
        </div>
        {isLogin && (
          <p className="absolute bottom-6 hidden text-caption text-gray-600 lg:block">
            {t('auth.copyright')}
          </p>
        )}
      </main>
    </div>
  );
}
