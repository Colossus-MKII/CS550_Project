"""Curated, bilingual H/R evidence pages. Never import or run a model here.

Only reviewed artifacts enter the existing website. Immutable baseline files,
raw masks and machine-specific paths stay outside this import.
"""

import argparse
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re
import shutil

from .navigation import decorate_page
from .study import WEB, link, pick, section

PAGES = ("recovery.html", "recovery.en.html")
EVENTS = {"equestrian-person-poor-mask": "rider", "cat-stable-control": "cat"}
GROUPS = ("A-H", "A-R", "B-H", "B-R")
CODE = (
    "recovery.py",
    "recovery_engines.py",
    "recovery_events.py",
    "recovery_state.py",
    "recovery_metrics.py",
    "sam_io.py",
)


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def import_recovery(source, output):
    """Require checked outputs and exact repeat proof; expose a strict allowlist."""
    source, output = Path(source).resolve(), Path(output).resolve()
    summary = read_json(source / "summary.json")
    verification = read_json(source / "verification.json")
    repeat = read_json(source / "repeat-verification.json")
    if (
        summary["status"] != "completed"
        or verification["status"] != "passed"
        or repeat["status"] != "passed"
    ):
        raise ValueError(
            "Only completed, verified and repeated H/R results may be imported"
        )
    if digest(source / "summary.json") not in (
        repeat["first_summary_sha256"],
        repeat["second_summary_sha256"],
    ):
        raise ValueError("Repeat proof does not cover this summary")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", source.name):
        raise ValueError("Unsafe run name")
    if len(summary["events"]) != 2 or {e["name"] for e in summary["events"]} != set(
        EVENTS
    ):
        raise ValueError("This analysis covers only the reviewed rider/cat batch")
    baseline_source = Path(summary["baseline_source"])
    if digest(baseline_source / "summary.json") != summary["baseline_summary_sha256"]:
        raise ValueError("Source baseline changed")
    baseline = read_json(output / "pilot-results/manifest.json")
    if baseline["run"] != baseline_source.name:
        raise ValueError("Website baseline does not match the H/R experiment")
    if any(
        summary["synchronized_reference"]["historical_B0_different_frames"].values()
    ):
        raise ValueError("H/R replay differs from the corrected baseline")
    config = summary["configuration"]
    reviewed = {
        "equestrian-person-poor-mask": (2718, 1, 14),
        "cat-stable-control": (2689, 2, 20),
    }
    if (config["window"], config["mask_iou_threshold"], config["streak_required"]) != (
        8,
        0.5,
        3,
    ) or any(
        (e["video_id"], e["gt_id"], e["frame"]) != reviewed[e["name"]]
        for e in summary["events"]
    ):
        raise ValueError(
            "This narrative requires the reviewed rider/cat events and recovery rule"
        )
    if config["conditions"] != ["yolo", "reference"] or len(summary["branches"]) != 16:
        raise ValueError("Incomplete two-condition four-group batch")
    expected = {
        (name, condition, group)
        for name in EVENTS
        for condition in config["conditions"]
        for group in GROUPS
    }
    actual = {(r["event"], r["condition"], r["group"]) for r in summary["branches"]}
    if expected != actual or verification["branches"] != 16 or repeat["branches"] != 16:
        raise ValueError("H/R branch coverage differs")

    destination = output / "recovery-results" / source.name
    files, curves, references = {}, {}, {}

    def copy(relative):
        src, target = source / relative, destination / relative
        if target.exists() and digest(target) != digest(src):
            raise ValueError("Refuse to overwrite different archived H/R evidence")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        files[relative] = digest(target)

    for event in summary["events"]:
        for condition in config["conditions"]:
            key = f'{event["name"]}-{condition}'
            for suffix in ("curves.png", "four-groups.mp4", "baseline.json"):
                copy(f"visuals/{key}-{suffix}")
            for offset in (1, 3, config["window"]):
                copy(f'visuals/{key}-step{event["frame"] + offset}.png')
            references[key] = read_json(source / f"visuals/{key}-baseline.json")
    for record in summary["branches"]:
        folder = f'{record["event"]}/{record["condition"]}/{record["group"]}'
        if record["folder"] != folder:
            raise ValueError("Unexpected branch path")
        copy(folder + "/recovery.json")
        curves[folder] = read_json(source / folder / "recovery.json")
        if any(
            record[key] != value for key, value in curves[folder]["summary"].items()
        ):
            raise ValueError("Branch scores disagree with the saved recovery curve")
    for name in CODE:
        relative = "code/" + name + ".txt"
        if digest(source / relative) != summary["source_sha256"][name]:
            raise ValueError("Inference source snapshot differs")
        copy(relative)
    for name in (
        "config.json",
        "events.json",
        "verification.json",
        "repeat-verification.json",
        "paired-differences.csv",
        "frame-curves.csv",
        "association-audit.json",
    ):
        copy(name)
    manifest = {
        "kind": "verified-rider-cat-hr",
        "run": source.name,
        "prefix": f"recovery-results/{source.name}/",
        "baseline_run": baseline["run"],
        "baseline_summary_sha256": summary["baseline_summary_sha256"],
        "configuration": config,
        "events": summary["events"],
        "branches": summary["branches"],
        "curves": curves,
        "references": references,
        "verification": verification,
        "repeat": repeat,
        "associations": read_json(source / "association-audit.json"),
        "device": summary["environment"]["device"],
        "created_utc": summary["created_utc"],
        "weights": summary["weights"],
        "files": files,
    }
    # summary.json contains private absolute paths; do NOT copy it to the site.
    public = json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    archived = destination / "evidence.json"
    if archived.exists() and archived.read_text(encoding="utf-8") != public:
        raise ValueError("Refuse to overwrite a different archived H/R manifest")
    archived.write_text(public, encoding="utf-8")
    active = output / "recovery-results/manifest.json"
    if active.exists() and read_json(active)["run"] != source.name:
        backup = active.with_name("manifest-" + read_json(active)["run"] + ".json")
        if not backup.exists():
            shutil.copy2(active, backup)
    active.write_text(public, encoding="utf-8")
    write_recovery_pages(output)
    return manifest


