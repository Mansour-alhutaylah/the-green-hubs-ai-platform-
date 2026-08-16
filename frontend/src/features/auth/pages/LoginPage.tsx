import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { useAuth } from '../useAuth';
import {
  InvalidCredentialsError,
  ProfileNotProvisionedError,
  RateLimitedError,
} from '../services/AuthService';
import { AuthSplitLayout } from '../components/AuthSplitLayout';
import { LoginForm } from '../components/LoginForm';
import { PreviewWorkspaceEntry } from '../components/PreviewWorkspaceEntry';
import { resolveReturnPath } from '@/app/router/returnPath';

/**
 * The single sign-in route.
 *
 * Live: the real Supabase email/password sign-in, one step. There is no OTP
 * screen — Supabase's password grant has no second factor, so the step that
 * used to render here could only ever be satisfied by a mock. Real MFA is a
 * later dedicated security phase and is not represented anywhere in this
 * flow today.
 *
 * Preview: a credential-free workspace entry (see `PreviewWorkspaceEntry`);
 * the password form is not rendered at all, so there is nothing to fall
 * through to.
 *
 * On success the user lands on the protected route they originally asked
 * for, when there was one and it validates — otherwise /dashboard.
 */
export function LoginPage() {
  const { requestLogin, enterPreviewWorkspace } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string>();
  const [lockoutSeconds, setLockoutSeconds] = useState<number>();

  const returnPath = resolveReturnPath(location.state);

  async function handleCredentials(email: string, password: string) {
    setIsSubmitting(true);
    setError(undefined);
    try {
      await requestLogin(email, password);
      navigate(returnPath, { replace: true });
    } catch (caught) {
      if (caught instanceof RateLimitedError) {
        setLockoutSeconds(caught.retryAfterSec);
      } else if (
        caught instanceof InvalidCredentialsError ||
        caught instanceof ProfileNotProvisionedError
      ) {
        setError(caught.message);
      } else {
        setError('Something went wrong. Try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handlePreviewEntry() {
    if (!enterPreviewWorkspace) return;
    setIsSubmitting(true);
    setError(undefined);
    try {
      await enterPreviewWorkspace();
      navigate(returnPath, { replace: true });
    } catch {
      setError('The Preview workspace is unavailable.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthSplitLayout variant="login">
      {enterPreviewWorkspace ? (
        <PreviewWorkspaceEntry
          onEnter={() => void handlePreviewEntry()}
          isSubmitting={isSubmitting}
          error={error}
        />
      ) : (
        <LoginForm
          onSubmit={handleCredentials}
          isSubmitting={isSubmitting}
          error={error}
          lockoutSeconds={lockoutSeconds}
        />
      )}
    </AuthSplitLayout>
  );
}
