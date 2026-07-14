import type { ImgHTMLAttributes } from 'react';
import { cn } from '@/lib/utils/cn';

const OFFICIAL_LOGO_SRC = '/brand/green-hubs-official.png';
const OFFICIAL_LOGO_TRANSPARENT_SRC = '/brand/green-hubs-official-transparent.png';

export interface BrandLogoProps extends Omit<ImgHTMLAttributes<HTMLImageElement>, 'src'> {
  size?: 'compact' | 'standard' | 'hero';
  surface?: 'dark' | 'light';
}

/**
 * The single approved Green Hubs company lockup. Every application surface
 * renders the supplied artwork through this component so its source,
 * proportions, spacing, and responsive sizing cannot drift between pages.
 * The transparent derivative is reserved for light surfaces only.
 */
export function BrandLogo({
  size = 'standard',
  surface = 'dark',
  className,
  alt = 'The Green Hubs',
  ...props
}: BrandLogoProps) {
  return (
    <img
      src={surface === 'light' ? OFFICIAL_LOGO_TRANSPARENT_SRC : OFFICIAL_LOGO_SRC}
      alt={alt}
      width={1774}
      height={887}
      draggable={false}
      className={cn(
        'block h-auto max-w-full shrink-0 select-none object-contain',
        size === 'compact' && 'w-14',
        size === 'standard' && 'w-52',
        size === 'hero' && 'w-52',
        className,
      )}
      {...props}
    />
  );
}