def read_recovery(output):
    path = Path(output) / "recovery-results/manifest.json"
    if not path.is_file():
        return None
    data = read_json(path)
    if not re.fullmatch(r"recovery-results/[A-Za-z0-9_-]+/", data["prefix"]):
        raise ValueError("Unsafe H/R evidence prefix")
    if (
        read_json(Path(output) / "pilot-results/manifest.json")["run"]
        != data["baseline_run"]
    ):
        raise ValueError("Active website baseline no longer matches H/R evidence")
    if (
        data["verification"]["status"] != "passed"
        or data["repeat"]["status"] != "passed"
    ):
        raise ValueError("Unverified H/R evidence")
    # Check every curated artifact, including figures, video, curves and code.
    root = Path(output) / data["prefix"]
    for name, expected in data["files"].items():
        relative = Path(name)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not (root / relative).resolve().is_relative_to(root.resolve())
        ):
            raise ValueError("Unsafe H/R artifact path")
        if digest(root / relative) != expected:
            raise ValueError("H/R evidence fingerprint differs: " + name)
        if (
            name.endswith(".csv")
            and (root / (name + ".txt")).exists()
            and digest(root / (name + ".txt")) != expected
        ):
            raise ValueError("H/R CSV download alias fingerprint differs")
    if read_json(root / "evidence.json") != data:
        raise ValueError("H/R manifest differs from its archived evidence")
    return data


def recovery_link(output, language, label=None):
    if not (Path(output) / "recovery-results/manifest.json").is_file():
        return ""
    return link(
        "recovery" + (".en" if language == "en" else "") + ".html",
        label
        or pick(language, "继续：骑手／猫 H/R 实测 →", "Next: rider/cat H/R results →"),
    )


