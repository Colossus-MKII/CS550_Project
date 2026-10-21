"""Shared navigation with explicit project and learning workspaces."""

from html import escape
from pathlib import Path
import re

WEB = Path(__file__).with_name("web")


def contextual_links(language, current):
    """Explain this page's role and connect only the relevant prerequisites."""
    en = language == "en"
    suffix = ".en" if en else ""
    topics = {
        "program": (
            "把模型接成两套程序：A0 用 ByteTrack 关联 YOLO 检测；B0 用 YOLO 框提示 SAM。",
            "Connect the models: A0 associates YOLO detections with ByteTrack; B0 prompts SAM with YOLO boxes.",
            [
                ("handbook", "#chapter-3", "ByteTrack 原理", "ByteTrack basics"),
                ("handbook", "#chapter-4", "SAM 原理", "SAM basics"),
                ("results", "", "接着看真实结果 →", "Then review real results →"),
            ],
        ),
        "results": (
            "A0 = YOLO + ByteTrack；B0 = YOLO 框辅助 SAM。两套预测都与同一份真实标注（GT）比较。",
            "A0 = YOLO + ByteTrack; B0 = YOLO-box-assisted SAM. Both predictions are compared with the same ground truth (GT).",
            [
                ("handbook", "#chapter-6", "先弄懂评分", "Understand the scores"),
                ("dataset", "#samples", "看原图与 GT", "Inspect RGB and GT"),
                (
                    "program",
                    "#evidence",
                    "从失败现象进入恢复研究 →",
                    "From failures to recovery research →",
                ),
            ],
        ),
        "recovery": (
            "接着基线看 H/R：H 保留历史，R 重置目标状态；两组都收到同一个纠正框。",
            "Continue from baselines to H/R: H retains history; R resets target state. Both receive the same corrective box.",
            [
                ("results", "", "回看 A0/B0 基线", "Review A0/B0 baselines"),
                (
                    "experiments",
                    "#walkthrough",
                    "理解四组对照",
                    "Understand the four groups",
                ),
                ("handbook", "#chapter-6", "IoU 与评分", "IoU and evaluation"),
            ],
        ),
        "dataset": (
            "原图是模型输入；GT mask 是人工标注，用来判断预测对不对，不是自动基线的输入。",
            "RGB images are model inputs; GT masks are human annotations used to score predictions, not inputs to the automatic baselines.",
            [
                ("handbook", "#chapter-2", "mask 是什么", "What a mask means"),
                (
                    "program",
                    "?step=data#steps",
                    "这些文件怎样进入程序 →",
                    "How these files enter the program →",
                ),
            ],
        ),
        "experiments": (
            "先比较 A0/B0 完整系统，再分别在 ByteTrack 和 SAM 内比较保留／重置历史（H/R）。第二步不是重新训练模型。",
            "First compare the complete A0/B0 systems, then compare retaining/resetting history (H/R) within ByteTrack and SAM. The second step is not model retraining.",
            [
                ("handbook", "#chapter-3", "运动状态记忆", "Motion-state memory"),
                ("handbook", "#chapter-4", "视觉记忆", "Visual memory"),
                (
                    "program",
                    "#recovery",
                    "用已观察到的失败理解对照 →",
                    "Connect the protocol to observed failures →",
                ),
            ],
        ),
    }
    if current not in topics:
        return ""
    zh, english, links = topics[current]
    return (
        '<aside class="context-links" id="page-context" aria-label="'
        + ("Learning and experiment connections" if en else "知识与实验的对应关系")
        + '"><p>'
        + escape(english if en else zh)
        + "</p><div>"
        + " · ".join(
            f'<a href="{slug}{suffix}.html{target}">{escape(label_en if en else label)}</a>'
            for slug, target, label, label_en in links
        )
        + "</div></aside>"
    )


