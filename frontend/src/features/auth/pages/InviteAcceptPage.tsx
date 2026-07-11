import { useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router';
import { Button, Input, OtpCells, useToast } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { ROUTES } from '@/app/navigation/routePaths';
import { MOCK_ORGANIZATIONS, localizedOrgName } from '@/features/organizations/mockOrgs';
import { AuthSplitLayout } from '../components/AuthSplitLayout';
import { AuthPageHeader } from '../components/AuthPageHeader';
import { OrgInviteChip } from '../components/OrgInviteChip';
import { OtpDevHint } from '../components/OtpDevHint';
import { useAuth } from '../useAuth';

type Step = 'details' | 'otp';

const invitingOrg = MOCK_ORGANIZATIONS[0]!;

/** §9.1: "set name + password -> OTP -> /dashboard (first-run coachmarks)".
 * Phase 1 has no seeded invite tokens to attach a real session to, so this
 * confirms the code and returns the new user to /login to sign in with
 * their credentials — the OTP mechanics themselves are real and shared
 * with LoginPage's OtpForm pattern. */
export function InviteAcceptPage() {
  const { t, locale } = useLocale();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { checkDevOtpCode } = useAuth();
  const [step, setStep] = useState<Step>('details');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [otpError, setOtpError] = useState<string>();

  function handleDetailsSubmit(event: FormEvent) {
    event.preventDefault();
    setStep('otp');
  }

  function handleOtpComplete(code: string) {
    if (!checkDevOtpCode(code)) {
      setOtpError(t('auth.otp.invalid'));
      return;
    }
    showToast(t('auth.invite.success', { name }), { kind: 'success' });
    navigate(ROUTES.login, { replace: true });
  }

  return (
    <AuthSplitLayout>
      {step === 'details' ? (
        <form onSubmit={handleDetailsSubmit}>
          <AuthPageHeader
            eyebrow={t('auth.invite.eyebrow')}
            heading={t('auth.invite.title')}
            supporting={t('auth.invite.supporting', { org: localizedOrgName(invitingOrg, locale) })}
          />
          <OrgInviteChip organization={invitingOrg} />
          <div className="flex flex-col gap-4">
            <Input
              label={t('auth.invite.nameLabel')}
              inputSize="xl"
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
            <Input
              label={t('auth.invite.passwordLabel')}
              type="password"
              inputSize="xl"
              autoComplete="new-password"
              required
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <Button type="submit" size="xl" className="mt-1 w-full">
              {t('auth.invite.submit')}
            </Button>
          </div>
        </form>
      ) : (
        <div>
          <AuthPageHeader
            eyebrow={t('auth.otp.eyebrow')}
            heading={t('auth.otp.heading')}
            supporting={t('auth.otp.supporting', { contact: name })}
          />
          <div className="flex flex-col gap-4">
            <OtpDevHint />
            <OtpCells
              label={t('auth.otp.supporting', { contact: name })}
              error={Boolean(otpError)}
              onComplete={handleOtpComplete}
            />
            {otpError && <p className="text-meta text-amber-700">{otpError}</p>}
          </div>
        </div>
      )}
    </AuthSplitLayout>
  );
}
