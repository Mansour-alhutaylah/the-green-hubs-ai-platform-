/**
 * Derives every browser/OS/social brand asset in `public/` from one file:
 *
 *   brand-source/the-green-hubs-logo.png   the official company logo,
 *                                          1536x1024, 8-bit RGB, no alpha
 *
 * That file is the single source of truth for this branch's branding. It
 * lives outside `public/` on purpose: it is a build-time input, not a
 * runtime asset, so its 1.2 MB never ships in a deployment.
 *
 * Nothing here draws, recolours, reproportions, or reinterprets the logo.
 * Every output is a rectangular crop of that file resampled to size — no
 * compositing, no added background, no glow, no rounded tile. The crop
 * boxes below were measured off the file itself, by treating any pixel
 * more than 22 luminance units above the canvas as foreground and taking
 * the bounding box of each column run; `scripts/` has no measurement code
 * because the numbers are fixed properties of a fixed file.
 *
 * Run by hand whenever the official artwork changes; the outputs are
 * committed, so neither the build nor the runtime depends on this file,
 * and re-running it reproduces every asset byte for byte:
 *
 *   node scripts/generate-brand-assets.mjs
 *
 * Deliberately dependency-free (node:zlib does the PNG deflate/inflate) —
 * a one-time asset conversion does not justify adding an image toolchain
 * to the project.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { deflateSync, inflateSync } from 'node:zlib';
import path from 'node:path';

const FRONTEND_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PUBLIC_DIR = path.join(FRONTEND_DIR, 'public');
const SOURCE_LOGO = path.join(FRONTEND_DIR, 'brand-source/the-green-hubs-logo.png');

/* ------------------------------------------------------------------ PNG */

const CRC_TABLE = (() => {
  const table = new Int32Array(256);
  for (let n = 0; n < 256; n += 1) {
    let c = n;
    for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c;
  }
  return table;
})();

function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i += 1) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function paeth(a, b, c) {
  const p = a + b - c;
  const pa = Math.abs(p - a);
  const pb = Math.abs(p - b);
  const pc = Math.abs(p - c);
  if (pa <= pb && pa <= pc) return a;
  return pb <= pc ? b : c;
}

/** Decodes an 8-bit, non-interlaced RGB/RGBA PNG to a flat RGBA buffer. */
function decodePng(buffer) {
  let offset = 8;
  const idat = [];
  let width = 0;
  let height = 0;
  let channels = 0;

  while (offset < buffer.length) {
    const length = buffer.readUInt32BE(offset);
    const type = buffer.toString('ascii', offset + 4, offset + 8);
    const body = buffer.subarray(offset + 8, offset + 8 + length);

    if (type === 'IHDR') {
      width = body.readUInt32BE(0);
      height = body.readUInt32BE(4);
      const [bitDepth, colorType] = [body[8], body[9]];
      const interlace = body[12];
      if (bitDepth !== 8 || interlace !== 0 || (colorType !== 2 && colorType !== 6)) {
        throw new Error(
          `Unsupported PNG: depth=${bitDepth} color=${colorType} interlace=${interlace}`,
        );
      }
      channels = colorType === 6 ? 4 : 3;
    } else if (type === 'IDAT') {
      idat.push(body);
    } else if (type === 'IEND') {
      break;
    }
    offset += 12 + length;
  }

  const raw = inflateSync(Buffer.concat(idat));
  const stride = width * channels;
  const pixels = Buffer.alloc(width * height * 4);
  let previous = Buffer.alloc(stride);

  for (let y = 0; y < height; y += 1) {
    const filter = raw[y * (stride + 1)];
    const line = Buffer.from(raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1)));

    for (let i = 0; i < stride; i += 1) {
      const left = i >= channels ? line[i - channels] : 0;
      const up = previous[i];
      const upLeft = i >= channels ? previous[i - channels] : 0;
      if (filter === 1) line[i] = (line[i] + left) & 0xff;
      else if (filter === 2) line[i] = (line[i] + up) & 0xff;
      else if (filter === 3) line[i] = (line[i] + ((left + up) >> 1)) & 0xff;
      else if (filter === 4) line[i] = (line[i] + paeth(left, up, upLeft)) & 0xff;
      else if (filter !== 0) throw new Error(`Unknown PNG filter ${filter}`);
    }

    for (let x = 0; x < width; x += 1) {
      const src = x * channels;
      const dst = (y * width + x) * 4;
      pixels[dst] = line[src];
      pixels[dst + 1] = line[src + 1];
      pixels[dst + 2] = line[src + 2];
      pixels[dst + 3] = channels === 4 ? line[src + 3] : 255;
    }
    previous = line;
  }

  return { width, height, pixels };
}

