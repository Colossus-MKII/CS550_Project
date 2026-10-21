// node check_experiments.cjs URL PLAYWRIGHT_MODULE CHROME_EXECUTABLE ARTIFACT_DIRECTORY LOCAL_DIRECTORY
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const [url, modulePath, browserPath, artifacts, localDirectory] = process.argv.slice(2);
const { chromium } = require(modulePath);

(async () => {
  fs.mkdirSync(artifacts, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: browserPath });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [], external = [], failed = [];
    page.on('pageerror', err => errors.push(err.message));
    page.on('request', request => { if (/^https?:/.test(request.url()) && new URL(request.url()).origin !== new URL(url).origin) external.push(request.url()); });
    page.on('response', response => { if (response.status() >= 400) failed.push([response.status(), response.url()]); });
    for (const name of ['experiments.html', 'experiments.en.html']) {
      await page.goto(new URL(name, url).href, { waitUntil: 'networkidle' });
      assert.equal(await page.locator('#recovery-groups tbody tr').count(), 4);
      assert.equal(await page.locator('[data-event-panel]:visible').count(), 1);
      assert.equal(await page.locator('#event-prev').isDisabled(), true);
      await page.locator('#logic').evaluate(node => node.scrollIntoView({ behavior: 'instant' }));
      await page.screenshot({ path: path.join(artifacts, name.replace('.html', '-flow.png')) });
      for (let step = 0; step < 5; step++) {
        await page.locator(`[data-event-step="${step}"]`).click();
        assert.equal(await page.locator(`#event-panel-${step}`).isVisible(), true);
        assert.equal(await page.locator('[data-event-panel]:visible').count(), 1);
        assert.equal(await page.locator('[aria-current="step"]').getAttribute('data-event-step'), String(step));
        assert.equal(await page.locator('#event-progress').textContent(), `${step + 1} / 5`);
        if (step === 2) {
          await page.locator('#event-panel-2').evaluate(node => node.scrollIntoView({ behavior: 'instant' }));
          await page.screenshot({ path: path.join(artifacts, name.replace('.html', '-four-branches.png')) });
        }
      }
      assert.equal(await page.locator('#event-next').isDisabled(), true);
      await page.locator('#event-prev').click();
      assert.equal(await page.locator('#event-panel-3').isVisible(), true);
      await page.locator('#event-next').focus();
      await page.keyboard.press('Enter');
      assert.equal(await page.locator('#event-panel-4').isVisible(), true);
      for (const width of [1440, 768, 390, 320]) {
        await page.setViewportSize({ width, height: 1000 });
        await page.locator('[data-event-step="2"]').click();
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, `${name} at ${width}`);
        if (width === 390) {
          await page.locator('#walkthrough').evaluate(node => node.scrollIntoView({ behavior: 'instant' }));
          await page.screenshot({ path: path.join(artifacts, name.replace('.html', '-mobile.png')) });
        }
      }
      await page.setViewportSize({ width: 1440, height: 1000 });
    }
    // Selected step survives a language switch, even though no measurements exist.
    await page.goto(new URL('experiments.html?step=4#walkthrough', url).href);
    assert.equal(await page.locator('#event-panel-3').isVisible(), true);
    const bounds = await page.locator('#language-toggle').boundingBox();
    await Promise.all([
      page.waitForURL(destination => destination.pathname.endsWith('experiments.en.html') && destination.searchParams.get('step') === '4'),
      page.mouse.click(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2)
    ]);
    assert.equal(await page.locator('#event-panel-3').isVisible(), true);
    assert.equal(new URL(page.url()).hash, '#walkthrough');
    const oldTheme = await page.locator('html').getAttribute('data-theme');
    await page.locator('#theme-toggle').click();
    assert.notEqual(await page.locator('html').getAttribute('data-theme'), oldTheme);
    await page.goto(new URL('experiments.en.html?step=999', url).href);
    assert.equal(await page.locator('#event-panel-0').isVisible(), true);
    // No-JS direct files retain the complete five-step protocol, not an empty widget.
    const noJs = await browser.newContext({ javaScriptEnabled: false });
    const offline = await noJs.newPage();
    for (const name of ['experiments.html', 'experiments.en.html']) {
      await offline.goto(pathToFileURL(path.join(localDirectory, name)).href);
      assert.equal(await offline.locator('[data-event-panel]:visible').count(), 5);
      assert.equal(await offline.locator('#event-controls').isVisible(), false);
    }
    await noJs.close();
    await page.goto(pathToFileURL(path.join(localDirectory, 'experiments.html')).href);
    await page.locator('[data-event-step="2"]').click();
    assert.equal(await page.locator('#event-panel-2').isVisible(), true);
    assert.deepEqual(errors, []); assert.deepEqual(external, []); assert.deepEqual(failed, []);
    console.log(JSON.stringify({ status: 'passed', groups: 4, steps: 5, responsiveWidths: [1440, 768, 390, 320], languagePreservesStep: true, noJavaScriptOffline: true, noInventedScores: true, pageErrors: errors, externalRequests: external }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
