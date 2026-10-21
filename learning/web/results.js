;(() => {
  'use strict';
  const payload = document.getElementById('pilot-data');
  if (!payload) return;
  const data = JSON.parse(payload.textContent);
  const el = id => document.getElementById(id);
  const en = data.language === 'en';
  const t = (zh, english) => en ? english : zh;
  const reasons = {
    matched: t('已匹配', 'Matched'),
    matched_id_changed: t('匹配 ID 发生变化', 'Matched ID changed'),
    good_yolo_mask_but_no_matching_output: t('YOLO mask 足够好，但无匹配跟踪输出', 'Good YOLO mask, no matching track output'),
    yolo_box_ok_mask_or_propagation_poor: t('YOLO 框足够好，mask / 传播需检查', 'Good YOLO box; inspect mask / propagation'),
    no_adequate_same_class_yolo_box: t('无足够准确的同类 YOLO 框', 'No adequate same-class YOLO box')
  };
  const query = new URLSearchParams(location.search);
  let video = data.videos.find(v => String(v.id) === query.get('video')) || data.videos[0];
  const requested = Number(query.get('frame'));
  let frame = Number.isFinite(requested) ? Math.max(0, Math.min(video.frames - 1, Math.trunc(requested))) : 0;
  let token = 0;

  async function render() {
    const request = ++token;
    el('video-select').value = String(video.id);
    el('frame-range').max = video.frames - 1;
    el('frame-range').value = frame;
    el('position').value = `${frame} / ${video.frames - 1}`;
    el('prev').disabled = frame === 0;
    el('next').disabled = frame === video.frames - 1;
    el('frame-image').setAttribute('aria-busy', 'true');
    el('frame-status').textContent = t('正在读取当前帧…', 'Loading current frame…');
    el('diagnostic-table').hidden = true;
    const path = `${data.prefix}${video.id}/visuals/${String(frame).padStart(5, '0')}.jpg`;
    const image = new Image();
    image.src = path;
    const params = new URLSearchParams({video:String(video.id), frame:String(frame)});
    el('language-toggle').search = params.toString();
    try { history.replaceState(null, '', `?${params}${location.hash}`); } catch { /* file:// */ }
    try {
      await image.decode();
      if (request !== token) return;
      el('frame-image').src = path;
      el('frame-image').style.visibility = 'visible';
      el('frame-image').setAttribute('aria-busy', 'false');
      el('frame-image').dataset.frame = frame;
      el('frame-image').dataset.video = video.id;
      el('frame-status').textContent = `${t('视频', 'Video')} ${video.id} · ${t('导出帧', 'exported frame')} ${frame} · A0: FP ${video.A0[frame].FP}, FN ${video.A0[frame].FN} · B0: FP ${video.B0[frame].FP}, FN ${video.B0[frame].FN}`;
      el('diagnostic-rows').replaceChildren();
      for (const method of ['A0', 'B0']) {
        for (const target of video[method][frame].targets) {
          const row = document.createElement('tr');
          const values = [method, target.gt_id, target.category,
            target.matched_prediction_id ?? t('未匹配', 'Unmatched'), target.best_mask_iou.toFixed(3),
            `${target.yolo_box_iou.toFixed(3)} / ${target.yolo_mask_iou.toFixed(3)}`,
            reasons[target.reason] || target.reason];
          for (const value of values) {
            const cell = document.createElement('td');
            cell.textContent = value;
            row.append(cell);
          }
          el('diagnostic-rows').append(row);
        }
      }
      el('diagnostic-table').hidden = false;
      const event = video.events[frame];
      el('events').textContent = (event.detector_called ? t('B0 本帧使用 YOLO 提示；', 'B0 uses YOLO prompts on this frame; ') : t('B0 本帧未使用 YOLO 提示；', 'B0 uses no YOLO prompts on this frame; ')) + event.actions.map(a => `${a.action} ${a.id ?? a.detector_index}`).join(', ');
    } catch {
      if (request !== token) return;
      el('frame-image').style.visibility = 'hidden';
      el('frame-image').setAttribute('aria-busy', 'false');
      el('frame-status').textContent = t('当前帧读取失败，请切换帧或重新加载。', 'Frame loading failed. Change frame or reload.');
    }
  }
  el('viewer-controls').hidden = false;
  el('frame-range').addEventListener('input', () => { frame = Number(el('frame-range').value); render(); });
  el('video-select').addEventListener('change', () => { video = data.videos.find(v => String(v.id) === el('video-select').value); frame = 0; render(); });
  el('prev').addEventListener('click', () => { frame = Math.max(0, frame - 1); render(); });
  el('next').addEventListener('click', () => { frame = Math.min(video.frames - 1, frame + 1); render(); });
  document.querySelectorAll('[data-jump-video]').forEach(button => button.addEventListener('click', () => {
    video = data.videos.find(v => String(v.id) === button.dataset.jumpVideo);
    frame = Number(button.dataset.jumpFrame);
    render(); el('viewer').scrollIntoView();
  }));
  render();
})();
