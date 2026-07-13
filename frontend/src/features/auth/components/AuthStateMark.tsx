import { Icon } from '@/design-system';
import { cn } from '@/lib/utils/cn';

export function AuthStateMark({ tone = 'attention' }: { tone?: 'success' | 'attention' }) {
  return (
    <span
      className={cn(
        'relative mb-6 inline-flex h-14 w-14 items-center justify-center rounded-xl border shadow-card before:absolute before:inset-1 before:rounded-l before:border before:border-current before:opacity-15',
        tone === 'success'
          ? 'border-leaf-300 bg-leaf-100 text-leaf-700'
          : 'border-amber-100 bg-amber-100 text-amber-700',
      )}
      aria-hidden
    >
      <Icon name={tone === 'success' ? 'check' : 'circle-alert'} size={26} />
    </span>
  );
}
