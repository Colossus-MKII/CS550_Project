(() => {
  'use strict';
  const controls = document.getElementById('program-controls');
  if (!controls) return;
  const panels = [...document.querySelectorAll('[data-program-panel]')];
  const buttons = [...document.querySelectorAll('[data-program-step]')];
  const en = document.documentElement.lang === 'en';
  const query = new URLSearchParams(location.search);
  let selected = panels.some(p => p.dataset.programPanel === query.get('step')) ? query.get('step') : 'data';
  let all = query.get('view') === 'all';
  const hashStep = () => location.hash.startsWith('#stage-') ? location.hash.slice(7) : null;
  if (panels.some(p => p.dataset.programPanel === hashStep())) { selected = hashStep(); all = false; }
  function render() {
    panels.forEach(panel => { panel.hidden = !all && panel.dataset.programPanel !== selected; });
    buttons.forEach(button => button.setAttribute('aria-pressed', String(!all && button.dataset.programStep === selected)));
    const index = panels.findIndex(p => p.dataset.programPanel === selected);
    document.getElementById('program-position').textContent = all ? (en ? 'All eight steps' : '全部八个步骤') : `${en ? 'Step' : '步骤'} ${index+1} / ${panels.length}`;
    const params = new URLSearchParams({ step: selected });
    if (all) params.set('view', 'all');
    document.getElementById('language-toggle').search = params.toString();
    const hash = location.hash.startsWith('#stage-') ? (all ? '#steps' : `#stage-${selected}`) : location.hash;
    try { history.replaceState(null, '', `?${params}${hash}`); } catch { /* file:// still works */ }
  }
  controls.hidden = false;
  buttons.forEach(button => button.addEventListener('click', () => { selected = button.dataset.programStep; all = false; render(); }));
  document.getElementById('program-show-all').addEventListener('click', () => { all = true; render(); });
  window.addEventListener('hashchange', () => { if (panels.some(p => p.dataset.programPanel === hashStep())) { selected = hashStep(); all = false; render(); } });
  render();
})();
