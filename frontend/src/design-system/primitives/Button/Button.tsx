import { forwardRef } from 'react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils/cn';
import { LoadingDiamond } from '../LoadingDiamond/LoadingDiamond';

const buttonStyles = cva(
  'inline-grid place-items-center rounded-m font-semibold transition-colors duration-[var(--motion-fast)] ease-out disabled:cursor-not-allowed disabled:bg-gray-400 disabled:text-white',
  {
    variants: {
      variant: {
        primary: 'bg-forest-900 text-white hover:bg-forest-950 active:scale-[var(--scale-press)]',
        ghost:
          'border border-line-200 bg-transparent text-forest-900 hover:bg-tint-100 active:scale-[var(--scale-press)]',
        text: 'bg-transparent px-0 text-leaf-700 hover:underline',
      },
      size: {
        xl: 'h-[var(--size-control-xl)] px-6 text-body',
        lg: 'h-12 px-5 text-body',
        md: 'h-10 px-4 text-body',
        sm: 'h-8 px-3 text-meta',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonStyles> {
  isLoading?: boolean;
  /** Shown in place of children while loading, e.g. "Approving…" (§14.8). */
  loadingLabel?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, isLoading, loadingLabel, disabled, children, ...props },
  ref,
) {
  const spinnerSize = size === 'xl' || size === 'lg' ? 24 : 16;
  return (
    <button
      ref={ref}
      className={cn(
        buttonStyles({ variant, size: variant === 'text' ? undefined : size }),
        className,
      )}
      disabled={disabled || isLoading}
      aria-busy={isLoading}
      {...props}
    >
      {/* Both layers share one grid cell (§14.8: "width locked to prevent
          reflow") — the button sizes to whichever is wider. */}
      <span
        className={cn('col-start-1 row-start-1 flex items-center gap-2', isLoading && 'invisible')}
      >
        {children}
      </span>
      {isLoading && (
        <span className="col-start-1 row-start-1 flex items-center gap-2">
          <LoadingDiamond size={spinnerSize} />
          {loadingLabel ?? children}
        </span>
      )}
    </button>
  );
});
