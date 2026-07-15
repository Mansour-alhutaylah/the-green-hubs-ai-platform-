import { cn } from '@/lib/utils/cn';

export function LoadingSkeleton({
  className,
  lines = 1,
  label = 'Loading content',
}: {
  className?: string;
  lines?: number;
  label?: string;
}) {
  return (
    <output className={cn('block space-y-2', className)} aria-label={label}>
      {Array.from({ length: lines }, (_, index) => (
        <span
          key={index}
          className={cn(
            'loading-skeleton block h-3 rounded-s',
            index === lines - 1 && lines > 1 ? 'w-2/3' : 'w-full',
          )}
          aria-hidden
        />
      ))}
    </output>
  );
}