function pngChunk(type, body) {
  const out = Buffer.alloc(body.length + 12);
  out.writeUInt32BE(body.length, 0);
  out.write(type, 4, 'ascii');
  body.copy(out, 8);
  out.writeUInt32BE(crc32(out.subarray(4, 8 + body.length)), 8 + body.length);
  return out;
}

/** Encodes a flat RGBA buffer as an 8-bit PNG, RGB unless alpha is asked for. */
function encodePng({ width, height, pixels }, { alpha = false } = {}) {
  const channels = alpha ? 4 : 3;
  const stride = width * channels;
  const raw = Buffer.alloc((stride + 1) * height);
  const line = Buffer.alloc(stride);
  const candidates = Array.from({ length: 5 }, () => Buffer.alloc(stride));
  let previous = Buffer.alloc(stride);

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const src = (y * width + x) * 4;
      const dst = x * channels;
      line[dst] = pixels[src];
      line[dst + 1] = pixels[src + 1];
      line[dst + 2] = pixels[src + 2];
      if (alpha) line[dst + 3] = pixels[src + 3];
    }

    // Per-row adaptive filtering (the standard minimum-sum-of-absolute-
    // differences heuristic) — the flat canvas and hard-edged mark cost
    // roughly twice as many bytes under the trivial "None" filter.
    let best = 0;
    let bestScore = Infinity;
    for (let f = 0; f < 5; f += 1) {
      const out = candidates[f];
      let score = 0;
      for (let i = 0; i < stride; i += 1) {
        const left = i >= channels ? line[i - channels] : 0;
        const up = previous[i];
        const upLeft = i >= channels ? previous[i - channels] : 0;
        let v;
        if (f === 0) v = line[i];
        else if (f === 1) v = line[i] - left;
        else if (f === 2) v = line[i] - up;
        else if (f === 3) v = line[i] - ((left + up) >> 1);
        else v = line[i] - paeth(left, up, upLeft);
        v &= 0xff;
        out[i] = v;
        score += v < 128 ? v : 256 - v;
      }
      if (score < bestScore) {
        bestScore = score;
        best = f;
      }
    }

    raw[y * (stride + 1)] = best;
    candidates[best].copy(raw, y * (stride + 1) + 1);
    previous = Buffer.from(line);
  }

  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;
  ihdr[9] = alpha ? 6 : 2;

  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    pngChunk('IHDR', ihdr),
    pngChunk('IDAT', deflateSync(raw, { level: 9 })),
    pngChunk('IEND', Buffer.alloc(0)),
  ]);
}

/* ------------------------------------------------------------- Resample */

function axisWeights(sourceLength, targetLength) {
  const scale = targetLength / sourceLength;
  // Support widens when shrinking so every source pixel contributes (area
  // averaging, no aliasing) and stays at 1 when growing (bilinear).
  const support = scale < 1 ? 1 / scale : 1;
  const entries = [];

  for (let i = 0; i < targetLength; i += 1) {
    const center = (i + 0.5) / scale - 0.5;
    const start = Math.floor(center - support + 0.5);
    const end = Math.ceil(center + support - 0.5);
    const weights = [];
    let total = 0;
    for (let j = start; j <= end; j += 1) {
      const w = Math.max(0, 1 - Math.abs(j - center) / support);
      weights.push(w);
      total += w;
    }
    for (let j = 0; j < weights.length; j += 1) weights[j] /= total;
    entries.push({ start, weights });
  }
  return entries;
}

const clamp = (v, min, max) => (v < min ? min : v > max ? max : v);
const round8 = (v) => clamp(Math.round(v), 0, 255);

