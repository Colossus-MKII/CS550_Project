// Run through the connected browser's cua_repl, passing its existing Tab.
// This harness never launches a browser or imports browser-control packages.
export function createReadingQa(tab, fs, directory, base = 'http://127.0.0.1:8765/cs550-tracking-lab/') {
  const routes = new Map();
  const read = () => tab.playwright.evaluate(() => {
    const main = document.querySelector('main');
    const line = Math.max(document.querySelector('.topbar').getBoundingClientRect().bottom + 24,
      Number.parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0);
    const sections = [...main.querySelectorAll(':scope > section[id]')];
    const edge = scrollY <= 2 ? 'top' : scrollY + innerHeight >= document.documentElement.scrollHeight - 2 ? 'bottom' : null;
    const section = edge === 'bottom' ? sections.at(-1) : sections.reduce((a, n) => n.getBoundingClientRect().top <= line ? n : a, sections[0]);
    const blocks = [...main.querySelectorAll('h1,h2,h3,h4,h5,p,li,pre,figure,table,tr,video,.lab,.equation,summary')].filter(n => {
      const r = n.getBoundingClientRect(), closed = n.closest('details:not([open])');
      return r.width > 0 && r.height > 0 && !n.closest('[hidden]') && getComputedStyle(n).visibility !== 'hidden' &&
        (!closed || closed.querySelector(':scope > summary')?.contains(n));
    });
    let block;
    for (const n of blocks) {
      const r = n.getBoundingClientRect();
      if (r.top <= line && r.bottom > line && (!block || block.contains(n))) block = n;
    }
    block = block || blocks.find(n => n.getBoundingClientRect().top > line) || section;
    let root = block;
    const path = [];
    while (root !== main && !root.id) root = root.parentElement;
    for (let n = block; n !== root; n = n.parentElement) {
      path.unshift([n.tagName, [...n.parentElement.children].filter(a => a.tagName === n.tagName).indexOf(n)]);
    }
    const r = block.getBoundingClientRect();
    const active = [...document.querySelectorAll('#course-nav a[aria-current="location"]')];
    const link = active[0], group = link?.closest('.course-group'), sidebar = document.getElementById('sidebar');
    const lr = link?.getBoundingClientRect(), sr = sidebar.getBoundingClientRect();
    const pending = [...main.querySelectorAll('img')].some(n => {
      if (n.closest('details:not([open])') || n.closest('[hidden]')) return false;
      const box = n.getBoundingClientRect();
      return box.width > 0 && box.height > 0 && box.bottom > 0 && box.top < innerHeight && !n.complete;
    });
    return {
      url: location.pathname + location.search + location.hash, lang: document.documentElement.lang,
      y: scrollY, height: document.documentElement.scrollHeight, viewport: [innerWidth, innerHeight],
      line, edge, section: section.id, anchor: { id: root.id, path },
      fraction: Math.max(0, Math.min(1, (line - r.top) / Math.max(1, r.height))),
      gap: Math.max(0, r.top - line), blockTop: r.top, blockHeight: r.height,
      active: active.map(n => n.hash), groupOpen: !group || group.open,
      sidebarVisible: !!sidebar.getClientRects().length,
      linkVisible: !!lr && lr.height > 0 && lr.top >= sr.top && lr.bottom <= sr.bottom,
      overflow: document.documentElement.scrollWidth > innerWidth + 1, pending
    };
  });
  const bad = s => s.active.length !== 1 || s.active[0] !== '#' + s.section || !s.groupOpen ||
    (s.sidebarVisible && !s.linkVisible) || s.overflow;
  async function settle(previousY) {
    let previous = '', since = Date.now(), value;
    const until = Date.now() + 3500;
    while (Date.now() < until) {
      await tab.getScreenshot({ emit: false });
      value = await read();
      const signature = JSON.stringify([value.y, value.height, value.blockTop, value.blockHeight, value.active, value.groupOpen, value.linkVisible, value.pending]);
      if (signature !== previous) { previous = signature; since = Date.now(); }
      if (!value.pending && !bad(value) && Date.now() - since >= 220 && (previousY === undefined || previousY !== value.y || value.edge === 'bottom')) return value;
    }
    return value;
  }
  const error = saved => tab.playwright.evaluate(s => {
    let n = document.getElementById(s.anchor.id);
    for (const [tag, i] of s.anchor.path) n = n && [...n.children].filter(x => x.tagName === tag)[i];
    if (!n) return 100000;
    const r = n.getBoundingClientRect(), max = Math.max(0, document.documentElement.scrollHeight - innerHeight);
    const line = Math.max(document.querySelector('.topbar').getBoundingClientRect().bottom + 24,
      Number.parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0);
    const desired = s.edge === 'top' ? 0 : s.edge === 'bottom' ? max : Math.max(0, Math.min(max, scrollY + r.top + r.height * s.fraction - s.gap - line));
    return Math.abs(scrollY - desired);
  }, saved);
  async function check(label, bucket = 'desktop-final') {
    await settle();
    await tab.getScreenshot({ emit: false });
    const before = await read(), checks = [];
    for (let i = 0; i < 2; i++) {
      if (i) await tab.getScreenshot({ emit: false });
      const point = await tab.playwright.locator('#language-toggle').evaluate(n => {
        const r = n.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2];
      });
      await tab.playwright.expectNavigation(() => tab.click(point), { waitUntil: 'load' });
      await tab.playwright.domSnapshot();
      await settle();
      checks.push({ after: await read(), errorPx: await error(before) });
    }
    const row = { label, bucket, before, checks, pass: !bad(before) && checks.every(c => c.errorPx <= 1.1 && !bad(c.after)) };
    await fs.appendFile(directory + '/checks.jsonl', JSON.stringify(row) + '\n');
    return { label, pass: row.pass, maxError: Math.max(...checks.map(c => c.errorPx)), ...(!row.pass ? { before, checks } : {}) };
  }
  async function visit(slug, start = 0, end = 5, bucket) {
    if (!routes.has(slug)) {
      await tab.goto(base + slug + '.html');
      await tab.playwright.domSnapshot();
      const hashes = await tab.playwright.locator('#course-nav a').evaluateAll(nodes => nodes.map(n => n.hash).filter(Boolean));
      routes.set(slug, ['', ...hashes]);
    }
    const result = [];
    for (const hash of routes.get(slug).slice(start, end)) {
      await tab.goto(base + slug + '.html' + hash);
      await tab.playwright.waitForLoadState({ state: 'load' });
      await tab.playwright.domSnapshot();
      result.push(await check(slug + ':' + (hash || 'top'), bucket));
    }
    return { slug, total: routes.get(slug).length, result };
  }
  async function tap(selector) {
    await tab.getScreenshot({ emit: false });
    const point = await tab.playwright.locator(selector).evaluate(n => {
      const r = n.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2];
    });
    await tab.click(point);
    await tab.playwright.domSnapshot();
  }
  async function mobile(slug, hash) {
    const top = await visit(slug, 0, 1, 'mobile-final');
    await tab.goto(base + slug + '.html' + hash);
    await tab.playwright.domSnapshot();
    const initial = await settle();
    if (initial.edge !== 'bottom') {
      await tab.scroll([320, 650], 'down', 0.18);
      await settle(initial.y);
    }
    const reading = await check(slug + ':mobile-reading', 'mobile-final');
    await tap('#menu-toggle');
    await settle();
    const nav = await read();
    const record = { slug, pass: !bad(nav) && nav.sidebarVisible && nav.linkVisible, nav };
    await fs.appendFile(directory + '/mobile-navigation.jsonl', JSON.stringify(record) + '\n');
    await tap('#menu-toggle');
    return { slug, top: top.result[0], reading, navigation: record.pass };
  }
  return { read, settle, check, visit, mobile, tap, base };
}
