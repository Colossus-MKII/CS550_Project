// Optional local browser QA. Requires an existing server and a separately supplied Playwright runtime.
// node check_tutorial.cjs URL PLAYWRIGHT_MODULE CHROME_EXECUTABLE SCREENSHOT_DIRECTORY [LOCAL_INDEX]
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const [url, modulePath, browserPath, artifacts, localIndex] = process.argv.slice(2);
if (!url || !modulePath || !browserPath || !artifacts) throw new Error('Pass URL, Playwright module, browser executable and screenshot directory.');
const { chromium } = require(modulePath);
async function switchLanguage(page) {
  // Click the visible sticky-header link as a reader would. Locator auto-scroll
  // can move the document underneath a sticky element before clicking it.
  const bounds = await page.locator('#language-toggle').boundingBox();
  assert(bounds && bounds.y >= 0 && bounds.height > 0);
  const target = new URL(await page.locator('#language-toggle').getAttribute('href'), page.url()).pathname;
  await Promise.all([
    page.waitForURL(url => url.pathname === target, { timeout: 15000 }),
    page.mouse.click(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2)
  ]);
}

(async () => {
  fs.mkdirSync(artifacts, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: browserPath });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [], external = [], badResponses = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if (/^https?:/.test(request.url()) && new URL(request.url()).origin !== new URL(url).origin) external.push(request.url()); });
    page.on('response', response => { if (response.status() >= 400) badResponses.push([response.status(), response.url()]); });
    const response = await page.goto(url, { waitUntil: 'networkidle' });
    assert.equal(response.status(), 200);
    const icons = await page.locator('link[rel="icon"]').evaluateAll(links => links.map(link => link.href));
    assert.equal(icons.length, 3);
    for (const icon of icons) {
      assert.equal(new URL(icon).origin, new URL(url).origin);
      const result = await page.request.get(icon);
      assert.equal(result.status(), 200);
      assert.match(result.headers()['content-type'], /^image\/(svg\+xml|png|x-icon)$/);
    }
    assert.equal(await page.locator('[data-complete]').count(), 7);
    assert.equal(await page.locator('#experiment-quick-link').getAttribute('href'), 'experiments.html');
    assert.equal(await page.locator('#workspace-switcher a[href="index.html"]').isVisible(), true);
    assert.equal(await page.locator('#start-learning-link').evaluate(link => {
      const box = link.getBoundingClientRect();
      return box.top >= 0 && box.bottom <= innerHeight;
    }), true);
    assert.equal(await page.locator('video').count(), 5);
    assert.equal(await page.locator('#iou-score').textContent(), '0.667');
    assert.equal(await page.locator('#source-frame').evaluate(image => image.complete && image.naturalWidth > 0), true);
    const duplicateIds = await page.evaluate(() => {
      const ids = [...document.querySelectorAll('[id]')].map(node => node.id);
      return ids.filter((id, i) => ids.indexOf(id) !== i);
    });
    assert.deepEqual(duplicateIds, []);
    await page.screenshot({ path: path.join(artifacts, 'desktop-dark.png') });

    // Proposal text is embedded, searchable and bilingual; PDFs stay local.
    assert.equal(await page.locator('#project-conditions tbody tr').count(), 2);
    assert.equal(await page.locator('#recovery-conditions tbody tr').count(), 4);
    assert.match(await page.locator('#chapter-7').innerText(), /最多选择一项/);
    assert.match(await page.locator('#chapter-5').innerText(), /不在最新版项目范围内/);
    await page.locator('#proposal').evaluate(element => element.scrollIntoView({ behavior: 'instant' }));
    assert.match(await page.locator('#proposal-content').innerText(), /多目标分割与跟踪：历史状态对错误恢复的影响/);
    assert.equal(await page.locator('#proposal-content h4').count(), 7);
    await page.screenshot({ path: path.join(artifacts, 'proposal-zh.png') });
    await switchLanguage(page);
    await page.waitForLoadState('networkidle');
    assert.equal(new URL(page.url()).hash, '#proposal');
    assert.match(await page.locator('#proposal-content').innerText(), /Multi-Object Segmentation and Tracking: The Role of Historical State in Error Recovery/);
    assert.equal(await page.locator('#proposal-content h4').count(), 7);
    await page.screenshot({ path: path.join(artifacts, 'proposal-en.png') });
    await page.locator('#proposal-latex summary').click();
    assert.match(await page.locator('#proposal-latex').innerText(), /not the original archive bytes/);
    await page.locator('#proposal-latex').screenshot({ path: path.join(artifacts, 'latex-downloads-en.png') });
    for (const [selector, filename] of [
      ['#latex-download', 'proposal-latex.zip'],
      ['#template-download', 'neurips-2026-template-files.zip'],
      ['#tex-download', 'proposal.tex'],
      ['#short-latex-download', 'proposal-short-latex.zip'],
      ['#short-tex-download', 'proposal_short.tex'],
      ['#short-source-download', 'proposal_short.md.txt'],
    ]) {
      const waiting = page.waitForEvent('download');
      await page.locator(selector).click();
      const download = await waiting;
      assert.equal(download.suggestedFilename(), filename);
      assert.equal(await download.failure(), null);
      const resource = await page.request.get(new URL('proposal/' + filename, url).href);
      assert.equal(resource.status(), 200);
      if (!filename.endsWith('.txt')) assert.equal(resource.headers()['content-disposition'], 'attachment');
    }
    for (const name of ['proposal.pdf', 'proposal_zh.pdf', 'proposal_short.pdf', 'proposal_short_zh.pdf']) {
      const pdf = await page.request.get(new URL('proposal/' + name, url).href);
      assert.equal(pdf.status(), 200);
      assert.equal(pdf.headers()['content-type'], 'application/pdf');
      assert.equal((await pdf.body()).subarray(0, 4).toString(), '%PDF');
    }
    assert.match(await page.locator('#proposal-short').innerText(), /Up to three body pages, with natural continuous layout/);
    assert.match(await page.locator('#proposal-latex').innerText(), /5 body pages plus 1 reference page/);
    await page.setViewportSize({ width: 390, height: 1000 });
    await page.locator('#proposal-latex').evaluate(element => element.scrollIntoView({ behavior: 'instant' }));
    await page.evaluate(() => document.activeElement.blur());
    await page.screenshot({ path: path.join(artifacts, 'latex-downloads-mobile-en.png') });
    await page.locator('#proposal').evaluate(element => element.scrollIntoView({ behavior: 'instant' }));
    await page.screenshot({ path: path.join(artifacts, 'proposal-mobile-en.png') });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.locator('#proposal').evaluate(element => element.scrollIntoView({ behavior: 'instant' }));
    await switchLanguage(page);
    await page.waitForLoadState('networkidle');
    assert.equal(new URL(page.url()).hash, '#proposal');

    for (const [offset, expected] of [[0, '1.000'], [50, '0.333'], [100, '0.000'], [20, '0.667']]) {
      await page.locator('#iou-offset').evaluate((input, value) => { input.value = String(value); input.dispatchEvent(new Event('input')); }, offset);
      assert.equal(await page.locator('#iou-score').textContent(), expected);
    }
    for (const [scenario, expected] of [
      ['stable', ['100.0%', '100.0%', '100.0%', '100.0%']],
      ['split', ['50.0%', '100.0%', '50.0%', '70.7%']],
      ['miss', ['66.7%', '50.0%', '50.0%', '50.0%']]
    ]) {
      await page.locator('#identity-scenario').selectOption(scenario);
      for (const [i, metric] of ['idf1', 'deta', 'assa', 'hota'].entries()) assert.equal(await page.locator('#metric-' + metric).textContent(), expected[i]);
    }
    await page.locator('#identity-scenario').selectOption('split');
    await page.locator('#identity-lab').screenshot({ path: path.join(artifacts, 'identity-lab.png') });

    await page.locator('#frame-presets button').filter({ hasText: /^帧 106$/ }).click();
    assert.equal(await page.locator('#frame-value').textContent(), '106');
    const rows = await page.locator('#frame-records').innerText();
    assert.match(rows, /ByteTrack\s+dog\s+6/);
    assert.match(rows, /SAM 2.1\s+dog（提示标签）\s+2/);
    await page.locator('#seek-videos').click();
    await page.waitForFunction(() => [...document.querySelectorAll('video')].every(video => !video.seeking && video.readyState >= 2));
    const states = await page.locator('video').evaluateAll(videos => videos.map(video => ({ time: video.currentTime, paused: video.paused, error: video.error && video.error.message })));
    for (const state of states) { assert(state.paused); assert.equal(state.error, null); assert(Math.abs(state.time - 106 / 29.97002997002997) < 0.04); }
    await page.locator('[data-video="video-comparison"][data-step="1"]').click();
    await page.waitForFunction(() => !document.getElementById('video-comparison').seeking);
    assert(Math.abs(await page.locator('#video-comparison').evaluate(video => video.currentTime) - 107 / 29.97002997002997) < 0.04);
    await page.locator('[data-speed="video-comparison"]').selectOption('0.5');
    assert.equal(await page.locator('#video-comparison').evaluate(video => video.playbackRate), 0.5);

    await page.locator('[data-complete="chapter-6"]').click();
    assert.equal(await page.locator('#progress-label').textContent(), '已读 1 / 7 章');
    await page.locator('#theme-toggle').click();
    assert.equal(await page.locator('html').getAttribute('data-theme'), 'light');
    await page.reload({ waitUntil: 'networkidle' });
    assert.equal(await page.locator('#progress-label').textContent(), '已读 1 / 7 章');
    assert.equal(await page.locator('html').getAttribute('data-theme'), 'light');
    await page.locator('#search-input').fill('ultralytics');
    await page.locator('#search-form button').click();
    assert.match(await page.locator('#search-status').textContent(), /找到/);
    assert.equal(await page.locator('#ultralytics').evaluate(details => details.open), true);

    const localLinks = await page.locator('a[href]').evaluateAll(links => [...new Set(links.map(link => link.getAttribute('href')).filter(href => href && !href.startsWith('#') && !/^https?:/.test(href)))]);
    for (const href of localLinks) { const result = await page.request.get(new URL(href, url).href); assert.equal(result.status(), 200, href); }
    for (const width of [1440, 768, 390, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
      await page.waitForTimeout(150);
      const dimensions = await page.evaluate(() => ({ content: document.documentElement.scrollWidth, viewport: innerWidth }));
      assert(dimensions.content <= dimensions.viewport + 1, 'Horizontal overflow: ' + JSON.stringify(dimensions));
      if (width < 860) {
        await page.locator('#menu-toggle').click();
        assert.equal(await page.locator('#menu-toggle').getAttribute('aria-expanded'), 'true');
        await page.locator('#course-group-2 > summary').click();
        await page.locator('#course-nav a[href="#chapter-6"]').click();
        assert.equal(await page.locator('#menu-toggle').getAttribute('aria-expanded'), 'false');
      }
      await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
      await page.waitForTimeout(150);
      await page.screenshot({ path: path.join(artifacts, 'layout-' + width + '.png') });
    }
    // Language links preserve chapters, progress, theme and experiment/player state.
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.locator('#identity-scenario').selectOption('split');
    await page.locator('#iou-offset').evaluate(input => { input.value = '50'; input.dispatchEvent(new Event('input')); });
    await page.locator('#frame-presets button').filter({ hasText: /^帧 106$/ }).click();
    await page.locator('#seek-videos').click();
    await page.waitForFunction(() => [...document.querySelectorAll('video')].every(video => !video.seeking && video.readyState >= 2));
    await page.locator('[data-speed="video-comparison"]').selectOption('0.5');
    await page.locator('#chapter-6').evaluate(element => element.scrollIntoView({ behavior: 'instant' }));
    await switchLanguage(page);
    await page.waitForLoadState('networkidle');
    assert.equal(new URL(page.url()).hash, '#chapter-6', page.url());
    assert(new URL(page.url()).pathname.endsWith('/handbook.en.html'), page.url());
    assert.equal(await page.locator('html').getAttribute('lang'), 'en');
    assert.equal(await page.locator('html').getAttribute('data-theme'), 'light');
    assert.equal(await page.locator('#progress-label').textContent(), 'Read 1 / 7 chapters');
    assert.equal(await page.locator('#identity-scenario').inputValue(), 'split');
    assert.equal(await page.locator('#metric-hota').textContent(), '70.7%');
    assert.equal(await page.locator('#iou-score').textContent(), '0.333');
    assert.equal(await page.locator('#frame-value').textContent(), '106');
    assert.match(await page.locator('#frame-records').innerText(), /SAM 2.1\s+dog \(prompt label\)\s+2/);
    assert.match(await page.locator('#frame-caption').textContent(), /Source frame 106/);
    assert.equal(await page.locator('#video-comparison').evaluate(video => video.playbackRate), 0.5);
    await page.waitForFunction(() => [...document.querySelectorAll('video')].every(video => !video.seeking && video.readyState >= 2));
    for (const time of await page.locator('video').evaluateAll(videos => videos.map(video => video.currentTime))) assert(Math.abs(time - 106 / 29.97002997002997) < 0.04);
    // No leftover untranslated prose in rendered English (the Chinese switch is intentional).
    const untranslated = await page.evaluate(() => {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      const found = [];
      while (walker.nextNode()) {
        const node = walker.currentNode;
        if (!node.parentElement.closest('script,style,#language-toggle') && /[\u4e00-\u9fff]/.test(node.textContent)) found.push(node.textContent);
      }
      return found;
    });
    assert.deepEqual(untranslated, []);
    await page.locator('#identity-lab').screenshot({ path: path.join(artifacts, 'identity-lab-en.png') });
    for (const width of [1440, 768, 390, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
      await page.waitForTimeout(150);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'English overflow at ' + width);
      const controls = await page.locator('.top-actions').boundingBox();
      const brand = await page.locator('.brand').boundingBox();
      assert(controls.y >= brand.y + brand.height || controls.x >= brand.x + brand.width, 'Header controls overlap the brand');
      if (width < 860) { await page.locator('#menu-toggle').click(); assert.equal(await page.locator('#menu-toggle').getAttribute('aria-expanded'), 'true'); await page.locator('#menu-toggle').click(); }
      await page.screenshot({ path: path.join(artifacts, 'english-layout-' + width + '.png') });
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.locator('#identity-scenario').selectOption('miss');
    assert.equal(await page.locator('#metric-idf1').textContent(), '66.7%');
    await page.bringToFront();
    await page.locator('[data-copy]').first().click();
    await page.waitForFunction(() => /Code copied|Clipboard access/.test(document.getElementById('toast').textContent));
    assert.match(await page.locator('#toast').textContent(), /Code copied|Clipboard access/);
    await page.locator('#search-input').fill('ultralytics');
    await page.locator('#search-form button').click();
    assert.match(await page.locator('#search-status').textContent(), /Found/);
    assert.equal(await page.locator('#ultralytics').evaluate(details => details.open), true);
    await page.locator('#chapter-1').evaluate(element => element.scrollIntoView({ behavior: 'instant' }));
    await switchLanguage(page);
    await page.waitForURL('**/handbook.html#chapter-1');
    await page.waitForLoadState('networkidle');
    assert.equal(await page.locator('html').getAttribute('lang'), 'zh-CN');
    assert.equal(await page.locator('#progress-label').textContent(), '已读 1 / 7 章');
    assert.equal(await page.locator('#identity-scenario').inputValue(), 'miss');
    assert.equal(await page.locator('#iou-score').textContent(), '0.333');
    assert.equal(await page.locator('#frame-value').textContent(), '106');
    assert.match(await page.locator('#frame-caption').textContent(), /原始帧/);
    assert.deepEqual(errors, []);
    assert.deepEqual(external, []);
    assert.deepEqual(badResponses, []);
    if (localIndex) {
      const offline = await browser.newPage({ viewport: { width: 1280, height: 900 } });
      const offlineErrors = [];
      offline.on('pageerror', error => offlineErrors.push(error.message));
      await offline.goto(pathToFileURL(localIndex).href, { waitUntil: 'load' });
      assert.equal(await offline.locator('#iou-score').textContent(), '0.667');
      await offline.locator('#identity-scenario').selectOption('split');
      assert.equal(await offline.locator('#metric-idf1').textContent(), '50.0%');
      await switchLanguage(offline);
      await offline.waitForURL('**/handbook.en.html*');
      assert.equal(await offline.locator('html').getAttribute('lang'), 'en');
      assert.equal(await offline.locator('#metric-idf1').textContent(), '50.0%');
      assert.deepEqual(offlineErrors, []);
      await offline.close();
      const noScript = await browser.newPage({ javaScriptEnabled: false });
      await noScript.goto(pathToFileURL(localIndex).href, { waitUntil: 'load' });
      await switchLanguage(noScript);
      await noScript.waitForURL('**/handbook.en.html');
      assert.equal(await noScript.locator('html').getAttribute('lang'), 'en');
      assert.equal(await noScript.locator('[data-complete]').count(), 7);
      await noScript.close();
    }
    console.log(JSON.stringify({ result: 'PASS', languages: ['zh-CN', 'en'], chapters: 7, videos: 5, tests: ['IoU endpoints', 'IDF1/DetA/AssA/HOTA scenarios', 'real frame-106 IDs', 'synchronized seek', 'frame stepping', 'speed control', 'saved progress and theme', 'FAQ search', 'all local links', '1440/768/390/320 layouts in both languages', 'language round-trip preserves chapter and UI state', 'English prose and dynamic labels', 'file URL language switching', 'no-JavaScript language links', 'no external runtime requests'], screenshotDirectory: artifacts }, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
