import type { ImgHTMLAttributes } from 'react';
import { cn } from '@/lib/utils/cn';

const OFFICIAL_LOGO_SRC = '/brand/logo-lockup-white-on-forest.png';
const SOURCE_WIDTH = 1536;
const SOURCE_HEIGHT = 1024;

/**
 * The source canvas carries a soft atmospheric glow well past the mark
 * itself. Measured against the 1536x1024 canvas: the full lockup (diamond
 * mark + divider + "THE GREEN HUBS" wordmark) spans x:300-1162, y:222-684;
 * the mark alone (before the divider, which starts at x:782) spans
 * x:300-766, y:222-684. Every size variant renders through the same CSS
 * crop-window technique — an oversized `<img>` absolutely positioned inside
 * an `overflow-hidden` frame — rather than separate cropped files, so there
 * is only ever one source asset on disk. No pixels are edited, redrawn, or
 * recolored; only the visible window changes per context:
 *
 * - `hero` (login): generous margin around the full lockup (~22%) — enough
 *   glow left to read as atmospheric, not cropped, without the excessive
 *   dead canvas the raw asset carries.
 * - `standard` (expanded sidebar): tighter margin around the full lockup
 *   (~9%) so the compact brand block doesn't carry much empty space.
 * - `compact` (collapsed sidebar): cropped to the mark alone, centered,
 *   bounded by the divider on the right — same box `public/favicon.png`
 *   was mechanically cropped from.
 */
interface CropBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

const HERO_CROP: CropBox = { x0: 110, y0: 120, x1: 1352, y1: 786 };
const STANDARD_CROP: CropBox = { x0: 222, y0: 180, x1: 1240, y1: 726 };
const COMPACT_CROP: CropBox = { x0: 292, y0: 212, x1: 774, y1: 694 };

const HERO_CONTAINER_WIDTH = 256; // ~230-260px target
const STANDARD_CONTAINER_WIDTH = 160; // ~140-160px target
const COMPACT_CONTAINER_WIDTH = 40;

function cropGeometry(containerWidth: number, box: CropBox) {
  const cropWidth = box.x1 - box.x0;
  const cropHeight = box.y1 - box.y0;
  const scale = containerWidth / cropWidth;
  return {
    containerWidth,
    containerHeight: containerWidth * (cropHeight / cropWidth),
    imgWidth: SOURCE_WIDTH * scale,
    imgHeight: SOURCE_HEIGHT * scale,
    offsetLeft: -(box.x0 * scale),
    offsetTop: -(box.y0 * scale),
  };
}

const CROP_GEOMETRY = {
  hero: cropGeometry(HERO_CONTAINER_WIDTH, HERO_CROP),
  standard: cropGeometry(STANDARD_CONTAINER_WIDTH, STANDARD_CROP),
  compact: cropGeometry(COMPACT_CONTAINER_WIDTH, COMPACT_CROP),
};

export interface BrandLogoProps extends Omit<ImgHTMLAttributes<HTMLImageElement>, 'src'> {
  size?: 'compact' | 'standard' | 'hero';
}

/**
 * The single approved Green Hubs company lockup. Every application surface
 * renders the supplied artwork through this component so its source,
 * proportions, spacing, and responsive sizing cannot drift between pages.
 */
export function BrandLogo({
  size = 'standard',
  className,
  alt = 'The Green Hubs',
  ...props
}: BrandLogoProps) {
  const geometry = CROP_GEOMETRY[size];

  return (
    <span
      className={cn('relative block shrink-0 select-none overflow-hidden', className)}
      style={{ width: geometry.containerWidth, height: geometry.containerHeight }}
    >
      <img
        src={OFFICIAL_LOGO_SRC}
        alt={alt}
        width={SOURCE_WIDTH}
        height={SOURCE_HEIGHT}
        draggable={false}
        className="pointer-events-none absolute max-w-none select-none"
        style={{
          width: `${geometry.imgWidth}px`,
          height: `${geometry.imgHeight}px`,
          left: `${geometry.offsetLeft}px`,
          top: `${geometry.offsetTop}px`,
        }}
        {...props}
      />
    </span>
  );
}
