"""Bilingual follow-up: the same events beyond the original eight steps."""

from html import escape
from pathlib import Path
import re

from .navigation import decorate_page
from .program_page import table
from .recovery_long_data import CODE_LONG, EVENTS, PAGES, TABLES, read_long
from .study import WEB, link, pick, section


def long_link(output, language, label=None, anchor=""):
    if not (Path(output) / "recovery-long-results/manifest.json").exists():
        return ""
    return link(
        "recovery-long" + (".en" if language == "en" else "") + ".html" + anchor,
        label
        or pick(
            language,
            "继续：30 步跟随与刷新消融 →",
            "Continue: 30-step follow-up and refresh ablation →",
        ),
    )


def checkpoint_table(data, alias, condition, language, mode="normal"):
    t = lambda zh, en: pick(language, zh, en)
    event = next(name for name, value in EVENTS.items() if value == alias)
    rows = []
    for window in (8, 20, 30):
        for letter in (("A", "B") if mode == "normal" else ("B",)):
            h, r = [
                next(
                    x
                    for x in data["scores"]
                    if x["mode"] == mode
                    and x["event"] == event
                    and x["condition"] == condition
                    and int(x["window"]) == window
                    and x["group"] == letter + suffix
                )
                for suffix in ("-H", "-R")
            ]

            def confirmed(row):
                value = row["recovery_confirmed_offset"]
                return ("+" + value) if value else t("未确认", "Not confirmed")

            rows.append(
                [
                    str(window),
                    letter + " · " + ("ByteTrack" if letter == "A" else "SAM"),
                    f'{float(h["mean_visible_mask_iou"]):.4f} / {float(r["mean_visible_mask_iou"]):.4f}',
                    f'H {h["correct_visible_steps"]}/{h["visible_steps"]} · R {r["correct_visible_steps"]}/{r["visible_steps"]}',
                    confirmed(h) + " / " + confirmed(r),
                    h["longest_correct_streak"] + " / " + r["longest_correct_streak"],
                    h["relapses"] + " / " + r["relapses"],
                ]
            )
    return table(
        [
            t("窗口（步）", "Window (steps)"),
            t("系统", "System"),
            t("平均 IoU H / R", "Mean IoU H / R"),
            t("达标步 H / R", "Correct steps H / R"),
            t("首次确认偏移 H / R", "First confirmation offset H / R"),
            t("最长连续 H / R", "Longest streak H / R"),
            t("复发 H / R", "Relapses H / R"),
        ],
        rows,
        f"long-{mode}-{alias}-{condition}-scores",
    )


def timeline(points, language, label):
    return (
        '<ol class="long-timeline" aria-label="'
        + escape(label, quote=True)
        + '">'
        + "".join(
            "<li><strong>"
            + escape(step)
            + "</strong><span>"
            + escape(pick(language, zh, en))
            + "</span></li>"
            for step, zh, en in points
        )
        + "</ol>"
    )