def results_table(data, event, condition, language):
    from .program_page import table

    t = lambda zh, en: pick(language, zh, en)
    rows = []
    key = f'{event["name"]}-{condition}'
    for letter in ("A", "B"):
        h, r = (
            data["curves"][f'{event["name"]}/{condition}/{letter}-{suffix}']["summary"]
            for suffix in ("H", "R")
        )
        base = data["references"][key][letter]["summary"]
        rows.append(
            [
                letter + (" · ByteTrack" if letter == "A" else " · SAM"),
                f'{base["mean_visible_mask_iou"]:.4f}',
                f'{h["mean_visible_mask_iou"]:.4f}',
                f'{r["mean_visible_mask_iou"]:.4f}',
                f'{h["correct_visible_steps"]}/{h["visible_steps"]} · {r["correct_visible_steps"]}/{r["visible_steps"]}',
                f'{h["longest_correct_streak"]} · {r["longest_correct_streak"]}',
                f'{h["relapses"]} · {r["relapses"]}',
            ]
        )
    return table(
        [
            t("系统", "System"),
            t("无额外纠正 IoU", "Uncorrected IoU"),
            "H IoU",
            "R IoU",
            t("正确步 H · R", "Correct steps H · R"),
            t("最长连续 H · R", "Longest streak H · R"),
            t("复发 H · R", "Relapses H · R"),
        ],
        rows,
        f'hr-{EVENTS[event["name"]]}-{condition}-scores',
    )


