/**
 * The brand's diamond motif used as a quiet corner watermark — a handful of
 * large, sparse, low-opacity outlines, never a tiled background texture.
 * Per the approved auth redesign: "Do not tile the pattern across the
 * entire panel... it should feel like a quiet watermark." Built from the
 * same diamond geometry as the rest of the design system's status glyphs
 * (not a foreign texture), scattered and weighted toward the bottom-start
 * corner as the brand guideline's own cover-page usage does.
 */
const DIAMONDS = [
  { start: '-8%', top: '46%', size: 240, opacity: 0.05 },
  { start: '6%', top: '66%', size: 130, opacity: 0.06 },
  { start: '20%', top: '54%', size: 74, opacity: 0.05 },
  { start: '30%', top: '6%', size: 96, opacity: 0.04 },
] as const;

export function BrandPatternAccent() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      {DIAMONDS.map((d) => (
        <svg
          key={`${d.start}-${d.top}`}
          width={d.size}
          height={d.size}
          viewBox="0 0 100 100"
          className="absolute"
          style={{ insetInlineStart: d.start, top: d.top }}
        >
          <rect
            x="20"
            y="20"
            width="60"
            height="60"
            fill="none"
            stroke="white"
            strokeWidth={2}
            opacity={d.opacity}
            transform="rotate(45 50 50)"
          />
        </svg>
      ))}
    </div>
  );
}
