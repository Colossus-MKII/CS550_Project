"""Read-only reading order and status for the CS550 project website."""

from dataclasses import dataclass
from html import escape
import json
from pathlib import Path


@dataclass(frozen=True)
class Stage:
    page: str
    title: tuple[str, str]
    purpose: tuple[str, str]
    takeaway: tuple[str, str]
    anchor: str = ""
    evidence: str = ""


STAGES = (
    Stage(
        "documents",
        ("研究问题与 Proposal", "Research question & proposal"),
        (
            "先定义要比较什么：跟踪同一目标，以及跟错后怎样处理历史。",
            "Define what to compare: keeping the same target and handling history after an error.",
        ),
        (
            "整体 A0/B0 对比与同框历史干预是两个问题。",
            "Whole-system A0/B0 comparison and same-box history intervention answer different questions.",
        ),
        "approved-design",
    ),
    Stage(
        "dataset",
        ("数据与真实标注", "Data & ground truth"),
        (
            "辨认模型输入、GT mask、实例通道和导出帧。",
            "Identify model inputs, GT masks, instance channels and exported frames.",
        ),
        (
            "原图用于自动推理；同一套 GT 用于两套系统的评分。",
            "RGB feeds automatic inference; the same GT scores both pipelines.",
        ),
    ),
    Stage(
        "program",
        ("A0/B0 程序调用", "A0/B0 program flow"),
        (
            "沿着同一批原图和 YOLO 观测查文件、函数与输出。",
            "Follow the same frames and YOLO observations through files, functions and outputs.",
        ),
        (
            "A0 关联逐帧检测；B0 用周期性检测框传播 mask。GT 在推理之后进入评分。",
            "A0 associates per-frame detections; B0 propagates masks using periodic boxes. GT enters after inference.",
        ),
    ),
    Stage(
        "results",
        ("阶段 1：五段 A0/B0 基线", "Phase 1: five-clip A0/B0 baselines"),
        (
            "先看五段对比，再用 GT 评分和逐帧诊断定位具体错误。",
            "Watch the five comparisons, then use GT scores and frame diagnostics to locate specific errors.",
        ),
        (
            "207 个导出步中，B0 的宏平均分较高、漏检较少，但误检更多。整体分数还不能回答历史保留是否有用。",
            "Across 207 exported steps, B0 had higher macro scores and fewer misses, but more false positives. Whole-system scores do not answer whether retention helps.",
        ),
        evidence="pilot-results/manifest.json",
    ),
    Stage(
        "experiments",
        ("H/R 对照怎么做", "How the H/R comparison works"),
        (
            "两套系统各自在相同前史、同一个纠正框下比较保留 H 和重置 R。",
            "Within each system, compare retention (H) and reset (R) with the same prior state and corrective box.",
        ),
        (
            "固定原 ID，纠正帧不计分；YOLO 框和标注参考框分别报告。",
            "Track the original ID, exclude the correction frame, and report YOLO and annotation-derived boxes separately.",
        ),
        "walkthrough",
    ),
    Stage(
        "recovery",
        ("骑手／猫：8 步初测", "Rider & cat: eight-step pilot"),
        (
            "先用一个失败案例和一个稳定对照，检查同框干预后的短期变化。",
            "Use a failure case and a stable control to check short-term effects of a same-box intervention.",
        ),
        (
            "16 个分支完成并复跑。短窗口尚不能判断骑手 SAM 是否会延迟恢复。",
            "Sixteen branches completed and were repeated. The short window cannot resolve delayed SAM recovery in the rider case.",
        ),
        evidence="recovery-results/manifest.json",
    ),
    Stage(
        "recovery-long",
        ("30 步跟随与单次刷新消融", "30-step follow-up & refresh ablation"),
        (
            "延长观察同一组案例，另查跳过一次刷新会不会改变结论。",
            "Follow the same cases for longer and separately check the effect of skipping one refresh.",
        ),
        (
            "16 个主分支与 16 个消融分支分开读。骑手 SAM 重置后延迟恢复，随后仍有复发。",
            "Read the 16 main branches separately from the 16 ablation branches. Rider SAM reset showed delayed recovery followed by relapse.",
        ),
        evidence="recovery-long-results/manifest.json",
    ),
    Stage(
        "recovery-cohort",
        ("16 段开发对照", "16-event development cohort"),
        (
            "在更多开发视频里区分已有正确跟踪、低质量框、关联竞争和删除。",
            "Use more development videos to distinguish existing correct tracking, poor boxes, association competition and deletion.",
        ),
        (
            "128 个主分支；指定复跑不计新样本。多数事件主要考察维持跟踪，因此还需要专门看持续失败。",
            "128 main branches; selected repeats do not add samples. Most events mainly test maintenance, motivating a closer look at sustained failures.",
        ),
        evidence="recovery-cohort-results/manifest.json",
    ),
    Stage(
        "recovery-natural",
        ("7 个自然失败事件", "Seven natural-failure events"),
        (
            "在已有开发预测里找持续失败且原状态仍可操作的事件，与未纠正运行一起读。",
            "Examine sustained failures with usable prior state in existing development predictions, alongside the uncorrected run.",
        ),
        (
            "52 个主分支，另有 20 个验证分支。保留、重置和自然恢复均有实例；结论尚不能推广为通用策略。",
            "52 main branches plus 20 validation branches. Retention, reset and native recovery all have examples; none establishes a universal policy.",
        ),
        evidence="natural-recovery-results/manifest.json",
    ),
    Stage(
        "runs",
        ("正式评估待办", "Formal evaluation still pending"),
        (
            "明确开发结果的适用范围，以及正式评估还缺什么。",
            "State the scope of the development results and what formal evaluation still needs.",
        ),
        (
            "保留集评分、正式 AP 与预热同步的端到端计时尚未完成。",
            "Held-out scores, formal AP and warmed, synchronized end-to-end timing remain unfinished.",
        ),
        "pending",
    ),
)
BY_PAGE = {stage.page: stage for stage in STAGES}
GROUPS = (
    (("起点与基线", "Question to baselines"), ("index", *(s.page for s in STAGES[:4]))),
    (("H/R 实验", "H/R studies"), tuple(s.page for s in STAGES[4:9])),
    (("评估与查证", "Evaluation & records"), ("runs",)),
)
SPLIT_MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "experiments/manifests/ytvis2021-200-seed550-v1.json"
)


