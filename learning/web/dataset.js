;(() => {
  'use strict';
  const root = document.getElementById('dataset-viewer');
  const json = document.getElementById('dataset-data');
  if (!root || !json) return;
  const data = JSON.parse(json.textContent), en = root.dataset.language === 'en';
  const t = (zh, english) => en ? english : zh;
  const names = {person:'人',dog:'狗',cat:'猫',horse:'马',car:'汽车',motorbike:'摩托车',squirrel:'松鼠'};
  const name = c => en ? c : (names[c] || c);
  const el = id => document.getElementById(id);
  const sampleSelect=el('sample-select'), objectSelect=el('object-select'), modeSelect=el('view-select');
  const range=el('dataset-frame'), speed=el('browse-speed'), play=el('frame-play');
  const panel=el('dataset-panels'), rgb=el('dataset-rgb'), canvas=el('dataset-mask');
  const ctx=canvas.getContext('2d'), status=el('dataset-status');
  let sample=data.samples[0], frame=0, channel='all', mode='overlay', token=0, timer=null, playing=false;
  const params=new URLSearchParams(location.search);
  sample=data.samples.find(s=>String(s.id)===params.get('sample')) || sample;
  const initial=Number(params.get('frame'));
  frame=Number.isFinite(initial) ? Math.max(0,Math.min(sample.frames-1,Math.trunc(initial))) : 0;
  channel=sample.channels.some(c=>String(c.index)===params.get('channel')) ? params.get('channel') : 'all';
  mode=params.get('view')==='binary' ? 'binary' : 'overlay';
  if (['2','5','10'].includes(params.get('speed'))) speed.value=params.get('speed');
  const imageCache=new Map();
  function load(path) {
    if(imageCache.has(path)) return imageCache.get(path);
    const promise=new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(new Error(path));img.src=path;});
    imageCache.set(path,promise);
    promise.catch(()=>imageCache.delete(path));
    if(imageCache.size>100) imageCache.delete(imageCache.keys().next().value);
    return promise;
  }
  function syncUrl() {
    const q=new URLSearchParams({sample:String(sample.id),frame:String(frame),channel,view:mode,speed:speed.value});
    el('language-toggle').search=q.toString();
    try {history.replaceState(null,'',location.pathname+'?'+q+location.hash);} catch (_) { /* file:// */ }
  }
  function objects() {
    objectSelect.replaceChildren();
    const all=new Option(t('所有实例','All instances'),'all'); objectSelect.add(all);
    for(const c of sample.channels) objectSelect.add(new Option(`${t('通道','Ch')} ${c.index} · ${name(c.category)} (${c.category_id})`,String(c.index)));
    objectSelect.value=channel;
  }
  function stop() {
    playing=false;clearTimeout(timer);timer=null;play.textContent=t('播放','Play');play.setAttribute('aria-pressed','false');
  }
  function schedule(request) {
    if(playing && request===token) timer=setTimeout(()=>{if(frame>=sample.frames-1){stop();return;}frame++;render();},1000/Number(speed.value));
  }
  async function render() {
    clearTimeout(timer);
    const request=++token, currentSample=sample, currentFrame=frame, currentMode=mode;
    const selected=sample.channels.filter(c=>channel==='all'||String(c.index)===channel);
    sampleSelect.value=String(sample.id);range.max=String(sample.frames-1);range.value=String(frame);modeSelect.value=mode;
    el('frame-position').value=`${frame} / ${sample.frames-1} (${sample.frames} ${t('帧','frames')})`;
    el('frame-prev').disabled=frame===0;el('frame-next').disabled=frame===sample.frames-1;
    panel.setAttribute('aria-busy','true');panel.classList.remove('failed');
    el('instance-details').hidden=true;el('dataset-shapes').textContent='';
    status.textContent=t('正在读取当前帧…','Loading current frame…');
    syncUrl();
    const file=String(frame).padStart(5,'0')+'.png', base=`dataset-samples/${sample.id}/`;
    try {
      const [source,...masks]=await Promise.all([load(base+'rgb/'+file),...selected.map(c=>load(base+`mask-${c.index}/`+file))]);
      if(request!==token) return;
      rgb.src=source.src;rgb.width=sample.width;rgb.height=sample.height;
      canvas.width=sample.width;canvas.height=sample.height;
      if(currentMode==='overlay') ctx.drawImage(source,0,0);else {ctx.fillStyle='#000';ctx.fillRect(0,0,canvas.width,canvas.height);}
      selected.forEach((c,i)=>{
        if(currentMode==='binary') {ctx.drawImage(masks[i],0,0);return;}
        const layer=document.createElement('canvas');layer.width=canvas.width;layer.height=canvas.height;
        const lc=layer.getContext('2d');lc.drawImage(masks[i],0,0);lc.globalCompositeOperation='source-in';
        lc.fillStyle=`rgb(${c.color.join(',')})`;lc.fillRect(0,0,layer.width,layer.height);
        ctx.globalAlpha=.53;ctx.drawImage(layer,0,0);ctx.globalAlpha=1;
      });
      el('dataset-poster').hidden=true;canvas.hidden=false;
      el('mask-caption').textContent=t('真实标注','Ground truth')+' · '+(currentMode==='binary'?t('二值 mask','binary mask'):t('彩色叠加','color overlay'));
      canvas.setAttribute('aria-label',`${t('视频','Video')} ${sample.id}, ${t('帧','frame')} ${frame}, ${channel==='all'?t('所有通道','all channels'):t('通道','channel')+' '+channel}, ${mode}`);
      el('dataset-shapes').textContent=`video: (${sample.video_shape.join(', ')}) · segmentations: (${sample.mask_shape.join(', ')}) · uint8`;
      const rows=el('instance-rows');rows.replaceChildren();
      for(const c of sample.channels) {
        const tr=document.createElement('tr');
        const a=document.createElement('td'), swatch=document.createElement('span');swatch.className='instance-color';swatch.style.background=`rgb(${c.color.join(',')})`;
        a.append(swatch,`${c.index}${channel!=='all'&&channel!==String(c.index)?t('（未选）',' (not selected)'):''}`);tr.append(a);
        for(const text of [`${name(c.category)} / ${c.category_id}`,c.areas[frame]>0?t('可见','Visible'):t('无标注前景','No labeled foreground'),c.areas[frame].toLocaleString(en?'en-US':'zh-CN')]) {const td=document.createElement('td');td.textContent=text;tr.append(td);}
        rows.append(tr);
      }
      el('instance-details').hidden=false;
      status.textContent=`${t('视频','Video')} ${sample.id} · ${t('已显示帧','Showing frame')} ${frame} · ${selected.length} ${t('个选中通道','selected channels')} · ${sample.width} × ${sample.height}`;
      panel.dataset.sample=String(currentSample.id);panel.dataset.frame=String(currentFrame);panel.dataset.view=currentMode;
      panel.setAttribute('aria-busy','false');schedule(request);
    } catch (error) {
      if(request!==token) return;
      stop();panel.setAttribute('aria-busy','false');panel.classList.add('failed');
      status.textContent=t('此帧读取失败，请切换帧或重新加载；未显示旧帧以免混淆。','This frame could not load. Change frame or reload; stale images are hidden to avoid confusion.');
    }
  }
  el('dataset-controls').hidden=false;objects();render();
  sampleSelect.addEventListener('change',()=>{stop();sample=data.samples.find(s=>String(s.id)===sampleSelect.value);frame=0;channel='all';objects();render();});
  objectSelect.addEventListener('change',()=>{channel=objectSelect.value;render();});
  modeSelect.addEventListener('change',()=>{mode=modeSelect.value;render();});
  range.addEventListener('input',()=>{stop();frame=Number(range.value);render();});
  el('frame-prev').addEventListener('click',()=>{stop();frame=Math.max(0,frame-1);render();});
  el('frame-next').addEventListener('click',()=>{stop();frame=Math.min(sample.frames-1,frame+1);render();});
  play.addEventListener('click',()=>{if(playing){stop();return;}if(frame===sample.frames-1)frame=0;playing=true;play.textContent=t('暂停','Pause');play.setAttribute('aria-pressed','true');render();});
  speed.addEventListener('change',()=>{syncUrl();if(playing)render();});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
})();
