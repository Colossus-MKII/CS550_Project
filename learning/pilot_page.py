"""Import saved pilot evidence into the EXISTING learning website, without inference.

Only explicitly allowlisted figures, videos, source snapshots and safe metadata
are copied. Raw masks, arbitrary run files and private absolute paths stay out.
"""
import argparse
from hashlib import sha256
from html import escape
import json
from pathlib import Path
from . import journey
import re
import shutil

from .study import WEB, link, pick, section
from .navigation import decorate_page
from .baseline_revision import revision_notice
from .recovery_page import recovery_link

PAGES = ('results.html', 'results.en.html')


def digest(path):
    result = sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            result.update(chunk)
    return result.hexdigest()


def import_results(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    summary = json.loads((source/'summary.json').read_text(encoding='utf-8'))
    verification = json.loads((source/'verification.json').read_text(encoding='utf-8'))
    if summary['status'] != 'completed' or verification['status'] != 'passed':
        raise ValueError('Only completed, verified results can enter the learning site')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', source.name):
        raise ValueError('Invalid run name')
    viewer = json.loads((source/'viewer-data.json').read_text(encoding='utf-8'))
    destination = output/'pilot-results'/source.name
    files = {}

    def copy(relative):
        target = destination/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source/relative, target)
        files[relative] = digest(target)

    for video in viewer['videos']:
        key = str(int(video['id']))
        if video['frames'] != summary['videos'][key]['frames']:
            raise ValueError('Viewer and source frame counts differ')
        for t in range(video['frames']):
            copy(f'{key}/visuals/{t:05d}.jpg')
        copy(f'{key}/iou-curve.png')
        copy(f'{key}/comparison.mp4')
    for name, expected in summary['source_files'].items():
        if not re.fullmatch(r'[a-z_][a-z0-9_]*\.py', name):
            raise ValueError('Unexpected source filename')
        relative = f'code/{name}.txt'
        if digest(source/relative) != expected:
            raise ValueError('Inference source fingerprint mismatch')
        copy(relative)
    for name in ('metrics.json','config.json','evaluator-self-checks.json','verification.json','input-manifest.json','viewer-data.json'):
        copy(name)
    correction = None
    if (source/'correction-audit.json').is_file():
        copy('correction-audit.json')
        correction = json.loads((source/'correction-audit.json').read_text(encoding='utf-8'))
        if correction['new_run'] != source.name or correction['new_metrics'] != json.loads((source/'metrics.json').read_text()):
            raise ValueError('Correction audit does not describe this run')
        if correction.get('full_inference_repeat', {}).get('status') != 'passed':
            raise ValueError('Corrected baseline requires a complete inference repeat')
    # Do not expose samples_root or any other host-specific paths from summary.
    public_summary = {key:summary[key] for key in ('status','created_utc','environment','configuration',
        'classes','selection','weights','source_files','limitations','videos','yolo_peak_allocated_mib','sam_peak_allocated_mib')}
    if 'sam_cpu_offload_guard' in summary:
        public_summary['sam_cpu_offload_guard'] = summary['sam_cpu_offload_guard']
    (destination/'summary.json').write_text(json.dumps(public_summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    files['summary.json'] = digest(destination/'summary.json')
    shutil.copy2(Path(__file__).resolve().parents[1]/'experiments/CODE_GUIDE.md', destination/'code/README.md.txt')
    files['code/README.md.txt'] = digest(destination/'code/README.md.txt')
    manifest = {'run':source.name,'prefix':f'pilot-results/{source.name}/','summary':public_summary,
        'metrics':json.loads((source/'metrics.json').read_text(encoding='utf-8')),'viewer':viewer,'files':files}
    if correction:
        manifest['correction'] = correction
    manifest_path = output/'pilot-results/manifest.json'
    if correction and manifest_path.is_file():
        legacy = json.loads(manifest_path.read_text(encoding='utf-8'))
        backup = output/'pilot-results/manifest-before-sync.json'
        if not backup.exists():
            if legacy['metrics'] != correction['old_metrics']:
                raise ValueError('Active legacy scores do not match the correction audit')
            shutil.copy2(manifest_path, backup)
    if correction and (output/'pilot-results/manifest-before-sync.json').is_file():
        manifest['legacy_manifest'] = 'pilot-results/manifest-before-sync.json'
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    write_results_pages(output)
    return manifest


def score_table(metrics, language):
    t = lambda zh,en: pick(language,zh,en)
    rows = []
    for method,result in metrics.items():
        for name,scores in [(t('五类等权','Class macro'),result['macro']),*((c,r['scores']) for c,r in result['per_class'].items())]:
            values = ''.join(f'<td>{scores[key]*100:.1f}</td>' for key in ('HOTA','DetA','AssA','IDF1'))
            values += ''.join(f'<td>{scores[key]}</td>' for key in ('FP','FN','IDSW'))
            rows.append(f'<tr><th scope="row">{method} · {escape(name)}</th>{values}</tr>')
    return '<div class="table-wrap"><table><thead><tr><th>'+t('方法 / 类别','Method / class')+'</th>'+''.join(f'<th>{key}</th>' for key in ('HOTA','DetA','AssA','IDF1','FP','FN','IDSW'))+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'


def frame_guide(manifest, language):
    t = lambda zh,en: pick(language,zh,en)
    suffix = '.en' if language == 'en' else ''
    example = journey.baseline_fp_example(manifest)
    title = t('从误检追到代码', 'Trace a false positive to the code')
    example_link = ''
    if example:
        video, frame = example
        example_link = '<p>' + link(
            journey.baseline_frame_href(language, video, frame),
            t(f'打开 B0 误检示例：视频 {video}，导出帧 {frame} →', f'Open a B0 false positive: video {video}, exported frame {frame} →'),
        ).replace('<a ', '<a id="baseline-fp-example" ', 1) + '</p>'
    return (
        '<aside class="baseline-case-guide"><strong>' + title + '</strong>' + example_link + '<p>'
        + t('在六格图看额外预测，再对照本帧 FP 计数。未匹配的预测是评分上的误检；单帧不足以确定是提示、发现还是关联造成。',
            'Look for the extra prediction in the six panels and compare it with the frame FP count. An unmatched prediction counts as a false positive; one frame does not isolate prompting, discovery or association.')
        + '</p><p>' + link(f'program{suffix}.html?step=diagnose#stage-diagnose', t('查逐帧诊断函数 diagnose() →', 'Inspect the frame diagnosis function diagnose() →'))
        + ' · ' + link(f'program{suffix}.html?step=b0#stage-b0', t('查 B0 预测入口 run_sam() →', 'Inspect the B0 prediction entry run_sam() →'))
        + ' · ' + link('#code', t('本次运行源码快照', 'Source snapshot for this run')) + '</p></aside>'
    )


def content(manifest, language):
    t = lambda zh,en: pick(language,zh,en)
    if not manifest:
        return [('scores',t('真实基线结果','Real-data baseline results'),'<p class="notice">'+t('尚未导入已验证的本地实验。','No verified local run has been imported yet.')+'</p>')]
    prefix = manifest['prefix']
    summary = manifest['summary']
    viewer = manifest['viewer']
    first = viewer['videos'][0]
    total = sum(v['frames'] for v in viewer['videos'])
    blocks = [('scores',t('GT 评分','Ground-truth evaluation'),
        '<p>'+link('program'+('.en' if language=='en' else '')+'.html#evidence',t('结合程序地图解读基线分数 →','Interpret baseline scores with the program map →'))+'</p>'+
        '<p>'+t('A0：YOLO11s-seg 每帧检测 + 按类别 ByteTrack。B0：同一个 YOLO 每 5 步提供框，由 SAM 2.1 Tiny 传播、刷新提示、发现和管理目标；不读取 ByteTrack ID。',
            'A0: YOLO11s-seg on every frame plus per-class ByteTrack. B0: the same YOLO supplies boxes every five exported steps; SAM 2.1 Tiny propagates, refreshes prompts, discovers and manages targets, without ByteTrack IDs.')+'</p>'+score_table(manifest['metrics'],language)+
        '<p class="small">'+t('质量指标显示为 0–100 分。HOTA / DetA / AssA 平均 mask IoU 0.05–0.95 的 19 个阈值；IDF1、FP、FN、IDSW 使用 mask IoU 0.5。先按官方规则合并同类视频，再对五类等权平均质量指标，计数求和。',
            'Quality scores are on a 0–100 scale. HOTA / DetA / AssA average 19 mask-IoU thresholds from 0.05 to 0.95; IDF1, FP, FN and IDSW use mask IoU 0.5. Official rules combine videos within each class, then quality scores are class-macro averaged; counts are summed.')+'</p>'+ '<p>'+link(prefix+'metrics.json',t('全部指标','Full metrics'))+' · '+link(prefix+'evaluator-self-checks.json',t('评分器自检','Evaluator self-checks'))+' · '+link(prefix+'verification.json',t('独立重算验证','Independent replay verification'))+'</p>'+
        '<p class="small">'+t(f'PyTorch 峰值 allocated：YOLO {summary["yolo_peak_allocated_mib"]:.0f} MiB；SAM {summary["sam_peak_allocated_mib"]:.0f} MiB。不是整卡显存占用。本轮使用共享检测缓存，未做暖机端到端 FPS 基准。',
            f'Peak PyTorch allocated memory: YOLO {summary["yolo_peak_allocated_mib"]:.0f} MiB; SAM {summary["sam_peak_allocated_mib"]:.0f} MiB. This is not total GPU memory. This run shares a detector cache and is not a warmed-up end-to-end FPS benchmark.')+'</p>')]
    if manifest.get('correction'):
        blocks.insert(0, ('revision', t('修订记录与归因纠正','Correction record and revised attribution'), revision_notice(manifest, language, full=True)))
    options = ''.join(f'<option value="{v["id"]}">{v["id"]} · {escape(v["focus"])}</option>' for v in viewer['videos'])
    payload = {**viewer,'prefix':prefix,'language':language}
    encoded = json.dumps(payload,ensure_ascii=False).replace('<','\\u003c')
    blocks.append(('viewer',t('逐帧错误检查','Frame-by-frame error inspection'),frame_guide(manifest, language) + f'''
<div id="viewer-controls" hidden><div class="controls"><label>{t('视频','Video')} <select id="video-select">{options}</select></label><button id="prev">{t('上一帧','Previous')}</button><button id="next">{t('下一帧','Next')}</button><output id="position">0</output></div><label for="frame-range">{t('导出帧索引（从 0 开始）','Exported frame index (zero-based)')}</label><input id="frame-range" type="range" min="0" max="{first['frames']-1}" value="0"></div>
<p class="results-legend"><span style="--color:#3c964b">{t('同类前景覆盖','Covered class foreground')}</span><span style="--color:#2d7df5">{t('漏掉的 GT 前景','Missing GT foreground')}</span><span style="--color:#f04632">{t('额外 / 错类前景','Extra / wrong-class foreground')}</span></p>
<p class="small">{t('上排：原图 / GT；中排：A0 预测 / 像素错误；下排：B0 预测 / 像素错误。GT 身份为 channel+1，预测 ID 独立编号，不必数值相等。像素图比较类别并集，不检查同类实例的 ID 互换；身份问题需结合标签、下表和跟踪指标判断。', 'Top: RGB / GT; middle: A0 / pixel errors; bottom: B0 / pixel errors. GT IDs are channel+1; predicted IDs are independently assigned and need not match numerically. Pixel maps compare class unions, not same-class identity swaps: inspect labels, the table and tracking metrics for identity errors.')}</p>
<img id="frame-image" src="{prefix}{first['id']}/visuals/00000.jpg" alt="{t('原图、GT、两套预测与错误六格图','Six-panel RGB, GT, baseline predictions and errors')}"><p id="frame-status" class="small" role="status">{t('启用 JavaScript 可逐帧查看；当前为首段视频第一帧。','Enable JavaScript for frame controls; the first video frame is shown.')}</p><p id="events" class="small"></p>
<div class="table-wrap" id="diagnostic-table" hidden><table><thead><tr>{''.join('<th>'+s+'</th>' for s in [t('方法','Method'),t('GT 实例','GT instance'),t('类别','Class'),t('预测 ID','Predicted ID'),t('最佳 mask IoU','Best mask IoU'),'YOLO box / mask IoU',t('诊断','Diagnostic')])}</tr></thead><tbody id="diagnostic-rows"></tbody></table></div>
<p class="small">{t('最佳 IoU 仅诊断定位，不是跟踪指标。本帧一对一匹配门限为 0.5；“有好 YOLO mask 但无匹配输出”只是关联、确认或生命周期问题的检查线索。B0 非提示帧的 YOLO 缓存只用于事后诊断，没有输入 B0。','Best IoU diagnoses localization, not tracking. Frame matching uses a 0.5 gate; a good YOLO mask without a matched track is a clue for association, confirmation or lifecycle review, not proof of a mechanism failure. Off-schedule YOLO cache entries are diagnostic only and are not fed to B0.')}</p>
<script id="pilot-data" type="application/json">{encoded}</script>'''))
    clips = []
    for v in viewer['videos']:
        key = str(v['id'])
        buttons = ' · '.join(f'<button data-jump-video="{key}" data-jump-frame="{f}">{t("帧","Frame")} {f}</button>' for f in v['worst_frames'])
        clips.append(f'<div id="video-{key}" class="results-video"><h3>{t("视频","Video")} {key} · {escape(v["focus"])}</h3><p>{v["frames"]} {t("帧","frames")} · {buttons}</p><img src="{prefix}{key}/iou-curve.png" loading="lazy" alt="{t("逐帧定位 IoU 曲线","Frame-level localization IoU curves")}"><details><summary>{t("播放六格对比视频（浏览速度 5 fps）","Play six-panel video (browse speed: 5 fps)")}</summary><video controls preload="none" src="{prefix}{key}/comparison.mp4" poster="{prefix}{key}/visuals/00000.jpg"></video></details></div>')
    blocks.append(('curves',t('五段对比视频与曲线','Five comparison clips and curves'),'<p class="small">'+t('曲线是忽略身份的定位诊断。复查按钮按漏检、误检和 ID 变化标记选取；全部帧均保留。5 fps 仅为浏览速度，原始时间戳未知。',
        'Curves diagnose localization and ignore identity. Review buttons use missed/extra outputs and ID-change flags; all frames are retained. Five fps is browsing speed only; source timestamps are unavailable.')+'</p>'+''.join(clips)))
    code_links = ' · '.join(link(prefix+'code/'+name+'.txt',name) for name in summary['source_files'])
    blocks.append(('code',t('代码与运行记录','Code and run records'),'<p>'+link(prefix+'code/README.md.txt',t('中文代码导读','Code reading guide (Chinese)'))+'</p><p>'+t('从 run.py 开始，按数据、YOLO、ByteTrack、SAM、评分、诊断的顺序查阅。下面是本次推理实际使用的源码快照，不是重新运行的结果。',
        'Start with run.py, then follow data, YOLO, ByteTrack, SAM, evaluation and diagnostics. These are source snapshots from the actual inference run; no model was rerun for this page.')+'</p><p>'+code_links+'</p><p>'+link(prefix+'config.json',t('固定参数','Fixed configuration'))+' · '+link(prefix+'summary.json',t('环境与模型哈希','Environment and checkpoint hashes'))+' · '+link(prefix+'input-manifest.json',t('输入来源与哈希','Input provenance and hashes'))+'</p>'))
    order = ('curves', 'scores', 'viewer', 'revision', 'code')
    return sorted(blocks, key=lambda block: order.index(block[0]))


def write_results_pages(output):
    from .recovery_long_page import long_link
    output = Path(output)
    path = output/'pilot-results/manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None
    template = (WEB/'study.html').read_text(encoding='utf-8')
    css = ''.join((WEB/name).read_text(encoding='utf-8') for name in ('tutorial.css','study.css','results.css'))
    script = ''.join((WEB/name).read_text(encoding='utf-8') for name in ('study.js','results.js'))
    for language,name in zip(('zh','en'),PAGES):
        t = lambda zh,en: pick(language,zh,en)
        blocks = content(manifest,language)
        saved = [item for item in (recovery_link(output, language), long_link(output, language)) if item]
        blocks.append(('recovery', t('读完基线：为什么要做 H/R？', 'After the baselines: why compare H/R?'),
                       '<p>' + t('基线说明哪里出错。A0/B0 同时改变检测频率、掩码生成和关联；要判断历史处理的作用，下一步在各自系统内固定纠正框和前史，只比较保留与重置。',
                                'The baselines locate errors. A0/B0 differ in detection frequency, mask generation and association. To study history handling, the next step fixes the prior state and corrective box within each pipeline and compares retention with reset.')
                       + '</p>' + ('<p>' + t('已保存实测：', 'Saved follow-ups: ') + ' · '.join(saved) + '</p>' if saved else '')))
        count = len(manifest['viewer']['videos']) if manifest else 0
        frames = sum(v['frames'] for v in manifest['viewer']['videos']) if manifest else 0
        intro = ''
        if manifest:
            intro = '<p>' + t(f'{count} 段真实视频，{frames} 个导出帧。开发预实验；GT 只用于事后评分。', f'{count} real clips and {frames} exported frames. Development pilot; GT is used only for offline scoring.') + '</p>'
            intro += '<div class="baseline-entry-links">' + ''.join(
                link('#'+key,label).replace('<a ', '<a class="button secondary" ', 1) for key,label in (
                    ('curves',t('看五段对比视频 ↓', 'Watch the comparison clips ↓')),
                    ('scores',t('看 GT 评分 ↓', 'See GT scores ↓')),
                    ('viewer',t('查逐帧错误 ↓', 'Inspect frame errors ↓')),
                )) + '</div>'
            if manifest.get('correction'):
                intro += '<p class="small">' + link('#revision',t('同步修订、复核与归因说明', 'Synchronization correction, verification and attribution')) + '</p>'
        values = {'LANG':t('zh-CN','en'),'TITLE':t('阶段 1：五段 A0/B0 基线','Phase 1: five-clip A0/B0 baselines'),
            'INTRO':intro,
            'HOME':t('index.html','index.en.html'),'OTHER':t('results.en.html','results.html'),
            'CSS':css,'JS':script,'NAV':''.join(link('#'+key,label) for key,label,_ in blocks),
            'BODY':''.join(section(key,label,body) for key,label,body in blocks),
            'SWITCH':t('English','中文'),'BACK':t('返回学习主线','Back to the handbook'),
            'MENU':t('本页目录','On this page'),'THEME':t('切换主题','Theme'),
            'SKIP':t('跳到正文','Skip to content'),'TRAIL':t('研究与实验 · 实际结果','Research and experiments · Actual results'),
            'FOOT':t('默认展示最新验证运行；旧版存档保留，不再用旧 B0 异常推断记忆机制。','The latest verified run is shown by default; legacy artifacts are preserved and legacy B0 anomalies are not evidence about memory.')}
        (output/name).write_text(decorate_page(re.sub(r'@@([A-Z_]+)@@',lambda m:values[m[1]],template),language,'results', output),encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args = parser.parse_args()
    result = import_results(args.source,args.output)
    print(f'Integrated {len(result["viewer"]["videos"])} videos into {args.output / "results.html"}')