def tr(language, pair):
    return pair[language == "en"]


def href(page, language, anchor=""):
    return (
        page
        + (".en.html" if language == "en" else ".html")
        + ("#" + anchor if anchor else "")
    )


def stage_href(stage, language):
    return href(stage.page, language, stage.anchor)


def baseline_fp_example(evidence):
    """Prefer the documented duplicate rider; otherwise use a saved B0 FP frame."""
    if not evidence:
        return None
    videos = evidence["viewer"]["videos"]
    for video in videos:
        if str(video["id"]) == "2686" and len(video["B0"]) > 7 and video["B0"][7]["FP"]:
            return video["id"], 7
    return next(
        (
            (v["id"], frame)
            for v in videos
            for frame, row in enumerate(v["B0"])
            if row["FP"]
        ),
        None,
    )


def baseline_frame_href(language, video, frame):
    return f"{href('results', language)}?video={video}&frame={frame}#viewer"


def label(page, language):
    if page == "index":
        return tr(language, ("实验总览", "Project overview"))
    return (
        f"{STAGES.index(BY_PAGE[page]) + 1:02d} · {tr(language, BY_PAGE[page].title)}"
    )


def has_evidence(stage, output):
    return bool(
        output is not None
        and stage.evidence
        and (Path(output) / stage.evidence).is_file()
    )


def latest(output):
    return next(
        (stage for stage in reversed(STAGES) if has_evidence(stage, output)), None
    )


def status(stage, output, language):
    if stage.page == "runs":
        return "pending", tr(language, ("尚未完成", "Pending"))
    if stage.evidence:
        return (
            ("done", tr(language, ("开发证据已导入", "Development evidence available")))
            if has_evidence(stage, output)
            else (
                "unavailable",
                tr(language, ("此副本未导入证据", "Evidence absent from this copy")),
            )
        )
    return "reference", tr(language, ("设计与说明", "Design & context"))