def connect_lessons(text, language):
    en = language == "en"
    suffix = ".en" if en else ""
    entries = [
        (
            1,
            "YOLO 观测是两套基线的共同起点。",
            "YOLO observations are the shared starting point of both baselines.",
            "program",
            "?step=yolo#steps",
            "看真实检测输入／输出",
            "Inspect real detection inputs/outputs",
            2,
        ),
        (
            2,
            "A0 使用 YOLO mask；B0 使用 SAM mask；两者都与 GT mask 评分。",
            "A0 uses YOLO masks; B0 uses SAM masks; both are scored against GT masks.",
            "dataset",
            "#samples",
            "逐帧看原图与标注",
            "Inspect RGB and annotations frame by frame",
            3,
        ),
        (
            3,
            "这对应 A0 的关联器；保留／重置实验改变它的运动状态，不改变 YOLO mask。",
            "This is A0's associator. Retain/reset interventions change its motion state, not YOLO masks.",
            "program",
            "?step=a0#steps",
            "看 A0 的程序步骤",
            "Inspect the A0 program step",
            4,
        ),
        (
            4,
            "教学版只演示首帧提示；真实 B0 还包含周期性 YOLO 框刷新和目标管理。",
            "The lesson demonstrates first-frame prompts; real B0 also refreshes YOLO box prompts periodically and manages targets.",
            "program",
            "?step=b0#steps",
            "看 B0 如何使用 SAM",
            "Inspect how B0 uses SAM",
            6,
        ),
        (
            6,
            "这里先用合成例子理解指标，再用真实标注给 A0/B0 评分。",
            "Learn the metrics with synthetic examples here, then inspect A0/B0 scores against real annotations.",
            "results",
            "",
            "看真实分数与错误帧",
            "Inspect real scores and failure frames",
            7,
        ),
        (
            7,
            "从完整系统差异，进一步研究同一纠正后历史状态怎样影响恢复。",
            "Move from whole-system differences to how history affects recovery after the same correction.",
            "experiments",
            "#walkthrough",
            "进入四组受控实验",
            "Open the four-group controlled study",
            None,
        ),
    ]
    for chapter, zh, english, slug, target, label, label_en, following in entries:
        marker = f'<button class="complete" data-complete="chapter-{chapter}"'
        bridge = (
            f'<aside class="lesson-connection" id="lesson-connection-{chapter}"><strong>'
            + ("In this project" if en else "在本项目中")
            + "</strong><p>"
            + escape(english if en else zh)
            + "</p><div>"
            + f'<a href="{slug}{suffix}.html{target}">{escape(label_en if en else label)} →</a>'
        )
        if following:
            bridge += (
                " · "
                + f'<a href="#chapter-{following}">'
                + ("Continue the lesson" if en else "继续学习")
                + " →</a>"
            )
        text = text.replace(marker, bridge + "</div></aside>" + marker, 1)
    return text


def render_navigation_groups(
    groups, language, prefix="course-group", current_page=False
):
    """Render native accordions for either page destinations or section links."""
    sections = []
    for index, (title, links) in enumerate(groups, 1):
        count = len(re.findall(r"<a\b", links))
        label = (
            f"{count} {'item' if count == 1 else 'items'}"
            if language == "en"
            else f"{count} 个条目"
        )
        selected = 'aria-current="page"' in links if current_page else index == 1
        opened = " open" if selected else ""
        current = " is-current" if selected and current_page else ""
        sections.append(
            f'<details class="{prefix} outline-group{current}" name="{prefix}-outline" id="{prefix}-{index}"{opened}>'
            f'<summary><span class="nav-group">{title}</span>'
            f'<span class="course-group-count" aria-label="{label}">{count}</span></summary>'
            f'<div class="course-group-links">{links}</div></details>'
        )
    return "".join(sections)


PROJECT_OUTLINES = {
    "index": [
        ("项目起点", "Getting started", ("overview", "pathways")),
        (
            "结果与进展",
            "Results & progress",
            ("results", "recovery-results", "runs", "next"),
        ),
        (
            "实现与资料",
            "Implementation & resources",
            ("pipeline", "dataset", "proposal", "resources"),
        ),
    ],
    "runs": [
        ("过程与进展", "Process & progress", ("start", "process")),
        ("已验证记录", "Verified records", ("hr-long-run", "hr-run", "baseline")),
        ("后续工作", "Next steps", ("pending",)),
    ],
    "results": [
        ("基线与评分", "Baselines & scores", ("start", "revision", "scores")),
        ("结果回看", "Review results", ("recovery", "viewer", "curves")),
        ("代码与记录", "Code & records", ("code",)),
    ],
    "recovery": [
        ("对照与设计", "Controls & design", ("start", "design")),
        ("实测与解释", "Measurements & interpretation", ("rider", "cat", "limits")),
        ("复核与记录", "Verification & records", ("records",)),
    ],
    "recovery-long": [
        ("设计与概念", "Design & concepts", ("start", "design", "mechanisms")),
        ("主实验与机制", "Main study & mechanisms", ("rider", "association", "cat")),
        ("消融与复核", "Ablation & verification", ("refresh", "records", "limits")),
    ],
    "recovery-cohort": [
        ("设计与总览", "Design & overview", ("start", "design", "summary")),
        ("机制与逐段证据", "Mechanisms & event evidence", ("findings", "events")),
        ("代码与边界", "Code & limits", ("code", "verification", "next")),
    ],
    "experiments": [
        ("研究与基线", "Research & baselines", ("start", "logic", "baselines")),
        ("受控对照", "Controlled comparisons", ("walkthrough", "matrix", "readouts")),
        ("范围与来源", "Scope & sources", ("scope", "sources")),
    ],
    "program": [
        ("程序与调用", "Program & calls", ("start", "map", "steps", "calls")),
        ("证据与恢复", "Evidence & recovery", ("evidence", "recovery", "criteria")),
        ("运行与准备", "Running & preparation", ("support", "next")),
    ],
    "dataset": [
        ("数据与样本", "Data & samples", ("start", "samples", "format")),
        ("覆盖与使用", "Coverage & usage", ("coverage", "usage")),
    ],
    "documents": [
        ("方案与文档", "Design & documents", ("start", "downloads", "approved-design")),
        ("实现与参考", "Implementation & references", ("references",)),
    ],
}