def case_content(data, event, language, output=None):
    from .recovery_long_page import long_link

    t = lambda zh, en: pick(language, zh, en)
    suffix = ".en" if language == "en" else ""
    rider = EVENTS[event["name"]] == "rider"
    base_frame = event["frame"]
    text = (
        "<p>"
        + t(
            "基线里，2718 第 14 步的骑手 B0 mask IoU 只有 0.324，YOLO mask 为 0.651；马本身不是这个失败目标。",
            "In the baseline, rider B0 mask IoU at 2718/14 is only 0.324 versus YOLO mask 0.651. The horse is not the failed target.",
        )
        if rider
        else "<p>"
        + t(
            "2689 的猫在检测空档中仍被 SAM 稳定描出。本事件检验重置是否改善或破坏可靠视觉历史；不表示 ByteTrack 在这段也始终稳定。",
            "SAM keeps the cat segmented through a detector gap in 2689. This tests whether resetting helps or harms reliable visual history; it does not mean ByteTrack is stable throughout the clip.",
        )
    )
    text += (
        "</p><p>"
        + link(
            f'results{suffix}.html?video={event["video_id"]}&frame={base_frame}#viewer',
            t("先回看对应基线帧 →", "First inspect the corresponding baseline frame →"),
        )
        + "</p>"
    )
    ids = " / ".join(str(event["anchors"][m]["prediction_id"]) for m in ("A0", "B0"))
    text += (
        '<p class="small">'
        + t(
            f'纠正步 {base_frame}；GT {event["gt_id"]}；固定 A/B ID：{ids}；评分步 {base_frame+1}–{base_frame+data["configuration"]["window"]}。',
            f'Correction step {base_frame}; GT {event["gt_id"]}; fixed A/B IDs: {ids}; scored steps {base_frame+1}–{base_frame+data["configuration"]["window"]}.',
        )
        + "</p>"
    )
    for condition in ("yolo", "reference"):
        tag = EVENTS[event["name"]] + "-" + condition
        prefix = data["prefix"] + "visuals/" + event["name"] + "-" + condition
        label = (
            t("YOLO 实际框", "Actual YOLO box")
            if condition == "yolo"
            else t(
                "标注参考框：单独条件，不是全自动成绩",
                "Annotation-derived reference box: separate condition, not automatic-system performance",
            )
        )
        text += (
            f'<details class="hr-condition" id="{tag}" data-hr-condition="{tag}"'
            + (" open" if condition == "yolo" else "")
            + "><summary>"
            + label
            + "</summary>"
        )
        text += results_table(data, event, condition, language)
        text += f'<img loading="lazy" src="{prefix}-curves.png" alt="{escape(t("A/B 保留、重置与无额外纠正的逐步 IoU 曲线", "Stepwise IoU curves for retain, reset and uncorrected A/B"),quote=True)}">'
        text += (
            '<p class="small">'
            + t(
                "左图 A，右图 B；绿 H、橙 R、灰色无额外纠正。重合曲线可能互相覆盖，不表示缺了一组。",
                "Left: A; right: B. Green: H; orange: R; gray: uncorrected. Overlapping curves may hide one another; no group is omitted.",
            )
            + "</p>"
        )
        text += (
            f'<details id="player-{tag}"><summary>{t("播放四组同屏视频", "Play four-group comparison video")}</summary><p>'
            + t(
                "上排原图／指定 GT，中排 A-H／A-R，下排 B-H／B-R。只显示指定 ID，不是全画面误检清理结果。5 fps 仅为浏览速度。",
                "Top: RGB/designated GT; middle: A-H/A-R; bottom: B-H/B-R. Only the designated ID is shown, not whole-frame FP cleanup. Five fps is browsing speed only.",
            )
            + f'</p><video id="video-{tag}" controls preload="none" poster="{prefix}-step{base_frame+1}.png" src="{prefix}-four-groups.mp4"></video></details>'
        )
        text += f'<details id="last-{tag}"><summary>{t("查看观察窗口末帧", "Inspect the last observation step")}</summary><img loading="lazy" src="{prefix}-step{base_frame+data["configuration"]["window"]}.png" alt="{t("四组观察窗口末帧", "Last observation step for four groups")}"></details></details>'
    if rider:
        text += (
            "<h3>"
            + t("这里究竟发生了什么？", "What actually happened?")
            + "</h3><ol><li>"
            + t(
                "ByteTrack／YOLO 条件：H 在 17 步把 ID1 关联到检测 3，另一个 ID40 使用检测 1；R 的 ID1 使用检测 1。18 步 H 的 ID1 无输出，但骑手仍由 ID40 检出。R 则延续 ID1，8/8 步正确。因此是身份关联的差异，不是 R 训练出了更强的检测器。",
                "ByteTrack / YOLO condition: at step 17, H assigns ID1 to detection 3 while ID40 uses detection 1; R assigns ID1 to detection 1. At 18, H has no ID1 output but ID40 still detects the rider. R preserves ID1 and is correct on 8/8 steps. This is an association difference, not a better-trained detector.",
            )
            + "</li><li>"
            + t(
                "换成参考框后，A-H/A-R 的输出相同，都只正确 3/8 步并随后复发。重置优势依赖纠正条件，不能从 YOLO 条件推出普遍结论。",
                "With reference boxes, A-H/A-R outputs are identical: both are correct on 3/8 steps and then relapse. Reset benefits depend on the correction condition; the YOLO result is not a universal rule.",
            )
            + "</li><li>"
            + t(
                "SAM：两种框条件下 R 的平均 IoU 都提高，但正确的 3 步并不连续，最长只有 2 步。它改善了 mask，却没有达到持续恢复标准。",
                "SAM: R improves mean IoU under both box conditions, but its three correct steps are not consecutive; the longest streak is two. Masks improve without meeting the sustained-recovery criterion.",
            )
            + "</li></ol>"
        )
        text += association_table(data, language)
    else:
        text += (
            "<h3>"
            + t("这个对照告诉我们什么？", "What does this control tell us?")
            + "</h3><p>"
            + t(
                "SAM 的 H/R 都保持 8/8 步正确，平均 IoU 差小于 0.001，而且方向随框条件变化：没有明显重置收益，也没有观察到明显损伤。ByteTrack 在 23 步起缺少猫检测，两组都只能正确输出前两步；重置运动状态不能凭空补出分割 mask。",
                "SAM H/R are both correct on 8/8 steps, with mean-IoU differences below 0.001 and direction changing across box conditions: no clear reset benefit or observed harm. ByteTrack lacks cat detections from step 23, so both branches are correct only on the first two steps. Resetting motion state cannot invent a segmentation mask.",
            )
            + "</p>"
        )
    extension = (
        long_link(output, language, anchor="#" + EVENTS[event["name"]])
        if output is not None
        else ""
    )
    if extension:
        text += (
            '<p class="status-note">'
            + t(
                "以上仅限 8 步窗口。继续看同一事件的长窗口，区分延迟恢复与后续丢失。",
                "These findings cover eight steps only. Follow the same event longer to distinguish delayed recovery from later loss.",
            )
            + " "
            + extension
            + "</p>"
        )
    return text