def media(data, alias, condition, language, mode="normal"):
    t = lambda zh, en: pick(language, zh, en)
    run = data["runs"][mode]
    event = next(e for e in run["events"] if EVENTS[e["name"]] == alias)
    base = data["prefix"] + run["prefix"] + f'visuals/{event["name"]}-{condition}'
    tag = f"{mode}-{alias}-{condition}"
    title = (
        t("主实验", "Main experiment")
        if mode == "normal"
        else t("跳过一次刷新", "Skip one refresh")
    )
    confirmed = run["curves"][f'{event["name"]}/{condition}/B-R']["summary"][
        "recovery_confirmed_offset"
    ]
    jumps = (
        [
            (event["frame"] + confirmed, "确认恢复", "Recovery confirmed"),
            (35, "复发", "Relapse"),
            (44, "窗口末帧", "Last step"),
        ]
        if alias == "rider"
        else [
            (35, "删除前仍准确", "Accurate before removal"),
            (36, "生命周期删除", "Lifecycle removal"),
            (50, "窗口末帧", "Last step"),
        ]
    )
    buttons = (
        '<div class="long-seek">'
        + "".join(
            f'<button type="button" data-video="long-video-{tag}" data-seek="{(step-(event["frame"]-2))/5:.2f}">'
            + t(f"第 {step} 步：{zh}", f"Step {step}: {en}")
            + "</button>"
            for step, zh, en in jumps
        )
        + "</div>"
    )
    return (
        f'<details class="long-player" id="long-player-{tag}"><summary>'
        + t("查看四组视频与关键帧", "View four-group video and key steps")
        + " · "
        + title
        + "</summary><p>"
        + t(
            "上排原图／GT，中排 A-H／A-R，下排 B-H／B-R。只显示固定指定 ID；其他编号仍可能检测到同一对象。视频为 5 fps 浏览，非原始帧率或推理速度。",
            "Top: RGB/GT; middle: A-H/A-R; bottom: B-H/B-R. Only the fixed designated ID is shown; another ID may still detect the same object. Five fps is browsing speed, not source or inference speed.",
        )
        + "</p>"
        + buttons
        + f'<video id="long-video-{tag}" controls preload="none" poster="{base}-step{event["frame"]+1}.png" src="{base}-four-groups.mp4"></video><p>'
        + link(base + "-four-groups.mp4", t("下载该视频", "Download this video"))
        + "</p></details>"
        + f'<details id="long-last-{tag}"><summary>'
        + t(
            "窗口末帧：指定 ID 是否仍在？",
            "Last step: is the designated ID still present?",
        )
        + f'</summary><img loading="lazy" src="{base}-step{event["frame"]+30}.png" alt="'
        + escape(
            t("固定身份的四组末帧", "Last step of four fixed-ID groups"), quote=True
        )
        + '"></details>'
    )


