import { useLocale } from '@/lib/i18n/useLocale';
import { useAuth } from '../useAuth';

/** Shared by OtpForm (login) and InviteAcceptPage's OTP step — renders
 * nothing once `devOtpHint` is absent (i.e. a real AuthService is wired
 * in), so this disappears automatically without any UI change. */
export function OtpDevHint() {
  const { t } = useLocale();
  const { devOtpHint } = useAuth();

  if (!devOtpHint) return null;

  return (
    <p className="rounded-l border border-leaf-300 bg-mist-50 px-3 py-2.5 text-caption text-gray-600">
      <span className="font-bold text-leaf-700">Demo verification · </span>
      {t('auth.otp.devHint', { code: devOtpHint })}
    </p>
  );
}
