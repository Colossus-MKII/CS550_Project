(() => {
  'use strict';
  const panels = [...document.querySelectorAll('[data-event-panel]')];
  if (!panels.length) return;
  const buttons = [...document.querySelectorAll('[data-event-step]')];
  const previous = document.getElementById('event-prev');
  const next = document.getElementById('event-next');
  const progress = document.getElementById('event-progress');
  const english = document.documentElement.lang === 'en';
  const query = new URLSearchParams(location.search);
  const requested = Number(query.get('step') || 1) - 1;
  let step = Number.isInteger(requested) && requested >= 0 && requested < panels.length ? requested : 0;
  function show(index) {
    step = Math.max(0, Math.min(panels.length - 1, index));
    panels.forEach((panel, i) => { panel.hidden = i !== step; });
    buttons.forEach((button, i) => {
      if (i === step) button.setAttribute('aria-current', 'step');
      else button.removeAttribute('aria-current');
    });
    previous.disabled = step === 0;
    next.disabled = step === panels.length - 1;
    progress.value = `${step + 1} / ${panels.length}`;
    progress.setAttribute('aria-label', english ? `Step ${step + 1} of ${panels.length}` : `第 ${step + 1} 步，共 ${panels.length} 步`);
    const alternate = document.getElementById('language-toggle');
    const destination = new URL(alternate.href, location.href);
    destination.searchParams.set('step', String(step + 1));
    alternate.href = destination.href;
  }
  buttons.forEach(button => button.addEventListener('click', () => show(Number(button.dataset.eventStep))));
  previous.addEventListener('click', () => show(step - 1));
  next.addEventListener('click', () => show(step + 1));
  document.getElementById('event-controls').hidden = false;
  show(step);
})();
