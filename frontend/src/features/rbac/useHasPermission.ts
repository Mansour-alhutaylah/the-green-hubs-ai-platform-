import { useAuth } from '@/features/auth/useAuth';
import { hasPermission, type Permission } from './permissions';

/** Whether the signed-in user holds `permission` according to the shared
 * policy table. False — never an error — when there is no signed-in user,
 * so a component rendered outside a ProtectedRoute simply sees everything
 * as gated rather than crashing.
 *
 * This gates what is *offered*, not what is *allowed*: the backend
 * re-derives the role server-side and refuses an unauthorized command with
 * 403 whatever this returns. */
export function useHasPermission(permission: Permission): boolean {
  const { user } = useAuth();
  return hasPermission(user?.role, permission);
}
