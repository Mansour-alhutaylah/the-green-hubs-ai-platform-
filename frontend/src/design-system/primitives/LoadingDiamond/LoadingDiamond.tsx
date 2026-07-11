import { cn } from '@/lib/utils/cn';
import { useReducedMotion } from '@/lib/motion/useReducedMotion';

export interface LoadingDiamondProps {
  /** §14.8: 16 (inline/buttons), 24 (panels), 40 (page). */
  size?: 16 | 24 | 40;
  className?: string;
  /** Centers the indicator in a full-viewport-height container — used by
   * route-level loading states (e.g. ProtectedRoute while session restores). */
  fullPage?: boolean;
  label?: string;
}

const DASH = 9;
const GAP = 28;

/**
 * §12 / §14.8 signature motion: "the monogram diamond drawing itself
 * clockwise", gray-400 track with a Leaf-colored leading arc, 1.1s loop.
 * Freezes to a static hollow diamond under prefers-reduced-motion (§17/§18).
 */
export function LoadingDiamond({
  size = 24,
  className,
  fullPage,
  label = 'Loading',
}: LoadingDiamondProps) {
  const reducedMotion = useReducedMotion();

  const indicator = (
    <output aria-label={label} className={cn('inline-block shrink-0', className)}>
      <svg width={size} height={size} viewBox="0 0 10 10" aria-hidden>
        <path
          d="M5 0.9 L9.1 5 L5 9.1 L0.9 5 Z"
          fill="none"
          stroke="var(--color-gray-400)"
          strokeWidth={1.25}
        />
        {!reducedMotion && (
          <path
            d="M5 0.9 L9.1 5 L5 9.1 L0.9 5 Z"
            fill="none"
            stroke="var(--color-leaf-500)"
            strokeWidth={1.5}
            strokeLinecap="round"
            strokeDasharray={`${DASH} ${GAP}`}
            className="animate-[loading-diamond-spin_1.1s_linear_infinite]"
          />
        )}
      </svg>
    </output>
  );

  if (!fullPage) return indicator;

  return <div className="flex h-full min-h-40 w-full items-center justify-center">{indicator}</div>;
}
