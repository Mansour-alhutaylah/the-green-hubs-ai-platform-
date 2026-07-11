import { useAuth } from '@/features/auth/useAuth';
import { meetsMinTier, type Role } from './roles';

/** True when the signed-in user's tier meets or exceeds `minTier`. False
 * (never an error) when there is no signed-in user — callers outside a
 * ProtectedRoute simply see everything as gated. */
export function useHasMinTier(minTier: Role): boolean {
  const { user } = useAuth();
  return user != null && meetsMinTier(user.role, minTier);
}
