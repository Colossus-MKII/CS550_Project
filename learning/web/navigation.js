(() => {
  'use strict';
  const nav = document.getElementById('course-nav');
  const sidebar = document.getElementById('sidebar');
  if (!nav || !sidebar) return;
  const groups = [...nav.querySelectorAll('.course-group')];
  const locate = document.getElementById('locate-current-section');
  let previous = null;
  let frame = 0;
  let forceNext = false;

  function reveal(link) {
    if (!sidebar.getClientRects().length) return;
    const bounds = sidebar.getBoundingClientRect();
    const item = link.getBoundingClientRect();
    if (item.top < bounds.top + 12 || item.bottom > bounds.bottom - 12) {
      // Scroll only the outline, leaving the reader's position in the content intact.
      sidebar.scrollTo({
        top: sidebar.scrollTop + item.top - bounds.top - bounds.height * 0.4,
        behavior: 'instant'
      });
    }
  }

  function sync(force) {
    const active = nav.querySelector('a[aria-current="location"]');
    if (!active) return;
    const group = active.closest('.course-group');
    groups.forEach(item => item.classList.toggle('is-current', item === group));
    if (active === previous && !force) return;
    previous = active;
    if (group) {
      groups.forEach(item => { item.open = item === group; });
    }
    reveal(active);
  }

  function schedule(force = false) {
    forceNext = forceNext || force;
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      const requested = forceNext;
      forceNext = false;
      sync(requested);
    });
  }

  // Reuse each page's existing scroll-based active-section state.
  // Expand the new group in the same update as its active link. Deferring this
  // to another animation frame can leave the highlight inside a closed group,
  // especially while a language switch is restoring the reading position.
  new MutationObserver(() => sync(false)).observe(nav, {
    subtree: true, attributes: true, attributeFilter: ['aria-current']
  });
  new MutationObserver(() => {
    if (sidebar.classList.contains('is-open')) schedule(true);
  }).observe(sidebar, { attributes: true, attributeFilter: ['class'] });
  window.addEventListener('hashchange', () => schedule(true));
  window.addEventListener('resize', () => schedule(true));
  window.addEventListener('load', () => schedule(true), { once: true });
  if (locate) {
    locate.hidden = false;
    locate.addEventListener('click', () => schedule(true));
  }
  schedule(true);
})();