def association_table(data, language):
    from .program_page import table

    t = lambda zh, en: pick(language, zh, en)
    rows = []
    for row in data["associations"]["frames"]:
        if (
            row["event"] != "equestrian-person-poor-mask"
            or row["condition"] != "yolo"
            or row["frame"] not in (17, 18)
        ):
            continue
        items = [x for x in row["outputs"] if x["id"] == row["designated_id"]]
        other = [
            str(x["id"])
            for x in row["outputs"]
            if x["id"] != row["designated_id"] and x["target_mask_iou"] >= 0.5
        ]
        rows.append(
            [
                str(row["frame"]),
                row["group"],
                ", ".join(str(x) for i in items for x in i["source_detection_indices"])
                or "—",
                (
                    f'{items[0]["target_mask_iou"]:.3f}'
                    if items
                    else t("指定 ID 无输出", "No designated-ID output")
                ),
                ", ".join(other) or "—",
            ]
        )
    return (
        "<details><summary>"
        + t(
            "证据：ByteTrack 从哪一步开始分岔？",
            "Evidence: where did ByteTrack diverge?",
        )
        + "</summary>"
        + table(
            [
                t("步", "Step"),
                t("组", "Group"),
                t("ID1 的检测来源", "ID1 detector source"),
                "ID1 IoU",
                t("其他合格 ID", "Other qualifying IDs"),
            ],
            rows,
            "hr-association-evidence",
        )
        + '<p class="small">'
        + t(
            "来源按输出与 YOLO 的 mask、框、分数精确一致重建；不是内部匹配代价日志。GT IoU 仅事后诊断，没有用于后续自动关联。",
            "Sources are reconstructed by exact mask/box/score equality with YOLO, not internal assignment-cost logs. GT IoU is offline diagnosis, not a future association input.",
        )
        + "</p></details>"
    )


