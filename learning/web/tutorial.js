(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('lesson-data').textContent);
  const language = data.language === 'en' ? 'en' : 'zh';
  const t = (zh, en) => language === 'en' ? en : zh;
  const get = id => document.getElementById(id);
  const storageKey = 'cs550-learning-handbook-v2';
  const switchKey = storageKey + ':language-switch:' + data.run;
  let switchState = null;
  try {
    const candidate = JSON.parse(sessionStorage.getItem(switchKey) || 'null');
    if (candidate && candidate.language === language && Date.now() - candidate.created < 300000) switchState = candidate;
    sessionStorage.removeItem(switchKey);
  } catch { /* Language links still work when session storage is unavailable. */ }
  const readStored = key => { try { return JSON.parse(localStorage.getItem(key) || 'null'); } catch { return null; } };
  const saveStored = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* Private/file browsing may deny storage. */ } };
  const saved = readStored(storageKey) || {};
  const completed = new Set(Array.isArray(saved.completed) ? saved.completed.filter(id => /^chapter-[1-7]$/.test(id)) : []);
  let theme = saved.theme === 'light' ? 'light' : 'dark';
  let toastTimer;
  function toast(message) {
    get('toast').textContent = message;
    get('toast').classList.add('visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => get('toast').classList.remove('visible'), 2600);
  }
  function savePreferences() { saveStored(storageKey, { theme, completed: [...completed], language }); }
  function applyTheme() {
    document.documentElement.dataset.theme = theme;
    get('theme-toggle').textContent = theme === 'dark' ? t('浅色', 'Light') : t('深色', 'Dark');
    get('theme-toggle').setAttribute('aria-label', theme === 'dark' ? t('切换到浅色主题', 'Switch to light theme') : t('切换到深色主题', 'Switch to dark theme'));
  }
  applyTheme();
  get('theme-toggle').addEventListener('click', () => { theme = theme === 'dark' ? 'light' : 'dark'; applyTheme(); savePreferences(); });
  function updateProgress() {
    document.querySelectorAll('[data-complete]').forEach(button => {
      const done = completed.has(button.dataset.complete);
      button.setAttribute('aria-pressed', String(done));
      button.textContent = done ? t('✓ 已读 · 取消标记', '✓ Read · Undo') : t('标记已读', 'Mark as read');
    });
    document.querySelectorAll('#course-nav a').forEach(link => link.classList.toggle('done', completed.has(link.hash.slice(1))));
    get('progress-label').textContent = t(`已读 ${completed.size} / 7 章`, `Read ${completed.size} / 7 chapters`);
    get('course-progress').value = completed.size;
  }
  updateProgress();
  document.querySelectorAll('[data-complete]').forEach(button => button.addEventListener('click', () => {
    const id = button.dataset.complete;
    if (completed.has(id)) completed.delete(id); else completed.add(id);
    updateProgress(); savePreferences();
  }));
  get('menu-toggle').addEventListener('click', () => {
    const open = get('sidebar').classList.toggle('is-open');
    get('menu-toggle').setAttribute('aria-expanded', String(open));
  });
  document.querySelectorAll('#course-nav a').forEach(link => link.addEventListener('click', () => {
    if (window.innerWidth <= 860) { get('sidebar').classList.remove('is-open'); get('menu-toggle').setAttribute('aria-expanded', 'false'); }
  }));
  const sections = [...document.querySelectorAll('.chapter')];
  function updateActiveChapter() {
    let active = sections[0];
    const line = Math.max(document.querySelector('.topbar').getBoundingClientRect().bottom + 24,
      parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0);
    for (const section of sections) {
      if (section.getBoundingClientRect().top <= line) active = section;
    }
    if (scrollY > 2 && scrollY + innerHeight >= document.documentElement.scrollHeight - 2) active = sections.at(-1);
    document.querySelectorAll('#course-nav a').forEach(link => {
      const selected = link.hash === '#' + active.id;
      link.classList.toggle('active', selected);
      if (selected) link.setAttribute('aria-current', 'location'); else link.removeAttribute('aria-current');
    });
  }
  let scrollPending = false;
  function scheduleChapterUpdate() {
    if (scrollPending) return;
    scrollPending = true;
    requestAnimationFrame(() => { updateActiveChapter(); scrollPending = false; });
  }
  window.addEventListener('scroll', scheduleChapterUpdate, { passive: true });
  window.addEventListener('resize', updateActiveChapter);
  new ResizeObserver(scheduleChapterUpdate).observe(document.querySelector('main'));
  document.querySelector('main').addEventListener('toggle', scheduleChapterUpdate, true);
  updateActiveChapter();

  let previousQuery = '', searchIndex = -1;
  get('search-form').addEventListener('submit', event => {
    event.preventDefault();
    const query = get('search-input').value.trim().toLocaleLowerCase();
    document.querySelectorAll('.search-hit').forEach(element => element.classList.remove('search-hit'));
    if (!query) { get('search-status').textContent = t('输入术语或问题，再点击查找。', 'Enter a term or question, then select Find.'); return; }
    const matches = sections.filter(section => (section.dataset.title + ' ' + section.textContent).toLocaleLowerCase().includes(query));
    if (!matches.length) { get('search-status').textContent = t('没有找到相关章节。试试“ID”“提示”或“置信度”。', 'No matching chapters. Try “ID”, “prompt” or “confidence”.'); return; }
    searchIndex = query === previousQuery ? (searchIndex + 1) % matches.length : 0;
    previousQuery = query;
    const section = matches[searchIndex];
    section.querySelectorAll('details').forEach(details => { if (details.textContent.toLocaleLowerCase().includes(query)) details.open = true; });
    section.classList.add('search-hit');
    section.scrollIntoView({ block: 'start', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
    get('search-status').textContent = t(`找到 ${matches.length} 章，当前 ${searchIndex + 1} / ${matches.length}；再次查找跳到下一章。`, `Found ${matches.length} chapters; ${searchIndex + 1} / ${matches.length}. Select Find again for the next match.`);
    toast(t('找到：', 'Found: ') + section.querySelector('h1,h2').textContent.replace(/\s+/g, ' '));
  });
  get('search-input').addEventListener('input', () => {
    if (!get('search-input').value) { previousQuery = ''; searchIndex = -1; get('search-status').textContent = ''; document.querySelectorAll('.search-hit').forEach(element => element.classList.remove('search-hit')); }
  });
  document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {
    const code = get(button.dataset.copy);
    try { await navigator.clipboard.writeText(code.textContent); toast(t('代码已复制。', 'Code copied.')); }
    catch {
      const range = document.createRange(); range.selectNodeContents(code);
      const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
      toast(t('无法自动访问剪贴板，已选中代码，请按 Ctrl+C。', 'Clipboard access is unavailable. Code selected; press Ctrl+C.'));
    }
  }));

  const videos = [...document.querySelectorAll('video')];
  function seekVideo(video, time) {
    video.pause();
    const duration = Number.isFinite(video.duration) ? video.duration : data.totalFrames / data.fps;
    const target = Math.max(0, Math.min(time, Math.max(0, duration - 1 / data.fps)));
    if (video.readyState >= 1) video.currentTime = target;
    else { video.dataset.pendingTime = String(target); video.load(); }
  }
  videos.forEach(video => {
    video.addEventListener('play', () => videos.forEach(other => { if (other !== video) other.pause(); }));
    video.addEventListener('loadedmetadata', () => {
      if (video.dataset.pendingTime !== undefined) { const value = Number(video.dataset.pendingTime); delete video.dataset.pendingTime; seekVideo(video, value); }
    });
  });
  document.querySelectorAll('[data-step]').forEach(button => button.addEventListener('click', () => {
    const video = get(button.dataset.video);
    const frame = Math.round(video.currentTime * data.fps) + Number(button.dataset.step);
    seekVideo(video, frame / data.fps);
  }));
  document.querySelectorAll('[data-speed]').forEach(select => select.addEventListener('change', () => {
    const video = get(select.dataset.speed);
    video.defaultPlaybackRate = Number(select.value); video.playbackRate = Number(select.value);
  }));

  function drawIou() {
    const offset = Number(get('iou-offset').value);
    const width = get('iou-geometry').parentElement.getBoundingClientRect().width;
    get('iou-geometry').setAttribute('viewBox', `0 0 ${Math.max(width, 210)} 125`);
    const left = (Math.max(width, 210) - 200) / 2;
    get('iou-truth').setAttribute('x', String(left));
    get('iou-prediction').setAttribute('x', String(left + offset));
    const intersection = (100 - offset) * 80, union = 16000 - intersection;
    get('iou-offset-value').textContent = String(offset);
    get('iou-score').textContent = (intersection / union).toFixed(3);
    get('iou-intersection').textContent = String(intersection);
    get('iou-union').textContent = String(union);
    get('iou-svg-desc').textContent = t(`预测区域右移 ${offset} 像素，交集 ${intersection} 像素，并集 ${union} 像素。`, `Prediction shifted right by ${offset} pixels; intersection ${intersection} pixels; union ${union} pixels.`);
  }
  get('iou-offset').addEventListener('input', drawIou);
  new ResizeObserver(drawIou).observe(get('iou-geometry').parentElement);
  drawIou();
  const scenarios = { stable: Array(10).fill(7), split: [...Array(5).fill(7), ...Array(5).fill(8)], miss: [...Array(5).fill(7), ...Array(5).fill(null)] };
  function lane(id, values, type) {
    get(id).replaceChildren(...values.map((value, index) => {
      const cell = document.createElement('span'); cell.className = 'cell';
      if (type === 'truth') cell.classList.add('truth');
      if (type === 'pred') cell.classList.add(value === null ? 'missing' : 'id' + value);
      cell.textContent = value === null ? '—' : String(value);
      cell.setAttribute('aria-label', t(`第 ${index + 1} 帧：${value === null ? '漏检' : value}`, `Frame ${index + 1}: ${value === null ? 'missing' : value}`));
      return cell;
    }));
  }
  lane('metric-frames', Array.from({length: 10}, (_, i) => i + 1), 'frame');
  lane('metric-truth', Array(10).fill('A'), 'truth');
  function drawIdentity() {
    const ids = scenarios[get('identity-scenario').value];
    lane('metric-prediction', ids, 'pred');
    const counts = new Map();
    for (const id of ids) if (id !== null) counts.set(id, (counts.get(id) || 0) + 1);
    const lengths = [...counts.values()];
    const predicted = lengths.reduce((sum, n) => sum + n, 0);
    const idtp = Math.max(0, ...lengths), idfp = predicted - idtp, idfn = 10 - idtp;
    const idf1 = 2 * idtp / (2 * idtp + idfp + idfn);
    const deta = predicted / 10;
    // Single-GT, perfect-present-masks, no-FP special case. Not a general evaluator.
    const assa = predicted ? lengths.reduce((sum, n) => sum + n * (n / 10), 0) / predicted : 0;
    const hota = Math.sqrt(deta * assa); // All 19 thresholds agree because present IoU is 1.
    for (const [name, value] of Object.entries({idf1, deta, assa, hota})) get('metric-' + name).textContent = (value * 100).toFixed(1) + '%';
    get('metric-counts').textContent = `IDTP ${idtp} · IDFP ${idfp} · IDFN ${idfn}`;
  }
  get('identity-scenario').addEventListener('change', drawIdentity);
  drawIdentity();

  if (data.frames.length) {
    const yoloByFrame = new Map(data.yolo.map(row => [row.frame, row]));
    const samByFrame = new Map(data.sam.map(row => [row.frame, row]));
    const frameRange = get('frame-range'); frameRange.max = String(data.frames.length - 1);
    const oldFrame = switchState && Number.isInteger(switchState.frame) ? { frame: switchState.frame } : readStored(storageKey + ':' + data.run);
    frameRange.value = String(oldFrame && data.frames.includes(oldFrame.frame) ? data.frames.indexOf(oldFrame.frame) : Math.floor(data.frames.length / 2));
    const asArray = value => Array.isArray(value) ? value : [];
    const display = value => value === null || value === undefined ? '—' : String(value);
    const confidence = value => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(3) : '—';
    function showFrame() {
      const frame = data.frames[Number(frameRange.value)];
      get('frame-value').textContent = String(frame);
      get('source-frame').src = 'frames/' + String(frame).padStart(5, '0') + '.jpg';
      get('source-frame').alt = t(`本次输入的第 ${frame} 帧原始图像`, `Original input image at frame ${frame}`);
      get('frame-caption').textContent = t(`原始帧 ${frame} · ${((frame) / data.fps).toFixed(3)} 秒 · 不含预测覆盖层`, `Source frame ${frame} · ${(frame / data.fps).toFixed(3)} seconds · No prediction overlay`);
      const yolo = yoloByFrame.get(frame), sam = samByFrame.get(frame), rows = [];
      for (const item of asArray(yolo && yolo.detections)) rows.push(['YOLO', item.class_name, t('无跨帧 ID', 'No cross-frame ID'), confidence(item.confidence), item.mask_pixels]);
      for (const item of asArray(yolo && yolo.tracks)) rows.push(['ByteTrack', item.class_name, item.track_id, confidence(item.confidence), item.mask_pixels]);
      for (const item of asArray(sam && sam.objects)) rows.push(['SAM 2.1', item.label_from_prompt + t('（提示标签）', ' (prompt label)'), item.object_id, t('不作检测分数展示', 'Not a detection score'), item.empty_mask ? t(`${item.mask_pixels}（空 mask）`, `${item.mask_pixels} (empty mask)`) : item.mask_pixels]);
      get('frame-records').replaceChildren(...rows.map(row => {
        const tr = document.createElement('tr');
        row.forEach(value => { const td = document.createElement('td'); td.textContent = display(value); tr.append(td); });
        return tr;
      }));
      if (!rows.length) { const tr = document.createElement('tr'), td = document.createElement('td'); td.colSpan = 5; td.textContent = t('这一帧没有可展示的目标记录。', 'No object records are available for this frame.'); tr.append(td); get('frame-records').append(tr); }
      get('frame-evidence-status').textContent = t(`YOLO / ByteTrack：${yolo ? '已读取该帧记录' : '没有该帧记录'}；SAM：${sam ? '已读取该帧记录' : '没有该帧记录'}。表格只是预测输出，不是标准标注。`, `YOLO / ByteTrack: ${yolo ? 'frame record loaded' : 'no frame record'}; SAM: ${sam ? 'frame record loaded' : 'no frame record'}. These are predictions, not ground-truth annotations.`);
      get('frame-prev').disabled = Number(frameRange.value) === 0;
      get('frame-next').disabled = Number(frameRange.value) === data.frames.length - 1;
    }
    frameRange.addEventListener('input', showFrame);
    frameRange.addEventListener('change', () => saveStored(storageKey + ':' + data.run, { frame: data.frames[Number(frameRange.value)] }));
    get('frame-prev').addEventListener('click', () => { frameRange.value = String(Math.max(0, Number(frameRange.value) - 1)); showFrame(); });
    get('frame-next').addEventListener('click', () => { frameRange.value = String(Math.min(data.frames.length - 1, Number(frameRange.value) + 1)); showFrame(); });
    get('seek-videos').addEventListener('click', () => {
      const frame = data.frames[Number(frameRange.value)];
      videos.forEach(video => seekVideo(video, frame / data.fps));
      toast(t(`已将 ${videos.length} 个视频定位到第 ${frame} 帧并暂停。`, `All ${videos.length} videos paused at frame ${frame}.`));
    });
    const presets = [...new Set([data.frames[0], ...[30, 60, 75, 90, 106].filter(n => data.frames.includes(n)), data.frames[data.frames.length - 1]])];
    get('frame-presets').replaceChildren(...presets.map(frame => {
      const button = document.createElement('button'); button.textContent = t('帧 ', 'Frame ') + frame;
      button.addEventListener('click', () => { frameRange.value = String(data.frames.indexOf(frame)); showFrame(); });
      return button;
    }));
    showFrame();
  }

  // Both files are self-contained and share the same measurements and progress key.
  // Only a language switch transfers transient UI state; a normal reload is unchanged.
  if (switchState) {
    if (Number.isInteger(switchState.offset) && switchState.offset >= 0 && switchState.offset <= 100) {
      get('iou-offset').value = String(switchState.offset); drawIou();
    }
    if (Object.hasOwn(scenarios, switchState.scenario)) {
      get('identity-scenario').value = switchState.scenario; drawIdentity();
    }
    if (Array.isArray(switchState.details)) document.querySelectorAll('details').forEach((element, index) => {
      if (typeof switchState.details[index] === 'boolean') element.open = switchState.details[index];
    });
    videos.forEach(video => {
      const state = switchState.videos && switchState.videos[video.id];
      if (!state) return;
      if ([0.25, 0.5, 1].includes(state.speed)) {
        video.defaultPlaybackRate = state.speed;
        video.playbackRate = state.speed;
        document.querySelector(`[data-speed="${video.id}"]`).value = String(state.speed);
      }
      if (Number.isFinite(state.time) && state.time >= 0) seekVideo(video, state.time);
    });
  }
  get('language-toggle').addEventListener('click', event => {
    // Respect open-in-new-tab gestures without mutating the current page's state.
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    updateActiveChapter();
    const active = document.querySelector('#course-nav a[aria-current="location"]');
    get('language-toggle').hash = active ? active.hash : '#overview';
    savePreferences();
    try {
      sessionStorage.setItem(switchKey, JSON.stringify({
        language: language === 'en' ? 'zh' : 'en', created: Date.now(),
        offset: Number(get('iou-offset').value), scenario: get('identity-scenario').value,
        frame: data.frames[Number(get('frame-range').value)],
        details: [...document.querySelectorAll('details')].map(element => element.open),
        videos: Object.fromEntries(videos.map(video => [video.id, { time: video.currentTime, speed: video.playbackRate }]))
      }));
    } catch { /* A regular language link remains useful without saved transient state. */ }
  });
})();
