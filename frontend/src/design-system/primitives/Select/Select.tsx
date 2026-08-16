import { forwardRef } from 'react';
import type { SelectHTMLAttributes } from 'react';
import { cn } from '@/lib/utils/cn';
import { Icon } from '../Icon/Icon';
import type { IconName } from '../Icon/iconRegistry';

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps
  extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children' | 'size'> {
  options: readonly SelectOption[];
  /** Optional leading affordance drawn inside the control (e.g. `filter`). */
  icon?: IconName;
  /** `sm` is the 36px filter control used in list toolbars; `md` is the 40px
   * form control used in the upload form. */
  controlSize?: 'sm' | 'md';
  /** Classes for the positioning wrapper, not the control itself. */
  containerClassName?: string;
}

/**
 * The one styled `<select>`. This deliberately stays a **native** select
 * rather than a custom listbox: the repository has no established
 * custom-select pattern, and the native control already gives us keyboard
 * behavior, type-ahead, mobile pickers, and screen-reader support that a
 * hand-rolled replacement would have to re-earn.
 *
 * What it consolidates is the styling that had been copy-pasted across the
 * Documents, Analysis, and Upload pages — including the icon inset, which
 * previously had to be kept in sync by hand.
 *
 * One deliberate change from the copied original: the control no longer
 * sets `outline-none`. That had suppressed the product-wide 2px focus ring
 * (§17) and left only a border-color change, which is not a sufficient
 * focus indicator; the border change is kept as well.
 */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { options, icon, controlSize = 'sm', className, containerClassName, ...props },
  ref,
) {
  return (
    <div className={cn('relative', containerClassName)}>
      {icon && (
        <Icon
          name={icon}
          size={14}
          className="pointer-events-none absolute start-2.5 top-1/2 -translate-y-1/2 text-gray-400"
        />
      )}
      <select
        ref={ref}
        className={cn(
          'rounded-m border border-line-300 bg-surface-0 text-ink-900 transition-colors focus:border-forest-900',
          controlSize === 'sm' ? 'h-9 text-meta' : 'h-10 text-body',
          icon ? 'ps-8 pe-3' : 'px-3',
          className,
        )}
        {...props}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value} disabled={option.disabled}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
});
