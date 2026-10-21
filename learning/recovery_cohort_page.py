"""Publish saved development-cohort evidence; never run inference from the site.

Only selected presentation assets are copied. No raw RGB/GT, model state,
credentials, full experiment trees or weights enter the served directory.
"""

import json
from html import escape
from pathlib import Path
import re
import shutil

from .navigation import decorate_page
from .program_page import table
from .study import WEB, link, pick, section

ROOT = Path(__file__).resolve().parents[1]
COHORT = ROOT / "experiments/runs/recovery-independent-20261020-3080"
ANALYSIS = ROOT / "experiments/runs/recovery-independent-20261020-analysis"
PREFIX = "recovery-cohort-results/"
PAGES = ("recovery-cohort.html", "recovery-cohort.en.html")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def copy_asset(source, destination):
    """Incremental copy, restricted to explicitly selected public assets."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists() or source.read_bytes() != destination.read_bytes():
        shutil.copy2(source, destination)


def progress_block(output, language):
    if not (Path(output) / PREFIX / "manifest.json").is_file():
        return None
    t = lambda zh, en: pick(language, zh, en)
    suffix = ".en" if language == "en" else ""
    return (
        "independent-cohort",
        t("最新：16段独立开发事件", "Latest: 16 independent development events"),
        "<p>"
        + t(
            "稳定对照、运动突变、检测竞争、遮挡各4段；128个主分支、32段四组视频。2967边界案例未跑。多数事件H/R持平，主要差异涉及关联门槛、纠正框质量与目标生命周期，不能概括为一种记忆总是更好。",
            "Four events each for stable controls, motion changes, detection competition and occlusion: 128 main branches and 32 four-group videos. Boundary case 2967 was not run. Most events tie in correct-step counts; important differences involve association thresholds, corrective-box quality and target lifecycle—not a universally superior memory.",
        )
        + "</p><p>"
        + link(
            "recovery-cohort" + suffix + ".html",
            t("查看结果、视频与代码流程 →", "Review results, videos and code flow →"),
        )
        + "</p>",
    )


def publish_assets(output, plan, results):
    target = Path(output) / PREFIX
    for row in plan["events"]:
        folder, name = Path(row["folder"]), row["name"]
        for condition in ("yolo", "reference"):
            stem = name + "-" + condition
            for ext in ("-four-groups.mp4", "-curves.png"):
                copy_asset(folder / "visuals" / (stem + ext), target / (stem + ext))
            zoom = row["event_id"] + "-" + condition + "-zoom-plus8.png"
            copy_asset(ANALYSIS / zoom, target / zoom)
    for name in ("paired-8-20-30.csv", "aggregates.csv"):
        copy_asset(ANALYSIS / name, target / name)
    copy_asset(
        ROOT / "experiments/RECOVERY_COHORT_GUIDE.txt", target / "CODE_GUIDE.txt"
    )
    # Compact public manifest: intentionally omit machine paths and raw traces.
    manifest = {
        "status": "completed",
        "primary_events": 16,
        "main_branches": 128,
        "repeat_branches": 16,
        "repeat_events": ["E09", "E13"],
        "boundary_case_2967_run": False,
        "device": "RTX 3080",
        "windows": [8, 20, 30],
        "normal_refresh": True,
        "review_sha256": plan["review_sha256"],
        "split_sha256": plan["split_sha256"],
        "events": [
            {k: row[k] for k in ("event_id", "name", "video_id", "scene")}
            for row in plan["events"]
        ],
        "verification": {
            "main": read(ANALYSIS / "verification.json")["status"],
            "repeat": read(ANALYSIS / "repeat-verification.json")["status"],
            "old_results": read(COHORT / "old-results-integrity.json")["status"],
        },
        "aggregates": results["aggregates"],
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def content(plan, data, language):
    t = lambda zh, en: pick(language, zh, en)
    suffix = ".en" if language == "en" else ""
    blocks = []

    def add(key, zh, en, body):
        blocks.append((key, t(zh, en), body))

    add(
        "design",
        "从两段案例到独立视频",
        "From two cases to independent videos",
        "<p>"
        + t(
            "之前骑手与猫的长窗口提供机制线索；本批按审阅过的v3清单，在开发集扩展到16段，每段只取一个事件。四类各4段。2967仅作边界案例，未运行；E05改用2705，纠正后30步GT连续可见。E09有3步GT缺失、E13有1步缺失，分别按27/29个可见步骤计分。",
            "The earlier rider/cat follow-up suggested mechanisms. This batch expands to 16 development videos using the reviewed v3 list, one event per video and four events per scene group. Boundary case 2967 was not run; E05 uses 2705 with 30 continuously GT-visible future steps. E09 has three missing-GT steps and E13 has one, so their visible-step denominators are 27 and 29.",
        )
        + '</p><ol class="cohort-flow"><li>'
        + t("复现同一前史与原ID", "Replay the same prefix and original ID")
        + "</li><li>"
        + t("同一纠正框：H保留 / R重置", "Same corrective box: H retain / R reset")
        + "</li><li>"
        + t(
            "正常跟随30步 → 读取8/20/30步",
            "Follow normally for 30 steps → read 8/20/30",
        )
        + "</li></ol><p>"
        + t(
            "A = YOLO分割 + ByteTrack，B = YOLO框辅助SAM2.1。两种框为实际YOLO框和可见GT外接参考框；参考框不是GT mask输入，也不是自动部署方案。每段两种框×四组=8分支。固定权重与阈值，没有跳过刷新。",
            "A = YOLO segmentation + ByteTrack; B = YOLO-box-assisted SAM 2.1. Corrective boxes are actual YOLO boxes or visible-GT bounding reference boxes. Reference boxes are not GT-mask inputs or an automatic deployment method. Two box conditions × four groups = eight branches per event. Weights and thresholds are fixed; refresh is not skipped.",
        )
        + "</p><p>"
        + t(
            "只跟踪纠正前锚定的原ID，排除纠正当步。mask IoU≥0.5连续3个GT可见步骤表示曾达到判据，不保证末尾仍成功。GT缺失打断连续成功，不直接算作模型失败。8/20/30是同一预测的读数，不是新独立样本。",
            "Score the original prefix-anchored ID and exclude the correction step. Three successive GT-visible steps with mask IoU ≥ 0.5 indicate that the criterion was reached, not guaranteed terminal recovery. Missing GT breaks the success streak and is not itself model failure. The 8/20/30 checkpoints read the same predictions; they are not independent samples.",
        )
        + "</p>",
    )

    rows = []
    for a in data["aggregates"]:
        rows.append(
            [
                a["model"],
                a["condition"],
                str(a["window"]),
                str(a["H_more_correct_steps"]),
                str(a["R_more_correct_steps"]),
                str(a["threshold_count_ties"]),
                f'{a["mean_R_minus_H_mask_iou"]:+.4f}',
            ]
        )
    add(
        "summary",
        "配对结果：多数持平，保留并非总是改善",
        "Paired results: mostly ties, not universal improvement",
        "<p>"
        + t(
            "每行16个视频事件；H优/R优只比较正确可见步骤数。持平不等于mask或状态完全相同；不把A/B两种机制混成统一记忆排行榜。",
            "Each row contains 16 video events. H/R wins compare correct visible-step counts only. A count tie does not imply identical masks or states; A/B are not pooled into a memory ranking.",
        )
        + "</p>"
        + table(
            [
                t("系统", "System"),
                t("框", "Box"),
                t("窗口", "Window"),
                t("H更多", "H more"),
                t("R更多", "R more"),
                t("步数持平", "Count ties"),
                "Mean IoU R−H",
            ],
            rows,
            "cohort-aggregates",
        ),
    )

    findings = [
        (
            "E15 · ByteTrack",
            "篮球中H 26/30、R 7/30，未纠正基线26/30。第23步，同一检测候选的代价H 0.7789、R 0.8501跨过0.8门槛。状态仍存在，是预测框与关联路径变化，不是删除。当前代价=1−框IoU×置信度，不是直接马氏距离门控。",
            "Basketball: H 26/30, R 7/30, uncorrected baseline 26/30. At step 23, the same candidate costs 0.7789 for H versus 0.8501 for R across a 0.8 threshold. The state still exists: this is a forecast/association-path difference, not deletion. Installed cost = 1 − box IoU × confidence, not a direct Mahalanobis gate.",
        ),
        (
            "E09/E10 · SAM",
            "E09的YOLO框下H 26/27、R 0/27；换参考框为25/27、24/27。E10则为30/30对0/30，参考框30/30对23/30。历史与框质量存在交互。E09重置后跟向邻近人物，状态仍活跃。原始B0已分别为26/27和30/30，H主要保住既有表现。",
            "E09 with a YOLO box: H 26/27, R 0/27; with a reference box: 25/27 versus 24/27. E10: 30/30 versus 0/30, or 30/30 versus 23/30 with a reference box. History interacts with box quality. E09 reset follows a neighboring person while remaining active. Original B0 already scores 26/27 and 30/30 respectively; H largely preserves existing performance.",
        ),
        (
            "E16 · ByteTrack",
            "犬只基线0/30，纠正后H 20/30、R 21/30。一次显式定位纠正是主要收益，重置相对保留只多1步。不能将0→21全部算作重置收益。",
            "Dog: baseline 0/30, corrected H 20/30 and R 21/30. One explicit positional correction accounts for the main gain; reset adds only one step relative to retention. Do not attribute the entire 0→21 change to reset.",
        ),
        (
            "E13 · SAM",
            "H 12/29、R 10/29。两组第34步（纠正后+16）均因超过15步未接受检测而被外围TTL删除，之后15个GT可见步骤无输出。删除不等于活跃模型分割漂移。纠正也推迟了基线删除时间，基线6/29→H12/29不是纯神经记忆增益。",
            "H 12/29, R 10/29. Both targets are removed at step 34 (+16 after correction) by the wrapper TTL after more than 15 steps without an accepted detection. The next 15 GT-visible steps have no output. Removal is not active-model segmentation drift. Correction also delays baseline expiry; baseline 6/29→H 12/29 is not a pure neural-memory gain.",
        ),
    ]
    add(
        "findings",
        "先按机制解释，再看分数",
        "Interpret mechanisms before scores",
        "".join(
            '<article class="cohort-finding"><h3>'
            + title
            + "</h3><p>"
            + t(zh, en)
            + "</p></article>"
            for title, zh, en in findings
        )
        + "<p>"
        + t(
            "四段稳定对照均30/30。多数运动案例也存在上限效应。KF状态不同而输出相同说明干预未必改变关联，并非重置没执行。后续检测缓存相同，不保证SAM接受的提示框相同；YOLO条件存在关联—提示—记忆闭环，不能称为未来提示完全受控。",
            "All four stable controls score 30/30. Many motion cases also reach a ceiling. Different KF states with identical outputs mean the intervention need not change assignment, not that reset failed. Identical detector caches do not guarantee identical accepted SAM prompts: YOLO conditions can contain association–prompt–memory feedback, so future prompts are not claimed to be fully controlled.",
        )
        + "</p>",
    )

    scenes = {
        "stable": ("稳定对照", "Stable control"),
        "motion": ("运动突变", "Motion change"),
        "competition": ("检测竞争", "Detection competition"),
        "occlusion": ("遮挡", "Occlusion"),
    }
    cards = []
    for event in plan["events"]:
        eid, name = event["event_id"], event["name"]
        scene = scenes.get(event["scene"], (event["scene"], event["scene"]))
        pieces = [
            f'<details id="{eid}" class="cohort-event"><summary>{escape(eid + " · " + t(*scene) + " · " + name.split("-", 2)[-1])}</summary>'
        ]
        for condition in ("yolo", "reference"):
            stem = PREFIX + name + "-" + condition
            pieces.append(
                "<h3>"
                + t(
                    "YOLO纠正框" if condition == "yolo" else "GT参考纠正框",
                    (
                        "YOLO corrective box"
                        if condition == "yolo"
                        else "GT-reference corrective box"
                    ),
                )
                + "</h3>"
            )
            erows = []
            for p in data["pair_results"]:
                if p["event_id"] != eid or p["condition"] != condition:
                    continue

                def counts(key):
                    x = p[key]
                    return f'{x["correct_visible_steps"]}/{x["visible_steps"]}'

                erows.append(
                    [
                        p["model"],
                        str(p["window"]),
                        counts("uncorrected"),
                        counts("H"),
                        counts("R"),
                        f'{p["H"]["mean_visible_mask_iou"]:.3f} / {p["R"]["mean_visible_mask_iou"]:.3f}',
                        str(p["H"]["longest_correct_streak"])
                        + " / "
                        + str(p["R"]["longest_correct_streak"]),
                    ]
                )
            pieces.append(
                table(
                    [
                        t("系统", "System"),
                        t("窗口", "Window"),
                        t("原基线", "Baseline"),
                        "H",
                        "R",
                        "IoU H / R",
                        t("最长连续 H / R", "Longest streak H / R"),
                    ],
                    erows,
                    eid + "-" + condition + "-scores",
                )
            )
            zoom = PREFIX + eid + "-" + condition + "-zoom-plus8.png"
            pieces.append(
                f'<video controls playsinline preload="none" aria-label="{eid} {condition} A-H A-R B-H B-R"><source src="{stem}-four-groups.mp4" type="video/mp4"></video>'
            )
            pieces.append(
                f'<figure><img loading="lazy" src="{stem}-curves.png" alt="{eid} {condition} IoU curves"><figcaption>'
                + t(
                    "完整30步曲线：短暂达标不等于持续恢复。",
                    "Full 30-step curves: temporary success is not sustained recovery.",
                )
                + "</figcaption></figure>"
            )
            pieces.append(
                f'<figure><img loading="lazy" src="{zoom}" alt="{eid} {condition} fixed +8-step target crop"><figcaption>'
                + t(
                    "固定纠正后+8步、相同裁剪区域，不按结果挑帧。E15此时两条A分支都已丢失；H稍后第23步才重关联。",
                    "Fixed +8-step frame, same crop—not selected by outcome. In E15 both A branches are lost here; H only reconnects later at step 23.",
                )
                + "</figcaption></figure>"
            )
        pieces.append("</details>")
        cards.append("".join(pieces))
    add(
        "events",
        "16段逐段视频与读数",
        "Videos and readouts for all 16 events",
        "<p>"
        + t(
            "展开一段再播放，默认不预加载32段视频。A-H/A-R为ByteTrack，B-H/B-R为SAM。表中分子为达标可见步数，不是目标总数或训练精度。",
            "Expand an event to play its videos; all 32 videos use no preloading by default. A-H/A-R are ByteTrack; B-H/B-R are SAM. Table numerators count correct visible steps, not objects or training accuracy.",
        )
        + "</p>"
        + "".join(cards),
    )

    code_rows = [
        (
            "recovery_cohort.py → prepare_plan",
            "冻结16段、框和目标ID",
            "Freeze 16 events, boxes and target IDs",
        ),
        (
            "recovery.py → execute",
            "复现基线/前缀，复制状态，纠正一次",
            "Replay baseline/prefix, fork state, correct once",
        ),
        (
            "recovery_engines.py → ByteEngine.step / SamEngine.step",
            "执行H/R，记录真实关联与提示",
            "Apply H/R and log actual assignments/prompts",
        ),
        (
            "recovery_metrics.py → evaluate_recovery",
            "按固定ID评分，排除纠正帧",
            "Score fixed IDs, exclude the correction frame",
        ),
        (
            "recovery_cohort_report.py → per_event / aggregate",
            "同一预测读取8/20/30步，按模型配对",
            "Read 8/20/30 from one prediction; pair within model",
        ),
        (
            "recovery_cohort_repeat.py → compare_verified",
            "独立复跑与数值一致性检查",
            "Independent rerun and exact numerical checks",
        ),
    ]
    add(
        "code",
        "实验步骤对应代码",
        "Experiment steps mapped to code",
        table(
            [t("文件 → 函数", "File → function"), t("职责", "Role")],
            [["<code>" + escape(f) + "</code>", t(zh, en)] for f, zh, en in code_rows],
            "cohort-code",
        )
        + "<p>"
        + link(
            PREFIX + "CODE_GUIDE.txt",
            t("下载中英代码导读", "Download bilingual code guide"),
        )
        + "</p>",
    )
    add(
        "verification",
        "复核与下载",
        "Verification and downloads",
        "<p>"
        + t(
            "128个主分支独立重评分；64个A分支用冻结检测缓存独立CPU重放，输出与KF/关联记录一致。预先选定E09/E13另做16个原配置GPU验证分支，mask、ID、框、分数、曲线与状态记录完全复现。验证分支不计入主统计。旧16个结果目录的16,686个文件哈希未变。",
            "All 128 main branches were independently rescored. All 64 A branches were independently replayed on CPU from frozen detections, matching outputs and KF/assignment traces. Preselected E09/E13 were rerun on GPU as 16 verification branches: masks, IDs, boxes, scores, curves and state traces match exactly. These are not additional statistical samples. Hashes for 16,686 files across 16 older result directories are unchanged.",
        )
        + "</p><p>"
        + " · ".join(
            link(PREFIX + file, label)
            for file, label in [
                (
                    "manifest.json",
                    t("批次指纹与状态", "Cohort fingerprints and status"),
                ),
                (
                    "paired-8-20-30.csv",
                    t("192行配对读数 CSV", "192 paired readouts CSV"),
                ),
                ("aggregates.csv", t("汇总 CSV", "Aggregate CSV")),
            ]
        )
        + "</p>",
    )
    add(
        "next",
        "适用边界与下一步",
        "Limits and next step",
        "<p>"
        + t(
            "120/40/40内部划分已冻结，但这批是人工选取的开发机制样本：12段person、3段car、1段dog，没有cat/horse，且要求可锚定的可靠前缀。不是均衡五类评测，也不是正式保留集结论。E14/E15为部分遮挡，不应写作完全消失后重现。",
            "The 120/40/40 internal split is frozen, but these are manually selected development mechanism cases: 12 person, three car and one dog events, no cat/horse, with anchorable reliable prefixes. This is neither a balanced five-class benchmark nor a held-out conclusion. E14/E15 contain partial occlusion, not complete disappearance and re-entry.",
        )
        + "</p><p>"
        + t(
            "下一步先预注册历史可靠性×纠正框质量的受控实验，单独检查目标TTL与后续实际提示；不能根据本批赢家重选样本或直接宣布永远保留。延迟恢复、关联失败、活跃时mask失败和生命周期删除继续分开统计。新实验尚未运行。",
            "Next, preregister a controlled history-reliability × corrective-box-quality experiment, separately checking target TTL and actual future prompts. Do not reselect samples based on current winners or declare that retention is always best. Keep delayed recovery, association failure, active-mask failure and lifecycle removal separate. This follow-up has not been run.",
        )
        + "</p>",
    )
    return blocks


def write_cohort_pages(output, import_assets=False):
    output = Path(output)
    available = import_assets or (output / PREFIX / "manifest.json").is_file()
    if available:
        plan, data = read(COHORT / "cohort.json"), read(ANALYSIS / "results.json")
        assert plan["status"] == data["status"] == "completed"
        assert len(plan["events"]) == 16 and data["branches"] == 128
        assert not data["boundary_case_2967_run"]
        if import_assets:
            publish_assets(output, plan, data)
    template = (WEB / "study.html").read_text(encoding="utf-8")
    css = "".join(
        (WEB / n).read_text(encoding="utf-8")
        for n in ("tutorial.css", "study.css", "recovery.css")
    )
    css += ".cohort-flow{display:flex;flex-wrap:wrap;gap:1rem;padding-left:1.5rem}.cohort-flow li{flex:1;min-width:180px;padding:1rem;background:var(--panel)}.cohort-event{margin:1rem 0;border:1px solid var(--line);border-radius:8px;padding:1rem}.cohort-event summary{cursor:pointer;font-weight:700}.cohort-event video,.cohort-event img{width:100%;height:auto;max-width:100%}.cohort-finding{border-left:3px solid var(--accent);padding-left:1rem}.cohort-event figure{margin:1rem 0}"
    for language, filename in zip(("zh", "en"), PAGES):
        t = lambda zh, en: pick(language, zh, en)
        suffix = ".en" if language == "en" else ""
        blocks = (
            content(plan, data, language)
            if available
            else [
                (
                    "status",
                    t("未导入结果", "No imported results"),
                    "<p>"
                    + t(
                        "此站点尚未导入已复核的16段开发实验；不从页面启动推理。",
                        "No verified 16-event cohort has been imported into this site; this page does not start inference.",
                    )
                    + "</p>",
                )
            ]
        )
        route = " → ".join(
            link(slug + suffix + ".html", t(zh, en))
            for slug, zh, en in [
                ("results", "修正版基线", "Corrected baselines"),
                ("recovery", "8步H/R", "8-step H/R"),
                ("recovery-long", "长窗口机制", "Long-window mechanisms"),
            ]
        )
        values = {
            "LANG": t("zh-CN", "en"),
            "TITLE": t(
                "16段独立事件：历史何时有用？",
                "16-event cohort: when does history help?",
            ),
            "HOME": "index" + suffix + ".html",
            "OTHER": "recovery-cohort" + ("" if suffix else ".en") + ".html",
            "INTRO": "<p>"
            + route
            + (" → " + t("本批128分支", "128-branch cohort") if available else "")
            + "</p>"
            + (
                "<p>"
                + t(
                    "本地RTX 3080 · 16个视频事件 · 32段四组视频 · 未进行正式保留集评估",
                    "Local RTX 3080 · 16 video events · 32 four-group videos · no held-out evaluation yet",
                )
                + "</p>"
                if available
                else ""
            ),
            "CSS": css,
            "JS": (WEB / "study.js").read_text(encoding="utf-8"),
            "NAV": "".join(link("#" + k, label) for k, label, _ in blocks),
            "BODY": "".join(section(k, label, body) for k, label, body in blocks),
            "SWITCH": t("English", "中文"),
            "BACK": t("项目总览", "Project overview"),
            "MENU": t("本页目录", "On this page"),
            "THEME": t("切换主题", "Theme"),
            "SKIP": t("跳到正文", "Skip to content"),
            "TRAIL": t(
                "真实实验 · 独立开发视频扩展",
                "Real experiments · independent development-video expansion",
            ),
            "FOOT": t(
                "只读保存结果；页面不执行推理。",
                "Saved results only; this page does not run inference.",
            ),
        }
        text = re.sub(r"@@([A-Z_]+)@@", lambda m: values[m[1]], template)
        (output / filename).write_text(
            decorate_page(text, language, "recovery-cohort"), encoding="utf-8"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    write_cohort_pages(parser.parse_args().output, import_assets=True)
