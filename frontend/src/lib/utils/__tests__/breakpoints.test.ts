import { describe, expect, it } from 'vitest';
import { navModeForWidth } from '../breakpoints';

describe('responsive navigation at required review widths', () => {
  it.each([
    [1440, 'desktop'],
    [1280, 'desktop'],
    [1024, 'tablet'],
    [768, 'tablet'],
    [390, 'mobile'],
    [360, 'mobile'],
  ] as const)('uses %s px as %s navigation', (width, expectedMode) => {
    expect(navModeForWidth(width)).toBe(expectedMode);
  });
});