def fold_course_navigation(text, language, current="handbook"):
    """Group a page's outline while retaining every original destination."""
    en = language == "en"

    def render(match):
        if current == "handbook":
            groups = re.findall(
                r'<span class="nav-group">(.*?)</span>(.*?)(?=<span class="nav-group">|$)',
                match[1],
                flags=re.S,
            )
        else:
            links = {
                key: html
                for html, key in re.findall(
                    r'(<a\b[^>]*href="#([^"]+)"[^>]*>.*?</a>)', match[1], re.S
                )
            }
            hero = re.search(r'<main\b.*?<section\b[^>]*\bid="([^"]+)"', text, re.S)
            if hero and hero[1] not in links:
                links = {
                    hero[1]: f'<a href="#{hero[1]}">'
                    + ("Page overview" if en else "页面概览")
                    + "</a>",
                    **links,
                }
            groups = []
            for zh, english, keys in PROJECT_OUTLINES[current]:
                content = "".join(links.pop(key, "") for key in keys)
                if content:
                    title = f"{len(groups) + 1} · {english if en else zh}"
                    groups.append((title, content))
            if links:
                groups.append(
                    ("More content" if en else "其他内容", "".join(links.values()))
                )
        return (
            '<nav id="course-nav">'
            + render_navigation_groups(groups, language)
            + "</nav>"
        )

    text = re.sub(
        r'<nav id="course-nav">(.*?)</nav>', render, text, count=1, flags=re.S
    )
    label = "Locate current section" if en else "定位当前章节"
    button = (
        f'<button id="locate-current-section" type="button" aria-label="{label}" hidden>'
        + ("Current section" if en else "定位当前")
        + "</button>"
    )
    return re.sub(
        r'(<p class="nav-label">.*?)(</p>)', r"\1" + button + r"\2", text, count=1
    )