def content(data, language, output=None):
    t = lambda zh, en: pick(language, zh, en)
    suffix = ".en" if language == "en" else ""
    if not data:
        return [
            (
                "status",
                t("H/R 实测记录", "H/R measurements"),
                "<p>"
                + t(
                    "尚未导入已验证的 H/R 结果，不显示示例分数。",
                    "No verified H/R run has been imported; no placeholder scores are displayed.",
                )
                + "</p>",
            )
        ]
    cfg = data["configuration"]
    design = (
        '<ol class="hr-journey">'
        + "".join(
            "<li>" + t(*pair) + "</li>"
            for pair in [
                (
                    "先看修正版 A0/B0，选真实失败与稳定对照。",
                    "Inspect corrected A0/B0; select a genuine failure and a stable control.",
                ),
                (
                    "各系统复制自己的相同前史；H 保留历史，R 重建该目标状态；两组都接收相同框一次。",
                    "Fork each system's own identical prefix. H retains history; R reinitializes target state. Both receive the same box once.",
                ),
                (
                    "恢复正常后续输入，固定原目标 ID，不追加人工纠正。",
                    "Resume native inputs, keep the designated ID fixed and add no further manual corrections.",
                ),
                (
                    "排除纠正当帧，看后续质量、正确持续时间和复发，不只看刚画框时。",
                    "Exclude the correction frame; inspect subsequent quality, duration and relapse, not just the freshly prompted output.",
                ),
            ]
        )
        + "</ol><p>"
        + t(
            f'本批：2 个事件 × 2 种框来源 × 4 组 = 16 分支；权重冻结。后续 {cfg["window"]} 步、mask IoU ≥ {cfg["mask_iou_threshold"]}，连续 {cfg["streak_required"]} 个可见步才确认达标。缺输出计失败；曾经达标后再失败计复发。',
            f'This batch: 2 events × 2 box sources × 4 groups = 16 branches; weights fixed. Score the next {cfg["window"]} steps at mask IoU ≥ {cfg["mask_iou_threshold"]}; confirmation requires {cfg["streak_required"]} consecutive visible correct steps. Missing outputs fail; failure after confirmation is a relapse.',
        )
        + '</p><p class="small">'
        + t(
            "表中的 IoU 是指定 ID 在同一观察窗口内、所有可见步的平均 mask IoU（0–1），不是五类 HOTA／IDF1。无额外纠正列也只评价这个目标、这 8 步。",
            "Table IoU is mean designated-ID mask IoU over visible steps in the same window (0–1), not five-class HOTA/IDF1. The uncorrected column also evaluates only this target and these eight steps.",
        )
        + "</p><p>"
        + t(
            "A-H/A-R 改变 ByteTrack 的运动状态；B-H/B-R 改变 SAM 的目标历史。参考框来自 GT 外接框，单独报告，不代表自动纠正或自动重识别。",
            "A-H/A-R change ByteTrack motion state; B-H/B-R change SAM target history. Reference boxes come from GT bounds and are reported separately, not as automatic correction or re-identification.",
        )
        + "</p><p>"
        + link(
            "experiments" + suffix + ".html#walkthrough",
            t("完整对照方案 →", "Full controlled protocol →"),
        )
        + " · "
        + link(
            "program" + suffix + ".html#recovery",
            t("对应程序与函数 →", "Related program/functions →"),
        )
        + "</p>"
    )
    blocks = [
        (
            "design",
            t("从基线到四组实测", "From baselines to four measured groups"),
            design,
        )
    ]
    for event in data["events"]:
        rider = EVENTS[event["name"]] == "rider"
        blocks.append(
            (
                EVENTS[event["name"]],
                (
                    t("骑手：重置何时有用？", "Rider: when does reset help?")
                    if rider
                    else t(
                        "猫：稳定历史需要重置吗？",
                        "Cat: should stable history be reset?",
                    )
                ),
                case_content(data, event, language, output),
            )
        )
    blocks.append(
        (
            "limits",
            t("能得出什么，不能得出什么", "Findings and limits"),
            "<p>"
            + t(
                "本批支持：历史处理能改变结果，而且收益依赖场景与纠正条件。此8步窗口内，SAM尚未确认恢复；这不等于以后也无法恢复。不支持重置普遍更好或运动记忆优于视觉记忆。两个事件只是开发预实验，不是正式200段结论。",
                "Supported: history handling can change outcomes depending on event and correction conditions. SAM has not confirmed recovery within these eight steps; this does not mean later recovery is impossible. Reset is not universally better, nor is motion memory proven superior. Two development events are not the formal 200-video study.",
            )
            + "</p><p>"
            + t(
                "下一步扩展同类视频，重点看 A 的重复检测竞争与提示条件敏感性、B 的改善持续多久；继续保留稳定对照。先锁定规则再看保留评估，不直接据此制定“出错就清空”策略。",
                "Next, expand comparable videos: investigate A's competing detections and prompt-condition sensitivity, and how long B's improvement lasts. Keep stable controls. Freeze rules before held-out evaluation; do not turn this pilot into an automatic reset-on-error rule.",
            )
            + "</p>",
        )
    )
    prefix = data["prefix"]
    downloads = " · ".join(
        (
            link(
                prefix + name + (".txt" if name.endswith(".csv") else ""), label
            ).replace("<a ", '<a download="' + name + '" ', 1)
            if name.endswith(".csv")
            else link(prefix + name, label)
        )
        for name, label in [
            ("paired-differences.csv", t("配对汇总 CSV", "Paired summary CSV")),
            ("frame-curves.csv", t("逐步曲线 CSV", "Stepwise curves CSV")),
            ("association-audit.json", t("关联来源审计", "Association provenance")),
            ("verification.json", t("干预与重算验证", "Intervention/rescoring checks")),
            (
                "repeat-verification.json",
                t("完整推理复跑验证", "Complete inference-repeat proof"),
            ),
            ("config.json", t("本批固定配置", "Frozen batch configuration")),
            (
                "evidence.json",
                t("完整公开证据清单", "Complete public evidence manifest"),
            ),
        ]
    )
    provenance = (
        "<p>"
        + t(
            f'运行：{data["run"]}；设备：{data["device"]}。完整复跑的 {data["repeat"]["saved_branch_frames"]} 个已保存分支帧、{data["repeat"]["masks_compared"]} 个实例 mask、ID、框和评分曲线完全一致。',
            f'Run: {data["run"]}; device: {data["device"]}. A complete independent repeat exactly matched {data["repeat"]["saved_branch_frames"]} saved branch frames, {data["repeat"]["masks_compared"]} instance masks, IDs, boxes and score curves.',
        )
        + '</p><p class="small">'
        + t(
            "这是本机当前配置下的重复性观察，不是所有平台逐位确定性的保证。早期 24 分支用于实现冒烟检查，本页展示的是修正版基线后的这批 16 分支。",
            "This is observed repeatability on this setup, not a universal bitwise-determinism guarantee. The earlier 24 branches checked implementation; this page shows the 16-branch batch after baseline correction.",
        )
        + "</p><p>"
        + downloads
        + "</p><details><summary>"
        + t("查阅本次推理源码快照", "Read inference source snapshots")
        + "</summary><p>"
        + " · ".join(link(prefix + "code/" + name + ".txt", name) for name in CODE)
        + "</p></details>"
    )
    blocks.append(
        (
            "records",
            t("记录、下载与复现证据", "Records, downloads and reproducibility"),
            provenance,
        )
    )
    return blocks


