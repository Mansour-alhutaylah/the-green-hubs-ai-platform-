import { useRef } from 'react';
import type { KeyboardEvent, ReactNode } from 'react';
import { useLocale } from '@/lib/i18n/useLocale';
import { cn } from '@/lib/utils/cn';
import { tabButtonId } from './tabIds';

export interface TabItem<Value extends string = string> {
  value: Value;
  label: string;
  /** Rendered but not selectable, and skipped by arrow/Home/End navigation. */
  disabled?: boolean;
}

export interface TabsProps<Value extends string = string> {
  /** Stable prefix for the generated tab element ids — must be unique on the
   * page and must not change between renders, since `aria-labelledby` on the
   * panel points at it. */
  id: string;
  items: readonly TabItem<Value>[];
  value: Value;
  onChange: (value: Value) => void;
  /** Accessible name of the tab list itself. */
  label: string;
  /** Id of the `TabPanel` these tabs control. */
  panelId: string;
  className?: string;
}

/**
 * The shared tab-list primitive (APG tabs pattern), replacing the three
 * hand-rolled `role="tablist"` strips that had matching styling but no
 * keyboard support, no `aria-controls`, and no associated panel.
 *
 * Activation is **manual**: arrow keys move focus, Enter/Space (the native
 * button activation, so no extra key handling) selects. Automatic
 * activation is the APG default only when revealing a panel is cheap — here
 * a selection change re-queries the server, so arrowing across five filters
 * would fire and abort four requests the user never asked for.
 *
 * Arrow direction follows the document direction: in RTL, ArrowLeft moves
 * to the *next* tab, matching how the list is actually laid out. Focus
 * management is a roving tabindex on the buttons themselves — the tab list
 * container is not a tab stop, per the pattern.
 */
export function Tabs<Value extends string = string>({
  id,
  items,
  value,
  onChange,
  label,
  panelId,
  className,
}: TabsProps<Value>) {
  const { dir } = useLocale();
  const listRef = useRef<HTMLDivElement>(null);

  function tabButtons(): HTMLButtonElement[] {
    return Array.from(listRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]') ?? []);
  }

  /** Next selectable index in `step` direction, skipping disabled tabs and
   * wrapping around. Returns `null` when nothing else is selectable. */
  function nextEnabledIndex(from: number, step: number): number | null {
    for (let offset = 1; offset <= items.length; offset += 1) {
      const index = (from + step * offset + items.length * items.length) % items.length;
      if (!items[index]?.disabled) return index;
    }
    return null;
  }

  function edgeEnabledIndex(step: 1 | -1): number | null {
    const start = step === 1 ? 0 : items.length - 1;
    if (!items[start]?.disabled) return start;
    return nextEnabledIndex(start, step);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const forward = dir === 'rtl' ? 'ArrowLeft' : 'ArrowRight';
    const backward = dir === 'rtl' ? 'ArrowRight' : 'ArrowLeft';

    let target: number | null = null;
    if (event.key === forward) target = nextEnabledIndex(index, 1);
    else if (event.key === backward) target = nextEnabledIndex(index, -1);
    else if (event.key === 'Home') target = edgeEnabledIndex(1);
    else if (event.key === 'End') target = edgeEnabledIndex(-1);
    else return;

    event.preventDefault();
    if (target != null) tabButtons()[target]?.focus();
  }

  return (
    <div
      ref={listRef}
      role="tablist"
      aria-label={label}
      className={cn('flex flex-wrap items-center gap-1', className)}
    >
      {items.map((item, index) => {
        const selected = item.value === value;
        return (
          <button
            key={item.value}
            id={tabButtonId(id, item.value)}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={panelId}
            // Roving tabindex: the tab strip is one Tab stop, and arrow keys
            // move within it.
            tabIndex={selected ? 0 : -1}
            disabled={item.disabled}
            onKeyDown={(event) => handleKeyDown(event, index)}
            onClick={() => {
              if (!item.disabled) onChange(item.value);
            }}
            className={cn(
              'rounded-m px-3 py-1.5 text-caption font-bold transition-colors',
              selected
                ? 'bg-forest-900 text-white'
                : 'text-gray-600 hover:bg-tint-100 hover:text-forest-900',
              item.disabled && 'cursor-not-allowed opacity-40 hover:bg-transparent',
            )}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

export interface TabPanelProps {
  /** Must match the `panelId` given to the `Tabs` that control this panel. */
  id: string;
  /** The `id` given to those `Tabs`. */
  tabsId: string;
  /** The currently selected tab value — names the panel after its tab. */
  value: string;
  /** Set when the panel has no focusable content of its own (APG: give the
   * panel itself a tab stop so keyboard users can reach the content). */
  focusable?: boolean;
  className?: string;
  children: ReactNode;
}

export function TabPanel({ id, tabsId, value, focusable, className, children }: TabPanelProps) {
  return (
    <div
      id={id}
      role="tabpanel"
      aria-labelledby={tabButtonId(tabsId, value)}
      tabIndex={focusable ? 0 : undefined}
      className={className}
    >
      {children}
    </div>
  );
}
