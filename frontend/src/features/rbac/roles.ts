/**
 * Role model — spec §4: Owner ⊃ Admin ⊃ Approver ⊃ Editor ⊃ Viewer, each
 * tier superseding the next. Permissions are render-time: a nav item or
 * route either exists for a tier or it doesn't — never a disabled state
 * (§19). Server re-validates everything; this is a UX layer only.
 *
 * A plain const-object union (not `enum`) because the project's tsconfig
 * sets `erasableSyntaxOnly`, which forbids TypeScript `enum` (it emits
 * runtime code that isn't erasable type syntax).
 */
export const Role = {
  Viewer: 'viewer',
  Editor: 'editor',
  Approver: 'approver',
  Admin: 'admin',
  Owner: 'owner',
} as const;

export type Role = (typeof Role)[keyof typeof Role];

/** Ascending tier order — index is the comparison basis for `meetsMinTier`. */
const TIER_ORDER: readonly Role[] = [
  Role.Viewer,
  Role.Editor,
  Role.Approver,
  Role.Admin,
  Role.Owner,
];

export function tierIndex(role: Role): number {
  return TIER_ORDER.indexOf(role);
}

/** Does `userRole` meet or exceed `minTier`? */
export function meetsMinTier(userRole: Role, minTier: Role): boolean {
  return tierIndex(userRole) >= tierIndex(minTier);
}

export const ROLE_LABELS: Record<Role, string> = {
  [Role.Viewer]: 'Viewer',
  [Role.Editor]: 'Editor',
  [Role.Approver]: 'Approver',
  [Role.Admin]: 'Admin',
  [Role.Owner]: 'Owner',
};
