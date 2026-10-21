"""Bilingual, local-only views of audited dataset samples."""
from html import escape
import json
from pathlib import Path
import re

from .study import WEB, link, pick, section

PAGES = ("dataset.html", "dataset.en.html")
NAMES = {'person': '人', 'dog': '狗', 'cat': '猫', 'horse': '马', 'car': '汽车',
         'motorbike': '摩托车', 'squirrel': '松鼠'}


def load_manifest(output):
    path = Path(output) / 'dataset-samples/manifest.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def homepage_summary(output, language):
    if not load_manifest(output):
        return pick(language, '当前页面尚未附带本地数据审计与样本。',
                    'This page does not yet include a local data audit and sample export.')
    return pick(language,
        '本地完整审计：2,985 段视频，其中 300 段带标注，2,685 段仅有 RGB；五个目标类别共覆盖 226 段不同视频。数量足够选取 200 段，但类别明显不均衡，正式划分仍需锁定。',
        'Complete local audit: 2,985 videos, including 300 with labels and 2,685 with RGB only. The five target classes cover 226 distinct labeled videos. A 200-video subset is feasible, but class imbalance and the final split still require attention.')


def viewer(data, language):
    t = lambda zh, en: pick(language, zh, en)
    if not data or not data.get('samples'):
        return '<p class="notice">' + t('未附带样本预览。请先运行本地样本导出工具；以下数据格式说明仍可阅读。',
            'No sample preview is attached. Run the local sample exporter first; the format guide below remains available.') + '</p>'
    first = data['samples'][0]
    options = ''.join(f'<option value="{s["id"]}">{escape(t(NAMES.get(s["focus"], s["focus"]), s["focus"]))} · {s["id"]}</option>' for s in data['samples'])
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('&', '\\u0026')
    return f'''
<p>{t('五段真实标注样本，共 207 帧；展示的是 Ground Truth，不是模型预测。', 'Five real annotated samples, 207 frames in total. These are ground-truth labels, not model predictions.')}</p>
<div id="dataset-viewer" data-language="{language}">
<div id="dataset-controls" hidden>
<div class="dataset-selectors">
<label for="sample-select">{t('视频样本', 'Video sample')}<select id="sample-select">{options}</select></label>
<label for="object-select">{t('实例通道', 'Instance channel')}<select id="object-select"></select></label>
<label for="view-select">{t('标注显示', 'Label view')}<select id="view-select"><option value="overlay">{t('彩色叠加', 'Color overlay')}</option><option value="binary">{t('二值 mask', 'Binary mask')}</option></select></label>
</div>
<div class="controls"><button id="frame-prev">{t('上一帧', 'Previous')}</button><button id="frame-play" aria-pressed="false">{t('播放', 'Play')}</button><button id="frame-next">{t('下一帧', 'Next')}</button>
<label for="browse-speed">{t('浏览速度', 'Browse speed')}<select id="browse-speed"><option value="2">2 fps</option><option value="5" selected>5 fps</option><option value="10">10 fps</option></select></label></div>
<label for="dataset-frame">{t('导出帧索引（从 0 开始）', 'Exported frame index (zero-based)')} · <output id="frame-position" for="dataset-frame">0</output></label>
<input id="dataset-frame" type="range" min="0" max="{first['frames']-1}" value="0" step="1">
</div>
<div class="dataset-panels" id="dataset-panels" aria-busy="false">
<figure><figcaption>{t('原始 RGB 帧', 'Original RGB frame')}</figcaption><img id="dataset-rgb" src="dataset-samples/{first['id']}/rgb/00000.png" width="{first['width']}" height="{first['height']}" alt="{t('真实视频原图', 'Real source video frame')}"></figure>
<figure><figcaption id="mask-caption">{t('真实标注 · 所有实例', 'Ground truth · all instances')}</figcaption><img id="dataset-poster" src="dataset-samples/{first['id']}/poster.png" width="{first['width']}" height="{first['height']}" alt="{t('第一帧真实标注叠加图', 'First-frame ground-truth overlay')}"><canvas id="dataset-mask" hidden role="img" aria-label="{t('当前帧真实标注', 'Current-frame ground truth')}"></canvas></figure>
</div>
<p id="dataset-status" class="small" role="status" aria-live="polite">{t('启用 JavaScript 可逐帧查看；当前为样本第一帧。', 'Enable JavaScript for frame controls; the first sample frame is shown.')}</p>
<p id="dataset-shapes" class="small"></p>
<div class="table-wrap" id="instance-details" hidden><table><thead><tr><th>{t('通道 / 颜色', 'Channel / color')}</th><th>{t('类别 / 像素值', 'Class / value')}</th><th>{t('本帧状态', 'This frame')}</th><th>{t('前景像素数', 'Foreground pixels')}</th></tr></thead><tbody id="instance-rows"></tbody></table></div>
</div>
<p class="small">{t('颜色只区分当前视频内的实例，并不表示类别。选择单个通道可隔离目标；“所有实例 + 二值 mask”显示所选通道的并集。播放速度仅供浏览，数据未提供原始 FPS 或时间戳。', 'Colors distinguish instances within this video, not classes. Select a channel to isolate one target; all instances + binary mask shows their union. Playback speed is for browsing only: original FPS and timestamps are unavailable.')}</p>
<script id="dataset-data" type="application/json">{payload}</script>'''


