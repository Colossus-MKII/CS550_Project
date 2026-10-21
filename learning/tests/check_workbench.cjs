// node check_workbench.cjs URL PLAYWRIGHT_MODULE CHROME OUTPUT_DIR LOCAL_SITE_DIR
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const [url, modulePath, browserPath, artifacts, localDirectory] = process.argv.slice(2);
const { chromium } = require(modulePath);

async function switchLanguage(page) {
  const link = page.locator('#language-toggle');
  const destination = new URL(await link.getAttribute('href'), page.url()).pathname;
  const box = await link.boundingBox();
  await Promise.all([
    page.waitForURL(target => target.pathname === destination),
    page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
  ]);
  await page.waitForLoadState('load');
}

(async () => {
  fs.mkdirSync(artifacts, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: browserPath });
  const errors = [], external = [], failed = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if (/^https?:/.test(request.url()) && new URL(request.url()).origin !== new URL(url).origin) external.push(request.url()); });
    page.on('response', response => { if (response.status() >= 400) failed.push([response.status(), response.url()]); });
    for (const suffix of ['', '.en']) {
      await page.goto(new URL(`index${suffix}.html`, url).href, { waitUntil: 'networkidle' });
      assert.equal(await page.locator('#project-navigation a').count(), 8);
      assert.equal(await page.locator('#project-navigation [aria-current="page"]').getAttribute('href'), `index${suffix}.html`);
      assert.equal(await page.locator('#course-progress').count(), 0);
      assert.equal(await page.locator('video').count(), 0);
      assert.equal(await page.locator('#project-score-table tbody tr').count(), 2);
      assert.equal(await page.locator('.evidence-card').count(), 3);
      assert.equal(await page.locator('#next .pending').count(), 5);
      assert.equal(await page.locator('.project-pathways li').count(), 4);
      assert.equal(await page.locator('#learning-entry-link').isVisible(), true);
      assert.equal(await page.locator('#learning-entry-link').getAttribute('href'), `handbook${suffix}.html`);
      assert.equal(await page.locator('.project-pathways .pathway-links').count(), 4);
      await page.screenshot({ path: path.join(artifacts, `overview${suffix}-desktop.png`) });
      // A language switch preserves the viewport, even when the next chapter
      // occupies more screen area than the introduction.
      await page.setViewportSize({ width: 1440, height: 1500 });
      for (let round = 0; round < 2; round++) {
        await switchLanguage(page);
        await page.waitForFunction(() => scrollY <= 1);
      }
      await page.setViewportSize({ width: 1440, height: 1000 });
      const selector = '#pathways .project-pathways li:nth-child(3)';
      await page.locator(selector).evaluate(item => {
        const box = item.getBoundingClientRect();
        const line = document.querySelector('.topbar').getBoundingClientRect().bottom + 24;
        window.scrollTo({ top: scrollY + box.top + box.height / 2 - line, behavior: 'instant' });
      });
      for (let round = 0; round < 2; round++) {
        await switchLanguage(page);
        await page.waitForFunction(selector => {
          const box = document.querySelector(selector).getBoundingClientRect();
          const line = document.querySelector('.topbar').getBoundingClientRect().bottom + 24;
          return Math.abs((line - box.top) / box.height - 0.5) < 0.02;
        }, selector);
      }
      await page.goto(new URL(`index${suffix}.html`, url).href);
      await page.locator('#learning-entry-link').click();
      await page.waitForURL(destination => destination.pathname.endsWith(`handbook${suffix}.html`));
      assert.equal(await page.locator('[data-complete]').count(), 7);
      await page.goto(new URL(`index${suffix}.html`, url).href);
      const latestHref = await page.locator('#latest-results-link').getAttribute('href');
      await page.locator('#latest-results-link').click();
      await page.waitForURL(destination => destination.pathname.endsWith(latestHref));
      if (latestHref === `recovery-long${suffix}.html`) {
        assert.equal(await page.locator('video').count(), 8);
        assert.equal(await page.locator('#long-normal-rider-yolo-scores tbody tr').count(), 6);
        await page.locator(`main .long-route a[href="results${suffix}.html"]`).click();
        await page.waitForURL(destination => destination.pathname.endsWith(`results${suffix}.html`));
      }
      assert.equal(await page.locator('#viewer-controls').isVisible(), true);
      await page.locator('#project-group-1 > summary').click();
      await page.locator(`#project-navigation a[href="runs${suffix}.html"]`).click();
      await page.waitForURL(destination => destination.pathname.endsWith(`runs${suffix}.html`));
      assert.equal(await page.locator('#run-record-table').count(), 1);
      assert.equal(await page.locator('#pending .pending').count(), 5);
      await page.locator('#project-group-3 > summary').click();
      await page.locator(`#project-navigation a[href="documents${suffix}.html"]`).click();
      await page.waitForURL(destination => destination.pathname.endsWith(`documents${suffix}.html`));
      assert.equal(await page.locator('#project-proposal-downloads tbody tr').count(), 4);
      await page.locator(`#workspace-switcher a[href="handbook${suffix}.html"]`).click();
      await page.waitForURL(destination => destination.pathname.endsWith(`handbook${suffix}.html`));
      assert.equal(await page.locator('[data-complete]').count(), 7);
      for (const name of [`index${suffix}.html`, `runs${suffix}.html`, `documents${suffix}.html`, `results${suffix}.html`, `program${suffix}.html`, `handbook${suffix}.html`]) {
        await page.goto(new URL(name, url).href, { waitUntil: 'networkidle' });
        assert.equal(await page.locator('#project-navigation').count(), 1);
        const ids = await page.locator('[id]').evaluateAll(nodes => nodes.map(node => node.id));
        assert.equal(ids.length, new Set(ids).size);
        for (const width of [1440,768,390,320]) {
          await page.setViewportSize({ width, height: 1000 });
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, `${name} overflow at ${width}`);
          if (width === 390 && name.startsWith('index')) await page.screenshot({ path: path.join(artifacts, `overview${suffix}-mobile.png`) });
        }
        await page.setViewportSize({ width: 1440, height: 1000 });
      }
    }
    // Legacy teaching bookmarks still work, but the default URL is the workbench.
    await page.goto(new URL('index.html?source=bookmark#chapter-3', url).href);
    await page.waitForURL('**/handbook.html?source=bookmark#chapter-3');
    await page.goto(new URL('index.en.html#ultralytics', url).href);
    await page.waitForURL('**/handbook.en.html#ultralytics');
    await page.goto(new URL('index.html#next', url).href);
    assert.equal(new URL(page.url()).pathname.endsWith('/index.html'), true);
    const oldTheme = await page.locator('html').getAttribute('data-theme');
    await page.locator('#theme-toggle').click();
    const theme = await page.locator('html').getAttribute('data-theme');
    assert.notEqual(theme, oldTheme);
    await page.locator('#next').evaluate(node => node.scrollIntoView({ behavior: 'instant' }));
    const bounds = await page.locator('#language-toggle').boundingBox();
    await Promise.all([page.waitForURL('**/index.en.html#next'), page.mouse.click(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2)]);
    assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
    await page.setViewportSize({ width:390, height:900 });
    await page.goto(new URL('index.html',url).href);
    await page.locator('#menu-toggle').click();
    await page.locator('#project-navigation a[href="runs.html"]').click();
    await page.waitForURL('**/runs.html');
    // No-JS readers retain evidence, documents and handbook links.
    const context = await browser.newContext({ javaScriptEnabled:false });
    const offline = await context.newPage();
    for (const name of ['index.html','index.en.html','runs.html','documents.en.html']) {
      await offline.goto(pathToFileURL(path.join(localDirectory,name)).href);
      assert.equal(await offline.locator('#project-navigation').count(),1);
      assert.equal(await offline.locator('h1').count()>=1,true);
    }
    await context.close();
    await page.goto(pathToFileURL(path.join(localDirectory,'index.html')).href);
    await page.locator('#handbook-link').click();
    await page.waitForURL('**/handbook.html');
    assert.deepEqual(errors,[]); assert.deepEqual(external,[]); assert.deepEqual(failed,[]);
    console.log(JSON.stringify({ status:'passed', experimentFirst:true, sharedNavigation:8, legacyBookmarks:true, responsive:[1440,768,390,320], bilingualTheme:true, offline:true, noPageErrors:true }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
