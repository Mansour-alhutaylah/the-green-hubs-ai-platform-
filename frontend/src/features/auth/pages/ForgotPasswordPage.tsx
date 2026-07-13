import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router';
import { Button, Input } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { ROUTES } from '@/app/navigation/routePaths';
import { AuthSplitLayout } from '../components/AuthSplitLayout';
import { AuthPageHeader } from '../components/AuthPageHeader';
import { AuthStateMark } from '../components/AuthStateMark';

/** §9.1: "email entry -> 'check your inbox' state -> reset form -> /login".
 * No real email delivery exists yet — this is the UI shape only. */
export function ForgotPasswordPage() {
  const { t } = useLocale();
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitted(true);
  }

  return (
    <AuthSplitLayout>
      {submitted ? (
        <div role="status">
          <AuthStateMark tone="success" />
          <AuthPageHeader
            eyebrow={t('auth.forgot.eyebrow')}
            heading={t('auth.forgot.checkInbox.title')}
            supporting={t('auth.forgot.checkInbox.body', { email })}
          />
          <Link
            to={ROUTES.login}
            className="inline-flex min-h-10 items-center rounded-m border border-line-200 px-4 text-meta font-semibold text-forest-900 hover:bg-tint-100"
          >
            {t('auth.forgot.backToLogin')}
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit}>
          <AuthPageHeader
            eyebrow={t('auth.forgot.eyebrow')}
            heading={t('auth.forgot.title')}
            supporting={t('auth.forgot.supporting')}
          />
          <div className="flex flex-col gap-4">
            <Input
              label={t('auth.forgot.emailLabel')}
              type="email"
              inputSize="xl"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
            <Button type="submit" size="xl" className="mt-1 w-full">
              {t('auth.forgot.submit')}
            </Button>
            <Link
              to={ROUTES.login}
              className="text-meta font-medium text-leaf-700 hover:underline"
            >
              {t('auth.forgot.backToLogin')}
            </Link>
          </div>
        </form>
      )}
    </AuthSplitLayout>
  );
}