def content(data, language):
    t = lambda zh, en: pick(language, zh, en)
    home = 'index.en.html' if language == 'en' else 'index.html'
    experiment = 'experiments.en.html' if language == 'en' else 'experiments.html'
    blocks = [('samples', t('逐帧查看真实样本', 'Explore real annotated frames'), viewer(data, language))]
    blocks.append(('format', t('文件里到底是什么', 'What the files contain'),
        '<pre><code>ytvis2021_resized.zip\n  ytvis-validation-000000.tar\n    2686.video.npy          # (30, 320, 568, 3)\n    2686.segmentations.npy  # (30, 320, 568, 4)</code></pre>' +
        '<p>' + t('一段视频不是一个 MP4，而是一组 NumPy 数组。video 的四个维度是“帧数、高、宽、RGB”；segmentations 的最后一维是实例通道数 N，并不是 RGB，也不是固定的类别数量。N 随视频变化。',
            'A video is stored as NumPy arrays rather than an MP4. The video axes are frames, height, width and RGB. The final segmentation axis is the number of instance channels N, not RGB or a fixed number of classes. N varies across videos.') + '</p>' +
        '<pre><code>frame = video[t]                              # RGB, uint8\nmask = segmentations[t, :, :, channel] &gt; 0      # one instance\n# sample 2686: segmentations[0, 209, 234, :] == [26, 0, 0, 0]</code></pre>' +
        '<p>' + t('以样本 2686 为例：通道 0、1 分别是两个人，非零值均为 26；通道 2、3 是两辆摩托车，非零值均为 23。0 表示该通道在该像素没有目标。因此“类别值 26”不能区分两个人，实例身份依赖“视频 ID + 通道索引”。通道内的同一目标应跨导出帧保持对应。',
            'In sample 2686, channels 0 and 1 are two people, both encoded with value 26; channels 2 and 3 are two motorbikes, both encoded with value 23. Zero means no foreground for that channel at that pixel. Class value 26 cannot distinguish the people: instance identity is video ID + channel index. Each channel represents the same annotated target across exported frames.') + '</p>' +
        '<p>' + t('这些预览保留原 RGB 像素和尺寸，使用无损 PNG；显示 mask 时将源数组 > 0 转为透明/白色 PNG，再着色。网页表格保留原类别值与逐帧面积。样本中的摩托车、松鼠等非研究类别也保留，便于理解原始结构。',
            'RGB previews retain source pixels and dimensions as lossless PNGs. Display masks encode source array > 0 as transparent/white PNGs, then apply color. The table retains original category values and per-frame areas. Non-study classes such as motorbikes and squirrels remain visible to explain the source structure.') + '</p>'))
    rows = ''.join(f'<tr><th scope="row">{t(NAMES[k], k)}</th><td>{v}</td><td>{n}</td></tr>' for k,v,n in (
        ('person',198,534),('dog',17,36),('cat',6,7),('horse',12,29),('car',33,94)))
    blocks.append(('coverage', t('完整数据与实验覆盖', 'Dataset coverage and the experiment'),
        '<p>' + homepage_summary_from_data(data, language) + '</p>' +
        '<div class="table-wrap"><table><thead><tr><th>' + t('目标类别','Target class') + '</th><th>' + t('包含该类的视频','Videos containing class') + '</th><th>' + t('实例轨迹','Instance tracks') + '</th></tr></thead><tbody>' + rows + '</tbody></table></div>' +
        '<p>' + t('一段视频可包含多个类别，所以上表视频数不能相加。五类去重后为 226 段；猫仅有 6 段，不能称为平衡数据集。300 段标注样本共 10,949 个导出帧，单段 12–62 帧，短边均为 320 像素。',
            'Videos may contain multiple classes, so class counts cannot be added. Their union is 226 videos; only six contain cats. This is not a balanced dataset. The 300 labeled samples contain 10,949 exported frames, 12–62 per sample, with a 320-pixel short side.') + '</p>' +
        '<p>' + t('计划仍是 200 段、120/40/40 的开发/验证/评估划分。同一视频及其全部实例必须留在同一组。当前 seed 550 选择器会把马全部分到开发集，不能直接作为最终划分；本地可行性检查已证明可通过视频交换让三组均包含五类，但正式清单尚未冻结，稀少类别的统计结论需谨慎。',
            'The plan remains 200 videos with a 120/40/40 development/validation/evaluation split. A video and all its instances must stay in one split. The current seed-550 selector places all horses in development, so it cannot be accepted unchanged. A local feasibility check found video swaps that give all three splits five-class coverage, but the final manifest is not frozen; rare-class conclusions require caution.') + '</p>' +
        '<p>' + t('SlotCurri 的 train/validation 是从原始已标注训练集内部划分的导出，不是官方挑战赛的 validation。其 2,685 段 train 导出只含视频，300 段 validation 导出才含 mask；不要误把 2,985 段都算作可直接评估的标注视频。',
            'SlotCurri train/validation are internal exports from the original labeled training set, not the official challenge validation set. Its 2,685 training exports contain video only; the 300 validation exports include masks. Do not count all 2,985 as directly evaluable labeled videos.') + '</p>'))
    blocks.append(('usage', t('怎样用于我们的实验', 'How these data enter our experiment'),
        '<ol><li>' + t('原图输入模型；GT mask 用于评分，不当作模型预测。模型不知道网页上这些颜色。', 'Feed RGB frames to the models; use GT masks for scoring, not as predictions. The models do not see these display colors.') + '</li><li>' +
        t('受控恢复实验可以从 GT 构造初始化或纠错框，但两种记忆条件必须使用相同提示与时点，并单独说明这是受控提示协议。', 'Controlled recovery can derive initialization or correction boxes from GT, but both memory conditions must receive the same prompts at the same times, explicitly under a controlled-prompt protocol.') + '</li><li>' +
        t('当前只能验证导出数组内部的尺寸、类别和实例通道一致性。原始 annotation ID、帧文件名、时间戳和 FPS 未附带，不能把导出帧差直接当作秒数或原始连续帧差。', 'The audit verifies internal array dimensions, class values and instance-channel consistency. Original annotation IDs, frame filenames, timestamps and FPS are absent. Exported frame gaps cannot be treated as seconds or consecutive original-frame gaps.') + '</li></ol>' +
        '<p>' + link(experiment, t('查看四组对照与记忆恢复实验流程 →', 'View the four conditions and memory-recovery workflow →')) + ' · ' + link(home+'#proposal', t('最新版 proposal', 'Latest proposal')) + '</p>' +
        '<p>' + link('https://github.com/wjun0830/SlotCurri', 'SlotCurri') + ' · ' + link('https://github.com/wjun0830/SlotCurri/blob/b3e676c966af554cde9921a90072930b730f291c/data/save_ytvis2021.py', t('导出脚本', 'Export script')) + ' · ' + link('https://drive.google.com/file/d/1Iv-2zK6MnH0oDFTx9iBgQcPNh5PBzM7i/view?usp=sharing', t('数据来源（Google Drive）','Data source (Google Drive)')) + '</p>'))
    return blocks


