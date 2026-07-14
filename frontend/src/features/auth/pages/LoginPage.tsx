import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from '../useAuth';
import {
  ChallengeExpiredError,
  InvalidCredentialsError,
  InvalidOtpError,
  RateLimitedError,
} from '../services/AuthService';
import { AuthSplitLayout } from '../components/AuthSplitLayout';
import { LoginForm } from '../components/LoginForm';
import { OtpForm } from '../components/OtpForm';
import { ROUTES } from '@/app/navigation/routePaths';

type Step = { name: 'credentials' } | { name: 'otp'; challengeId: string; maskedContact: string };

/**
 * §6.1/§9.1: a single route whose card content swaps between the
 * credentials step and the OTP step, rather than two separate pages.
 * OTP success always navigates to /dashboard (the landing rule, §7) —
 * never to whatever deep link was originally attempted.
 */
export function LoginPage() {
  const { requestLogin, verifyOtp, resendOtp, enterDemoWorkspace } = useAuth();
  const navigate = useNavigate();

  const [step, setStep] = useState<Step>({ name: 'credentials' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string>();
  const [lockoutSeconds, setLockoutSeconds] = useState<number>();

  async function handleCredentials(email: string, password: string) {
    setIsSubmitting(true);
    setError(undefined);
    try {
      const challenge = await requestLogin(email, password);
      setStep({
        name: 'otp',
        challengeId: challenge.challengeId,
        maskedContact: challenge.maskedContact,
      });
    } catch (caught) {
      if (caught instanceof RateLimitedError) {
        setLockoutSeconds(caught.retryAfterSec);
      } else if (caught instanceof InvalidCredentialsError) {
        setError(caught.message);
      } else {
        setError('Something went wrong. Try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleOtpComplete(code: string) {
    if (step.name !== 'otp') return;
    setIsSubmitting(true);
    setError(undefined);
    try {
      await verifyOtp(step.challengeId, code);
      navigate(ROUTES.dashboard, { replace: true });
    } catch (caught) {
      if (caught instanceof InvalidOtpError) {
        setError(caught.message);
      } else if (caught instanceof ChallengeExpiredError) {
        setError(caught.message);
        setStep({ name: 'credentials' });
      } else {
        setError('Something went wrong. Try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDemoWorkspace() {
    if (!enterDemoWorkspace) return;
    setIsSubmitting(true);
    setError(undefined);
    try {
      await enterDemoWorkspace();
      navigate(ROUTES.dashboard, { replace: true });
    } catch {
      setError('Development demo access is unavailable.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthSplitLayout variant="login">
      {step.name === 'credentials' ? (
        <LoginForm
          onSubmit={handleCredentials}
          isSubmitting={isSubmitting}
          error={error}
          lockoutSeconds={lockoutSeconds}
          onEnterDemoWorkspace={enterDemoWorkspace ? handleDemoWorkspace : undefined}
        />
      ) : (
        <OtpForm
          maskedContact={step.maskedContact}
          onComplete={handleOtpComplete}
          onBack={() => setStep({ name: 'credentials' })}
          onResend={() => void resendOtp(step.challengeId)}
          isSubmitting={isSubmitting}
          error={error}
        />
      )}
    </AuthSplitLayout>
  );
}
