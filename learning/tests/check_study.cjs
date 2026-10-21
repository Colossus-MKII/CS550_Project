// node check_study.cjs URL PLAYWRIGHT_MODULE CHROME_EXECUTABLE ARTIFACT_DIRECTORY LOCAL_DIRECTORY
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
    await page.goto(url, { waitUntil: 'networkidle' });
    assert.equal(await page.locator('.nav-group').count(), 4);
    assert.equal(await page.locator('#model-roles tbody tr').count(), 3);
    assert.equal(await page.locator('#learning-route li').count(), 3);
    await page.screenshot({ path: path.join(artifacts, 'reading-route-zh.png') });
    await page.locator('#learning-route a[href="math.html"]').click();
    await page.waitForLoadState('networkidle');
    assert.match(await page.locator('h1').innerText(), /数学与实现/);
    assert(await page.locator('math').count() >= 30);
    assert.equal(await page.locator('math').evaluateAll(nodes => nodes.every(node => node.namespaceURI === 'http://www.w3.org/1998/Math/MathML' && node.getBoundingClientRect().height > 10)), true);
    await page.locator('#kalman').evaluate(node => node.scrollIntoView({ behavior: 'instant' }));
    await page.screenshot({ path: path.join(artifacts, 'kalman-zh.png') });
    // Use the sticky-header link without locator auto-scroll changing the active section.
    let bounds = await page.locator('#language-toggle').boundingBox();
    await Promise.all([page.waitForURL('**/math.en.html#kalman'), page.mouse.click(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2)]);
    assert.match(await page.locator('#kalman').innerText(), /Kalman state/);
    const oldTheme = await page.locator('html').getAttribute('data-theme');
    await page.locator('#theme-toggle').click();
    assert.notEqual(await page.locator('html').getAttribute('data-theme'), oldTheme);
    await page.locator('#sam').evaluate(node => node.scrollIntoView({ behavior: 'instant' }));
    await page.screenshot({ path: path.join(artifacts, 'sam-en.png') });
    for (const name of ['math.html', 'math.en.html', 'research.html', 'research.en.html', 'experiments.html', 'experiments.en.html']) {
      const target = new URL(name, url).href;
      await page.goto(target, { waitUntil: 'networkidle' });
      const ids = await page.locator('[id]').evaluateAll(nodes => nodes.map(node => node.id));
      assert.equal(ids.length, new Set(ids).size);
      const links = await page.locator('a').evaluateAll(nodes => [...new Set(nodes.map(node => node.href))]);
      for (const href of links.filter(href => new URL(href).origin === new URL(url).origin)) {
        assert.equal((await page.request.get(href)).status(), 200, href);
      }
      for (const width of [1440, 768, 390, 320]) {
        await page.setViewportSize({ width, height: 950 });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, `${name} at ${width}`);
        if (width === 390) {
          await page.locator('#menu-toggle').click();
          assert.equal(await page.locator('#menu-toggle').getAttribute('aria-expanded'), 'true');
          await page.locator('#course-nav a').nth(2).click();
          assert.equal(await page.locator('#menu-toggle').getAttribute('aria-expanded'), 'false');
        }
      }
      await page.setViewportSize({ width: 390, height: 1000 });
      const focus = name.startsWith('math') ? '#memory' : name.startsWith('experiments') ? '#walkthrough' : '#inspiration';
      await page.locator(focus).evaluate(node => node.scrollIntoView({ behavior: 'instant' }));
      await page.screenshot({ path: path.join(artifacts, name.replace('.html', '-mobile.png')) });
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(new URL('research.html#map', url).href, { waitUntil: 'networkidle' });
    await page.screenshot({ path: path.join(artifacts, 'history-zh.png') });
    const noJs = await browser.newContext({ javaScriptEnabled: false });
    const offline = await noJs.newPage();
    for (const name of ['math.html', 'math.en.html', 'research.html', 'research.en.html', 'experiments.html', 'experiments.en.html']) {
      await offline.goto(pathToFileURL(path.join(localDirectory, name)).href);
      assert.equal(await offline.locator('h1').isVisible(), true);
      if (name.startsWith('math')) assert(await offline.locator('math').count() >= 30);
      if (name.startsWith('experiments')) assert.equal(await offline.locator('[data-event-panel]:visible').count(), 5);
    }
    await noJs.close();
    assert.deepEqual(errors, []); assert.deepEqual(external, []); assert.deepEqual(failed, []);
    console.log(JSON.stringify({ status: 'passed', bilingualReferences: 6, responsiveWidths: [1440, 768, 390, 320], nativeMathML: true, noJavaScriptOffline: true, pageErrors: errors, externalRequests: external, failedResponses: failed }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
