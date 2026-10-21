// node check_program.cjs URL PLAYWRIGHT_MODULE CHROME OUTPUT_DIR LOCAL_SITE_DIR
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const [url, modulePath, browserPath, artifacts, localDirectory] = process.argv.slice(2);
const { chromium } = require(modulePath);

(async () => {
  fs.mkdirSync(artifacts, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: browserPath });
  const errors = [], external = [], failed = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (/^https?:/.test(request.url()) && new URL(request.url()).origin !== new URL(url).origin) external.push(request.url());
    });
    page.on('response', response => { if (response.status() >= 400) failed.push([response.status(), response.url()]); });
    for (const suffix of ['', '.en']) {
      await page.goto(new URL(`index${suffix}.html`, url).href);
      assert.equal(await page.locator(`#project-navigation a[href="program${suffix}.html"]`).count(), 1);
      if (await page.locator('#menu-toggle').isVisible()) await page.locator('#menu-toggle').click();
      await page.locator('#project-group-3 > summary').click();
      await page.locator(`#project-navigation a[href="program${suffix}.html"]`).click();
      await page.waitForURL(destination => destination.pathname.endsWith(`program${suffix}.html`));
      assert.equal(await page.locator('[data-program-panel]:visible').count(), 1);
      assert.equal(await page.locator('#stage-data').isVisible(), true);
      for (const step of ['yolo', 'a0', 'b0', 'gt', 'diagnose', 'scores', 'report']) {
        await page.locator(`[data-program-step="${step}"]`).click();
        assert.equal(await page.locator(`#stage-${step}`).isVisible(), true);
        assert.equal(await page.locator('[data-program-panel]:visible').count(), 1);
      }
      await page.locator('#program-show-all').click();
      assert.equal(await page.locator('[data-program-panel]:visible').count(), 8);
      await page.locator('.program-flow a[href="#stage-b0"]').click();
      await page.waitForFunction(() => document.querySelector('[data-program-step="b0"]').getAttribute('aria-pressed') === 'true');
      assert.equal(await page.locator('#stage-b0').isVisible(), true);
      assert.equal(await page.locator('[data-program-panel]:visible').count(), 1);
      assert.equal(await page.locator('#program-pilot-scores tbody tr').count(), 5);
      assert.equal(await page.locator('.program-case').count(), 3);
      assert.equal(await page.locator('#support-details').getAttribute('open'), null);
      const sourceLink = page.locator('#stage-b0 .function-route a').first();
      await sourceLink.click();
      await page.waitForURL(destination => destination.pathname.includes('sam_baseline.py'));
      assert.equal(await page.locator(page.url().slice(page.url().indexOf('#'))).count(), 1);
      await page.goBack();
      for (const width of [1440, 768, 390, 320]) {
        await page.setViewportSize({ width, height: 1000 });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, `overflow at ${width}`);
        if (width === 390) {
          await page.locator('#map').evaluate(node => node.scrollIntoView({ behavior: 'instant' }));
          await page.screenshot({ path: path.join(artifacts, `program${suffix}-mobile.png`) });
        }
      }
      await page.setViewportSize({ width: 1440, height: 1000 });
      await page.goto(new URL(`program${suffix}.html?step=b0#steps`, url).href);
      await page.screenshot({ path: path.join(artifacts, `program${suffix}-desktop.png`) });
    }
    await page.goto(new URL('program.html?step=b0#steps', url).href);
    const theme = await page.locator('html').getAttribute('data-theme');
    await page.locator('#theme-toggle').click();
    const switched = await page.locator('html').getAttribute('data-theme');
    assert.notEqual(theme, switched);
    await Promise.all([page.waitForURL(destination => destination.pathname.endsWith('program.en.html')), page.locator('#language-toggle').click()]);
    assert.equal(new URL(page.url()).searchParams.get('step'), 'b0');
    assert.equal(await page.locator('#stage-b0').isVisible(), true);
    assert.equal(await page.locator('html').getAttribute('data-theme'), switched);
    await page.locator('#program-show-all').click();
    await Promise.all([page.waitForURL(destination => destination.pathname.endsWith('program.html')), page.locator('#language-toggle').click()]);
    assert.equal(await page.locator('[data-program-panel]:visible').count(), 8);
    await page.goto(new URL('program.html?step=invalid#stage-yolo', url).href);
    assert.equal(await page.locator('#stage-yolo').isVisible(), true);
    // Decode and seek one existing video. The page must not require new inference.
    await page.locator('#case-2689 details').nth(1).locator('summary').click();
    const video = page.locator('#case-2689 video');
    await video.evaluate(node => node.load());
    await page.waitForFunction(() => document.querySelector('#case-2689 video').readyState >= 2);
    await video.evaluate(node => { node.currentTime = 2; });
    await page.waitForFunction(() => { const node = document.querySelector('#case-2689 video'); return !node.seeking && node.currentTime >= 1.9; });
    await page.goto(pathToFileURL(path.join(localDirectory, 'program.html')).href);
    await page.locator('[data-program-step="a0"]').click();
    assert.equal(await page.locator('#stage-a0').isVisible(), true);
    const context = await browser.newContext({ javaScriptEnabled: false });
    const offline = await context.newPage();
    for (const name of ['program.html', 'program.en.html']) {
      await offline.goto(pathToFileURL(path.join(localDirectory, name)).href);
      assert.equal(await offline.locator('[data-program-panel]:visible').count(), 8);
      assert.equal(await offline.locator('#program-controls').isVisible(), false);
    }
    await context.close();
    assert.deepEqual(errors, []);
    assert.deepEqual(external, []);
    assert.deepEqual(failed, []);
    console.log(JSON.stringify({ status: 'passed', steps: 8, cases: 3, widths: [1440,768,390,320], moduleSourceAnchors: true, languageAndTheme: true, videoDecodeSeek: true, offlineNoJS: true }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