def case(data, alias, language):
    t = lambda zh, en: pick(language, zh, en)
    suffix = ".en" if language == "en" else ""
    rider = alias == "rider"
    text = (
        "<p>"
        + t(
            (
                "同一骑手、同一纠正步 14、同一初始框。旧 8 步窗口止于第 22 步；SAM 的 R 要到第 23 步才确认连续 3 步达标。不是推翻旧评分，而是原观察窗口尚未覆盖确认时刻。"
                if rider
                else "同一只猫、纠正步 20。它是 SAM 的早期稳定对照，不表示 A/B 都全程稳定。长窗口揭示：分割仍准确时，指定 ID 也可能被系统规则删除。"
            ),
            (
                "Same rider, correction step 14 and initial box. The old eight-step window ends at 22; SAM R confirms three consecutive correct steps only at 23. The old scores remain correct—the window simply ended before confirmation."
                if rider
                else "Same cat, correction step 20. It is an early SAM-stability control, not an assertion that both A/B stay stable throughout. The longer window shows that a still-accurate target can be removed by lifecycle rules."
            ),
        )
        + "</p><p>"
    )
    video, frame = (2718, 14) if rider else (2689, 20)
    text += (
        link(
            f"recovery{suffix}.html#{alias}",
            t("回看同一事件的 8 步结果 →", "Review the same event over eight steps →"),
        )
        + " · "
        + link(
            f"results{suffix}.html?video={video}&frame={frame}#viewer",
            t("对应修正版基线帧 →", "Corresponding corrected baseline frame →"),
        )
        + "</p>"
    )
    if rider:
        text += timeline(
            [
                (
                    "14",
                    "一次同框纠正；当帧排除评分",
                    "One same-box correction; frame excluded",
                ),
                (
                    "21–22",
                    "R 开始连续达标，但旧窗口到此结束",
                    "R begins a correct streak; the old window ends here",
                ),
                (
                    "23",
                    "R 连续第 3 步达标，首次确认恢复（+9）",
                    "Third correct step confirms R recovery (+9)",
                ),
                (
                    "35",
                    "R 再次低于阈值：恢复不等于永久修好",
                    "R drops below threshold: recovery is not permanent repair",
                ),
                (
                    "39–44",
                    "R 又连续正确；H 全窗口未达标",
                    "R becomes correct again; H never reaches threshold",
                ),
            ],
            language,
            t("骑手 SAM 延迟恢复时间线", "Rider SAM delayed-recovery timeline"),
        )
    else:
        text += timeline(
            [
                ("20", "最后一次检测刷新／纠正", "Last detector refresh/correction"),
                (
                    "21–35",
                    "H/R 连续 15 步正确，YOLO 框条件均值约 0.926",
                    "H/R correct for 15 steps; mean about 0.926 with YOLO box",
                ),
                (
                    "36",
                    "超过 15 步保留期限，删除旧 ID1",
                    "Retention exceeds 15 steps; old ID1 removed",
                ),
                (
                    "45",
                    "系统发现新 ID；不算旧 ID1 恢复",
                    "A new ID is discovered; not recovery of old ID1",
                ),
                (
                    "50",
                    "指定旧 ID 仍无输出；GT 仍可见",
                    "Old designated ID still absent; GT remains visible",
                ),
            ],
            language,
            t("猫的生命周期时间线", "Cat lifecycle timeline"),
        )
    for condition in ("yolo", "reference"):
        title = (
            t("实际 YOLO 框", "Actual YOLO box")
            if condition == "yolo"
            else t(
                "标注参考框：独立诊断条件",
                "Annotation-derived reference box: separate diagnostic",
            )
        )
        text += (
            f'<details class="hr-condition" id="long-{alias}-{condition}"'
            + (" open" if condition == "yolo" else "")
            + "><summary>"
            + title
            + "</summary>"
        )
        text += checkpoint_table(data, alias, condition, language)
        prefix = (
            data["prefix"]
            + data["runs"]["normal"]["prefix"]
            + f"visuals/{next(n for n,a in EVENTS.items() if a==alias)}-{condition}"
        )
        text += (
            f'<img loading="lazy" src="{prefix}-curves.png" alt="'
            + t(
                "30 步固定 ID 的 H/R 和原生基线曲线",
                "Thirty-step fixed-ID H/R and native-baseline curves",
            )
            + '"><p class="small">'
            + t(
                "左 A、右 B；绿 H、橙 R、灰色无额外纠正。重合曲线可能互相遮挡。",
                "Left A, right B; green H, orange R, gray uncorrected. Overlapping curves may hide one another.",
            )
            + "</p>"
        )
        text += media(data, alias, condition, language) + "</details>"
    text += (
        '<p class="status-note">'
        + t(
            (
                "正常刷新下，两种框条件的 SAM R 均正确 22/30 步，最长连续 14 步；H 均为 0/30。R 有一次确认后的复发，不能写成全程稳定。ByteTrack 的 R 只在 YOLO 框条件把连续正确从 3 步延长到 14 步；参考框没有此优势。"
                if rider
                else "猫的 SAM 30 步平均 IoU 约 0.463，不是存活 mask 逐渐变差到这个水平，而是前 15 步高质量、后 15 步旧 ID 无输出。另一个晚期差异是 ByteTrack 参考框 R 在 44–46 步短暂找回原 ID，第 47 步又失效；不能概括为 A 始终无差异。"
            ),
            (
                "With normal refresh, SAM R is correct on 22/30 steps under both box sources, with a longest streak of 14; H is 0/30. R relapses once after confirmation, so it is not stable throughout. ByteTrack R extends the correct streak from three to 14 only with YOLO boxes; reference boxes show no such benefit."
                if rider
                else "Cat SAM mean IoU about 0.463 does not mean a surviving mask gradually degrades to that value: 15 high-quality steps are followed by 15 steps without the old ID. Another late difference: ByteTrack reference-box R briefly regains its ID at 44–46 and fails again at 47. A is not identical throughout under every condition."
            ),
        )
        + "</p>"
    )
    return text