def takeaway(stage, output, language):
    if stage.evidence and not has_evidence(stage, output):
        return tr(
            language,
            (
                "当前副本可阅读流程，未附保存的测量、视频或帧证据。",
                "This copy documents the workflow; saved measurements, video or frame evidence are not attached.",
            ),
        )
    return tr(language, stage.takeaway)


def split_status(language):
    """Describe the selected split from the recorded manifest, without scanning data."""
    try:
        data = json.loads(SPLIT_MANIFEST.read_text(encoding="utf-8"))
        dev, val, held = (
            len(data["splits"][k]) for k in ("development", "validation", "evaluation")
        )
        frozen = (
            data["status"].startswith("frozen_")
            and dev + val + held == data["selected_video_count"]
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        frozen = False
    if frozen:
        return tr(
            language,
            (
                f"{dev+val+held} 段划分已冻结：{dev} 开发、{val} 验证、{held} 保留评估。",
                f"The {dev+val+held}-video split is frozen: {dev} development, {val} validation and {held} held out for evaluation.",
            ),
        )
    return tr(
        language,
        (
            "此副本未找到可核对的冻结划分。",
            "This copy has no verifiable frozen split manifest.",
        ),
    )


def assessment(language):
    return (
        "<p>"
        + escape(split_status(language) + " " + tr(language, BY_PAGE["runs"].takeaway))
        + "</p><p>"
        + escape(
            tr(
                language,
                (
                    "前面的案例与队列都属于开发研究。复跑分支和同一轨迹的多个读数不能增加独立样本量。",
                    "Earlier cases and cohorts are development studies. Repeat branches and multiple readouts of one trajectory do not increase the independent sample count.",
                ),
            )
        )
        + "</p>"
    )


def route_map(output, language):
    rows = []
    for index, stage in enumerate(STAGES, 1):
        kind, state = status(stage, output, language)
        rows.append(
            f'<li class="journey-row" data-stage="{stage.page}"><span class="journey-number" aria-hidden="true">{index:02d}</span>'
            f'<div><div class="journey-row-title"><a href="{stage_href(stage, language)}">{escape(tr(language, stage.title))}</a>'
            f'<span class="journey-state {kind}">{escape(state)}</span></div>'
            f'<p>{escape(tr(language, stage.purpose))}</p><p class="journey-takeaway">{escape(takeaway(stage, output, language))}</p></div></li>'
        )
    return '<ol class="journey-map">' + "".join(rows) + "</ol>"


def stage_brief(page, output, language):
    stage = BY_PAGE[page]
    kind, state = status(stage, output, language)
    return (
        f'<aside class="journey-brief" data-stage="{page}"><div class="journey-row-title">'
        f'<a href="{href("index", language, "experiment-route")}">{escape(tr(language, ("实验主线", "Experiment route")))} · {STAGES.index(stage)+1:02d}/{len(STAGES):02d}</a>'
        f'<span class="journey-state {kind}">{escape(state)}</span></div>'
        f'<p>{escape(tr(language, stage.purpose))}</p><p class="journey-takeaway">{escape(takeaway(stage, output, language))}</p></aside>'
    )


def stage_turns(page, language):
    index = STAGES.index(BY_PAGE[page])

    def item(neighbor, caption, rel):
        return (
            f'<a class="journey-turn {rel}" data-route-{rel} href="{stage_href(neighbor, language)}">'
            f"<span>{escape(tr(language, caption))}</span><strong>{escape(label(neighbor.page, language))}</strong></a>"
        )

    previous = (
        item(STAGES[index - 1], ("← 上一步", "← Previous step"), "prev")
        if index
        else ""
    )
    forward = (
        item(STAGES[index + 1], ("下一步 →", "Next step →"), "next")
        if index + 1 < len(STAGES)
        else ""
    )
    return f'<nav class="journey-turns" aria-label="{tr(language, ("实验主线前后步骤", "Adjacent steps in the experiment route"))}">{previous}{forward}</nav>'
