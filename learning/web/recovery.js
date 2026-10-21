;(() => {
  'use strict';
  // Language switches preserve open comparisons and a paused video position.
  // No model execution, external requests or autoplay.
  const key = 'cs550-hr-page-state-v1';
  const details = [...document.querySelectorAll('details[id]')];
  const videos = [...document.querySelectorAll('video[id]')];
  try {
    const state = JSON.parse(sessionStorage.getItem(key) || 'null');
    if (state) {
      for (const d of details) if (d.id in state.open) d.open = state.open[d.id];
      for (const v of videos) {
        const saved = state.videos[v.id];
        if (!saved || saved.time <= 0) continue;
        v.preload = 'metadata';
        v.addEventListener('loadedmetadata', () => {
          v.currentTime = Math.min(saved.time, Math.max(0, v.duration - 0.01));
          v.playbackRate = saved.rate;
        }, {once:true});
      }
    }
  } catch { /* Static pages and file:// still work without storage. */ }
  document.getElementById('language-toggle').addEventListener('click', () => {
    try {
      sessionStorage.setItem(key, JSON.stringify({
        open:Object.fromEntries(details.map(d => [d.id,d.open])),
        videos:Object.fromEntries(videos.map(v => [v.id,{time:v.currentTime,rate:v.playbackRate}]))
      }));
    } catch { /* Optional browser state only. */ }
  });
})();
