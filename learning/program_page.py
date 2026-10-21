"""Bilingual experiment map: read source and saved evidence, never run models."""

import ast
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re

from .study import WEB, link, pick, section
from .navigation import decorate_page
from .baseline_revision import revision_notice
from .recovery_page import read_recovery, recovery_link

PAGES = ("program.html", "program.en.html")
SOURCE_ROOT = Path(__file__).resolve().parents[1] / "experiments/tracking_lab"
SOURCE_FILES = (
    "run.py",
    "dataset.py",
    "detector.py",
    "bytetrack.py",
    "sam_baseline.py",
    "sam_io.py",
    "evaluate.py",
    "diagnose.py",
    "report.py",
    "render.py",
    "verify.py",
    "runtime.py",
    "common.py",
    "__init__.py",
)

# These are navigation data, not a second implementation of the experiment.
STEPS = (
    (
        "data",
        ("组织视频输入", "Organize video inputs"),
        (("dataset.py", "read_manifest"),),
        (
            "固定的视频清单、样本 manifest、原图路径",
            "Fixed video selection, sample manifest and image paths",
        ),
        (
            "核对文件与尺寸，按时间顺序组织每段视频。此时不加载评分用的 GT mask。",
            "Validate files and dimensions; organize each video's ordered frames. Do not load GT masks for scoring here.",
        ),
        (
            "videos：每段视频的编号、帧路径、宽高",
            "videos: video IDs, frame paths, width and height",
        ),
        (
            "没有把整段视频一次塞进 YOLO；先整理路径。",
            "This organizes paths; it does not feed an entire video to YOLO at once.",
        ),
    ),
    (
        "yolo",
        ("生成共享 YOLO 观测", "Generate shared YOLO observations"),
        (("detector.py", "detect_video"),),
        (
            "YOLO11s-seg、视频帧、固定配置",
            "YOLO11s-seg, video frames and fixed configuration",
        ),
        (
            "逐帧读取图片并调用 model.predict()，保留五类目标的预测。",
            "Read one image at a time and call model.predict(); retain predictions for the five target classes.",
        ),
        (
            "observations：逐帧的类别、框、分数、mask；stats：运行记录",
            "observations: per-frame classes, boxes, scores and masks; stats: runtime records",
        ),
        (
            "YOLO 的帧内编号不是跨帧跟踪 ID。A0/B0 在共同调用时刻共享相同检测数值。",
            "YOLO's within-frame index is not a tracking identity. A0/B0 share identical detector values at common call times.",
        ),
    ),
    (
        "a0",
        ("A0：交给 ByteTrack", "A0: hand observations to ByteTrack"),
        (("bytetrack.py", "run_bytetrack"),),
        (
            "每一帧的 YOLO 观测、ByteTrack 配置",
            "YOLO observations on every frame and ByteTrack settings",
        ),
        (
            "按类别维护跟踪器；tracker.update() 关联框和身份，再取回对应 YOLO mask。",
            "Maintain class-separated trackers; tracker.update() associates boxes and identities, then the adapter retrieves the corresponding YOLO mask.",
        ),
        (
            "a：带跟踪 ID 的 A0 预测；trace：内部状态日志",
            "a: A0 predictions with track IDs; trace: internal-state log",
        ),
        (
            "ByteTrack 不看原图来分割，不能凭空补出 YOLO 没有生成的 mask。",
            "ByteTrack does not segment the image or invent masks absent from YOLO.",
        ),
    ),
    (
        "b0",
        ("B0：框提示交给 SAM", "B0: send box prompts to SAM"),
        (
            ("sam_baseline.py", "run_sam"),
            ("sam_io.py", "synchronized_sam_offload"),
            ("sam_baseline.py", "_run_sam"),
            ("sam_baseline.py", "init_png_state"),
            ("sam_baseline.py", "propagate_one"),
        ),
        (
            "SAM 2.1、原图、YOLO 框／类别／分数",
            "SAM 2.1, images and YOLO boxes/classes/scores",
        ),
        (
            "初始化视频状态；每帧传播已有目标，每 5 个导出帧步用 YOLO 框发现／刷新目标。add_new_points_or_box() 将框传给 SAM。",
            "Initialize video state; propagate existing targets every frame and use YOLO boxes every five exported steps for discovery/refresh. add_new_points_or_box() passes a box to SAM.",
        ),
        (
            "b：SAM mask 与目标 ID；events：发现／刷新／删除事件；stats：运行记录",
            "b: SAM masks and target IDs; events: discovery/refresh/retirement; stats: runtime records",
        ),
        (
            "不使用 YOLO mask 或 ByteTrack ID。目标编号、类别和生命周期由我们的包装逻辑维护。",
            "It uses neither YOLO masks nor ByteTrack IDs. Our wrapper manages IDs, labels and lifecycle.",
        ),
    ),
    (
        "gt",
        ("推理后读取 GT", "Load GT after inference"),
        (("dataset.py", "load_ground_truth"),),
        (
            "所选视频的实例通道标注",
            "Instance-channel annotations for the selected videos",
        ),
        (
            "构造逐帧真实目标：固定身份、类别和可见 mask。分别与 A0、B0 配对。",
            "Build per-frame annotated identities, classes and visible masks; pair the same GT with A0 and B0 separately.",
        ),
        (
            "evaluation：每个方法／视频对应一对 (gt, prediction)",
            "evaluation: a (gt, prediction) pair for each method/video",
        ),
        (
            "GT 不进入自动推理。预测 ID 不必与 GT 的整数编号相同。",
            "GT does not enter automatic inference. Predicted and GT identity integers need not match.",
        ),
    ),
    (
        "diagnose",
        ("逐帧定位问题", "Locate frame-level problems"),
        (("diagnose.py", "diagnose"),),
        (
            "GT、某一套预测、原始 YOLO 缓存",
            "GT, one pipeline's predictions and the original YOLO cache",
        ),
        (
            "检查未匹配目标、额外预测、mask 重叠及 ID 变化标记；提供回看线索。",
            "Inspect unmatched targets, extra predictions, mask overlap and ID-change flags; provide review clues.",
        ),
        (
            "A0/B0/diagnostics.json：逐帧诊断和摘要",
            "A0/B0/diagnostics.json: per-frame diagnostics and summaries",
        ),
        (
            "诊断不是因果结论；最佳 IoU 和局部 ID 标记不替代正式跟踪指标。非提示帧的 YOLO 缓存只作事后诊断。",
            "Diagnostics are not causal conclusions. Best IoU and local ID flags do not replace tracking metrics. Off-schedule YOLO cache entries are diagnostic only.",
        ),
    ),
    (
        "scores",
        ("计算正式评分", "Compute official scores"),
        (("evaluate.py", "evaluate_all"), ("evaluate.py", "similarity_data")),
        (
            "A0/GT、B0/GT 配对及已验证的评分器",
            "A0/GT and B0/GT pairs plus validated metric objects",
        ),
        (
            "按类别构造 mask IoU 与身份输入，调用固定版本 TrackEval，合并视频及类别结果。",
            "Build class-aware mask-IoU and identity inputs; call pinned TrackEval and combine video/class results.",
        ),
        (
            "metrics.json：HOTA、DetA、AssA、IDF1、FP、FN、IDSW",
            "metrics.json: HOTA, DetA, AssA, IDF1, FP, FN and IDSW",
        ),
        (
            "质量分数按类别等权汇总；计数求和。不能仅看平均 mask IoU 就判断跟踪好坏。",
            "Quality scores use class-macro aggregation; counts are summed. Mean mask IoU alone does not establish tracking quality.",
        ),
    ),
    (
        "report",
        ("生成报告并复核", "Build reports and verify"),
        (("report.py", "build"), ("render.py", "comparison"), ("verify.py", "verify")),
        (
            "已经保存的预测、评分、诊断和原图",
            "Saved predictions, scores, diagnostics and images",
        ),
        (
            "单独生成六格图、视频和曲线；复核输入指纹、A0 回放、B0 事件安排及指标重算。",
            "Separately render six-panel figures, videos and curves; verify fingerprints, A0 replay, B0 schedules and recomputed scores.",
        ),
        (
            "对照报告、视频、曲线；verification.json",
            "Comparison report, videos, curves and verification.json",
        ),
        (
            "report 与 verify 是后处理入口，不由 run.py 自动完成；不会重新运行神经模型。网站只展示保存的结果。",
            "report and verify are separate post-processing commands, not automatic parts of run.py. They do not rerun neural inference; the website displays saved evidence.",
        ),
    ),
)