def association(data, language):
    t = lambda zh, en: pick(language, zh, en)
    rows = []
    for condition in ("yolo", "reference"):
        for group in ("A-H", "A-R"):
            stage = data["associations"][f"{condition}/{group}/17"][0]
            ri = next(i for i, x in enumerate(stage["tracks"]) if x["external_id"] == 1)
            values = {
                d["detector_index"]: stage["assignment_cost"][ri][j]
                for j, d in enumerate(stage["detections"])
            }
            choice = next(
                stage["detections"][di]["detector_index"]
                for ti, di in stage["matches"]
                if ti == ri
            )
            rows.append(
                [
                    (
                        t("YOLO 框", "YOLO box")
                        if condition == "yolo"
                        else t("参考框", "Reference box")
                    ),
                    group,
                    f"{values[1]:.4f}",
                    f"{values[3]:.4f}",
                    str(choice),
                ]
            )
    return (
        "<p>"
        + t(
            "重置不改变 YOLO 已生成的 mask；它改变运动状态，再影响哪个检测被分配给原 ID。这里新增的是实际内部匹配日志，不再只有输出来源推断。",
            "Reset does not improve an already-generated YOLO mask. It changes motion state and hence which detection is assigned to the old ID. These are actual internal assignment logs, beyond the earlier output-provenance reconstruction.",
        )
        + "</p>"
        + table(
            [
                t("纠正条件", "Correction"),
                t("分支", "Branch"),
                t("检测 1 代价", "Detection 1 cost"),
                t("检测 3 代价", "Detection 3 cost"),
                t("第 17 步选择", "Step 17 choice"),
            ],
            rows,
            "long-costs",
        )
        + '<div class="long-reasons"><article><h3>'
        + t(
            "第 18 步：有合格检测，但竞争输了",
            "Step 18: admissible detection, lost competition",
        )
        + "</h3><p>"
        + t(
            "YOLO 框 H 的 ID1 到检测 1 代价为 0.7025，低于 0.8 门槛；但 ID40 的代价为 0.6155，一对一分配把检测给了 ID40。ID1 转入 Lost，并非画面里没人被检测到。R 的 ID1 代价为 0.6041，继续获得检测。",
            "With a YOLO box, H's ID1-to-detection-1 cost is 0.7025, below 0.8; competing ID40 costs 0.6155 and wins the one-to-one assignment. ID1 becomes Lost, although the rider is still detected. R's ID1 costs 0.6041 and keeps the detection.",
        )
        + "</p></article><article><h3>"
        + t("第 29 步：R 也会被门槛挡住", "Step 29: R also hits the matching limit")
        + "</h3><p>"
        + t(
            "R 延续到第 28 步；第 29 步候选检测 4 的原始框 IoU 约 0.557，但融合置信度后的代价为 0.8568，高于 0.8，低分阶段也没有可关联候选。它不是又一次同样的竞争失败。",
            "R lasts through 28. At 29, candidate detection 4 has raw box IoU about 0.557, but its score-fused cost is 0.8568, above 0.8; the low-confidence stage has no usable match. This is not the same competition failure repeated.",
        )
        + '</p></article></div><p class="small">'
        + t(
            "当前高分阶段使用 1 − IoU × 检测置信度。低于门槛不保证赢得全局一对一分配。协方差影响状态估计，但不是这里直接使用的匹配距离。",
            "The high-confidence stage uses 1 − IoU × detection confidence. Being under threshold does not guarantee a globally assigned match. Covariance affects state estimation but is not the direct matching distance here.",
        )
        + "</p>"
    )


