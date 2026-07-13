import { OtpCells } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { useCountdown, formatCountdown } from '@/lib/utils/useCountdown';
import { OtpDevHint } from './OtpDevHint';
import { AuthPageHeader } from './AuthPageHeader';

export interface OtpFormProps {
  maskedContact: string;
  onComplete: (code: string) => Promise<void>;
  onBack: () => void;
  onResend: () => void;
  isSubmitting: boolean;
  error?: string;
}

const RESEND_SECONDS = 47;

/** §6.1/§11.1: same-card OTP step — six auto-advancing cells, a resend
 * countdown, and a back link. */
export function OtpForm({
  maskedContact,
  onComplete,
  onBack,
  onResend,
  isSubmitting,
  error,
}: OtpFormProps) {
  const { t } = useLocale();
  const { remaining, isDone } = useCountdown(RESEND_SECONDS);
  const supporting = t('auth.otp.supporting', { contact: maskedContact });

  return (
    <div>
      <AuthPageHeader
        eyebrow={t('auth.otp.eyebrow')}
        heading={t('auth.otp.heading')}
        supporting={supporting}
      />

      <div className="flex flex-col gap-4">
        <OtpDevHint />

        <OtpCells
          label={supporting}
          disabled={isSubmitting}
          error={Boolean(error)}
          onComplete={(code) => void onComplete(code)}
        />
        {error && <p className="text-meta text-amber-700" role="alert">{error}</p>}
        {isSubmitting && <output className="block text-caption text-gray-600">{t('auth.otp.verifying')}</output>}

        <div className="mt-1 flex flex-wrap items-center justify-between gap-3 text-meta">
          <button type="button" onClick={onBack} className="font-medium text-leaf-700 hover:underline">
            {t('auth.otp.back')}
          </button>
          {isDone ? (
            <button
              type="button"
              onClick={onResend}
              className="font-medium text-leaf-700 hover:underline"
            >
              {t('auth.otp.resendAction')}
            </button>
          ) : (
            <span className="text-gray-600">
              {t('auth.otp.resend', { countdown: formatCountdown(remaining) })}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