def write_recovery_pages(output):
    output = Path(output)
    data = read_recovery(output)
    if data:
        # The existing server intentionally allows .txt but not .csv. Preserve
        # its running process/security scope: expose exact-byte text aliases,
        # with download filenames ending in .csv; do not restart the service.
        for name in ("paired-differences.csv", "frame-curves.csv"):
            root = output / data["prefix"]
            shutil.copy2(root / name, root / (name + ".txt"))
    template = (WEB / "study.html").read_text(encoding="utf-8")
    css = "".join(
        (WEB / name).read_text(encoding="utf-8")
        for name in ("tutorial.css", "study.css", "recovery.css")
    )
    for language, filename in zip(("zh", "en"), PAGES):
        t = lambda zh, en: pick(language, zh, en)
        suffix = ".en" if language == "en" else ""
        blocks = content(data, language, output)
        intro = (
            "<p>"
            + t(
                "从基线发现的失败出发，看相同纠正之后，保留或重置历史究竟改变了什么。",
                "Start from a baseline failure and examine what retaining or resetting history changes after the same correction.",
            )
            + "</p><p>"
            + link("results" + suffix + ".html", t("① A0/B0 基线", "① A0/B0 baselines"))
            + " → "
            + link("#design" if data else "#status", t("② 同框 H/R", "② Same-box H/R"))
            + " → "
            + link(
                "#rider" if data else "#status",
                t("③ 实测与解释", "③ Measurements and interpretation"),
            )
            + "</p>"
        )
        from .recovery_long_page import long_link

        extension = long_link(output, language)
        if extension:
            intro += (
                '<p class="status-note">'
                + t(
                    "这是原始 8 步初测，分数与视频保留。30 步跟随补充发现：SAM R 会延迟恢复，猫会按期限删除；下文结论只适用于旧窗口。",
                    "This is the original eight-step pilot; scores and videos are preserved. Thirty-step follow-up reveals delayed SAM R recovery and cat lifecycle removal. Findings below apply only to the old window.",
                )
                + " "
                + extension
                + "</p>"
            )
        values = {
            "LANG": t("zh-CN", "en"),
            "TITLE": t(
                "8 步 H/R：骑手失败与猫稳定对照",
                "Eight-step H/R: Rider Failure and Stable Cat Control",
            ),
            "HOME": "index" + suffix + ".html",
            "OTHER": "recovery" + ("" if suffix else ".en") + ".html",
            "INTRO": intro,
            "CSS": css,
            "JS": (WEB / "study.js").read_text(encoding="utf-8")
            + (WEB / "recovery.js").read_text(encoding="utf-8"),
            "NAV": "".join(link("#" + key, label) for key, label, _ in blocks),
            "BODY": "".join(section(key, label, body) for key, label, body in blocks),
            "SWITCH": t("English", "中文"),
            "BACK": t("项目总览", "Project overview"),
            "MENU": t("本页目录", "On this page"),
            "THEME": t("切换主题", "Theme"),
            "SKIP": t("跳到正文", "Skip to content"),
            "TRAIL": t("真实实验 · 基线之后", "Real experiments · after baselines"),
            "FOOT": t(
                "只读取已验证结果；页面不运行模型。历史基线与 Proposal 保留不变。",
                "Reads verified outputs only; no models run on this page. Baseline archives and proposals remain unchanged.",
            ),
        }
        (output / filename).write_text(
            decorate_page(
                re.sub(r"@@([A-Z_]+)@@", lambda m: values[m[1]], template),
                language,
                "recovery",
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = import_recovery(args.source, args.output)
    print("Imported H/R:", result["run"])