/** Separable tent-filter resample of the source rect {sx, sy, sw, sh}. */
function resample(image, { sx = 0, sy = 0, sw = image.width, sh = image.height, width, height }) {
  const horizontal = axisWeights(sw, width);
  const vertical = axisWeights(sh, height);
  const intermediate = new Float32Array(width * sh * 4);

  for (let y = 0; y < sh; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const { start, weights } = horizontal[x];
      let r = 0;
      let g = 0;
      let b = 0;
      let a = 0;
      for (let i = 0; i < weights.length; i += 1) {
        const src = ((y + sy) * image.width + clamp(start + i, 0, sw - 1) + sx) * 4;
        const w = weights[i];
        r += image.pixels[src] * w;
        g += image.pixels[src + 1] * w;
        b += image.pixels[src + 2] * w;
        a += image.pixels[src + 3] * w;
      }
      const dst = (y * width + x) * 4;
      intermediate[dst] = r;
      intermediate[dst + 1] = g;
      intermediate[dst + 2] = b;
      intermediate[dst + 3] = a;
    }
  }

  const pixels = Buffer.alloc(width * height * 4);
  for (let y = 0; y < height; y += 1) {
    const { start, weights } = vertical[y];
    for (let x = 0; x < width; x += 1) {
      let r = 0;
      let g = 0;
      let b = 0;
      let a = 0;
      for (let i = 0; i < weights.length; i += 1) {
        const src = (clamp(start + i, 0, sh - 1) * width + x) * 4;
        const w = weights[i];
        r += intermediate[src] * w;
        g += intermediate[src + 1] * w;
        b += intermediate[src + 2] * w;
        a += intermediate[src + 3] * w;
      }
      const dst = (y * width + x) * 4;
      pixels[dst] = round8(r);
      pixels[dst + 1] = round8(g);
      pixels[dst + 2] = round8(b);
      pixels[dst + 3] = round8(a);
    }
  }

  return { width, height, pixels };
}

/* ------------------------------------------------------------------ ICO */

/** Packs 32-bit BGRA DIB entries into a classic multi-size .ico. */
function encodeIco(images) {
  const entries = [];
  const bodies = [];
  let offset = 6 + images.length * 16;

  for (const { width, height, pixels } of images) {
    const maskStride = Math.ceil(width / 32) * 4;
    const body = Buffer.alloc(40 + width * height * 4 + maskStride * height);
    body.writeUInt32LE(40, 0);
    body.writeInt32LE(width, 4);
    // A .ico DIB declares double height: the XOR (color) bitmap followed by
    // the AND (transparency) mask, which stays all-zero here — the mark
    // crop is fully opaque.
    body.writeInt32LE(height * 2, 8);
    body.writeUInt16LE(1, 12);
    body.writeUInt16LE(32, 14);

    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const src = ((height - 1 - y) * width + x) * 4; // DIB rows run bottom-up
        const dst = 40 + (y * width + x) * 4;
        body[dst] = pixels[src + 2];
        body[dst + 1] = pixels[src + 1];
        body[dst + 2] = pixels[src];
        body[dst + 3] = 255;
      }
    }

    const entry = Buffer.alloc(16);
    entry[0] = width >= 256 ? 0 : width;
    entry[1] = height >= 256 ? 0 : height;
    entry.writeUInt16LE(1, 4);
    entry.writeUInt16LE(32, 6);
    entry.writeUInt32LE(body.length, 8);
    entry.writeUInt32LE(offset, 12);
    entries.push(entry);
    bodies.push(body);
    offset += body.length;
  }

  const header = Buffer.alloc(6);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(images.length, 4);
  return Buffer.concat([header, ...entries, ...bodies]);
}

/* ----------------------------------------------------------- Generation */

/**
 * Measured off the official file (see the module docstring for how):
 *
 *   symbol    x 343-741, y 296-694   (399 x 399, exactly square)
 *   divider   x 798-802
 *   wordmark  x 879-1262
 *   lockup    x 343-1262, y 296-694  (920 x 399)
 *   canvas    flat rgb(12,32,17) = #0C2011, no gradient, no glow
 *
 * Every crop below is expressed against those numbers, and every output is
 * a straight resample of a crop — no compositing, no recolouring, no added
 * background. The source has no alpha channel: its dark canvas is part of
 * the artwork, so cropped icons simply carry it. That is deliberate. The
 * mark is half white; keyed to transparency it would lose those strokes
 * against a light browser tab strip and against the boot screen's own
 * light background.
 */
const SYMBOL = { sx: 295, sy: 248, sw: 495, sh: 495 };
const LOCKUP = { sx: 282, sy: 235, sw: 1040, sh: 520 };
const SHARE = { sx: 69, sy: 110, sw: 1467, sh: 770 };

const emit = (name, buffer, note) => {
  writeFileSync(path.join(PUBLIC_DIR, name), buffer);
  console.log(
    `${name.padEnd(22)} ${`${(buffer.length / 1024).toFixed(1)} KB`.padStart(9)}  ${note}`,
  );
};