def table(headers, rows, key):
    return (
        f'<div class="table-wrap"><table id="{key}"><thead><tr>'
        + "".join(f'<th scope="col">{x}</th>' for x in headers)
        + "</tr></thead><tbody>"
        + "".join(
            "<tr>" + "".join(f"<td>{x}</td>" for x in row) + "</tr>" for row in rows
        )
        + "</tbody></table></div>"
    )


def source_catalog(output):
    """Export only reviewed Python files; never import experiment code."""
    destination = Path(output) / "program-code"
    destination.mkdir(exist_ok=True)
    catalog = {}
    for name in SOURCE_FILES:
        raw = (SOURCE_ROOT / name).read_bytes()
        text = raw.decode("utf-8")
        functions = {
            node.name: node.lineno
            for node in ast.parse(text).body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))
        }
        catalog[name] = {"sha256": sha256(raw).hexdigest(), "functions": functions}
        (destination / (name + ".txt")).write_bytes(raw)
        for language in ("zh", "en"):
            t = lambda zh, en: pick(language, zh, en)
            suffix = ".en" if language == "en" else ""
            lines = "".join(
                f'<span id="L{number}" class="source-line"><a href="#L{number}">{number}</a> {escape(line)}\n</span>'
                for number, line in enumerate(text.splitlines(), 1)
            )
            nav = " · ".join(
                link(f"#L{line}", function) for function, line in functions.items()
            )
            css = (WEB / "tutorial.css").read_text(encoding="utf-8")
            page = f"""<!doctype html><html lang="{t('zh-CN','en')}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{name} · CS550</title><style>{css}
body{{padding:24px;max-width:1200px;margin:auto}}pre{{white-space:pre;max-width:100%;overflow:auto}}.source-line:target{{background:#25453a;color:#fff}}.source-line>a{{display:inline-block;min-width:3ch;text-align:right;user-select:none}}nav{{overflow-wrap:anywhere}}</style></head><body>
<p>{link('../program'+suffix+'.html#steps',t('← 返回程序地图','← Back to the program map'))} · {link(name+('.en' if language=='zh' else '')+'.html',t('English','中文'))} · {link(name+'.txt',t('原始文本','Plain source'))}</p>
<h1>{name}</h1><p>{t('当前工作区源码参考，不是历史实验的不可变快照。','Current workspace reference, not an immutable historical inference snapshot.')}</p><p class="small">SHA-256: {catalog[name]['sha256']}</p><nav>{nav}</nav><pre><code>{lines}</code></pre></body></html>"""
            (destination / (name + suffix + ".html")).write_text(page, encoding="utf-8")
    (destination / "manifest.json").write_text(
        json.dumps({"kind": "current-source-reference", "files": catalog}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return catalog


def read_evidence(output):
    path = Path(output) / "pilot-results/manifest.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not re.fullmatch(r"pilot-results/[A-Za-z0-9_-]+/", data["prefix"]):
        raise ValueError("Unsafe evidence prefix")
    if data["summary"]["status"] != "completed":
        raise ValueError("Evidence is not a completed run")
    for name, key in (
        ("metrics.json", "metrics"),
        ("viewer-data.json", "viewer"),
        ("verification.json", None),
    ):
        raw = (Path(output) / data["prefix"] / name).read_bytes()
        if sha256(raw).hexdigest() != data["files"][name]:
            raise ValueError(f"Evidence fingerprint differs: {name}")
        value = json.loads(raw)
        if key and value != data[key]:
            raise ValueError(f"Embedded evidence differs: {name}")
        if not key and value["status"] != "passed":
            raise ValueError("Evidence verification did not pass")
    if "correction" in data:
        raw = (Path(output) / data["prefix"] / "correction-audit.json").read_bytes()
        if (
            sha256(raw).hexdigest() != data["files"]["correction-audit.json"]
            or json.loads(raw) != data["correction"]
        ):
            raise ValueError("Correction audit fingerprint differs")
    return data


def candidate_table(evidence, language, hr=None):
    t = lambda zh, en: pick(language, zh, en)
    draft = evidence.get("correction", {}).get("next_candidates") if evidence else None
    if not draft:
        return ""
    rows = []
    for event in draft["events"]:
        anchors = event["anchors"]
        ids = " / ".join(
            str(anchors[m]["prediction_id"]) if anchors[m] else "—"
            for m in ("A0", "B0")
        )
        conditions = [
            name
            for name, eligible in event["condition_eligibility"].items()
            if eligible
        ]
        rows.append(
            [
                f'{event["video_id"]} / {event["frame"]} / GT{event["gt_id"]} ({event["category"]})',
                ids,
                (
                    ", ".join(conditions)
                    if conditions
                    else t("排除：无既有锚点", "Excluded: no prior anchor")
                ),
                (
                    t("已完成本批 H/R", "Completed in this H/R batch")
                    if hr and event["name"] in {e["name"] for e in hr["events"]}
                    else t(
                        "未运行" if conditions else "排除",
                        "Not run" if conditions else "Excluded",
                    )
                ),
            ]
        )
    return (
        "<h3>"
        + t("事件资格与执行状态", "Event eligibility and execution status")
        + "</h3>"
        + table(
            [
                t("视频 / 步 / 对象", "Video / step / target"),
                t("固定前史 ID：A / B", "Fixed prefix ID: A / B"),
                t("可用纠正条件", "Eligible correction conditions"),
                t("执行状态", "Execution status"),
            ],
            rows,
            "corrected-candidate-eligibility",
        )
        + '<p class="small">'
        + t(
            "yolo 为实际检测框，reference 为标注外接框；缺失条件不补造。资格来源是基线修订时的草案；完成状态来自最新 H/R 记录，其余事件仍未执行。",
            "yolo means actual detector boxes; reference means annotation-derived boxes. Missing conditions are not fabricated. Eligibility comes from the baseline-correction draft; completion comes from the latest H/R record. Other events remain unrun.",
        )
        + " "
        + link(
            evidence["prefix"] + "correction-audit.json", t("检查记录", "Audit record")
        )
        + "</p>"
    )


def content(language, catalog, evidence, hr=None):
    t = lambda zh, en: pick(language, zh, en)
    suffix = ".en" if language == "en" else ""
    sections = []

    def add(key, zh, en, body):
        title = t(zh, en)
        sections.append((key, title, section(key, title, body)))

    def code(name, function):
        line = catalog[name]["functions"][function]
        return link(
            f"program-code/{name}{suffix}.html#L{line}",
            f"{name} → {function}() · L{line}",
        )

    add(
        "map",
        "一张图看完整程序",
        "The complete program at a glance",
        f"""
<p>{t('总调度入口是','The coordinator is')} {code('run.py','main')} → {code('run.py','execute')}{t('。下面是逻辑数据流，不是并行执行图。','. The diagram shows logical data flow, not concurrent execution.')}</p>
<div class="program-flow" aria-label="{t('基线程序数据流','Baseline data flow')}">
<a class="flow-node" href="#stage-data">01 · {t('有序原图路径','Ordered image paths')}<small>dataset.read_manifest()</small></a><span class="flow-arrow" aria-hidden="true">↓</span>
<a class="flow-node" href="#stage-yolo">02 · YOLO<small>{t('类别／框／分数／mask → 共享缓存','Classes / boxes / scores / masks → shared cache')}</small></a><span class="flow-arrow" aria-hidden="true">↓</span>
<div class="program-branches"><a class="flow-node branch-a" href="#stage-a0">A0 · ByteTrack<small>{t('每帧框与分数 → 轨迹 ID；沿用 YOLO mask','Per-frame boxes/scores → track IDs; retain YOLO masks')}</small></a><a class="flow-node branch-b" href="#stage-b0">B0 · SAM 2.1<small>{t('原图＋周期性 YOLO 框 → SAM mask；不接收 YOLO mask','Images + periodic YOLO boxes → SAM masks; no YOLO masks')}</small></a></div><span class="flow-arrow" aria-hidden="true">↓</span>
<a class="flow-node" href="#stage-gt">{t('推理结束，才读取 GT','Load GT only after inference')}<small>{t('A0 ↔ GT；B0 ↔ 同一 GT','A0 ↔ GT; B0 ↔ the same GT')}</small></a><span class="flow-arrow" aria-hidden="true">↓</span>
<div class="program-branches"><a class="flow-node" href="#stage-diagnose">{t('逐帧诊断：哪里错了？','Frame diagnostics: where did it fail?')}<small>diagnose()</small></a><a class="flow-node" href="#stage-scores">{t('正式评分：整体怎样？','Official scores: how well overall?')}<small>evaluate_all() → TrackEval</small></a></div><span class="flow-arrow" aria-hidden="true">↓</span>
<a class="flow-node" href="#stage-report">{t('独立后处理：报告、视频、复核','Separate post-processing: reports, videos, verification')}<small>report.build() / verify.verify()</small></a></div>
<p class="status-note">{t('已跑通：五段／207 帧基线与 24 个 H/R 开发分支。正常 B0 入口现包含 CPU 卸载同步保护；正式 200 段实验及事件集仍待冻结。','Completed: five-clip / 207-frame baselines and 24 H/R development branches. Normal B0 now includes the CPU-offload fence; the formal 200-video experiment and event set remain unfrozen.')}</p>
<p>{t('实验代码独立位于 experiments/tracking_lab；learning 只生成学习页面、展示已保存结果。','Scientific code lives independently in experiments/tracking_lab; learning only builds teaching pages and displays saved evidence.')}</p>""",
    )

    buttons, cards = [], []
    for index, (key, titles, functions, inputs, action, outputs, boundary) in enumerate(
        STEPS
    ):
        buttons.append(
            f'<button type="button" data-program-step="{key}" aria-controls="stage-{key}">{index+1:02d} · {t(*titles)}</button>'
        )
        cards.append(
            f"""<article class="program-stage" id="stage-{key}" data-program-panel="{key}"><p class="small">{t('实验步骤','Experiment step')} {index+1:02d} / 08</p><h3>{t(*titles)}</h3><p class="function-route">{'<br>'.join(code(*function) for function in functions)}</p><dl><dt>{t('输入','Input')}</dt><dd>{t(*inputs)}</dd><dt>{t('职责','Responsibility')}</dt><dd>{t(*action)}</dd><dt>{t('输出交给下一步','Output passed onward')}</dt><dd>{t(*outputs)}</dd></dl><p class="status-note">{t(*boundary)}</p></article>"""
        )
    add(
        "steps",
        "按步骤查文件与函数",
        "Find the file and function by experiment step",
        "<p>"
        + t(
            "先看输入、职责和输出；点函数链接才进入源码。按钮只切换说明，不执行实验。",
            "Read inputs, responsibility and outputs first; open a function link only when needed. Controls navigate explanations; they do not execute experiments.",
        )
        + '</p><div class="program-step-controls" id="program-controls" hidden><div class="program-step-nav">'
        + "".join(buttons)
        + '</div><p id="program-position" class="small" role="status"></p><button id="program-show-all" type="button">'
        + t("展开全部步骤", "Show all steps")
        + '</button></div><div id="program-stages">'
        + "".join(cards)
        + "</div><noscript><p>"
        + t(
            "未启用 JavaScript：全部步骤仍按顺序显示。",
            "Without JavaScript, every step remains visible in order.",
        )
        + "</p></noscript>",
    )

    add(
        "calls",
        "谁调用谁：主程序调用树",
        "Who calls whom: coordinator call tree",
        '<pre class="call-tree"><code>'
        + escape(
            """run.main()
└─ run.execute(args)
   ├─ configure_runtime() / environment() / metric_objects() / self_checks()
   ├─ checked_weight() / dataset.read_manifest()
   ├─ for each video:
   │  ├─ detector.detect_video() → model.predict()
   │  └─ bytetrack.run_bytetrack() → tracker.update()
   ├─ for each video:
   │  └─ sam_baseline.run_sam()
   │     └─ with sam_io.synchronized_sam_offload(): _run_sam()
   │        ├─ init_png_state() → predictor.init_state()
   │        ├─ propagate_one() → predictor.propagate_in_video()
   │        └─ predictor.add_new_points_or_box() / propagate_in_video_preflight()
   ├─ dataset.load_ground_truth() / diagnose.diagnose()
   └─ evaluate.evaluate_all() → metric.eval_sequence()

Separate commands:
report.build() → render.comparison()
verify.verify() → replay / rescore"""
        )
        + "</code></pre><p>"
        + t(
            "这是函数职责图；具体循环与调用位置以当前源码为准。每段视频先缓存 YOLO 并完成 A0，之后完成各视频 B0，再加载 GT。",
            "This is a responsibility map; inspect current source for exact loop placement. Each video first caches YOLO and runs A0; B0 then runs for the videos, followed by GT loading.",
        )
        + "</p>",
    )

    add(
        "evidence",
        "用真实结果理解分数与失败",
        "Read scores and failures together",
        evidence_content(language, evidence)
        + (
            "<p>"
            + link(
                "recovery" + suffix + ".html",
                t(
                    "下一步：骑手／猫 H/R 实测、视频与分析 →",
                    "Next: rider/cat H/R measurements, videos and analysis →",
                ),
            )
            + "</p>"
            if hr
            else ""
        ),
    )

    groups = [
        [
            "A-H",
            t(
                "保留 ByteTrack 运动状态；用同一纠正框正常更新。",
                "Retain ByteTrack motion state; update normally using the same correction box.",
            ),
        ],
        [
            "A-R",
            t(
                "纠正框重建位置和尺寸，速度归零，协方差默认初始化。",
                "Reinitialize position/size from the box, zero velocity and use default initial covariance.",
            ),
        ],
        [
            "B-H",
            t(
                "保留 SAM 该目标历史，加入同一个框提示。",
                "Retain that SAM target’s history and add the same box prompt.",
            ),
        ],
        [
            "B-R",
            t(
                "清除该目标旧提示、视觉记忆及相关状态，用同一个框重新初始化。",
                "Clear that target’s old prompts, visual memory and related state; initialize from the same box.",
            ),
        ],
    ]
    add(
        "recovery",
        "历史保留／重置：逻辑与实现",
        "History retention/reset: logic and implementation",
        f"""
<p class="status-note">{t('以下是已批准的对照逻辑与事件选择动机。旧的骑手／马异常不能作为失败依据；使用同步修正版基线。哪些事件已完成，见下表与 H/R 实测入口。','Below are the approved comparison logic and event-selection rationale. Legacy rider/horse anomalies are not valid failure evidence; use corrected baselines. See the table and H/R measurement link for completed events.')}</p>
<ol class="recovery-route"><li>{t('选定视频、目标和纠正时刻 t；仅纳入仍有可操作旧状态的配对事件。缺少可保留状态的事件另报。','Fix video, target and correction time t. Include paired events with operable old state; report ineligible events separately.')}</li><li>{t('运行到 t 之前，分别复制 A 或 B 自己的状态；H/R 共享相同前史。','Run to just before t and fork each pipeline’s own state; H/R share the same prefix.')}</li><li>{t('两边获得同一框、附带信息与目标对应关系，且只处理一次。H 也接受纠正；参考基线另保留。','Both receive the same box, accompanying information and target routing, consumed once. H is corrected too; retain the uncorrected baseline separately.')}</li><li>{t('只改变历史处理，不改权重、外部 ID、纠正后存活状态或其他目标。','Change history treatment only, not weights, external ID, post-correction alive status or other targets.')}</li><li>{t('恢复正常输入：A 每帧检测；B 按固定安排自动刷新。窗口内不追加人工／GT 纠正，允许预测和关联自行分歧。','Resume normal inputs: per-frame detection for A and the fixed refresh schedule for B. No further manual/GT corrections; predictions and associations may diverge.')}</li><li>{t('排除纠正当帧，固定指定轨迹，比较之后是否恢复、用了多久、保持多久、是否复发。','Exclude the corrected frame; follow the designated track and compare subsequent recovery, latency, duration and relapse.')}</li></ol>
{table([t('组别','Group'),t('唯一改变的历史处理','History treatment')],groups,'program-recovery-groups')}
<p>{t('实际 YOLO 框与当前帧 GT 参考框分条件报告。人为指定框属于哪个目标，只用于机制实验，不证明自动重识别已经解决。后续不能用 GT 替系统重新路由。','Report actual YOLO boxes and current-frame GT reference boxes as separate conditions. Manual target routing is a mechanism-study control, not evidence that automatic re-identification is solved; do not use GT to reroute later inputs.')}</p>
<div class="program-notes">
<div><h3>{t('猫：先分清记忆与生命周期','Cat: separate history from lifecycle')}</h3><p>{t('2689/35 仍准确，36 步却按保留期限删除 ID1，45 步才发现新 ID。35 步只有参考框条件；20 步则适合作为可靠视觉历史对照。两种事件不要混称为记忆漂移。','2689/35 is still accurate, but the retention rule deletes ID1 at 36 and rediscovers a new ID at 45. Step 35 supports reference boxes only; step 20 is a reliable-visual-history control. Neither observation alone proves memory drift.')}</p></div>
<div><h3>{t('骑手：单目标重置能解决重复轨迹吗？','Riders: can one-target reset resolve duplicate tracks?')}</h3><p>{t('2686/7 有两个 mask 竞争同一骑手。固定最初锚定 ID，不随最佳 IoU 换号；指定目标质量与全画面 FP 分别报告。这个候选尚未纳入骑手／猫实测批次。','At 2686/7 two masks compete for one rider. Fix the original anchored ID; do not switch to the best-IoU identity. Report target quality separately from frame-wide FPs. This candidate is not part of the measured rider/cat batch.')}</p></div>
<div><h3>{t('马术：研究真正分不好的骑手','Equestrian: study the genuinely poor rider mask')}</h3><p>{t('2718/14 的马正常，骑手 B0 mask IoU 约 0.32，YOLO mask 约 0.65、框约 0.77。这是选择 rider GT1 做同框 H/R 的动机，不是历史有害的证明。实际差异和条件敏感性见实测页。','At 2718/14 the horse is fine, but rider B0 mask IoU is about 0.32 versus YOLO mask 0.65 and box 0.77. This motivates same-box H/R for rider GT1; it does not prove harmful history. See measured results for actual differences and condition sensitivity.')}</p></div></div>
<p>{link('experiments'+suffix+'.html#walkthrough',t('完整受控事件流程 →','Full controlled-event walkthrough →'))} · {link('index'+suffix+'.html#proposal',t('已批准 proposal →','Approved proposal →'))}</p>"""
        + candidate_table(evidence, language, hr)
        + (
            "<p>"
            + link(
                "recovery" + suffix + ".html",
                t(
                    "已完成的 16 分支：看实测结果 →",
                    "Completed 16 branches: inspect measurements →",
                ),
            )
            + "</p>"
            if hr
            else ""
        ),
    )

    recovery_rows = [
        [
            t("恢复成功", "Recovered"),
            t(
                "指定 ID 仍跟指定对象；定位达到锁定门槛；连续多个可评估标注时刻正确。",
                "The designated track follows the intended object, meets the locked localization threshold and remains correct for consecutive evaluable annotated times.",
            ),
        ],
        [
            t("不能冒充恢复", "Not recovery"),
            t(
                "ID 没变却跟错对象；每帧挑另一个 IoU 最大的预测；只看纠正当帧。",
                "An unchanged ID on the wrong object; choosing a new best-overlap prediction each frame; judging only the corrected frame.",
            ),
        ],
        [
            t("可见／不可见", "Visibility"),
            t(
                "可见而丢失／空输出计失败；不可见时单独统计错误输出，不凭空假设遮挡 GT。",
                "Missing/empty output for a visible target fails; score erroneous output during absence separately, without inventing occluded GT.",
            ),
        ],
        [
            t("报告内容", "Readouts"),
            t(
                "恢复比例与时间、正确保持时长、复发；未恢复事件不从分母删除。ByteTrack 加看运动／关联，SAM 加看漂移和错误前景。",
                "Recovery proportion/time, correct duration and relapse; retain unrecovered events in the denominator. Add motion/association diagnostics for ByteTrack and drift/false foreground for SAM.",
            ),
        ],
        [
            t("规则尚未锁定", "Not locked yet"),
            t(
                "IoU 门槛、连续成功次数、窗口和可见性处理须在开发／验证阶段确定，查看保留评估前锁定；例如 0.5＋三个时刻仅是候选示例。",
                "Choose localization threshold, success streak, window and visibility handling on development/validation and freeze before held-out evaluation; 0.5 plus three times is an illustration only.",
            ),
        ],
    ]
    add(
        "criteria",
        "怎样判断恢复，怎样汇总",
        "Define recovery and aggregate fairly",
        table(
            [t("项目", "Item"), t("规则", "Rule")],
            recovery_rows,
            "program-recovery-criteria",
        )
        + "<p>"
        + t(
            "按实际导出步／标注时刻画 H/R 配对曲线，不换算成未知的原始视频秒数。先比较 A-R−A-H、B-R−B-H；同一视频内先汇总事件，避免事件多的视频主导结论。跨系统绝对分数不能隔离记忆种类的优劣。",
            "Plot paired H/R curves in actual exported steps / annotation times, not unknown source seconds. Compare A-R−A-H and B-R−B-H first; aggregate events within each video before across videos. Cross-system absolute scores cannot isolate memory type.",
        )
        + "</p>",
    )

    add(
        "support",
        "需要时再看：启动与校验",
        "Optional: startup and validation",
        '<details id="support-details"><summary>'
        + t(
            "展开辅助函数和变量，不影响主线阅读",
            "Expand helper functions and variables",
        )
        + "</summary>"
        + table(
            [t("职责", "Role"), t("文件／函数或变量", "File/function or variable")],
            [
                [
                    t("参数与环境", "Arguments and environment"),
                    code("run.py", "make_parser")
                    + "<br>"
                    + code("__init__.py", "configure_runtime")
                    + "<br>"
                    + code("runtime.py", "environment"),
                ],
                [
                    t("权重与评分器校验", "Weights and evaluator checks"),
                    code("runtime.py", "checked_weight")
                    + "<br>"
                    + code("evaluate.py", "metric_objects")
                    + "<br>"
                    + code("evaluate.py", "self_checks"),
                ],
                [
                    t("几个变量", "Key variables"),
                    t(
                        "args：启动参数／资源路径；config：算法参数；env：实际环境记录；metrics：评分器对象；checks：合成样例自检报告。",
                        "args: launch parameters/resource paths; config: algorithm settings; env: measured environment; metrics: metric objects; checks: synthetic evaluator-test results.",
                    ),
                ],
            ],
            "program-support-table",
        )
        + "<p>"
        + t(
            "self_checks 使用全对、漏一帧、换 ID、错类别、全漏五个可手算案例。HOTA／IDF1／FP／FN／IDSW 与预设答案比较，失败则停止。通过只说明这些基本场景正确，不保证所有复杂情况无误。",
            "self_checks uses five hand-solvable cases: perfect, one miss, ID switch, wrong class and empty. Compare HOTA/IDF1/FP/FN/IDSW against expected answers and stop on failure. Passing covers these basic cases, not every complex scene.",
        )
        + "</p></details>",
    )

    add(
        "next",
        "深度实验开始前，要准备什么",
        "Before the deeper experiments",
        "<p>"
        + t(
            "这是下一阶段待办，不是已完成状态。先锁定实验规则，再扩展测试。",
            "These are pending preparation tasks, not completed work. Freeze the protocol before scaling tests.",
        )
        + "</p><ol>"
        + "".join(
            "<li>" + t(*item) + "</li>"
            for item in [
                (
                    "核验候选视频与标注，确定具备足够后续观察窗口的事件；同时保留可靠历史对照。",
                    "Audit candidate videos/labels and select events with adequate post-correction windows, including reliable-history controls.",
                ),
                (
                    "建立事件清单：视频、目标、纠正时刻、框来源／坐标、既有状态是否可保留、可见性、窗口及分组依据。",
                    "Create an event manifest: video, target, correction time, box source/coordinates, retained-state eligibility, visibility, window and grouping criteria.",
                ),
                (
                    "复用已验证的 A-H/A-R、B-H/B-R 实现；每次仍审计共享前史、同框一次更新、同外部 ID、目标清空与其他对象未被主动重置。",
                    "Reuse the verified A-H/A-R and B-H/B-R implementation, auditing shared prefixes, one same-box update, fixed external IDs, cleared target history and unchanged other targets each time.",
                ),
                (
                    "用合成成功、失败、复发、换对象及空输出测试恢复评分器，锁定阈值、连续次数和窗口。",
                    "Test the recovery evaluator on synthetic success, failure, relapse, wrong-object and empty-output cases; freeze thresholds, streak and window.",
                ),
                (
                    "先跑少量开发事件，检查曲线和干预记录；再开展正式配对实验。固定权重，不把参考框结果冒充全自动性能。",
                    "Pilot a small development event set and inspect curves/intervention logs before formal paired experiments. Keep weights fixed; do not present reference-box results as fully automatic performance.",
                ),
            ]
        )
        + "</ol>",
    )
    return sections


def evidence_content(language, evidence):
    t = lambda zh, en: pick(language, zh, en)
    suffix = ".en" if language == "en" else ""
    if not evidence:
        return (
            '<p class="notice">'
            + t(
                "尚未导入已验证结果。此处不显示假分数；先阅读程序主线。",
                "No verified evidence has been imported. No invented scores are shown; read the program map first.",
            )
            + "</p>"
        )
    scores = evidence["metrics"]
    rows = []
    for key, label in [
        ("HOTA", "HOTA ↑"),
        ("IDF1", "IDF1 ↑"),
        ("FN", "FN ↓"),
        ("FP", "FP ↓"),
        ("IDSW", "IDSW ↓"),
    ]:
        values = [scores[method]["macro"][key] for method in ("A0", "B0")]
        rows.append(
            [label]
            + [f"{100*v:.1f}" if key in ("HOTA", "IDF1") else str(v) for v in values]
        )
    result = (
        revision_notice(evidence, language)
        + "<p>"
        + t(
            "本页读取已验证结果，未重跑模型。质量分数显示为 0–100；FP/FN 是目标-帧计数。B0 宏平均质量更高且漏检更少，但误检更多，不是全面胜出。",
            "This page reads verified evidence without rerunning models. Quality scores use 0–100; FP/FN count object-frame occurrences. B0 has higher macro quality and fewer misses, but more false positives: not a universal win.",
        )
        + "</p>"
        + table([t("指标", "Metric"), "A0", "B0"], rows, "program-pilot-scores")
    )
    result += (
        '<p class="small">'
        + t("来源运行：", "Source run: ")
        + escape(evidence["run"])
        + " · "
        + link(evidence["prefix"] + "metrics.json", t("原始指标", "Original metrics"))
        + "</p>"
    )
    result += (
        "<p>"
        + t(
            "六格图：上排原图／GT；中排 A0／像素错误；下排 B0／像素错误。绿为同类前景覆盖、蓝为漏掉、红为额外或错类。像素图不检查同类 ID 互换。",
            "Six panels: RGB/GT at top, A0/pixel errors in the middle, B0/pixel errors at bottom. Green means covered class foreground, blue missed foreground and red extra/wrong-class foreground. Pixel maps do not detect same-class ID swaps.",
        )
        + "</p>"
    )
    videos = {int(v["id"]): v for v in evidence["viewer"]["videos"]}
    cases = [
        (
            2689,
            35,
            (
                "猫：传播正确，但生命周期即将删掉它",
                "Cat: good propagation, but imminent lifecycle retirement",
            ),
            (
                "35 步 B0 猫 IoU 0.909，A0 无猫输出；36 步 B0 按保留期限删除猫 ID1，并非记忆自行漂移。45 步重新发现为 ID3。错误 person 轨迹仍存在，需单独研究提示与生命周期。",
                "At step 35 B0 cat IoU is 0.909 while A0 has no cat output. At 36, B0 explicitly retires cat ID1 under its retention rule, not spontaneous memory drift. It rediscovers ID3 at 45. A false person track remains and needs separate prompt/lifecycle analysis.",
            ),
        ),
        (
            2686,
            7,
            (
                "骑手：重复轨迹仍然存在",
                "Riders: duplicate tracks remain",
            ),
            (
                "A0 两人都匹配；B0 也匹配两人，但额外 ID2 与 ID3 竞争同一骑手。重复发现／关联是需检查的系统行为；不能再用旧 25 帧的破损 mask 证明记忆漂移。局部诊断选中 ID3 不等于指定 ID2 已消失。",
                "Both A0 and B0 match the two people, but B0 has competing IDs2/3 on one rider. Review duplicate discovery/association as system behavior; the corrupted legacy step-25 mask is not evidence of memory drift. Local selection of ID3 does not mean designated ID2 disappeared.",
            ),
        ),
        (
            2718,
            14,
            (
                "马术：骑手 mask 差，马正常",
                "Equestrian: poor rider mask; horse is fine",
            ),
            (
                "B0 马 IoU 0.737，但骑手只有 0.324；同帧 YOLO 的骑手框 IoU 0.769、mask IoU 0.651。B0 本帧不是自动提示时刻，所以这是改善提示的候选，不足以认定记忆有害。额外输出按现有标注计 FP，背景是否漏标仍需人工核查。",
                "B0 horse IoU is 0.737 but rider IoU is only 0.324; the rider YOLO box/mask IoUs are 0.769/0.651. This is not a scheduled B0 prompt step, making it a corrective-prompt candidate, not proof of harmful memory. Extra outputs count as FPs against current annotations; background label completeness still needs review.",
            ),
        ),
    ]
    for video_id, frame, title, text in cases:
        if video_id not in videos or videos[video_id]["frames"] <= frame:
            continue
        video = videos[video_id]
        base = evidence["prefix"] + str(video_id) + "/"
        image_path = base + f"visuals/{frame:05d}.jpg"
        counts = " · ".join(
            f'{method}: TP {video[method][frame]["TP"]}, FP {video[method][frame]["FP"]}, FN {video[method][frame]["FN"]}'
            for method in ("A0", "B0")
        )
        result += f"""<article class="program-case" id="case-{video_id}"><h3>{t(*title)}</h3><p>{t(*text)}</p><p class="small">{video_id} · {t('导出帧','exported frame')} {frame} · {counts}</p><p>{link(f'results{suffix}.html?video={video_id}&frame={frame}#viewer',t('到逐帧查看器核对 →','Inspect in the frame viewer →'))}</p><details><summary>{t('展开代表帧','Open the representative frame')}</summary><img loading="lazy" src="{image_path}" alt="{escape(t(*title),quote=True)}"></details><details><summary>{t('播放整段六格视频（5 fps 仅为浏览速度）','Play the full six-panel clip (5 fps is browsing speed only)')}</summary><video controls preload="none" poster="{image_path}" src="{base}comparison.mp4"></video></details></article>"""
    return (
        result
        + '<p class="status-note">'
        + t(
            "五段预实验不是最终排名，系统差异不能隔离记忆因果。24 个开发 H/R 分支已验证可重复，只说明实现跑通；旧事件不能因重置后分数较高就追认成记忆失败。",
            "Five pilot clips are not a final ranking and system differences do not isolate memory causality. The 24 development H/R branches repeated exactly, validating execution only; a higher reset score cannot retroactively label an old event a memory failure.",
        )
        + "</p>"
    )


def write_program_pages(output):
    from .recovery_long_page import long_link
    output = Path(output)
    evidence = read_evidence(output)
    hr = read_recovery(output)
    catalog = source_catalog(output)
    template = (WEB / "study.html").read_text(encoding="utf-8")
    css = "".join(
        (WEB / name).read_text(encoding="utf-8")
        for name in ("tutorial.css", "study.css", "program.css")
    )
    script = "".join(
        (WEB / name).read_text(encoding="utf-8") for name in ("study.js", "program.js")
    )
    for language, name in zip(("zh", "en"), PAGES):
        t = lambda zh, en: pick(language, zh, en)
        suffix = ".en" if language == "en" else ""
        blocks = content(language, catalog, evidence, hr)
        extension = long_link(output, language)
        if extension:
            key,title,body = next(b for b in blocks if b[0]=="recovery")
            updated = body+'<p class="status-note">'+t("后续已完成30步跟随、真实匹配代价记录和SAM单次刷新消融；实验结果及步骤→文件／函数对照见长窗口页。", "Thirty-step follow-up, native assignment-cost logging and SAM skip-one-refresh ablation are complete. See the long-window page for results and step-to-file/function mapping.")+" "+extension+"</p>"
            blocks = [(k,h,updated if k=="recovery" else b) for k,h,b in blocks]
        values = {
            "LANG": t("zh-CN", "en"),
            "TITLE": t("程序逻辑与实验地图", "Program and experiment map"),
            "HOME": "index" + suffix + ".html",
            "OTHER": "program" + ("" if suffix else ".en") + ".html",
            "INTRO": "<p>"
            + t(
                "先看实验步骤、调用关系和输入输出，再回看真实结果，最后进入历史保留／重置研究。实现细节按需展开。",
                "Follow experiment steps, calls and inputs/outputs; review real evidence, then move to retain/reset research. Open implementation details only as needed.",
            )
            + "</p><p>"
            + link("#map", t("程序总图", "Program flow"))
            + " · "
            + link("#steps", t("文件／函数索引", "Files/functions"))
            + " · "
            + link("#evidence", t("结果解读", "Evidence review"))
            + " · "
            + link("#recovery", t("下一阶段实验", "Next-phase experiment"))
            + "</p>",
            "CSS": css,
            "JS": script,
            "NAV": "".join(link("#" + key, title) for key, title, _ in blocks),
            "BODY": "".join(body for _, _, body in blocks),
            "SWITCH": t("English", "中文"),
            "BACK": t("返回学习主线", "Back to the handbook"),
            "MENU": t("本页目录", "On this page"),
            "THEME": t("切换主题", "Theme"),
            "SKIP": t("跳到正文", "Skip to content"),
            "TRAIL": t(
                "实验实现 · 从全局到局部", "Experiment implementation · global to local"
            ),
            "FOOT": t(
                "更新：2026-10-17。源码参考随页面更新；历史推理快照与指标保持原样。",
                "Updated 2026-10-17. Current source references refresh with this page; historical inference snapshots and scores remain unchanged.",
            ),
        }
        (output / name).write_text(
            decorate_page(
                re.sub(r"@@([A-Z_]+)@@", lambda match: values[match[1]], template),
                language,
                "program",
            ),
            encoding="utf-8",
        )
