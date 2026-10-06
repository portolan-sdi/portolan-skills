// Verification for a publisher-branded portolan-browser fork.
//
// Copy this file into the fork as verify-<publisher>.mjs and fill in every
// slot marked TODO. It drives a real browser and asserts what the fork
// promises. The inherited tests/e2e suite asserts the upstream multi-catalog
// product, so it does not apply here.
//
// This reaches the network on purpose. It verifies against the real catalog
// rather than a mock. Catalog-dependent checks skip, and do not fail, while
// the catalog is offline. The branding shell is the promise either way.
//
// The map probe needs Vue component internals, which a production build
// strips. Run against the dev server, or build with STAC_BROWSER_E2E=true.
//
// MapLibre renders only when the tab is visible. A backgrounded tab shows an
// inert map with no tile requests, which looks like a broken basemap.
//
// Usage:
//   node_modules/.bin/vite --port 8080 --strictPort &
//   node verify-<publisher>.mjs [baseUrl]
//
// Screenshots land in ./verify-out (override with VERIFY_OUT).

/* global process, fetch */
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const BASE = process.argv[2] || 'http://localhost:8080';
const OUT = process.env.VERIFY_OUT || './verify-out';

// TODO: the catalog this fork serves.
const CATALOG_URL = 'https://example.org/catalog.json';

// TODO: the approved tokens, as the browser reports them.
const TOKENS = {
  brand: 'rgb(0, 0, 0)',
  brandHover: 'rgb(0, 0, 0)',
  pageBg: 'rgb(255, 255, 255)',
  bodyFont: /TODO/,
  headingFont: /TODO/,
};

// TODO: the hosts this fork's basemaps and tiles come from.
const TILE_HOSTS = /cartocdn\.com|arcgisonline\.com/;

// TODO: the number of basemaps basemaps.config.js offers.
const BASEMAP_COUNT = 3;

const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 390, height: 844 };

mkdirSync(OUT, { recursive: true });

const results = [];
function check(name, pass, detail) {
  results.push({ name, pass, detail });
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${detail}` : ''}`);
}
function skip(name, detail) {
  console.log(`SKIP  ${name}${detail ? ` — ${detail}` : ''}`);
}

// Reaches into the page for the live MapLibre instance. MapView keeps it on
// the component, so walk the Vue tree up from the map container element.
const MAP_PROBE = `(() => {
  const el = document.querySelector('.maplibregl-map');
  if (!el) return null;
  let node = el;
  while (node) {
    let c = node.__vueParentComponent;
    while (c) {
      if (c.ctx && c.ctx.map && c.ctx.map.getStyle) return c.ctx.map;
      if (c.proxy && c.proxy.map && c.proxy.map.getStyle) return c.proxy.map;
      c = c.parent;
    }
    node = node.parentElement;
  }
  return null;
})()`;

const catalogLive = await fetch(CATALOG_URL).then(r => r.ok).catch(() => false);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: DESKTOP });

const consoleErrors = [];
page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); });
page.on('pageerror', e => consoleErrors.push(`pageerror: ${e.message}`));

const tileRequests = [];
page.on('request', r => { if (TILE_HOSTS.test(r.url())) tileRequests.push(r.url()); });

// ---------- 1. Root ----------
await page.goto(`${BASE}/#/`, { waitUntil: 'networkidle' });
await page.waitForTimeout(3000);
await page.screenshot({ path: `${OUT}/01-root-desktop.png` });

// ---------- 2. Branding ----------
// TODO: replace the selectors with this fork's header class names.
const header = await page.evaluate(() => {
  const cs = e => e && getComputedStyle(e);
  const brand = document.querySelector('.brand');
  return {
    barBg: cs(document.querySelector('header'))?.backgroundColor,
    brandColor: cs(brand)?.color,
    brandText: brand?.innerText.replace(/\s+/g, ''),
    logoSrc: document.querySelector('header img')?.getAttribute('src'),
    hOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  };
});
check('wordmark uses the brand color', header.brandColor === TOKENS.brand, header.brandColor);
check('logo asset is referenced', !!header.logoSrc, header.logoSrc);
check('no horizontal overflow on desktop', header.hOverflow === 0, `${header.hOverflow}px`);

// A control that changes on hover must actually change.
// TODO: point at this fork's primary action control.
await page.hover('header a, header button').catch(() => {});
const hoverBg = await page.evaluate(
  () => getComputedStyle(document.querySelector('header a, header button')).backgroundColor
).catch(() => null);
if (hoverBg) {
  check('primary control has a hover state', hoverBg === TOKENS.brandHover, hoverBg);
}
else {
  skip('primary control has a hover state', 'no header control found');
}
await page.mouse.move(0, 0);

// ---------- 3. Typography and palette ----------
const type = await page.evaluate(() => {
  const b = getComputedStyle(document.body);
  const h1 = document.querySelector('h1');
  const link = [...document.querySelectorAll('a')].find(a =>
    a.innerText.trim().length > 3 && !a.closest('.maplibregl-map') && !a.closest('header'));
  return {
    bodyFont: b.fontFamily,
    bodyBg: b.backgroundColor,
    h1Font: h1 && getComputedStyle(h1).fontFamily,
    linkColor: link && getComputedStyle(link).color,
    linkText: link && link.innerText.trim().slice(0, 20),
  };
});
check('body font matches the token', TOKENS.bodyFont.test(type.bodyFont || ''), type.bodyFont);
check('heading font matches the token', TOKENS.headingFont.test(type.h1Font || ''), type.h1Font);
check('page background matches the token', type.bodyBg === TOKENS.pageBg, type.bodyBg);
if (type.linkColor) {
  check('prose links use the brand color', type.linkColor === TOKENS.brand,
    `${type.linkColor} (${type.linkText})`);
}
else {
  skip('prose links use the brand color', 'no prose link on the page to sample');
}

