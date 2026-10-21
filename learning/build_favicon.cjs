// Raster fallbacks generated from the SVG, using the existing local browser runtime.
// node learning/build_favicon.cjs PLAYWRIGHT_MODULE CHROME_EXECUTABLE
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const [modulePath, executablePath] = process.argv.slice(2);
if (!modulePath || !executablePath) throw new Error('Pass the existing Playwright module and Chrome executable.');
const { chromium } = require(modulePath);
const web = path.join(__dirname, 'web');
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath });
  try {
    const page = await browser.newPage({ deviceScaleFactor: 1 });
    await page.goto(pathToFileURL(path.join(web, 'favicon.svg')).href);
    const frames = [];
    for (const size of [16, 32, 48, 128]) {
      await page.setViewportSize({ width: size, height: size });
      await page.locator('svg').evaluate((svg, size) => {
        svg.setAttribute('width', size);
        svg.setAttribute('height', size);
      }, String(size));
      const png = await page.screenshot({ omitBackground: true });
      if (size === 32) fs.writeFileSync(path.join(web, 'favicon-32.png'), png);
      if (size === 128) fs.writeFileSync(path.join(web, 'favicon-preview.png'), png);
      else frames.push({ size, png });
    }
    // ICO directory followed by PNG-encoded 16/32/48-pixel images.
    const directory = Buffer.alloc(6 + 16 * frames.length);
    directory.writeUInt16LE(1, 2);
    directory.writeUInt16LE(frames.length, 4);
    let offset = directory.length;
    frames.forEach(({ size, png }, index) => {
      const entry = 6 + 16 * index;
      directory[entry] = directory[entry + 1] = size;
      directory.writeUInt16LE(1, entry + 4);
      directory.writeUInt16LE(32, entry + 6);
      directory.writeUInt32LE(png.length, entry + 8);
      directory.writeUInt32LE(offset, entry + 12);
      offset += png.length;
    });
    fs.writeFileSync(path.join(web, 'favicon.ico'), Buffer.concat([directory, ...frames.map(frame => frame.png)]));
    console.log('Generated PNG and ICO fallbacks from favicon.svg.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
