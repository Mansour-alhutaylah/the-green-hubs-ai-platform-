import { Icon } from '@/design-system';
import { cn } from '@/lib/utils/cn';

export function AuthStateMark({ tone = 'attention' }: { tone?: 'success' | 'attention' }) {
  return (
    <span
      className={cn(
        'mb-5 inline-flex h-12 w-12 items-center justify-center rounded-l border',
        tone === 'success'
          ? 'border-leaf-300 bg-leaf-100 text-leaf-700'
          : 'border-amber-100 bg-amber-100 text-amber-700',
      )}
      aria-hidden
    >
      <Icon name={tone === 'success' ? 'check' : 'circle-alert'} size={24} />
    </span>
  );
}
