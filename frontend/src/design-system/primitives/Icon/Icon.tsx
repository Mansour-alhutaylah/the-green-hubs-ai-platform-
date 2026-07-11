import { cn } from '@/lib/utils/cn';
import { useLocale } from '@/lib/i18n/useLocale';
import { DiamondGlyph } from '../DiamondGlyph/DiamondGlyph';
import { ICON_REGISTRY, MIRRORED_ICONS, type IconName } from './iconRegistry';

export interface IconProps {
  name: IconName;
  size?: number;
  className?: string;
}

/**
 * Curated wrapper over lucide-react (§14.4: 1.75px stroke, squared joins,
 * 20px default). Icon color inherits text color (never a hard-coded fill),
 * and direction-encoding icons flip automatically in RTL — everything else
 * never does (bell, documents, brand stay put per §3.3).
 */
export function Icon({ name, size = 20, className }: IconProps) {
  const { dir } = useLocale();
  const shouldMirror = dir === 'rtl' && MIRRORED_ICONS.has(name);

  if (name === 'hub-diamond') {
    return (
      <DiamondGlyph variant="filled" size={size * 0.7} className={cn('text-current', className)} />
    );
  }

  const LucideIcon = ICON_REGISTRY[name];
  return (
    <LucideIcon
      size={size}
      strokeWidth={1.75}
      className={cn(shouldMirror && '-scale-x-100', className)}
      aria-hidden
    />
  );
}