def refresh(data, language):
    t = lambda zh, en: pick(language, zh, en)
    rows = []
    for condition in ("yolo", "reference"):
        values = []
        for mode in ("normal", "skip"):
            branches = data["runs"][mode]["curves"]
            h, r = [
                branches[f"equestrian-person-poor-mask/{condition}/B-{g}"]["summary"]
                for g in ("H", "R")
            ]
            values.append((h, r))
        normal, skipped = values
        rows.append(
            [
                (
                    t("YOLO 框", "YOLO box")
                    if condition == "yolo"
                    else t("参考框", "Reference box")
                ),
                f'{normal[0]["mean_visible_mask_iou"]:.4f} / {normal[1]["mean_visible_mask_iou"]:.4f}',
                f'{skipped[0]["mean_visible_mask_iou"]:.4f} / {skipped[1]["mean_visible_mask_iou"]:.4f}',
                f'{normal[1]["correct_visible_steps"]}/30 → {skipped[1]["correct_visible_steps"]}/30',
                f'+{normal[1]["recovery_confirmed_offset"]} → +{skipped[1]["recovery_confirmed_offset"]}',
            ]
        )
    body = (
        "<p>"
        + t(
            "独立消融：在同一个预定时刻，只不给指定目标下一次自动框提示。H/R 都跳过骑手第 15 步或猫第 25 步；其他目标正常，之后的刷新恢复，不额外延长生命周期。不是分别寻找 H/R 各自的下一次成功匹配。",
            "Separate ablation: at the same scheduled step, withhold only the designated target's next automatic box prompt. Both H/R skip rider step 15 or cat step 25; other targets continue normally, later refresh resumes and retention is not extended. We do not choose each branch's next successful match independently.",
        )
        + "</p>"
    )
    body += table(
        [
            t("骑手框", "Rider box"),
            t("正常 H / R IoU", "Normal H / R IoU"),
            t("跳过 H / R IoU", "Skip H / R IoU"),
            t("R 达标步：正常→跳过", "R correct: normal → skip"),
            t("R 首次确认偏移", "R confirmation offset"),
        ],
        rows,
        "long-refresh-scores",
    )
    body += (
        "<p>"
        + t(
            "骑手四个 SAM 分支均实际少了一次提示，但 R 优于 H 的关系没有反转。参考框 R 首次确认延后 1 步。它不支持差异被下一次刷新立刻消除；只跳过一次，也不能说明所有后续提示都不重要。",
            "All four rider SAM branches actually lose one prompt, but R remains better than H. Reference-box R confirms one step later. The gap is not immediately erased by the next refresh; skipping just once cannot establish that all later prompts are unimportant.",
        )
        + '</p><p class="status-note">'
        + t(
            "猫：预定跳过的第 25 步没有目标刷新匹配，因此没有实际提示被删掉。正常／跳过预测完全相同，是无实际干预对照，不是“刷新没有作用”的证据。A 的所有分支也完全一致，符合 SAM 开关不应改变 A 的负对照预期。",
            "Cat: step 25 has no target refresh match, so no actual prompt is removed. Normal/skip outputs are identical: a no-treatment control, not evidence that refresh has no effect. All A branches are also identical, as expected for a SAM-only switch.",
        )
        + "</p>"
    )
    for event, alias in EVENTS.items():
        for condition in ("yolo", "reference"):
            title = (
                (
                    t("骑手", "Rider")
                    if alias == "rider"
                    else t("猫：无实际提示跳过", "Cat: no prompt actually skipped")
                )
                + " · "
                + ("YOLO" if condition == "yolo" else t("参考框", "Reference box"))
            )
            body += (
                f'<details class="hr-condition" id="refresh-{alias}-{condition}"><summary>'
                + title
                + '</summary><img loading="lazy" src="'
                + data["prefix"]
                + f'{event}-{condition}-refresh-curves.png" alt="'
                + t(
                    "正常与跳过一次的 SAM H/R 曲线",
                    "SAM H/R curves with normal and skip-one refresh",
                )
                + '"><p class="small">'
                + t(
                    "绿／橙：正常 H/R；蓝／紫：跳过一次 H/R。曲线可能重合。",
                    "Green/orange: normal H/R; blue/purple: skip-one H/R. Curves may overlap.",
                )
                + "</p>"
                + media(data, alias, condition, language, "skip")
                + "</details>"
            )
    return body


