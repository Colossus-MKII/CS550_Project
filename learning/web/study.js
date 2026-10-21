(() => {
  'use strict';
  const key = 'cs550-learning-handbook-v2';
  const english = document.documentElement.lang === 'en';
  let preferences = {};
  try { preferences = JSON.parse(localStorage.getItem(key) || '{}') || {}; } catch { /* Offline storage is optional. */ }
  let theme = preferences.theme === 'light' ? 'light' : 'dark';
  const button = document.getElementById('theme-toggle');
  function applyTheme() {
    document.documentElement.dataset.theme = theme;
    button.textContent = theme === 'dark' ? (english ? 'Light' : '浅色') : (english ? 'Dark' : '深色');
    button.setAttribute('aria-label', english ? `Switch to ${theme === 'dark' ? 'light' : 'dark'} theme` : `切换到${theme === 'dark' ? '浅色' : '深色'}主题`);
  }
  applyTheme();
  button.addEventListener('click', () => {
    theme = theme === 'dark' ? 'light' : 'dark'; applyTheme();
    try { const latest = JSON.parse(localStorage.getItem(key) || '{}') || {}; localStorage.setItem(key, JSON.stringify({ ...latest, theme })); } catch { /* Keep working without storage. */ }
  });
  const menu = document.getElementById('menu-toggle');
  const sidebar = document.getElementById('sidebar');
  menu.addEventListener('click', () => { menu.setAttribute('aria-expanded', String(sidebar.classList.toggle('is-open'))); });
  const sections = [...document.querySelectorAll('main > section')];
  const links = [...document.querySelectorAll('#course-nav a')];
  function activeSection() {
    if (!sections.length) return 'start';
    const line = Math.max(document.querySelector('.topbar').getBoundingClientRect().bottom + 24,
      parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0);
    if (scrollY > 2 && scrollY + innerHeight >= document.documentElement.scrollHeight - 2) return sections.at(-1).id;
    return sections.reduce((active, section) => section.getBoundingClientRect().top <= line ? section : active, sections[0]).id;
  }
  let pending = false;
  function update() {
    const active = activeSection();
    links.forEach(link => { const selected = link.hash === '#' + active; link.classList.toggle('active', selected); if (selected) link.setAttribute('aria-current', 'location'); else link.removeAttribute('aria-current'); });
  }
  function scheduleUpdate() { if (!pending) { pending = true; requestAnimationFrame(() => { update(); pending = false; }); } }
  window.addEventListener('scroll', scheduleUpdate, { passive: true });
  window.addEventListener('resize', update);
  // Media loading, expanded comparisons and program panels can move chapters
  // without a window scroll or resize.
  new ResizeObserver(scheduleUpdate).observe(document.querySelector('main'));
  document.querySelector('main').addEventListener('toggle', scheduleUpdate, true);
  update();
  links.forEach(link => link.addEventListener('click', () => { sidebar.classList.remove('is-open'); menu.setAttribute('aria-expanded', 'false'); }));
  document.getElementById('language-toggle').addEventListener('click', event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.currentTarget.hash = '#' + activeSection();
  });
})();
