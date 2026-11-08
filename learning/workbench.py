"""Experiment-first project overview, records and documents; no inference."""

from datetime import datetime
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re

from . import journey
from .navigation import decorate_page
from .baseline_revision import revision_notice
from .recovery_page import read_recovery, recovery_link
from .recovery_long_data import read_long
from .recovery_long_page import long_link
from .program_page import read_evidence, table
from .study import WEB, link, pick, section

PAGES = (
    "index.html",
    "index.en.html",
    "runs.html",
    "runs.en.html",
    "documents.html",
    "documents.en.html",
)
HANDBOOK_PAGES = ("handbook.html", "handbook.en.html")


class Ids(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        value = dict(attrs).get("id")
        if value:
            self.ids.append(value)


def download_table(output, language, full=True):
    t = lambda zh, en: pick(language, zh, en)
    root = Path(output)
    entries = [
        ("proposal.pdf", "proposal.md.txt", "英文完整稿", "Full English"),
        ("proposal_zh.pdf", "proposal_zh.md.txt", "中文完整稿", "Full Chinese"),
        (
            "proposal_short.pdf",
            "proposal_short.md.txt",
            "英文精简稿",
            "Concise English",
        ),
        (
            "proposal_short_zh.pdf",
            "proposal_short_zh.md.txt",
            "中文精简稿",
            "Concise Chinese",
        ),
    ]
    rows = []
    for pdf, source, zh, en in entries:
        path = root / "proposal" / pdf
        if path.is_file():
            rows.append(
                [
                    t(zh, en),
                    link("proposal/" + pdf, "PDF"),
                    f"{path.stat().st_size:,} bytes",
                    link("proposal/" + source, t("文本", "Text")),
                ]
            )
    result = table(
        [
            t("版本", "Edition"),
            t("下载", "Download"),
            t("实际大小", "Actual size"),
            t("来源", "Source"),
        ],
        rows,
        "project-proposal-downloads",
    )
    if full:
        result += (
            "<p>"
            + " · ".join(
                link("proposal/" + name, label)
                for name, label in [
                    ("proposal-latex.zip", t("英文完整稿 LaTeX", "Full English LaTeX")),
                    (
                        "proposal-short-latex.zip",
                        t("英文精简稿 LaTeX", "Concise English LaTeX"),
                    ),
                    (
                        "neurips-2026-template-files.zip",
                        t("原始模板文件", "Original template files"),
                    ),
                    (
                        "manifest.json",
                        t("文件指纹与来源", "File fingerprints and provenance"),
                    ),
                ]
            )
            + "</p>"
        )
    return result


def run_facts(evidence):
    videos = evidence["viewer"]["videos"] if evidence else []
    return len(videos), sum(video["frames"] for video in videos)


def score_table(evidence, language):
    t = lambda zh, en: pick(language, zh, en)
    if not evidence:
        return (
            '<p class="notice">'
            + t(
                "尚未导入已验证的实验记录；不显示示例分数。",
                "No verified experiment record is imported; no placeholder scores are displayed.",
            )
            + "</p>"
        )
    rows = []
    for method in ("A0", "B0"):
        scores = evidence["metrics"][method]["macro"]
        rows.append(
            [method]
            + [f"{100*scores[key]:.1f}" for key in ("HOTA", "IDF1")]
            + [str(scores[key]) for key in ("FP", "FN", "IDSW")]
        )
    return table(
        ["", "HOTA ↑", "IDF1 ↑", "FP ↓", "FN ↓", "IDSW ↓"], rows, "project-score-table"
    )


def overview(output, language, evidence):
    t = lambda zh, en: pick(language, zh, en)
    suffix = ".en" if language == "en" else ""
    blocks = []

    def add(key, zh, en, body):
        title = t(zh, en)
        blocks.append((key, title, section(key, title, body)))

    hr = read_recovery(output)
    long_window = read_long(output)
    intro = (
        '<p class="project-summary">'
        + t(
            "同一段视频里，怎样持续跟对同一个目标？先比较两套自动流程，再研究跟错以后，旧历史应该保留还是重置。",
            "How do we keep following the same object in a video? Compare two automatic pipelines, then study whether retaining or resetting history helps after an error.",
        )
        + '</p><div class="baseline-key"><p><strong>A0</strong> · YOLO → ByteTrack · '
        + t(
            "逐帧检测与分割，再关联身份。",
            "Detect and segment each frame, then associate identities.",
        )
        + "</p><p><strong>B0</strong> · YOLO → SAM 2.1 · "
        + t(
            "定期提供检测框，由 SAM 传播目标 mask。",
            "Supply detection boxes periodically; SAM propagates target masks.",
        )
        + "</p></div>"
    )
    latest = journey.latest(output)
    latest_target = journey.stage_href(latest, language) if latest else journey.href("results", language)
    intro += (
        '<div class="hero-actions">'
        + link("#experiment-route", t("沿实验主线阅读 ↓", "Follow the experiment route ↓")).replace("<a ", '<a id="start-route-link" class="button primary" ', 1)
        + link(journey.href("results", language), t("阶段 1：五段 A0/B0 基线", "Phase 1: five-clip A0/B0 baselines")).replace("<a ", '<a id="baseline-entry-link" class="button secondary" ', 1)
        + link(latest_target, t("查看最新进展 →", "See latest progress →") if latest else t("查看结果页", "Open results page")).replace("<a ", '<a id="latest-results-link" class="button secondary" ', 1)
        + "</div>"
        + '<p class="small">' + escape(journey.split_status(language)) + " "
        + t("正式评估尚未完成。", "Formal evaluation remains pending.") + " · "
        + link(journey.href("handbook", language), t("独立教学区 →", "Open learning area →")).replace("<a ", '<a id="learning-entry-link" ', 1) + "</p>"
    )
    add("experiment-route", "沿实验主线阅读", "Follow the experiment route",
        "<p>" + t(
            "第一次来，从 01 开始。每页末尾都有前后步骤；熟悉项目时可直接跳到任一阶段。运行记录和下载放在后面，供查证。",
            "Start at 01 on your first visit. Each page ends with the previous and next steps. Jump to any stage if you know the project; use records and downloads for verification.",
        ) + "</p>" + journey.route_map(output, language))

    routes = [
        (
            "01",
            "目标在哪里、像素属于谁？",
            "Where is the object, and which pixels belong to it?",
            "YOLO 检测",
            "YOLO detection",
            "chapter-1",
            "program",
            "?step=yolo#steps",
            "共享 YOLO 输入与输出",
            "Shared YOLO inputs and outputs",
        ),
        (
            "02",
            "前后帧怎样维持同一身份？",
            "How is identity maintained across frames?",
            "ByteTrack 运动关联",
            "ByteTrack association",
            "chapter-3",
            "program",
            "#map",
            "A0/B0 两条实际流程",
            "The actual A0/B0 pipelines",
        ),
        (
            "03",
            "结果好坏，凭什么判断？",
            "How do we judge the outputs?",
            "IoU、IDF1、HOTA",
            "IoU, IDF1 and HOTA",
            "chapter-6",
            "results",
            "",
            "真实 GT、评分与错误帧",
            "Real GT, scores and failure frames",
        ),
        (
            "04",
            "跟错以后，历史帮忙还是拖累？",
            "After an error, does history help or hurt?",
            "记忆与项目研究问题",
            "Memory and the research question",
            "chapter-7",
            "experiments",
            "#walkthrough",
            "保留／重置四组对照",
            "Four retain/reset groups",
        ),
    ]
    route_body = (
        "<p>"
        + t(
            "学习和实验是同一条线的不同层次。可从任何问题进入；每课末尾连接对应的程序或结果，实验页也可返回相关知识。",
            "Learning and experiments are two levels of the same workflow. Enter at any question: lessons link to their implementation or evidence, and experiment pages link back to relevant concepts.",
        )
        + '</p><ol class="project-pathways">'
    )
    for (
        number,
        zh,
        en,
        label,
        label_en,
        chapter,
        slug,
        target,
        practice,
        practice_en,
    ) in routes:
        route_body += (
            '<li><span class="route-number">'
            + number
            + "</span><div><strong>"
            + t(zh, en)
            + '</strong><div class="pathway-links"><span>'
            + t("理解：", "Learn: ")
            + link("handbook" + suffix + ".html#" + chapter, t(label, label_en))
        )
        if number == "01":
            route_body += " / " + link(
                "handbook" + suffix + ".html#chapter-2", t("像素 mask", "Pixel masks")
            )
        if number == "02":
            route_body += " / " + link(
                "handbook" + suffix + ".html#chapter-4", "SAM 2.1"
            )
        route_body += (
            "</span><span>"
            + t("对应实验：", "In practice: ")
            + link(slug + suffix + ".html" + target, t(practice, practice_en))
            + "</span></div></div></li>"
        )
    route_body += "</ol>"
    add(
        "pathways",
        "从模型到实验：按问题进入",
        "From models to experiments: choose a question",
        route_body,
    )

    add("runs", "运行记录与查证", "Run records & verification",
        "<p>" + t("按阶段查运行配置、复跑证据和未完成项。", "Trace configurations, repeat checks and pending work by stage.") + " "
        + link(journey.href("runs", language), t("打开运行档案 →", "Open the run archive →")) + "</p>")
    result_body = revision_notice(evidence, language) + score_table(evidence, language)
    result_body += (
        '<p class="small">'
        + t(
            "质量分数为五类等权的 0–100 显示值；FP/FN/IDSW 为累计计数。五段预实验不是最终排名，也不能单独证明记忆机制优劣。",
            "Quality scores are class-macro values on a 0–100 display scale; FP/FN/IDSW are cumulative counts. Five pilot clips are not a final ranking or evidence that one memory mechanism is superior.",
        )
        + "</p>"
    )
    if evidence:
        examples = [
            (
                2689,
                35,
                "猫：传播仍准，下一步却被生命周期删除",
                "Cat: accurate propagation, then lifecycle retirement",
            ),
            (
                2686,
                7,
                "骑手：重复轨迹，而不是严重 mask 漂移",
                "Riders: duplicate tracks, not severe mask drift",
            ),
            (
                2718,
                14,
                "马术：马跟住了，骑手分割仍不准",
                "Equestrian: horse tracked; rider segmentation remains poor",
            ),
        ]
        by_id = {int(v["id"]): v for v in evidence["viewer"]["videos"]}
        cards = []
        for key, frame, zh, en in examples:
            if key not in by_id or by_id[key]["frames"] <= frame:
                continue
            href = f"results{suffix}.html?video={key}&frame={frame}#viewer"
            cards.append(
                f'<a class="evidence-card" href="{href}"><img loading="lazy" src="{evidence["prefix"]}{key}/visuals/{frame:05d}.jpg" alt="{escape(t(zh,en),quote=True)}"><strong>{t(zh,en)}</strong><span>{key} · {t("帧","frame")} {frame} →</span></a>'
            )
        result_body += '<div class="evidence-cards">' + "".join(cards) + "</div>"
    result_body += (
        "<p>"
        + link(
            "results" + suffix + ".html",
            t("全部评分、逐帧回看与视频 →", "All scores, frame review and videos →"),
        )
        + " · "
        + link(
            "program" + suffix + ".html#evidence",
            t("结果解读与研究问题 →", "Interpretation and research questions →"),
        )
        + "</p>"
    )
    add(
        "results", "阶段 1：基线分数与例帧", "Phase 1: baseline scores and example frames", result_body
    )
    if hr:
        add(
            "recovery-results",
            "接着基线看：H/R 实测结果",
            "Continue from baselines: measured H/R results",
            "<p>"
            + t(
                (
                    "8步之后，骑手SAM重置分支出现延迟恢复，但仍有复发。ByteTrack重置收益依赖框与关联条件；猫分割仍准，却会因保留期限删除旧ID。主实验与跳过一次刷新的消融分开展示。"
                    if long_window
                    else "8步窗口内，骑手的ByteTrack重置收益依赖纠正条件；SAM mask改善但尚未确认恢复；猫的视觉历史几乎不受重置影响。"
                ),
                (
                    "Beyond eight steps, rider SAM reset shows delayed recovery with relapse. ByteTrack benefits depend on box/association conditions; the cat is still well segmented before retention removes its ID. Main results and skip-one-refresh ablation are separate."
                    if long_window
                    else "Within eight steps, rider ByteTrack reset benefits depend on correction conditions; SAM masks improve without confirmed recovery; cat visual history barely changes."
                ),
            )
            + "</p><p>"
            + recovery_link(output, language)
            + (" · " + long_link(output, language) if long_window else "")
            + "</p>",
        )
    add("next", "正式评估待办", "Formal evaluation still pending",
        journey.assessment(language) + "<p>"
        + link(journey.href("runs", language, "pending"), t("核对正式评估缺口 →", "Review what remains for formal evaluation →"))
        + "</p>")
    add(
        "pipeline",
        "实验实现入口",
        "Experiment implementation",
        '<div class="compact-pipeline">'
        + t(
            "有序原图 → YOLO 缓存 → A0 / B0 → GT → 诊断与正式评分 → 报告与复核",
            "Ordered images → YOLO cache → A0 / B0 → GT → diagnostics and official scores → reports and verification",
        )
        + "</div><p>"
        + link(
            "program" + suffix + ".html",
            t("程序总图、文件与函数调用 →", "Program flow, files and function calls →"),
        )
        + '</p><p class="small">'
        + t(
            "实际实验代码位于 experiments/tracking_lab，可独立运行；网站负责展示流程、记录与结果。",
            "Scientific code in experiments/tracking_lab runs independently; the website presents workflows, records and results.",
        )
        + "</p>",
    )
    add(
        "dataset",
        "数据与标注",
        "Data and annotations",
        "<p>"
        + t(
            "初始验证运行使用五段真实标注视频。开发事件不等于完整五类评估；实例通道和时间戳限制见数据页。",
            "The initial verified run uses five genuinely annotated clips. Development events do not constitute full five-class evaluation; see the data page for instance channels and timing limitations.",
        )
        + "</p><p>"
        + link(
            "dataset" + suffix + ".html#coverage",
            t("数据覆盖与划分约束 →", "Coverage and split constraints →"),
        )
        + " · "
        + link(
            "dataset" + suffix + ".html#samples",
            t("原图与 GT mask 逐帧查看 →", "RGB and GT masks frame by frame →"),
        )
        + "</p>",
    )
    add(
        "proposal",
        "Proposal 与项目文档",
        "Proposal and project documents",
        "<p>"
        + t(
            "查看和下载当前中英文完整稿、精简稿、LaTeX 与原始格式模板。",
            "Read and download the current full and concise bilingual proposals, LaTeX sources and original format template.",
        )
        + "</p>"
        + download_table(output, language, False)
        + "<p>"
        + link(
            "documents" + suffix + ".html",
            t("全部项目文档与来源 →", "All project documents and provenance →"),
        )
        + "</p>",
    )
    legacy = ["chapter-" + str(i) for i in range(1, 8)] + [
        "deep-study",
        "evidence",
        "run-record",
        "ultralytics",
    ]
    shortcuts = (
        '<details id="legacy-bookmarks"><summary>'
        + t("旧教学书签入口", "Legacy handbook bookmarks")
        + "</summary><ul>"
        + "".join(
            "<li>" + f'<a id="{key}" href="handbook{suffix}.html#{key}">{key}</a></li>'
            for key in legacy
        )
        + "</ul></details>"
    )
    add(
        "resources",
        "学习资料（按需查阅）",
        "Learning references (on demand)",
        "<p>"
        + t(
            "模型职责不清楚时看课程；需要解释现象时查数学与论文。各页保留相关主题的往返链接。",
            "Use the lessons for model roles, and mathematics or papers to explain observed behavior. Relevant topics are linked in both directions.",
        )
        + '</p><div class="reference-links">'
        + link(
            "handbook" + suffix + ".html",
            t("七课模型学习手册 →", "Seven-lesson model handbook →"),
        ).replace("<a ", '<a id="handbook-link" ', 1)
        + link(
            "math" + suffix + ".html",
            t("数学与实现 →", "Mathematics and implementation →"),
        )
        + link(
            "research" + suffix + ".html",
            t("技术脉络与论文 →", "Technical history and papers →"),
        )
        + "</div>"
        + shortcuts,
    )
    return t("实验项目总览", "Experiment project overview"), intro, blocks


def records(language, evidence):
    t = lambda zh, en: pick(language, zh, en)
    suffix = ".en" if language == "en" else ""
    blocks = []

    def add(key, zh, en, body):
        title = t(zh, en)
        blocks.append((key, title, section(key, title, body)))

    add("process", "档案阅读顺序", "Reading the run archive",
        "<p>" + t(
            "以下按基线、8 步、30 步、16 段、自然失败排列。每项记录保留当时的配置、核验和局限；先沿主线看实验，再来查出处。",
            "Records follow the baseline, eight-step, 30-step, 16-event and natural-failure studies. Each keeps its configuration, checks and limits; read the experiment route before consulting the archive.",
        ) + "</p><p>" + escape(journey.split_status(language)) + "</p><p>"
        + link(journey.href("index", language, "experiment-route"), t("查看实验主线 →", "Open the experiment route →"))
        + " · " + link("#pending", t("查看正式评估待办 ↓", "See pending formal evaluation ↓")) + "</p>")
    if evidence:
        summary = evidence["summary"]
        env = summary["environment"]
        prefix = evidence["prefix"]
        count, frames = run_facts(evidence)
        created = summary.get("created_utc", "")
        try:
            from zoneinfo import ZoneInfo

            created = (
                datetime.fromisoformat(created)
                .astimezone(ZoneInfo("America/New_York"))
                .strftime("%Y-%m-%d %H:%M %Z")
            )
        except (ValueError, KeyError):
            pass
        rows = [
            [t("记录", "Record"), escape(evidence["run"])],
            [t("运行开始时间", "Run start"), escape(created)],
            [t("范围", "Scope"), f"{count} videos / {frames} exported frames"],
            [t("设备", "Device"), escape(str(env.get("device", "not recorded")))],
            [
                t("状态", "State"),
                t("完成，独立复核通过", "Completed; independent verification passed"),
            ],
            [
                t("A0 输入", "A0 input"),
                t(
                    "YOLO 每帧框／mask，ByteTrack 关联身份",
                    "Per-frame YOLO boxes/masks and ByteTrack identities",
                ),
            ],
            [
                t("B0 输入", "B0 input"),
                t(
                    "原图＋每 5 步 YOLO 框，SAM 分割与传播",
                    "Images + YOLO boxes every five steps; SAM segmentation/propagation",
                ),
            ],
            [
                t("时间限制", "Timing limit"),
                t(
                    "共享检测缓存，不是端到端 FPS 基准",
                    "Shared detector cache; not an end-to-end FPS benchmark",
                ),
            ],
        ]
        add(
            "baseline",
            "已验证运行：第一阶段基线",
            "Verified run: stage-one baselines",
            table(
                [t("字段", "Field"), t("记录值", "Recorded value")],
                rows,
                "run-record-table",
            )
            + score_table(evidence, language)
            + "<p>"
            + " · ".join(
                link(prefix + name, t(zh, en))
                for name, zh, en in [
                    (
                        "summary.json",
                        "环境、权重指纹与运行摘要",
                        "Environment, weight fingerprints and summary",
                    ),
                    ("config.json", "固定配置", "Fixed configuration"),
                    ("verification.json", "独立复核", "Independent verification"),
                    ("metrics.json", "全部指标", "Full metrics"),
                    ("input-manifest.json", "输入指纹", "Input fingerprints"),
                    (
                        "evaluator-self-checks.json",
                        "评分器自检",
                        "Evaluator self-checks",
                    ),
                ]
            )
            + "</p><p>"
            + link(
                "results" + suffix + ".html",
                t("逐帧结果与对照视频 →", "Frame review and videos →"),
            )
            + " · "
            + link(
                "program" + suffix + ".html#calls",
                t("程序调用地图 →", "Program call map →"),
            )
            + '</p><p class="small">'
            + t(
                "原始时间、数值和指纹保留在证据 JSON 中。源码快照属于实际推理版本；程序地图中的源码是当前工作区参考，两者不混淆。",
                "Original timestamps, values and hashes remain in evidence JSON. Inference snapshots belong to the measured run; the program map supplies a separate current-workspace reference.",
            )
            + "</p>",
        )
    else:
        add("baseline", "运行记录", "Run record", score_table(None, language))
    add("pending", "正式评估待办", "Formal evaluation still pending",
        journey.assessment(language) + "<p>" + t(
            "后续评估需要可复核的冻结配置、分组指标与完整运行记录。五段基线和开发 H/R 案例不能作为保留集成绩。",
            "A formal evaluation needs auditable frozen configurations, split-level metrics and complete run records. The five-clip baseline and development H/R cases cannot stand in for held-out scores.",
        ) + "</p>")
    return (
        t("过程与运行记录", "Process and run records"),
        "<p>"
        + t(
            "按证据追溯完成了什么、用了什么配置、还没有做什么。",
            "Trace what was completed, which configuration was used and what remains undone.",
        )
        + "</p>",
        blocks,
    )


def documents(output, language, proposal):
    t = lambda zh, en: pick(language, zh, en)
    suffix = ".en" if language == "en" else ""
    blocks = []
    for key, title, body in [
        (
            "downloads",
            t("版本与下载", "Editions and downloads"),
            download_table(output, language),
        ),
        (
            "approved-design",
            t("当前方案", "Current design"),
            "<p>"
            + t(
                "保留 A0/B0 基线对照，增加 A-H/A-R、B-H/B-R 成对历史干预。固定模型权重，分别报告机制实验与完整自动系统。",
                "Keep A0/B0 baselines and add paired A-H/A-R and B-H/B-R interventions. Freeze model weights and report controlled mechanisms separately from fully automatic performance.",
            )
            + "</p><p>"
            + link("experiments" + suffix + ".html", t("实验流程 →", "Protocol →"))
            + " · "
            + link(
                "program" + suffix + ".html#recovery",
                t(
                    "实现状态与恢复定义 →",
                    "Implementation status and recovery definition →",
                ),
            )
            + "</p><details><summary>"
            + t("展开本语言完整 proposal", "Read the full proposal in this language")
            + '</summary><article class="proposal-document">'
            + proposal["html"]
            + "</article></details>",
        ),
        (
            "references",
            t("实施与背景参考", "Implementation and background references"),
            "<ul><li>"
            + link(
                "program" + suffix + ".html",
                t(
                    "程序、函数与当前源码参考",
                    "Program, functions and current source references",
                ),
            )
            + "</li><li>"
            + link(
                "dataset" + suffix + ".html",
                t("数据说明和真实标注样本", "Data guide and real annotated samples"),
            )
            + "</li><li>"
            + link(
                "handbook" + suffix + ".html",
                t("完整模型学习手册", "Complete model handbook"),
            )
            + "</li><li>"
            + link(
                "math" + suffix + ".html", t("数学实现", "Mathematical implementation")
            )
            + " · "
            + link("research" + suffix + ".html", t("论文与来源", "Papers and sources"))
            + "</li></ul>",
        ),
    ]:
        blocks.append((key, title, section(key, title, body)))
    from .team_downloads import content as resource_content
    shared_resources = resource_content(output, language)
    if shared_resources:
        title = t("组内数据、权重与pilot资源下载", "Shared data, checkpoints and pilot downloads")
        blocks.insert(0, ("team-assets", title, section("team-assets", title, shared_resources)))
    order = ("approved-design", "downloads", "team-assets", "references")
    blocks.sort(key=lambda block: order.index(block[0]))
    return (
        t("研究问题与 Proposal", "Research question and proposal"),
        "<p>"
        + t(
            "中英文 Proposal、源文件及项目说明集中于此。",
            "Bilingual proposals, source files and project documentation in one place.",
        )
        + "</p>",
        blocks,
    )


def write_workbench(output, proposals):
    output = Path(output)
    evidence = read_evidence(output)
    hr = read_recovery(output)
    long_window = read_long(output)
    template = (WEB / "study.html").read_text(encoding="utf-8")
    css = "".join(
        (WEB / name).read_text(encoding="utf-8")
        for name in ("tutorial.css", "study.css", "workbench.css")
    )
    for language in ("zh", "en"):
        t = lambda zh, en: pick(language, zh, en)
        suffix = ".en" if language == "en" else ""
        for slug, builder in [
            ("index", lambda: overview(output, language, evidence)),
            ("runs", lambda: records(language, evidence)),
            ("documents", lambda: documents(output, language, proposals[language])),
        ]:
            title, intro, blocks = builder()
            from .team_downloads import download_link as resource_link
            resources = resource_link(output, language)
            if resources and slug == "index":
                pos = next(i for i, (key, _, _) in enumerate(blocks) if key == "resources")
                key, label, body = blocks[pos]
                blocks[pos] = (key, label, body.removesuffix("</section>")
                               + '<p id="team-resource-entry">' + resources + '</p></section>')
            from .recovery_cohort_page import progress_block

            cohort_block = progress_block(output, language)
            if cohort_block and slug in {"index", "runs"}:
                key, label, body = cohort_block
                blocks.insert(0, (key, label, section(key, label, body)))
            from .natural_page import progress_block as natural_progress
            natural_block = natural_progress(output, language)
            if natural_block and slug in {"index", "runs"}:
                key, label, body = natural_block
                blocks.insert(0, (key, label, section(key, label, body)))
            if slug == "runs" and hr:
                title_hr = t("8步 H/R：骑手与猫", "Eight-step H/R: rider and cat")
                body_hr = (
                    "<p>"
                    + escape(hr["run"])
                    + "</p><p>"
                    + t(
                        "16 分支完成并完整复跑一致。早期 24 分支仅作实现检查；本批基于同步修正版基线，不更改基线分数。",
                        "Sixteen branches completed and repeated exactly. The earlier 24 branches checked implementation; this batch uses corrected baselines without changing their scores.",
                    )
                    + "</p><p>"
                    + recovery_link(output, language)
                    + " · "
                    + link(
                        hr["prefix"] + "repeat-verification.json",
                        t("复跑证据", "Repeat proof"),
                    )
                    + "</p>"
                )
                blocks.insert(
                    1, ("hr-run", title_hr, section("hr-run", title_hr, body_hr))
                )
            if slug == "runs" and long_window:
                title_long = t(
                    "后续：30步与单次刷新消融",
                    "Follow-up: 30 steps and skip-one refresh",
                )
                body_long = (
                    "<p>"
                    + t(
                        "两个事件，16主实验分支＋16消融分支，均已完整复跑。8／20／30步是同一长预测的读数；SAM延迟恢复、ByteTrack关联失败、猫生命周期删除应分开解释。",
                        "Two events, 16 main and 16 ablation branches, each fully repeated. The 8/20/30 checkpoints read the same long prediction. Interpret delayed SAM recovery, ByteTrack association failure and cat lifecycle removal separately.",
                    )
                    + "</p><p>"
                    + long_link(output, language)
                    + "</p>"
                )
                blocks.insert(
                    1,
                    (
                        "hr-long-run",
                        title_long,
                        section("hr-long-run", title_long, body_long),
                    ),
                )
            if slug == "runs":
                record_order = ("process", "baseline", "hr-run", "hr-long-run",
                                "independent-cohort", "natural-followup", "pending")
                blocks.sort(key=lambda block: record_order.index(block[0]))
            elif slug == "index":
                home_order = ("experiment-route", "pathways", "results", "recovery-results",
                              "independent-cohort", "natural-followup", "next", "runs",
                              "pipeline", "dataset", "proposal", "resources")
                blocks.sort(key=lambda block: home_order.index(block[0]))
            legacy = (
                Ids(
                    (output / ("handbook" + suffix + ".html")).read_text(
                        encoding="utf-8"
                    )
                ).ids
                if slug == "index"
                else []
            )
            script = (WEB / "study.js").read_text(encoding="utf-8")
            if slug == "index":
                script += (
                    "\nwindow.cs550LegacyIds="
                    + json.dumps(legacy)
                    + ";\n"
                    + (WEB / "workbench.js").read_text(encoding="utf-8")
                )
            values = {
                "LANG": t("zh-CN", "en"),
                "TITLE": title,
                "INTRO": intro,
                "HOME": "index" + suffix + ".html",
                "OTHER": slug + ("" if suffix else ".en") + ".html",
                "CSS": css,
                "JS": script,
                "NAV": "".join(link("#" + key, label) for key, label, _ in blocks),
                "BODY": "".join(body for _, _, body in blocks),
                "SWITCH": t("English", "中文"),
                "BACK": t("项目总览", "Project overview"),
                "MENU": t("本页目录", "On this page"),
                "THEME": t("切换主题", "Theme"),
                "SKIP": t("跳到正文", "Skip to content"),
                "TRAIL": t("CS550 · 实验记录", "CS550 · Experiment records"),
                "FOOT": t(
                    "只读项目网站。实验在独立工作区运行；教学与数学为参考资料。",
                    "Read-only project site. Experiments run in the independent workspace; lessons and mathematics are references.",
                ),
            }
            text = re.sub(r"@@([A-Z_]+)@@", lambda match: values[match[1]], template)
            if slug == "index":
                text = text.replace('id="start"', 'id="overview"', 1)
            (output / (slug + suffix + ".html")).write_text(
                decorate_page(text, language, slug, output), encoding="utf-8"
            )
