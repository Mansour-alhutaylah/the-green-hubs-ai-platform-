import { describe, expect, it } from 'vitest';
import html from '../../../index.html?raw';
import manifestSource from '../../../public/site.webmanifest?raw';

/**
 * The browser-, OS-, and scraper-facing half of the branding lives in
 * static files that no component test can reach: a typo in an `href`, or an
 * asset that never got committed, ships a broken favicon or a blank
 * WhatsApp card and nothing else fails. These assertions cover exactly
 * that class of breakage — every referenced file exists, and the handful of
 * properties link previews actually depend on hold — rather than restating
 * the markup tag by tag.
 *
 * Everything is read through Vite (`?raw`, `import.meta.glob`) rather than
 * `node:fs`, because `src` typechecks against `vite/client` alone and app
 * code has no business reaching for Node built-ins.
 */
const PUBLIC_FILES = new Set(
  Object.keys(import.meta.glob('/public/**/*')).map((file) => file.replace(/^\/public/, '')),
);

const manifest = JSON.parse(manifestSource) as {
  name: string;
  short_name: string;
  display: string;
  theme_color: string;
  background_color: string;
  icons: { src: string; sizes: string; type: string }[];
};

function attribute(pattern: RegExp): string {
  const match = html.match(pattern);
  if (!match?.[1]) throw new Error(`index.html is missing ${pattern}`);
  return match[1];
}

describe('static branding assets', () => {
  it('ships every local file index.html points at', () => {
    const referenced = [...html.matchAll(/(?:href|src)="(\/[^"]+)"/g)]
      .flatMap((match) => (match[1] ? [match[1]] : []))
      .filter((href) => !href.startsWith('/src/'));

    expect(referenced.length).toBeGreaterThan(0);
    for (const href of referenced) {
      expect(PUBLIC_FILES.has(href), `${href} is referenced but missing`).toBe(true);
    }
  });

  it('ships every icon the web manifest declares', () => {
    expect(manifest.icons.length).toBeGreaterThan(0);
    for (const icon of manifest.icons) {
      expect(PUBLIC_FILES.has(icon.src), `${icon.src} is missing`).toBe(true);
    }
  });

  it('gives the manifest the product identity, not framework defaults', () => {
    expect(manifest.name).toBe('The Green Hubs');
    expect(manifest.short_name).toBe('Green Hubs');
    expect(manifest.display).toBe('standalone');
    // Forest-900 / paper-50, matching tokens.css and the theme-color tag.
    expect(manifest.theme_color).toBe('#122618');
    expect(manifest.background_color).toBe('#f7f9f6');
    expect(attribute(/name="theme-color"\s+content="([^"]+)"/)).toBe(manifest.theme_color);
  });

  it('boots with the official symbol on the application background', () => {
    // The pre-mount boot screen is the one surface that uses the official
    // logo asset. The application's own branding (login, sidebar) keeps its
    // established artwork through BrandLogo — the change of identity as the
    // app takes over is intended, not a bug.
    expect(attribute(/class="app-boot__symbol"\s+src="([^"]+)"/)).toBe('/brand-symbol.png');
    expect(PUBLIC_FILES.has('/brand-symbol.png')).toBe(true);
    // Paper-50: the boot screen shares the application's own surface, so it
    // must not reintroduce a full-bleed dark panel.
    expect(html).toContain('background-color: #f7f9f6;');
  });

  it('points no head tag or manifest icon at a retired asset', () => {
    // Superseded by the official-logo crops. Scoped to the external
    // surfaces this file owns; `public/brand/logo-lockup-white-on-forest.png`
    // is deliberately untouched and still serves the in-app UI.
    const surfaces = html + manifestSource;
    for (const retired of ['/icon-192.png', '/icon-512.png', '/favicon.png']) {
      expect(surfaces, `${retired} is still referenced`).not.toContain(`"${retired}"`);
    }
  });

  it('keeps the robots directives that hold this preview out of search', () => {
    expect(attribute(/name="robots"\s+content="([^"]+)"/)).toBe('noindex, nofollow, noarchive');
    expect(attribute(/name="googlebot"\s+content="([^"]+)"/)).toBe('noindex, nofollow, noarchive');
    // Social scrapers must still be allowed through, so no robots.txt rule.
    expect(PUBLIC_FILES.has('/robots.txt')).toBe(false);
  });

  it('gives scrapers absolute share-image URLs', () => {
    // WhatsApp, LinkedIn and iMessage resolve og:image against nothing —
    // a relative path silently yields a card with no image.
    for (const pattern of [
      /property="og:image"\s+content="([^"]+)"/,
      /name="twitter:image"\s+content="([^"]+)"/,
    ]) {
      expect(attribute(pattern)).toMatch(/^https:\/\//);
    }
    expect(PUBLIC_FILES.has('/og-image.png')).toBe(true);
  });

  it('describes the platform without claiming capabilities it does not have', () => {
    const description = attribute(/name="description"\s+content="([^"]+)"/);
    expect(description).toBe(attribute(/property="og:description"\s+content="([^"]+)"/));
    expect(description).not.toMatch(/\bESG\b|carbon|audit-ready|autonomous|agents?\b|isolat/i);
  });
});
