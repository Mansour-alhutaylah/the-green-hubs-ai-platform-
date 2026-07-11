import { ROLE_LABELS, Role } from '@/features/rbac/roles';
import { DiamondGlyph } from '../DiamondGlyph/DiamondGlyph';
import { Badge } from '../Badge/Badge';

export interface RoleBadgeProps {
  role: Role;
  className?: string;
}

/** §15: "RoleBadge: 11px/700 uppercase, hairline border, Forest text
 * (Owner adds filled diamond)." */
export function RoleBadge({ role, className }: RoleBadgeProps) {
  return (
    <Badge className={className}>
      {role === Role.Owner && <DiamondGlyph variant="filled" size={6} className="text-leaf-500" />}
      {ROLE_LABELS[role]}
    </Badge>
  );
}
