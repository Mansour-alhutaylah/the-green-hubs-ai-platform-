import type { ReactNode } from 'react';
import { cn } from '@/lib/utils/cn';
import { DiamondGlyph, type DiamondVariant } from '../DiamondGlyph/DiamondGlyph';

export type StatusTone = 'success' | 'processing' | 'pending' | 'attention' | 'danger' | 'neutral';

export interface StatusBadgeProps {
  children: ReactNode;
  tone?: StatusTone;
  className?: string;
}

const STATUS_STYLES: Record<StatusTone, { className: string; glyph: DiamondVariant }> = {
  success: { className: 'border-leaf-300 bg-leaf-100 text-leaf-700', glyph: 'filled' },
  processing: { className: 'border-leaf-300 bg-leaf-100 text-leaf-700', glyph: 'half' },
  pending: { className: 'border-line-200 bg-tint-100 text-gray-600', glyph: 'hollow' },
  attention: { className: 'border-amber-100 bg-amber-100 text-amber-700', glyph: 'warning' },
  danger: { className: 'border-red-100 bg-red-100 text-red-700', glyph: 'warning' },
  neutral: { className: 'border-sky-100 bg-sky-100 text-sky-700', glyph: 'hollow' },
};

/** Compact text-plus-glyph status: state is never communicated by color alone. */
export function StatusBadge({ children, tone = 'neutral', className }: StatusBadgeProps) {
  const style = STATUS_STYLES[tone];
  return (
    <span
      className={cn(
        'inline-flex min-h-6 items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-0.5 text-caption font-bold',
        style.className,
        className,
      )}
    >
      <DiamondGlyph
        variant={style.glyph}
        size={8}
        className={cn('shrink-0', tone === 'processing' && 'status-processing')}
      />
      {children}
    </span>
  );
}
