import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router';
import { Button, Icon, Input } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { useCountdown, formatCountdown } from '@/lib/utils/useCountdown';
import { ROUTES } from '@/app/navigation/routePaths';
import { AuthPageHeader } from './AuthPageHeader';

export interface LoginFormProps {
  onSubmit: (email: string, password: string) => Promise<void>;
  isSubmitting: boolean;
  /** Generic error — §11.1: "invalid credentials (inline, never revealing
   * which field)". */
  error?: string;
  /** Present only when the account is locked out (§9.1: "fail x3 -> lock
   * 5 min"); ticks down live while it's non-zero. */
  lockoutSeconds?: number;
  onEnterDemoWorkspace?: () => Promise<void>;
}

export function LoginForm({
  onSubmit,
  isSubmitting,
  error,
  lockoutSeconds,
  onEnterDemoWorkspace,
}: LoginFormProps) {
  const { t } = useLocale();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isPasswordVisible, setIsPasswordVisible] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const { remaining: lockoutRemaining } = useCountdown(lockoutSeconds ?? 0);
  const isLocked = lockoutRemaining > 0;

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (isLocked) return;
    void onSubmit(email, password);
  }

  const fieldError = isLocked
    ? t('auth.errors.rateLimited', { seconds: formatCountdown(lockoutRemaining) })
    : error;

  return (
    <form onSubmit={handleSubmit}>
      <div
        className="mb-5 flex h-12 w-12 items-center justify-center rounded-xl border border-leaf-300 bg-leaf-100 text-leaf-700 shadow-card"
        aria-hidden
      >
        <Icon name="lock" size={22} />
      </div>
      <AuthPageHeader
        eyebrow={t('auth.signin.eyebrow')}
        heading={t('auth.signin.title')}
        supporting={t('auth.signin.supporting')}
        spacing="compact"
      />

      <div className="flex flex-col gap-4">
        <Input
          label={t('auth.signin.emailLabel')}
          type="email"
          inputSize="xl"
          autoComplete="email"
          placeholder={t('auth.signin.emailPlaceholder')}
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          disabled={isSubmitting || isLocked}
        />
        <Input
          label={t('auth.signin.passwordLabel')}
          type={isPasswordVisible ? 'text' : 'password'}
          inputSize="xl"
          autoComplete="current-password"
          placeholder={t('auth.signin.passwordPlaceholder')}
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          disabled={isSubmitting || isLocked}
          error={fieldError}
          endAdornment={
            <button
              type="button"
              onClick={() => setIsPasswordVisible((visible) => !visible)}
              aria-label={
                isPasswordVisible ? t('auth.signin.hidePassword') : t('auth.signin.showPassword')
              }
              className="flex h-10 w-10 items-center justify-center rounded-m text-gray-600 transition-colors hover:bg-mist-50 hover:text-forest-900"
            >
              <Icon name={isPasswordVisible ? 'eye-off' : 'eye'} size={18} />
            </button>
          }
        />

        <div className="flex min-h-10 flex-wrap items-center justify-between gap-x-4 gap-y-1">
          <label className="inline-flex cursor-pointer items-center gap-2 text-meta font-medium text-gray-600">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(event) => setRememberMe(event.target.checked)}
              className="h-4 w-4 rounded-s border-line-300 accent-forest-900"
            />
            {t('auth.signin.rememberMe')}
          </label>
          <Link
            to={ROUTES.forgotPassword}
            className="inline-flex min-h-10 items-center rounded-m px-1 text-meta font-semibold text-leaf-700 hover:bg-leaf-100"
          >
            {t('auth.signin.forgotPassword')}
          </Link>
        </div>

        <Button
          type="submit"
          size="xl"
          isLoading={isSubmitting}
          disabled={isLocked}
          className="mt-1 w-full bg-gradient-to-b from-forest-800 to-forest-950 shadow-[0_12px_28px_rgb(18_38_24_/_0.3)] transition-all duration-[var(--motion-base)] hover:shadow-[0_16px_36px_rgb(18_38_24_/_0.38)] hover:brightness-110"
        >
          {t('auth.signin.submit')}
        </Button>

        {onEnterDemoWorkspace && (
          <section className="mt-1" aria-labelledby="development-demo-access-label">
            <div className="flex items-center gap-3" aria-hidden>
              <span className="h-px flex-1 bg-line-200" />
              <span className="text-caption font-semibold text-gray-600">{t('auth.demo.or')}</span>
              <span className="h-px flex-1 bg-line-200" />
            </div>
            <div className="mt-4 rounded-l border border-leaf-300 bg-mist-50 p-3 sm:p-4">
              <p id="development-demo-access-label" className="type-label text-leaf-700">
                {t('auth.demo.label')}
              </p>
              <p className="mt-1 text-caption leading-5 text-gray-600">
                {t('auth.demo.supporting')}
              </p>
              <Button
                type="button"
                variant="ghost"
                size="xl"
                className="mt-3 w-full border-leaf-300 bg-surface-0 text-forest-900 hover:bg-leaf-100"
                disabled={isSubmitting}
                onClick={() => void onEnterDemoWorkspace()}
              >
                {t('auth.demo.enter')}
              </Button>
            </div>
          </section>
        )}
      </div>
    </form>
  );
}
