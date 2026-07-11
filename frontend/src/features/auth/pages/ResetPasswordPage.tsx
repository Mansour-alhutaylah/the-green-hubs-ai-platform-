import { useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router';
import { Button, Input } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { ROUTES } from '@/app/navigation/routePaths';
import { AuthSplitLayout } from '../components/AuthSplitLayout';
import { AuthPageHeader } from '../components/AuthPageHeader';
import { PasswordRequirements } from '../components/PasswordRequirements';

export function ResetPasswordPage() {
  const { t } = useLocale();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showMismatch, setShowMismatch] = useState(false);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (password !== confirmPassword) {
      setShowMismatch(true);
      return;
    }
    navigate(ROUTES.login, { replace: true });
  }

  return (
    <AuthSplitLayout>
      <form onSubmit={handleSubmit}>
        <AuthPageHeader
          eyebrow={t('auth.reset.eyebrow')}
          heading={t('auth.reset.title')}
          supporting={t('auth.reset.supporting')}
        />
        <div className="flex flex-col gap-4">
          <Input
            label={t('auth.reset.passwordLabel')}
            type="password"
            inputSize="xl"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <PasswordRequirements password={password} />
          <Input
            label={t('auth.reset.confirmPasswordLabel')}
            type="password"
            inputSize="xl"
            autoComplete="new-password"
            required
            minLength={8}
            value={confirmPassword}
            onChange={(event) => {
              setConfirmPassword(event.target.value);
              setShowMismatch(false);
            }}
            error={showMismatch ? t('auth.reset.passwordMismatch') : undefined}
          />
          <Button type="submit" size="xl" className="mt-1 w-full">
            {t('auth.reset.submit')}
          </Button>
        </div>
      </form>
    </AuthSplitLayout>
  );
}