// ---------- 4. Footer provenance ----------
// A visitor should reach the data, the publisher, and the source code.
const footer = await page.evaluate(() =>
  [...document.querySelectorAll('footer a')].map(a => ({ text: a.innerText.trim(), href: a.href }))
);
const labels = footer.map(l => l.text).join(' | ') || 'no footer links';
// TODO: replace each host with this fork's own.
check('footer links to the publisher', footer.some(l => l.href.includes('example.org')), labels);
check('footer links to the catalog', footer.some(l => l.href.includes('source.coop')), labels);
check('footer links to the source code', footer.some(l => l.href.includes('github.com')), labels);

// ---------- 5. Mobile layout ----------
await page.setViewportSize(MOBILE);
await page.waitForTimeout(1500);
await page.screenshot({ path: `${OUT}/02-root-mobile.png` });
const mobile = await page.evaluate(() => ({
  hOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  headerVisible: !!document.querySelector('header')?.getBoundingClientRect().height,
}));
check('no horizontal overflow on mobile', mobile.hOverflow === 0, `${mobile.hOverflow}px`);
check('header renders on mobile', mobile.headerVisible, String(mobile.headerVisible));
await page.setViewportSize(DESKTOP);

// ---------- 6. Catalog and map ----------
if (!catalogLive) {
  skip('catalog checks', `catalog not reachable at ${CATALOG_URL}`);
}
else {
  const title = await page.textContent('h1').catch(() => null);
  check('root catalog loads a title', !!title, `h1 = ${JSON.stringify(title)}`);

  const cardCount = await page.locator('.catalog-card').count();
  check('collections are listed', cardCount > 0, `${cardCount} cards`);

  // TODO: assert this fork's own home sections, and its empty states.

  // Descend to a collection. A topic sub-catalog needs one more step.
  await page.locator('.catalog-card a').first().click();
  await page.waitForTimeout(2500);
  if (await page.locator('.maplibregl-map').count() === 0
      && await page.locator('.catalog-card a').count() > 0) {
    await page.locator('.catalog-card a').first().click();
  }
  await page.waitForSelector('.maplibregl-map', { timeout: 30000 }).catch(() => {});

  if (await page.locator('.maplibregl-map').count() === 0) {
    skip('map checks', 'the first collection shows no map');
  }
  else {
    await page.waitForFunction(
      `(() => { const m = ${MAP_PROBE}; return m && m.isStyleLoaded && m.isStyleLoaded(); })()`,
      null, { timeout: 45000}).catch(() => {});
    await page.waitForTimeout(4000);

    const mapState = await page.evaluate(`(() => {
      const m = ${MAP_PROBE};
      if (!m) return null;
      const layers = m.getStyle().layers.map(l => l.id + ':' + l.type);
      return {
        minZoom: m.getMinZoom(),
        maxBounds: m.getMaxBounds() && m.getMaxBounds().toArray(),
        layers,
      };
    })()`);

    if (!mapState) {
      console.error('Could not reach the MapLibre instance. This script needs Vue component '
        + 'internals, which production builds strip. Point it at the dev server, or build '
        + 'with STAC_BROWSER_E2E=true.');
      check('map is reachable', false, 'no MapLibre instance');
    }
    else {
      check('basemap tiles are requested', tileRequests.length > 0, `${tileRequests.length} requests`);

      // TODO: assert MAP_CONSTRAINTS when this fork bounds the map.
      // check('minZoom is clamped', mapState.minZoom === 9, String(mapState.minZoom));

      // Data draws above the basemap ground and below its labels.
      const symbolFirst = mapState.layers.findIndex(l => l.endsWith(':symbol'));
      // TODO: name this fork's data layer id prefix.
      const dataFirst = mapState.layers.findIndex(l => l.startsWith('stac-'));
      if (dataFirst >= 0 && symbolFirst >= 0) {
        check('data draws below the basemap labels', dataFirst < symbolFirst,
          `data at ${dataFirst}, first symbol at ${symbolFirst}`);
      }
      else {
        skip('data draws below the basemap labels', 'no data layer found in the style');
      }

      // The switcher offers exactly the configured basemaps.
      await page.click('.map-layercontrol button, .map-layercontrol').catch(() => {});
      await page.waitForTimeout(800);
      const radios = await page.locator('input[type=radio]').count();
      check(`basemap switcher offers ${BASEMAP_COUNT}`, radios === BASEMAP_COUNT, `${radios} options`);
    }
    await page.screenshot({ path: `${OUT}/03-collection.png` });
  }
}

// ---------- 7. Console ----------
const realErrors = consoleErrors.filter(e =>
  !/favicon|ResizeObserver/i.test(e)
  && (catalogLive || !/catalog\.json|Failed to fetch|NetworkError|ERR_|404/i.test(e)));
check('no console errors', realErrors.length === 0, realErrors.slice(0, 3).join(' ;; ') || 'clean');

await browser.close();

const failed = results.filter(r => !r.pass);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`
  + `${catalogLive ? '' : ' (catalog offline, data checks skipped)'}`);
if (failed.length) {
  console.log('FAILED:', failed.map(f => f.name).join(', '));
  process.exit(1);
}
