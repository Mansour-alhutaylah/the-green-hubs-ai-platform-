import { clsx } from 'clsx';
import type { ClassValue } from 'clsx';
import { extendTailwindMerge } from 'tailwind-merge';

/**
 * Tailwind's `text-*` prefix serves two unrelated purposes — font size
 * (`text-sm`) and text color (`text-white`) — and tailwind-merge tells
 * them apart using its built-in list of known font-size scale names. Our
 * custom §14.2 type scale (`text-display`, `text-body`, …) isn't on that
 * list, so plain `twMerge` mis-groups it with color utilities and silently
 * drops whichever text-color class comes second (e.g. `text-display
 * text-forest-900` would lose `text-forest-900`). Registering the custom
 * scale here fixes the classification.
 */
const twMerge = extendTailwindMerge({
  extend: {
    theme: {
      text: [
        'display',
        'metric',
        'title',
        'panel',
        'body',
        'caption',
        'label',
        'label-ar',
        'meta',
        'micro',
      ],
    },
  },
});

/** Merge conditional class names, resolving Tailwind utility conflicts (last wins). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