def content(data, language):
    t = lambda zh, en: pick(language, zh, en)
    suffix = ".en" if language == "en" else ""
    if not data:
        return [
            (
                "status",
                t("长窗口结果", "Long-window results"),
                "<p>"
                + t(
                    "尚未导入已验证长窗口结果。",
                    "No verified long-window study imported.",
                )
                + "</p>",
            )
        ]
    design = (
        "<p>"
        + t(
            "同一骑手与猫事件、同一纠正时刻和框、同一固定外部 ID；只把主实验跟随延长到 30 步。8／20／30 步是同一份长预测的三个读数，不是三个独立样本。主实验 16 分支，刷新消融另 16 分支；模型权重不更新。",
            "Same rider/cat events, correction times, boxes and fixed external IDs; extend primary follow-up to 30 steps. The 8/20/30 checkpoints are three readings of one prediction, not independent samples. Main experiment: 16 branches; separate refresh ablation: 16 more. Model weights stay fixed.",
        )
        + "</p><p>"
        + t(
            "H 保留目标历史，R 重置；两者均接受一次相同纠正框。IoU 为指定 ID 可见步的平均 mask IoU（0–1），不是 HOTA／IDF1。排除纠正当帧，IoU≥0.5 且连续 3 个可见导出步才确认。首次确认不代表以后不复发。",
            "H retains target history; R resets it. Both receive the same box once. IoU is mean designated-ID mask IoU over visible steps (0–1), not HOTA/IDF1. Exclude correction frame; confirmation needs IoU≥0.5 for three consecutive visible exported steps. First confirmation does not rule out relapse.",
        )
        + "</p><p>"
        + link(
            "experiments" + suffix + ".html#walkthrough",
            t("四组设计与模型职责 →", "Four-group design and model roles →"),
        )
        + "</p>"
    )
    terms = (
        '<div class="long-reasons">'
        + "".join(
            "<article><h3>" + t(*heading) + "</h3><p>" + t(*body) + "</p></article>"
            for heading, body in [
                (
                    ("延迟恢复", "Delayed recovery"),
                    (
                        "同一 ID 后来才连续达标。骑手 SAM R 第 23 步确认，旧窗口止于 22；之后仍会复发。",
                        "The same ID reaches a correct streak later. Rider SAM R confirms at 23; the old window ends at 22. Relapse remains possible.",
                    ),
                ),
                (
                    ("关联失败", "Association failure"),
                    (
                        "原 ID 没拿到正确检测，可能是竞争分配或超门槛；其他 ID 仍可能看到目标。骑手 ByteTrack 同时出现两种情况。",
                        "The old ID does not receive the right detection, due to competition or a cost limit; another ID may still see the object. Rider ByteTrack exhibits both.",
                    ),
                ),
                (
                    ("生命周期删除", "Lifecycle removal"),
                    (
                        "规则主动删除目标状态，即使最后的 mask 很准。猫第 36 步到期删除；新 ID 不算原 ID 恢复。",
                        "A rule removes target state even when the latest mask is accurate. Cat expires at 36; a new ID is not recovery of the old one.",
                    ),
                ),
            ]
        )
        + "</div>"
    )
    records = (
        "<p>"
        + t(
            "两次独立完整复跑共核对 1,536 个分支帧、3,750 个实例 mask；ID、框、分数、mask、恢复曲线及 32 个分支状态日志一致。长窗口前 8 步与旧结果一致；原生 B0 与修正版基线重放一致。8 个主／消融视频已完整解码 264 帧。",
            "Two independent full repeats match 1,536 saved branch frames and 3,750 instance masks: IDs, boxes, scores, masks, recovery curves and 32 branch state traces agree. The first eight steps match prior results; native B0 replay matches corrected baselines. All eight main/ablation videos decode completely (264 frames).",
        )
        + "</p><p>"
    )
    for name, label in [
        ("checkpoint-pairs.csv", t("8／20／30 配对表", "8/20/30 paired table")),
        ("checkpoint-scores.csv", t("逐分支评分", "Branch scores")),
        ("prompt-timeline.csv", t("提示与删除时间线", "Prompt/removal timeline")),
        ("assignment-candidates.csv", t("实际匹配代价", "Actual assignment costs")),
        ("frame-curves.csv", t("逐步曲线", "Stepwise curves")),
    ]:
        records += (
            link(data["prefix"] + name + ".txt", label).replace(
                "<a ", f'<a download="{name}" ', 1
            )
            + " · "
        )
    records += (
        link(
            data["prefix"] + "final-verification.json",
            t("完整复核记录", "Complete verification"),
        )
        + " · "
        + link(
            data["prefix"] + "evidence.json",
            t("公开证据清单", "Public evidence manifest"),
        )
        + "</p>"
    )
    records += (
        '<details id="long-code"><summary>'
        + t("本批代码：实验步骤对应文件", "Code: experiment steps mapped to files")
        + "</summary>"
    )
    code_rows = [
        (
            "recovery.py",
            "execute()",
            t(
                "固定前史、框和分支；安排一次跳过",
                "Freeze prefix, boxes and branches; schedule one skip",
            ),
        ),
        (
            "association_trace.py",
            "observe_assignments()",
            t(
                "调用原生匹配并复制实际代价与分配日志",
                "Call native matching and copy actual costs/assignments",
            ),
        ),
        (
            "recovery_engines.py",
            "ByteEngine.step() / SamEngine.step()",
            t(
                "执行运动状态、提示、跳过和删除",
                "Advance motion, prompts, skip and retirement",
            ),
        ),
        (
            "recovery_metrics.py",
            "evaluate_recovery()",
            t(
                "评分固定目标，而不是每帧挑最佳 ID",
                "Score fixed target, never reselect best ID",
            ),
        ),
    ]
    records += (
        table(
            [t("文件", "File"), t("入口", "Entry point"), t("作用", "Role")],
            [
                [
                    link(
                        data["prefix"]
                        + data["runs"]["normal"]["prefix"]
                        + "code/"
                        + name
                        + ".txt",
                        name,
                    ),
                    fn,
                    role,
                ]
                for name, fn, role in code_rows
            ],
            "long-code-map",
        )
        + "</details>"
    )
    limits = (
        "<p>"
        + t(
            "只有两个开发事件，不支持普遍排名或跨视频显著性。重置涉及整套目标状态，不能把系统反馈全部归结为一个记忆张量。参考框含 GT 信息，必须独立于自动系统成绩解释；后续没有追加 GT 纠正。窗口／阈值仍是开发设置，时间单位是导出步，不是秒。",
            "Only two development events: no population ranking or cross-video significance. Reset changes target state broadly; system feedback cannot all be attributed to one memory tensor. GT-derived reference boxes are separate from automatic-system scores; no further GT corrections follow. Windows/thresholds remain development settings; time is exported steps, not seconds.",
        )
        + "</p><p>"
        + t(
            "下一步增加独立视频：真正能跳过有效提示的稳定对照、运动突变、检测竞争和遮挡事件。分别统计 mask 漂移、关联失败与删除，再决定是否值得设计自动重置策略。正式 200 段评估尚未完成。",
            "Next add independent videos: stable controls with a real prompt to remove, motion changes, competing detections and occlusion. Separate mask drift, association failures and removal before proposing an automatic reset policy. The formal 200-video evaluation is not complete.",
        )
        + "</p>"
    )
    return [
        (
            "design",
            t("从 8 步到 30 步：什么变了？", "From eight to 30 steps: what changed?"),
            design,
        ),
        ("mechanisms", t("先区分三种过程", "Distinguish three processes"), terms),
        (
            "rider",
            t("骑手：SAM 的延迟恢复", "Rider: delayed SAM recovery"),
            case(data, "rider", language),
        ),
        (
            "association",
            t(
                "骑手：ByteTrack 为什么关联失败？",
                "Rider: why does ByteTrack lose association?",
            ),
            association(data, language),
        ),
        (
            "cat",
            t(
                "猫：准确传播之后，旧 ID 被删除",
                "Cat: accurate propagation, then old-ID removal",
            ),
            case(data, "cat", language),
        ),
        (
            "refresh",
            t(
                "单次刷新消融：有实际干预吗？",
                "Skip-one refresh: was a prompt actually removed?",
            ),
            refresh(data, language),
        ),
        ("records", t("数据、代码与复核记录", "Data, code and verification"), records),
        ("limits", t("结论边界与下一步", "Limits and next steps"), limits),
    ]


