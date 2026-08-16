import { Link } from 'react-router';
import { DiamondGlyph } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { ROUTES } from '@/app/navigation/routePaths';
import { AuthSplitLayout } from '../components/AuthSplitLayout';
import { AuthPageHeader } from '../components/AuthPageHeader';

/**
 * Invitation acceptance is not implemented.
 *
 * This screen used to collect a name and password and then run a
 * verification-code step that checked the submitted code against a
 * hard-coded development value. Nothing was created, nothing was verified,
 * and the code step read as a working second factor — three claims the
 * product could not support. Real invitations need a backend endpoint that
 * does not exist yet, and real MFA is a later dedicated security phase.
 *
 * What is left is the truth: the link is recognized, the flow is not
 * available yet, and here is the way to sign in if you already have an
 * account. No credential is collected on a screen that cannot use one.
 */
export function InviteAcceptPage() {
  const { t } = useLocale();

  return (
    <AuthSplitLayout>
      <AuthPageHeader
        eyebrow={t('auth.invite.eyebrow')}
        heading={t('auth.invite.unavailable.title')}
        supporting={t('auth.invite.unavailable.supporting')}
      />

      <div className="rounded-l border border-leaf-300 bg-mist-50 p-3 sm:p-4">
        <p className="flex items-start gap-2 text-meta leading-6 text-gray-600">
          <DiamondGlyph variant="hollow" size={10} className="mt-1.5 shrink-0 text-leaf-700" />
          <span>{t('auth.invite.unavailable.notice')}</span>
        </p>
      </div>

      <Link
        to={ROUTES.login}
        className="mt-4 inline-flex min-h-10 items-center rounded-m px-1 text-meta font-semibold text-leaf-700 hover:bg-leaf-100"
      >
        {t('auth.invite.unavailable.signIn')}
      </Link>
    </AuthSplitLayout>
  );
}
