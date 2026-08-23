import type { ReactNode } from 'react';
import { cn } from '@/lib/utils/cn';

/**
 * The toolbar strip above a listing: tabs, filters, a search field, and the
 * occasional inline action.
 *
 * It exists because every list page had been laying this row out by hand
 * with slightly different flex rules, which is how a toolbar ends up
 * pushing the page sideways at 360px on one route and not another. Here the
 * rule is stated once: stack on a phone, sit on one line from `sm` up, and
 * wrap rather than overflow in between.
 *
 * A `<fieldset>` with a visually-hidden `<legend>`, not `role="toolbar"`.
 * A toolbar promises arrow-key navigation between its controls as a single
 * tab stop; these controls are ordinary tab stops, and claiming otherwise
 * would make a screen reader announce an interaction model the component
 * does not implement. A fieldset groups related form controls and gives the
 * group a name, which is exactly what this is.
 */
export interface FilterBarProps {
  /** Accessible name for the group, e.g. "Filter engagements". */
  label: string;
  children: ReactNode;
  /** Right-aligned from `sm` up — typically a primary action. */
  trailing?: ReactNode;
  className?: string;
}

export function FilterBar({ label, children, trailing, className }: FilterBarProps) {
  return (
    <fieldset
      className={cn(
        'flex flex-col gap-3 border-b border-line-200 px-4 py-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:px-5',
        className,
      )}
    >
      <legend className="sr-only">{label}</legend>
      <div className="flex flex-col gap-3 min-[30rem]:flex-row min-[30rem]:flex-wrap min-[30rem]:items-center">
        {children}
      </div>
      {trailing && <div className="flex flex-wrap items-center gap-2">{trailing}</div>}
    </fieldset>
  );
}

/**
 * A labelled search input for a `FilterBar`.
 *
 * The label is visually hidden rather than absent: a placeholder is not a
 * label — it disappears on focus, is not read reliably, and leaves the
 * field anonymous to anyone navigating by form control.
 */
export function FilterSearch({
  label,
  placeholder,
  value,
  onChange,
  className,
}: {
  label: string;
  placeholder?: string;
  value: string;
  onChange: (value: string) => void;
  className?: string;
}) {
  return (
    <input
      type="search"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      aria-label={label}
      placeholder={placeholder}
      className={cn(
        'h-9 w-full rounded-m border border-line-300 bg-surface-0 px-3 text-meta text-ink-900 transition-colors placeholder:text-gray-400 focus:border-forest-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700 sm:w-56',
        className,
      )}
    />
  );
}
