const { readFile, writeFile } = require('node:fs/promises');
const { chromium } = require('playwright');

function validateSpec({ viewport, frame, tolerance = 1, targets }) {
  if (!viewport || !['width', 'height'].every((axis) =>
    Number.isInteger(viewport[axis]) && viewport[axis] > 0)) {
    throw new Error('viewport requires positive integer width and height');
  }
  if (typeof frame !== 'string' || !frame.trim() || !Number.isFinite(tolerance) || tolerance < 0) {
    throw new Error('frame must be a CSS selector and tolerance must be nonnegative');
  }
  if (!Array.isArray(targets) || targets.length === 0) {
    throw new Error('targets must be a nonempty list');
  }
  for (const { selector, bounds } of targets) {
    if (typeof selector !== 'string' || !selector.trim() || !bounds || !Object.keys(bounds).length ||
      !Object.entries(bounds).every(([axis, value]) =>
        ['x', 'y', 'width', 'height'].includes(axis) && Number.isFinite(value))) {
      throw new Error('Each target requires a CSS selector and finite x, y, width or height');
    }
  }
}

async function box(locator) {
  await locator.waitFor({ state: 'visible' });
  const bounds = await locator.boundingBox();
  if (!bounds) throw new Error('Visible target has no bounding box');
  return bounds;
}

async function compare(url, spec, screenshot) {
  validateSpec(spec);
  const { viewport, frame, tolerance = 1, targets } = spec;
  const browser = await chromium.launch({ executablePath: process.env.TALON_CHROMIUM_EXECUTABLE });
  try {
    const page = await browser.newPage({ viewport, deviceScaleFactor: 1, reducedMotion: 'reduce' });
    page.setDefaultTimeout(10000);
    const response = await page.goto(url, { waitUntil: 'load', timeout: 20000 });
    if (response && !response.ok()) throw new Error(`Page returned HTTP ${response.status()}`);
    await page.evaluate(() => document.fonts.ready);
    const root = page.locator(frame);
    await root.scrollIntoViewIfNeeded();
    const capture = await root.screenshot({ animations: 'disabled', scale: 'css' });
    await writeFile(screenshot, capture, { flag: 'wx' });

    const origin = await box(root);
    const measurements = [];
    for (const { selector, bounds } of targets) {
      const actual = await box(root.locator(selector));
      actual.x -= origin.x;
      actual.y -= origin.y;
      for (const [axis, expected] of Object.entries(bounds)) {
        const delta = actual[axis] - expected;
        measurements.push({ selector, axis, expected, actual: actual[axis], delta });
      }
    }
    const mismatch = measurements.some(({ delta }) => Math.abs(delta) > tolerance);
    return { result: mismatch ? 'MISMATCH' : 'PASS', screenshot, tolerance, measurements };
  } finally {
    await browser.close();
  }
}

async function main() {
  const [url, specPath, screenshot] = process.argv.slice(2);
  if (!url || !specPath || !screenshot || process.argv.length !== 5) {
    throw new Error('Usage: node compare-layout.cjs URL SPEC_JSON SCREENSHOT_PNG');
  }
  const report = await compare(url, JSON.parse(await readFile(specPath, 'utf8')), screenshot);
  console.log(JSON.stringify(report, null, 2));
  if (report.result === 'MISMATCH') process.exitCode = 1;
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 2;
});