def write_long_pages(output):
    output = Path(output)
    data = read_long(output)
    template = (WEB / "study.html").read_text(encoding="utf-8")
    css = "".join(
        (WEB / name).read_text(encoding="utf-8")
        for name in ("tutorial.css", "study.css", "recovery.css", "recovery-long.css")
    )
    for language, filename in zip(("zh", "en"), PAGES):
        t = lambda zh, en: pick(language, zh, en)
        suffix = ".en" if language == "en" else ""
        blocks = content(data, language)
        intro = (
            "<p>"
            + t(
                "同一批事件继续跟随：看清恢复发生得有多晚、身份怎样丢失，以及目标为什么被删除。",
                "Follow the same events longer: distinguish late recovery, identity-association failure and rule-based target removal.",
            )
            + '</p><p class="long-route">'
            + link(
                "results" + suffix + ".html", t("① 修正版基线", "① Corrected baselines")
            )
            + " → "
            + link("recovery" + suffix + ".html", t("② 8 步 H/R", "② Eight-step H/R"))
            + " → "
            + link(
                "#design" if data else "#status",
                t("③ 30 步跟随", "③ Thirty-step follow-up"),
            )
            + " → "
            + link(
                "#refresh" if data else "#status",
                t("④ 跳过一次刷新", "④ Skip one refresh"),
            )
            + "</p>"
        )
        if (output / "recovery-cohort-results/manifest.json").is_file():
            intro += (
                "<p>"
                + link(
                    "recovery-cohort" + suffix + ".html",
                    t(
                        "下一批：16段独立事件、128分支与机制检验 →",
                        "Next batch: 16 independent events, 128 branches and mechanism checks →",
                    ),
                )
                + "</p>"
            )
        values = {
            "LANG": t("zh-CN", "en"),
            "TITLE": t(
                "长窗口 H/R：恢复、关联与删除",
                "Long-window H/R: Recovery, Association and Removal",
            ),
            "HOME": "index" + suffix + ".html",
            "OTHER": "recovery-long" + ("" if suffix else ".en") + ".html",
            "INTRO": intro,
            "CSS": css,
            "JS": (WEB / "study.js").read_text(encoding="utf-8")
            + (WEB / "recovery.js")
            .read_text(encoding="utf-8")
            .replace("cs550-hr-page-state-v1", "cs550-long-page-state-v1")
            + (WEB / "recovery-long.js").read_text(encoding="utf-8"),
            "NAV": "".join(link("#" + k, label) for k, label, _ in blocks),
            "BODY": "".join(section(k, label, body) for k, label, body in blocks),
            "SWITCH": t("English", "中文"),
            "BACK": t("项目总览", "Project overview"),
            "MENU": t("本页目录", "On this page"),
            "THEME": t("切换主题", "Theme"),
            "SKIP": t("跳到正文", "Skip to content"),
            "TRAIL": t(
                "真实实验 · 8 步 H/R 的后续",
                "Real experiments · follow-up to eight-step H/R",
            ),
            "FOOT": t(
                "只读已验证输出；旧 8 步与基线证据保留不变。",
                "Verified outputs only; prior eight-step and baseline evidence remains unchanged.",
            ),
        }
        (output / filename).write_text(
            decorate_page(
                re.sub(r"@@([A-Z_]+)@@", lambda m: values[m[1]], template),
                language,
                "recovery-long",
            ),
            encoding="utf-8",
        )
