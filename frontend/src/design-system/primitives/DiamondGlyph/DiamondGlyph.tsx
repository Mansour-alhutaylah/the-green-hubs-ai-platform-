import { cn } from '@/lib/utils/cn';

export type DiamondVariant = 'filled' | 'half' | 'hollow' | 'warning';

export interface DiamondGlyphProps {
  variant: DiamondVariant;
  /** Pixel size — spec uses 7px (pips), 8px (rail bullet), 32px (empty state). */
  size?: number;
  className?: string;
  'aria-hidden'?: boolean;
}

/**
 * The OS's proprietary status glyph (§12): filled ◆ = complete/active,
 * half ◈ = in progress, hollow ◇ = pending/placeholder, warning = attention.
 * Color is inherited via `currentColor` — set it with a text-color utility
 * on the caller (e.g. `text-leaf-500`), matching §14.4's "icon color
 * inherits text color" rule.
 */
export function DiamondGlyph({
  variant,
  size = 8,
  className,
  'aria-hidden': ariaHidden = true,
}: DiamondGlyphProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 10 10"
      className={cn('shrink-0', className)}
      aria-hidden={ariaHidden}
    >
      {variant === 'filled' && <path d="M5 0 L10 5 L5 10 L0 5 Z" fill="currentColor" />}
      {variant === 'warning' && <path d="M5 0 L10 5 L5 10 L0 5 Z" fill="currentColor" />}
      {variant === 'hollow' && (
        <path
          d="M5 0.9 L9.1 5 L5 9.1 L0.9 5 Z"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.25}
        />
      )}
      {variant === 'half' && (
        <>
          <path d="M5 0 L5 10 L0 5 Z" fill="currentColor" />
          <path d="M5 0.9 L9.1 5 L5 9.1" fill="none" stroke="currentColor" strokeWidth={1.25} />
        </>
      )}
    </svg>
  );
}
