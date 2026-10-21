(() => {
  'use strict';
  const legacy = new Set(window.cs550LegacyIds || []);
  const projectSections = new Set(['overview','pathways','runs','results','next','pipeline','dataset','proposal','resources']);
  function routeLegacyBookmark() {
    let id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    if (!id || projectSections.has(id) || !legacy.has(id)) return;
    const suffix = document.documentElement.lang === 'en' ? '.en' : '';
    const target = new URL(`handbook${suffix}.html`, location.href);
    target.search = location.search;
    target.hash = location.hash;
    location.replace(target.href);
  }
  routeLegacyBookmark();
  window.addEventListener('hashchange', routeLegacyBookmark);
})();
