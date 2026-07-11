import { cn } from '@/lib/utils/cn';

export interface AvatarProps {
  name: string;
  src?: string;
  size?: 24 | 32 | 40;
  /** Circle for people (§15), square 4px-radius for organizations (§3.2/§6.6). */
  shape?: 'circle' | 'square';
  className?: string;
}

function initialsFor(name: string): string {
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? '';
  const last = parts.length > 1 ? (parts.at(-1)?.[0] ?? '') : '';
  return (first + last).toUpperCase();
}

export function Avatar({ name, src, size = 32, shape = 'circle', className }: AvatarProps) {
  const dimension = `${size}px`;
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center justify-center overflow-hidden bg-forest-900 font-bold text-white',
        shape === 'circle' ? 'rounded-full' : 'rounded-s',
        className,
      )}
      style={{ width: dimension, height: dimension, fontSize: size * 0.4 }}
    >
      {src ? (
        <img src={src} alt="" className="h-full w-full object-cover" />
      ) : (
        <span aria-hidden>{initialsFor(name)}</span>
      )}
    </span>
  );
}
