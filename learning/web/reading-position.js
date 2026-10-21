(() => {
  'use strict';
  const main = document.querySelector('main');
  const toggle = document.getElementById('language-toggle');
  if (!main || !toggle) return;
  const family = location.pathname.replace(/\.en(?=\.html$)/, '');
  const key = 'cs550-reading-position-v1:' + family;
  const sections = [...main.querySelectorAll(':scope > section[id]')];
  if (!sections.length) return;
  const line = () => Math.max(document.querySelector('.topbar').getBoundingClientRect().bottom + 24,
    parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0);
  function visible(element) {
    if (!element || !element.getClientRects().length || getComputedStyle(element).visibility === 'hidden') return false;
    const box = element.getBoundingClientRect();
    if (!box.width || !box.height) return false;
    for (let ancestor = element; ancestor && ancestor !== main; ancestor = ancestor.parentElement) {
      if (ancestor.hidden) return false;
      // Closed details can retain layout boxes for replaced content such as
      // videos. Only their visible summary is a valid reading-position anchor.
      if (ancestor.tagName === 'DETAILS' && !ancestor.open) {
        const summary = [...ancestor.children].find(item => item.tagName === 'SUMMARY');
        if (!summary?.contains(element)) return false;
      }
    }
    return true;
  }

  // IDs identify translated sections; tag/sibling paths identify matching paragraphs,
  // rows or media inside them without relying on translated text or page height.
  function describe(element) {
    const path = [];
    let root = element;
    while (root !== main && !root.id) root = root.parentElement;
    for (let current = element; current !== root; current = current.parentElement) {
      const siblings = [...current.parentElement.children].filter(item => item.tagName === current.tagName);
      path.unshift([current.tagName, siblings.indexOf(current)]);
    }
    return { id: root.id, path };
  }

  function resolve(reference) {
    if (!reference || typeof reference.id !== 'string' || !Array.isArray(reference.path)) return null;
    let element = document.getElementById(reference.id);
    if (!element || (element !== main && !main.contains(element))) return null;
    for (const [tag, index] of reference.path) {
      element = [...element.children].filter(item => item.tagName === tag)[index];
      if (!element) return null;
    }
    return element;
  }

  function capture() {
    const y = line();
    const section = sections.reduce((active, item) => item.getBoundingClientRect().top <= y ? item : active, sections[0]);
    const blocks = [...main.querySelectorAll('h1,h2,h3,h4,h5,p,li,pre,figure,table,tr,video,.lab,.equation,summary')]
      .filter(visible);
    let block = null;
    for (const item of blocks) {
      const box = item.getBoundingClientRect();
      if (box.top <= y && box.bottom > y && (!block || block.contains(item))) block = item;
    }
    if (!block) block = blocks.find(item => item.getBoundingClientRect().top > y) || section;
    const box = block.getBoundingClientRect();
    const bounds = section.getBoundingClientRect();
    return {
      edge: scrollY <= 2 ? 'top' : scrollY + innerHeight >= document.documentElement.scrollHeight - 2 ? 'bottom' : null,
      anchor: describe(block), section: section.id,
      fraction: Math.max(0, Math.min(1, (y - box.top) / Math.max(1, box.height))),
      gap: Math.max(0, box.top - y),
      sectionFraction: Math.max(0, Math.min(1, (y - bounds.top) / Math.max(1, bounds.height))),
      details: [...main.querySelectorAll('details')].map(item => ({ ...describe(item), open: item.open }))
    };
  }

  toggle.addEventListener('click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const target = new URL(toggle.href, location.href);
    if (target.origin !== location.origin || target.pathname.replace(/\.en(?=\.html$)/, '') !== family) return;
    const position = capture();
    target.hash = position.edge === 'top' ? '' : '#' + (position.edge === 'bottom' ? sections.at(-1).id : position.section);
    toggle.href = target.href;
    try {
      sessionStorage.setItem(key, JSON.stringify({ ...position, target: target.pathname, created: Date.now() }));
    } catch { /* The section link remains usable when storage is unavailable. */ }
  });

  let saved = null;
  try {
    const candidate = JSON.parse(sessionStorage.getItem(key) || 'null');
    sessionStorage.removeItem(key);
    if (candidate && candidate.target === location.pathname && Date.now() - candidate.created < 300000) saved = candidate;
  } catch { /* Direct links and normal reloads retain native browser behavior. */ }
  if (!saved) return;

  let restoring = true;
  let frame = 0;
  let observer;
  let timer;
  function stop() {
    restoring = false;
    cancelAnimationFrame(frame);
    observer?.disconnect();
    clearTimeout(timer);
    main.removeEventListener('load', schedule, true);
    main.removeEventListener('loadedmetadata', schedule, true);
    window.removeEventListener('load', schedule);
    document.removeEventListener('DOMContentLoaded', start);
    for (const name of ['wheel', 'touchstart', 'pointerdown', 'keydown']) window.removeEventListener(name, stop, true);
  }
  function restore() {
    frame = 0;
    if (!restoring) return;
    let top = 0;
    if (saved.edge === 'bottom') top = document.documentElement.scrollHeight - innerHeight;
    else if (saved.edge !== 'top') {
      const anchor = resolve(saved.anchor);
      const element = visible(anchor) ? anchor : document.getElementById(saved.section);
      if (!visible(element)) return;
      const box = element.getBoundingClientRect();
      const fraction = element === anchor ? saved.fraction : saved.sectionFraction;
      const gap = element === anchor ? saved.gap : 0;
      top = scrollY + box.top + box.height * fraction - gap - line();
    }
    window.scrollTo({ top: Math.max(0, top), behavior: 'instant' });
  }
  function schedule() {
    if (restoring && !frame) frame = requestAnimationFrame(restore);
  }
  function start() {
    if (!restoring) return;
    for (const state of saved.details || []) {
      const element = resolve(state);
      if (element?.tagName === 'DETAILS') element.open = state.open;
    }
    schedule();
    // Images, frame diagnostics and video metadata can settle after the first paint.
    observer = new ResizeObserver(schedule);
    observer.observe(main);
    main.addEventListener('load', schedule, true);
    main.addEventListener('loadedmetadata', schedule, true);
    window.addEventListener('load', schedule, { once: true });
    timer = setTimeout(stop, 5000);
  }
  // Never pull the page back after the reader starts scrolling or interacting.
  for (const name of ['wheel', 'touchstart', 'pointerdown', 'keydown']) window.addEventListener(name, stop, { capture: true, passive: true });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