const official = decodePng(readFileSync(SOURCE_LOGO));
if (official.width !== 1536 || official.height !== 1024) {
  throw new Error(
    `Unexpected source size ${official.width}x${official.height}; crops below assume 1536x1024`,
  );
}

/**
 * Square icons take the symbol alone: the wordmark is illegible below
 * ~128px, and the symbol crop stops 8px short of the divider so no sliver
 * of it can bleed in. 48px of the source's own canvas is kept on all four
 * sides (12% of the mark) — that is the "safe padding" iOS's home-screen
 * mask and Android's launcher need, and it is the artwork's real
 * background rather than an invented tile.
 */
const square = (size) => resample(official, { ...SYMBOL, width: size, height: size });

emit('favicon-16x16.png', encodePng(square(16)), 'symbol crop -> 16x16');
emit('favicon-32x32.png', encodePng(square(32)), 'symbol crop -> 32x32');
emit('favicon.ico', encodeIco([16, 32, 48].map(square)), 'symbol crop -> 16/32/48');
emit('apple-touch-icon.png', encodePng(square(180)), 'symbol crop -> 180x180');
emit('icon-192x192.png', encodePng(square(192)), 'symbol crop -> 192x192');
emit('icon-512x512.png', encodePng(square(512)), 'symbol crop -> 512x512');

/**
 * The boot/loading lockup. The crop is exactly 2:1 with a symmetric 60px
 * margin on all four sides of the lockup, emitted at 2x the 320x160 box it
 * is displayed in so it stays crisp on a retina screen.
 */
emit(
  'brand-lockup.png',
  encodePng(resample(official, { ...LOCKUP, width: 640, height: 320 })),
  'lockup crop -> 640x320 (2x of 320x160)',
);

/**
 * The symbol for the boot screen, which sits on the application's light
 * paper background rather than on the artwork's own dark canvas.
 *
 * Roughly half the mark is drawn in white, so a straight alpha-key of the
 * canvas would delete those strokes against light paper and leave a mark
 * with holes in it. Instead the canvas is kept — but only inside the mark's
 * own diamond. The mask is the L1 ball |dx| + |dy| <= r, which is precisely
 * the silhouette the mark already describes (its four tips sit at the
 * midpoints of its 399px bounding square), scaled 7% out so the tips and
 * the two detached accent squares keep a little of their ground. Outside
 * that diamond every pixel is fully transparent.
 *
 * So this is still only a crop plus a mask: no pixel is recoloured, no
 * geometry is redrawn, and the result carries no rectangle, card, tile,
 * glow, or shadow — just the official symbol on its own dark diamond.
 */
const BOOT_SYMBOL = { sx: 318, sy: 271, sw: 447, sh: 447 };
const BOOT_SYMBOL_SIZE = 320; // 4x the 80px box it is displayed in
const bootSymbol = resample(official, {
  ...BOOT_SYMBOL,
  width: BOOT_SYMBOL_SIZE,
  height: BOOT_SYMBOL_SIZE,
});

const outputScale = BOOT_SYMBOL_SIZE / BOOT_SYMBOL.sw;
// Symbol centre and half-extent (343-741 of the source) in output pixels.
const centre = (542 - BOOT_SYMBOL.sx) * outputScale;
const radius = 199.5 * outputScale * 1.07;
const FEATHER = 1.5;

for (let y = 0; y < BOOT_SYMBOL_SIZE; y += 1) {
  for (let x = 0; x < BOOT_SYMBOL_SIZE; x += 1) {
    const distance = Math.abs(x - centre) + Math.abs(y - centre);
    const coverage = clamp((radius - distance) / FEATHER + 0.5, 0, 1);
    bootSymbol.pixels[(y * BOOT_SYMBOL_SIZE + x) * 4 + 3] = Math.round(coverage * 255);
  }
}

emit(
  'brand-symbol.png',
  encodePng(bootSymbol, { alpha: true }),
  'symbol crop + diamond mask -> 320x320',
);

/**
 * The 1200x630 share card. 1467x770 is the widest 1.905:1 window that
 * keeps the lockup horizontally centred (its centre sits at x=802.5, so
 * the right edge is the binding constraint). No subtitle is drawn: the
 * only way to add one would be to set type in a font that is not the
 * brand's, and the artwork already carries the wordmark.
 */
const share = resample(official, { ...SHARE, width: 1200, height: 630 });
emit('og-image.png', encodePng(share), 'lockup crop -> 1200x630');
