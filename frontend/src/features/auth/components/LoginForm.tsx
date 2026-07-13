import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router';
import { Button, Input } from '@/design-system';
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
}

export function LoginForm({ onSubmit, isSubmitting, error, lockoutSeconds }: LoginFormProps) {
  const { t } = useLocale();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
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
      <AuthPageHeader eyebrow={t('auth.signin.eyebrow')} heading={t('auth.signin.title')} />

      <div className="flex flex-col gap-4">
        <Input
          label={t('auth.signin.emailLabel')}
          type="email"
          inputSize="xl"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          disabled={isSubmitting || isLocked}
        />
        <Input
          label={t('auth.signin.passwordLabel')}
          type="password"
          inputSize="xl"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          disabled={isSubmitting || isLocked}
          error={fieldError}
        />

        <Button
          type="submit"
          size="xl"
          isLoading={isSubmitting}
          disabled={isLocked}
          className="mt-1 w-full"
        >
          {t('auth.signin.submit')}
        </Button>

        <Link
          to={ROUTES.forgotPassword}
          className="inline-flex min-h-10 items-center self-start rounded-m px-1 text-meta font-semibold text-leaf-700 hover:bg-leaf-100"
        >
          {t('auth.signin.forgotPassword')}
        </Link>
      </div>
    </form>
  );
}
