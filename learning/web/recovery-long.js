;(() => {
  'use strict';
  // Key-step navigation seeks and PAUSES; no automatic playback or model work.
  document.querySelectorAll('button[data-video][data-seek]').forEach(button => {
    button.addEventListener('click', () => {
      const video = document.getElementById(button.dataset.video);
      const seek = () => {
        video.pause();
        video.currentTime = Math.min(Number(button.dataset.seek), Math.max(0, video.duration - 0.05));
      };
      if (video.readyState >= 1) seek();
      else {
        video.addEventListener('loadedmetadata', seek, {once:true});
        video.preload = 'metadata';
        video.load();
      }
    });
  });
})();