def homepage_summary_from_data(data, language):
    return pick(language,
        '以下为本地完整数据审计结果（2026-10-17）：2,985 段视频，300 段带标注，2,685 段仅 RGB；114 个 TAR 分片已校验，标注数组尺寸均与视频匹配。' if data else '以下数量来自 2026-10-17 的完整本地审计；此页面暂未附带样本文件。',
        'Complete local audit, 2026-10-17: 2,985 videos, 300 with labels and 2,685 RGB-only. All 114 TAR shards were verified, and mask dimensions match their videos.' if data else 'Counts below come from the complete local audit on 2026-10-17; sample assets are not attached to this page.')


def write_dataset_pages(output):
    output = Path(output)
    data = load_manifest(output)
    template = (WEB/'study.html').read_text(encoding='utf-8')
    css = ''.join((WEB/name).read_text(encoding='utf-8') for name in ('tutorial.css','study.css','dataset.css'))
    script = ''.join((WEB/name).read_text(encoding='utf-8') for name in ('study.js','dataset.js'))
    for language, name in zip(('zh','en'), PAGES):
        t = lambda zh, en: pick(language, zh, en)
        blocks = content(data, language)
        values = {'LANG':t('zh-CN','en'), 'TITLE':t('数据与真实样本','Data and real samples'),
            'INTRO':'<p>'+t('先看原图和真实标注，再理解数据结构及实验约束。','Start with source frames and ground truth, then inspect the format and experimental constraints.')+'</p>',
            'HOME':t('index.html','index.en.html'), 'CSS':css, 'JS':script,
            'NAV':''.join(link('#'+key,label) for key,label,_ in blocks),
            'BODY':''.join(section(key,label,body) for key,label,body in blocks),
            'OTHER':t('dataset.en.html','dataset.html'), 'SWITCH':t('English','中文'),
            'BACK':t('返回学习主线','Back to the handbook'), 'MENU':t('本页目录','On this page'),
            'THEME':t('切换主题','Theme'), 'SKIP':t('跳到正文','Skip to content'),
            'TRAIL':t('研究与实验 · 数据','Research and experiments · Data'),
            'FOOT':t('更新：2026-10-17。真实样本预览不包含模型推理结果。','Updated 2026-10-17. Real-data previews contain no model predictions.')}
        from .navigation import decorate_page
        (output/name).write_text(decorate_page(re.sub(r'@@([A-Z_]+)@@',lambda m: values[m[1]],template),language,'dataset'),encoding='utf-8')
