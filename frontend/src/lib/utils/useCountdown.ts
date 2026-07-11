import { useEffect, useState } from 'react';

/**
 * Counts down from `seconds` to 0, ticking every second. Used by the OTP
 * "Resend in 0:47" affordance and the login lockout countdown (§11.1).
 */
export function useCountdown(seconds: number): { remaining: number; isDone: boolean } {
  const [remaining, setRemaining] = useState(seconds);

  useEffect(() => {
    setRemaining(seconds);
    if (seconds <= 0) return;

    const interval = window.setInterval(() => {
      setRemaining((prev) => (prev <= 1 ? 0 : prev - 1));
    }, 1000);

    return () => window.clearInterval(interval);
  }, [seconds]);

  return { remaining, isDone: remaining <= 0 };
}

export function formatCountdown(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const secs = totalSeconds % 60;
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}
