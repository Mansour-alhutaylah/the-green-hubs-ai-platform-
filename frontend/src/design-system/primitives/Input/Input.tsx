import { forwardRef, useId } from 'react';
import type { InputHTMLAttributes } from 'react';
import { cn } from '@/lib/utils/cn';

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label: string;
  error?: string;
  hint?: string;
  /** 54px (the auth system's own spec: "comfortable height around 52–56px"),
   * 48px (other forms), 40px default — named `inputSize` since the native
   * `size` HTML attribute means something else entirely (a number of
   * visible characters). */
  inputSize?: 'xl' | 'lg' | 'md';
  containerClassName?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, hint, inputSize = 'md', className, containerClassName, id, ...props },
  ref,
) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const errorId = error ? `${inputId}-error` : undefined;
  const hintId = hint ? `${inputId}-hint` : undefined;

  return (
    <div className={cn('flex flex-col gap-1.5', containerClassName)}>
      <label htmlFor={inputId} className="text-meta font-bold text-ink-900">
        {label}
      </label>
      <input
        ref={ref}
        id={inputId}
        aria-invalid={Boolean(error)}
        aria-describedby={cn(errorId, hintId) || undefined}
        className={cn(
          'rounded-m border bg-surface-0 text-body text-ink-900 outline-none transition-colors duration-[var(--motion-fast)]',
          'placeholder:text-gray-400 disabled:bg-tint-100 disabled:text-gray-400',
          inputSize === 'xl' && 'h-[var(--size-control-xl)] px-4',
          inputSize === 'lg' && 'h-12 px-3',
          inputSize === 'md' && 'h-10 px-3',
          error
            ? 'border-[length:var(--border-width-error)] border-amber-700'
            : 'border-line-300 focus:border-2 focus:border-forest-900',
          className,
        )}
        {...props}
      />
      {error && (
        <p id={errorId} className="text-meta text-amber-700" role="alert">
          {error}
        </p>
      )}
      {!error && hint && (
        <p id={hintId} className="text-caption text-gray-600">
          {hint}
        </p>
      )}
    </div>
  );
});