def decorate_page(text, language, current):
    if 'id="project-navigation"' in text:
        return text
    en = language == "en"
    suffix = ".en" if en else ""
    learning = current in {"handbook", "math", "research"}
    workspace = "learning" if learning else "project"
    icons = {
        "project": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
        "learning": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M12 5v15M12 5C9 3 5 3 2.5 4v14c3-1 6.5-1 9.5 2 3-3 6.5-3 9.5-2V4C19 3 15 3 12 5Z"/></svg>',
    }
    switcher = (
        '<nav id="workspace-switcher" class="workspace-switcher" aria-label="'
        + ("Switch workspace" if en else "切换项目与教学区域")
        + '">'
    )
    for area, slug, zh, english in (
        ("project", "index", "项目", "Project"),
        ("learning", "handbook", "教学", "Learn"),
    ):
        # This is a location switch, so direct links also work offline without JS.
        active = ' aria-current="true"' if area == workspace else ""
        switcher += (
            f'<a href="{slug}{suffix}.html" data-workspace="{area}"{active}>'
            + icons[area]
            + f"<span>{english if en else zh}</span></a>"
        )
    switcher += "</nav>"
    text = text.replace(
        '<div class="top-actions">', switcher + '<div class="top-actions">', 1
    )
    text = re.sub(r"<body\b", f'<body data-workspace="{workspace}"', text, count=1)
    text = re.sub(
        r'(<button id="menu-toggle"[^>]*>).*?(</button>)',
        r"\g<1>" + ("Menu" if en else "目录") + r"\2",
        text,
        count=1,
    )
    entries = [
        ("index", "实验总览", "Project overview"),
        ("runs", "过程与运行记录", "Process & run records"),
        ("results", "评分与错误回看", "Scores & error review"),
        ("recovery", "H/R 恢复实测", "H/R recovery results"),
        ("recovery-cohort", "16段独立事件", "16-event cohort"),
        ("experiments", "对照实验方案", "Controlled protocol"),
        ("program", "程序与调用地图", "Program & call map"),
        ("dataset", "数据与标注", "Data & annotations"),
        ("documents", "Proposal 与项目文档", "Proposal & documents"),
    ]
    if learning:
        entries = [
            ("handbook", "课程手册", "Course handbook"),
            ("math", "数学与实现", "Math & implementation"),
            ("research", "技术脉络与来源", "History & sources"),
        ]
    items = {}
    for slug, zh, english in entries:
        active = (
            ' aria-current="page"'
            if ("recovery" if current == "recovery-long" else current) == slug
            else ""
        )
        items[slug] = (
            f'<a href="{slug}{suffix}.html"{active}>{escape(english if en else zh)}</a>'
        )
    if learning:
        destinations = "".join(items.values())
    else:
        groups = [
            ("项目与进展", "Project & progress", ("index", "runs")),
            (
                "结果与研究",
                "Results & research",
                ("results", "recovery", "recovery-cohort", "experiments"),
            ),
            (
                "实现与资料",
                "Implementation & resources",
                ("program", "dataset", "documents"),
            ),
        ]
        destinations = render_navigation_groups(
            [
                (f"{i} · {english if en else zh}", "".join(items[key] for key in keys))
                for i, (zh, english, keys) in enumerate(groups, 1)
            ],
            language,
            prefix="project-group",
            current_page=True,
        )
    title = (
        ("Learning area" if en else "教学区")
        if learning
        else ("Project area" if en else "项目区")
    )
    description = (
        ("Models, lessons & references" if en else "模型原理 · 课程与参考")
        if learning
        else (
            "Experiments, results & implementation" if en else "实验进展 · 结果与实现"
        )
    )
    html = (
        f'<div class="workspace-context">{icons[workspace]}<div><strong>{title}</strong>'
        + f"<p>{description}</p></div></div>"
        '<nav id="project-navigation" class="project-navigation" aria-label="'
        + title
        + '">'
        + destinations
        + "</nav>"
    )
    # The workspace selector replaces the old folded global page list.
    text = re.sub(r'<a class="reader-back"[^>]*>.*?</a>', "", text, count=1)
    text = re.sub(
        r'(<p class="nav-label">).*?(</p>)',
        r"\g<1>"
        + (
            ("Course contents" if en else "课程目录")
            if current == "handbook"
            else ("On this page" if en else "本页目录")
        )
        + r"\2",
        text,
        count=1,
    )
    if current == "handbook":
        # Keep experiment destinations in the project area, outside the course menu.
        text = re.sub(
            r'<a id="(?:experiment|dataset|results)-nav-link"[^>]*>.*?</a>', "", text
        )
        text = text.replace(
            'href="#overview"><span class="brand-mark">',
            f'href="index{suffix}.html"><span class="brand-mark">',
            1,
        )
    text = text.replace(
        '<div class="sidebar-inner">', '<div class="sidebar-inner">' + html, 1
    )
    text = text.replace(
        "</style>", (WEB / "navigation.css").read_text(encoding="utf-8") + "</style>", 1
    )
    if current == "index":
        text = re.sub(r'<a class="reader-back"[^>]*>.*?</a>', "", text, count=1)
    if current == "handbook":
        text = connect_lessons(text, language)
        text = re.sub(
            r'(<section id="chapter-7".*?</section>)(\s*)(<section id="chapter-6".*?</section>)',
            r"\3\2\1",
            text,
            count=1,
            flags=re.S,
        )
        # Make the local menu follow the same model -> scoring -> study sequence.
        text = re.sub(
            r'(<a href="#chapter-7">.*?</a>)(<a href="#chapter-6">.*?</a>)',
            r"\2\1",
            text,
            count=1,
        )
        text = fold_course_navigation(text, language)
    else:
        text = text.replace(
            "</section>", contextual_links(language, current) + "</section>", 1
        )
        if not learning:
            text = fold_course_navigation(text, language, current)
    text = text.replace(
        "</body>",
        "<script>"
        + (WEB / "reading-position.js").read_text(encoding="utf-8")
        + "</script><script>"
        + (WEB / "navigation.js").read_text(encoding="utf-8")
        + "</script></body>",
        1,
    )
    return text.replace("← 返回学习主线", "← 项目总览").replace(
        "← Back to the handbook", "← Project overview"
    )
