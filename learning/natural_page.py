"""Bilingual saved natural-failure evidence; no inference or raw-run serving.

Explicit import validates completed local studies and copies selected media.
Normal site refresh reads the sanitized public manifest, not experiment trees.
"""

import csv
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re

from .navigation import decorate_page
from .program_page import table
from .recovery_cohort_page import copy_asset
from .study import WEB, link, pick, section

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "natural-recovery-results/"
PAGES = ("recovery-natural.html", "recovery-natural.en.html")
BATCHES = (
    ("main", "recovery-natural"),
    ("reserve", "recovery-natural-reserves"),
    ("reference", "recovery-natural-reference"),
)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fingerprint(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def import_results(output):
    """Only allowlisted media, compact scores and current source references."""
    target = Path(output) / PREFIX
    cases, sources = [], []
    branches = repeats = 0
    for key, stem in BATCHES:
        run = ROOT / f"experiments/runs/{stem}-20261021-3080"
        analysis = ROOT / f"experiments/runs/{stem}-20261021-analysis"
        plan = read(run / "cohort.json")
        result = read(analysis / "results.json")
        checks = read(analysis / "verification.json")
        frozen = read(run / "frozen-events.json")
        assert plan["status"] == result["status"] == "completed"
        assert checks["status"] == plan["repeat_verification"]["status"] == "passed"
        assert fingerprint(run / "frozen-events.json") == plan["frozen_selection_sha256"]
        assert result["cohort_sha256"] == fingerprint(run / "cohort.json")
        assert plan["actual_branches"] == len(plan["events"]) * len(plan["conditions"]) * 4
        assert all(e["independent_Byte_branch_replay"]["status"] == "passed" for e in checks["events"])
        branches += plan["actual_branches"]
        repeats += plan["repeat_branches"]
        sources.append({"batch": key, "cohort_sha256": fingerprint(run / "cohort.json"),
                        "analysis_sha256": fingerprint(analysis / "results.json"), "verified": True})
        for row in plan["events"]:
            e = next(e for e in frozen["events"] if e["event_id"] == row["event_id"])
            case = {k: e[k] for k in ("event_id", "video_id", "gt_id", "frame", "category",
                                     "labels", "recent_three_iou", "reused_video_from_16")}
            case.update(key=key + "-" + e["event_id"], conditions=plan["conditions"], media={}, pairs=[])
            for condition in plan["conditions"]:
                stem_name = row["name"] + "-" + condition
                media = {}
                for label, source in (
                    ("video", Path(row["folder"]) / "visuals" / (stem_name + "-four-groups.mp4")),
                    ("curve", Path(row["folder"]) / "visuals" / (stem_name + "-curves.png")),
                    ("zoom", analysis / f"{e['event_id']}-{condition}-zoom-plus8.png"),
                ):
                    relative = Path(key) / source.name
                    copy_asset(source, target / relative)
                    media[label] = PREFIX + relative.as_posix()
                case["media"][condition] = media
            for p in result["pair_results"]:
                if p["event_id"] != e["event_id"]:
                    continue
                compact = {k: p[k] for k in ("model", "condition", "window", "pre_event_label",
                                            "uncorrected", "H", "R", "R_minus_H_correct_steps",
                                            "R_minus_H_mean_mask_iou", "actual_target_future_prompts_identical")}
                if p["window"] == 30:
                    compact["diagnostics"] = {label: {k: p[label + "_diagnostics"][k] for k in
                                                      ("counts", "first_state_deletion_offset")}
                                              for label in ("H", "R")}
                case["pairs"].append(compact)
            cases.append(case)
    assert len(cases) == 7 and branches == 52 and repeats == 20
    assert sum(len(c["conditions"]) for c in cases) == 13
    source_files = []
    for name in ("natural_events.py", "natural_recovery.py", "natural_coverage.py",
                 "natural_reference.py", "natural_report.py", "recovery_engines.py", "recovery_metrics.py"):
        source = ROOT / "experiments/tracking_lab" / name
        copy_asset(source, target / "code" / (name + ".txt"))
        source_files.append({"name": name, "url": PREFIX + "code/" + name + ".txt",
                             "sha256": fingerprint(source)})
    # Flatten inspectable scores; do not copy absolute-path run summaries or traces.
    rows = []
    for c in cases:
        for p in c["pairs"]:
            rows.append({"case": c["key"], "video": c["video_id"], "GT": c["gt_id"],
                         "t0": c["frame"], **{k: p[k] for k in ("model", "condition", "window", "pre_event_label")},
                         **{label + "_" + field: p[label][field] for label in ("uncorrected", "H", "R")
                            for field in ("correct_visible_steps", "mean_visible_mask_iou", "recovery_confirmed_offset",
                                          "longest_correct_streak", "relapses")}})
    with (target / "paired-scores.csv.txt").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = {"status": "completed", "events": 7, "main_branches": branches, "repeat_branches": repeats,
                "comparison_videos": 13, "paired_windows": len(rows), "device": "RTX 3080",
                "cases": cases, "sources": sources, "code": source_files,
                "history_pollution_included": False, "held_out_evaluation": False}
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def progress_block(output, language):
    if not (Path(output) / PREFIX / "manifest.json").is_file():
        return None
    t = lambda zh, en: pick(language, zh, en)
    suffix = ".en" if language == "en" else ""
    return ("natural-followup", t("最新：自然失败后的H/R补充", "Latest: H/R after natural failures"),
            "<p>" + t("7个事件、52主分支、20复跑验证分支。新增SAM失败中保留30/30、重置0/30；ByteTrack的H/R优劣可随框来源反转。旧基线与16段结果继续保留，不含人为污染。",
                        "Seven events, 52 main branches and 20 repeat-only branches. Retention scores 30/30 versus reset 0/30 in a new SAM failure; ByteTrack's H/R ordering can reverse with the box source. Earlier baselines and the 16-event study remain available; artificial history pollution is excluded.")
            + "</p><p>" + link("recovery-natural" + suffix + ".html", t("查看自然失败、视频与程序流程 →", "Review natural failures, videos and code flow →")) + "</p>")


def content(data, language):
    t = lambda zh, en: pick(language, zh, en)
    suffix = ".en" if language == "en" else ""
    blocks = []
    def add(key, zh, en, body):
        blocks.append((key, t(zh, en), body))
    add("design", "为什么补这一批", "Why this follow-up", "<p>" + t(
        "旧16段中多数是维持正确跟踪的对照。重新检查纠正前连续3步后，我们回到原方案，补选持续自然失败：曾连续正确3步，随后原ID连续3个可见步骤IoU低于0.5；两套旧状态仍可操作，之后30步GT持续可见。",
        "Most earlier 16-event cases tested maintenance. After checking the three steps ending at correction, we returned to the original plan: an earlier three-step correct streak, then three visible failures of the original ID below IoU 0.5; both old states remain operable and GT stays visible for 30 subsequent steps.")
        + "</p><ol class='natural-flow'><li>" + t("原生预测筛选 → 冻结事件", "Native predictions → freeze events")
        + "</li><li>" + t("同一前史、同框、一次纠正", "Same prefix and box, one correction")
        + "</li><li>" + t("四组跟随 → 读8/20/30步", "Four groups → read 8/20/30 steps") + "</li></ol><p>" + t(
        "先扫描既有31段（排除2967），再检查事先列出的全部6段备用视频。6个事件两种框均可用；2920/GT1没有合格YOLO纠正框，按proposal单独报告参考框四组，不补造检测。7个视频中4个未进旧16段，另外3个复用视频不当成跨批独立录像。",
        "We screened 31 existing videos (excluding 2967), then all six previously listed reserves. Six events support both box sources. Video 2920/GT1 has no eligible YOLO correction, so its four reference-box groups are reported separately as allowed by the proposal—no detection is fabricated. Four videos are new to the earlier cohort; three reused videos are not independent recordings across studies.") + "</p><p class='notice'>" + t(
        "N=未纠正原生运行；H=保留；R=重置。A=YOLO+ByteTrack，B=YOLO辅助SAM。纠正当步不计分，固定原ID，IoU≥0.5连续3步确认。输出错不等于历史全部无用；参考框也不保证正确分割。",
        "N = uncorrected native run; H = retain; R = reset. A = YOLO+ByteTrack; B = YOLO-assisted SAM. Exclude the correction step, keep the original ID, and confirm three successive steps at IoU ≥ 0.5. Wrong output does not mean all history is useless; a reference box does not guarantee correct segmentation.") + "</p>")
    add("findings", "先看三个结论", "Three findings first", "".join(
        "<article class='natural-finding'><h3>" + t(zh, en) + "</h3><p>" + t(body, english) + "</p></article>"
        for zh,en,body,english in (
            ("SAM：持续失败后，保留也可能更好", "SAM: retention can win after persistent failure",
             "2920/GT1参考框下N/H/R=27/30/0。H在+3步确认，N在+8步确认，实际多3个正确步骤，不是额外恢复30步。与早期骑手H0/R22形成相反证据。R先有19步活跃低IoU，再于+20步被TTL删除；不能把全部失败只归于删除。后续实际刷新也分歧，是闭环效果。",
             "2920/GT1 with a reference box: N/H/R = 27/30/0. H confirms at +3 versus native +8: three extra correct steps, not 30 additional recoveries. This contrasts with the earlier rider's H0/R22. R first has 19 active low-IoU steps, then TTL deletion at +20; deletion alone does not explain the failure. Actual later refreshes also diverge: this is a closed-loop effect."),
            ("ByteTrack：同一事件中，框来源使优劣反转", "ByteTrack: box source reverses the H/R ordering",
             "2694/GT4：YOLO框H20/R3，参考框H0/R21，原生2/30。第21步同一检测index4的代价依次为0.727/0.909、0.903/0.788，实际关联跨过0.8门槛。解释本例的是状态更新后的关联路径，不是“参考框总更好”或“重置总更好”。",
             "2694/GT4: YOLO-box H20/R3, reference-box H0/R21, native 2/30. At step 21, candidate index 4 costs 0.727/0.909 and 0.903/0.788 respectively, crossing the 0.8 assignment threshold. The state-dependent association path explains this case—not a universally better reference box or reset."),
            ("短暂收益、自然恢复，要与稳定修复区分", "Separate brief gains and natural recovery from durable repair",
             "2844中A-H5/R8，但最长连续正确只有1/2步，均未确认恢复。2890中H/R在正确4/6步后复发。犬只2893虽纠正前持续失败，原生随后本来就25/30；H仍25，R为23或24，不能把25步全部归于纠正。",
             "2844: A-H5/R8, but the longest correct streak is only 1/2 steps; neither confirms recovery. In 2890, H/R relapse after 4/6 correct steps. Dog 2893 fails before correction but native tracking already reaches 25/30 afterward; H remains 25 and R is 23 or 24. Those 25 steps are not all a correction benefit."),
        )))
    rows = []
    for c in data["cases"]:
        for p in c["pairs"]:
            if p["window"] == 30:
                rows.append([str(c["video_id"]) + "/GT" + str(c["gt_id"]) + "/t" + str(c["frame"]),
                             p["model"], p["condition"], str(p["uncorrected"]["correct_visible_steps"]),
                             str(p["H"]["correct_visible_steps"]), str(p["R"]["correct_visible_steps"])])
    add("scores", "30步总表：先与未纠正基线比较", "30-step scores: compare with native first",
        "<p>" + t("各格为固定原ID正确步骤数，分母均30。A/B前史标签分别解释；不把来源缺失记成0分。", "Entries count correct steps for the fixed original ID, all out of 30. Interpret each system's prefix label separately; an unavailable source is not a zero score.") + "</p>"
        + table([t("视频/目标/时刻", "Video/target/time"), t("系统", "System"), t("框来源", "Box source"), "N", "H", "R"], rows, "natural-scores"))
    cards = []
    labels = {"persistent_failure": ("持续失败", "Persistent failure"), "maintenance": ("维持正确", "Maintenance"),
              "recently_unstable": ("近期不稳定", "Recently unstable")}
    ordered = sorted(data["cases"], key=lambda c: (c["key"] != "reference-S01", c["video_id"] != 2694, c["video_id"]))
    for c in ordered:
        header = f"{c['video_id']} · GT{c['gt_id']} · t{c['frame']}"
        body = f'<details class="natural-event" id="{c["key"]}"><summary>{header}</summary><p>'
        body += " / ".join(m + ": " + t(*labels[c["labels"][m+"0"]]) for m in ("A", "B"))
        body += "</p><p>" + t("纠正前3步IoU：", "Three pre-correction IoUs: ")
        body += "; ".join(m + "=" + ", ".join(f"{v:.3f}" for v in c["recent_three_iou"][m+"0"]) for m in ("A", "B")) + "</p>"
        if len(c["conditions"]) == 1:
            body += "<p class='notice'>" + t("该时刻无合格YOLO纠正框，只有参考框条件；不是YOLO条件得零分。", "No eligible YOLO correction exists at this step. Reference-only condition; not a zero-scoring YOLO condition.") + "</p>"
        for condition in c["conditions"]:
            body += "<h3>" + t("YOLO框" if condition == "yolo" else "参考框", "YOLO box" if condition == "yolo" else "Reference box") + "</h3>"
            details = []
            for p in c["pairs"]:
                if p["condition"] != condition:
                    continue
                h,r = p["H"],p["R"]
                value = lambda x: "—" if x is None else str(x)
                details.append([p["model"], str(p["window"]), str(p["uncorrected"]["correct_visible_steps"]),
                                str(h["correct_visible_steps"]), str(r["correct_visible_steps"]),
                                value(h["recovery_confirmed_offset"]) + "/" + value(r["recovery_confirmed_offset"]),
                                str(h["relapses"]) + "/" + str(r["relapses"])])
            body += table([t("系统", "System"), t("窗口", "Window"), "N", "H", "R", t("H/R确认偏移", "H/R confirmation offset"), t("H/R复发", "H/R relapses")], details, c["key"] + "-" + condition)
            media = c["media"][condition]
            body += '<video controls preload="none" aria-label="' + escape(header + " " + condition, quote=True) + '" src="' + media["video"] + '"></video>'
            body += '<details><summary>' + t("曲线与固定+8步局部图", "Curves and fixed +8-step zoom") + '</summary>'
            body += '<img loading="lazy" src="' + media["curve"] + '" alt="' + t("恢复曲线", "Recovery curves") + '">'
            body += '<img loading="lazy" src="' + media["zoom"] + '" alt="' + t("固定+8步目标局部图", "Fixed +8-step target zoom") + '"></details>'
        cards.append(body + "</details>")
    add("events", "逐段看视频与恢复过程", "Inspect videos and recovery dynamics", "".join(cards))
    add("coverage", "没有选到，不等于没有失败", "Not selected does not mean no failure",
        "<p>" + t("首轮31段中，18个视频/GT目标键曾满足SAM持续失败，7个失败时SAM状态仍在；两系统有足够正确前史且可保留的有4个，具完整30步可见窗口的仅1个，而且没有合格YOLO纠正框。备用6段的对应计数为6、2、1、0。它们是目标键数，不是独立视频数或总体失败率。",
                        "Among the initial 31 videos, 18 video/GT-target keys exhibit persistent SAM failure; seven still retain SAM state. Four also meet both systems' prefix/state requirements, only one has 30 visible future steps, and it lacks an eligible YOLO correction. The corresponding reserve counts are 6, 2, 1 and 0. These count target keys, not independent videos or population failure rates.")
        + "</p><p>" + t("因此单独保留参考框层，不修改失败门槛、不缩短窗口、不继续找H/R赢家。自然前史质量只是观察到的代理指标，不是已操纵的“可靠/污染”因子。人为污染实验的代码与结果已于2026-10-28从当前工作区删除，未纳入本页。任何新增实验分支必须先经用户人工确认。",
                         "We therefore retain a separate reference-only stratum without changing failure thresholds, shortening windows or searching for H/R winners. Natural prefix quality is an observed proxy, not an experimentally manipulated reliable/polluted factor. Artificial-pollution code and results were deleted from the current workspace on 2026-10-28 and are excluded here. Every new experimental branch requires explicit human confirmation first.") + "</p>")
    code_rows = [
        ("natural_events.py → scan / choose_events", "原生失败筛选、确定性选样、先冻结", "Screen native failures; select deterministically and freeze first"),
        ("natural_recovery.py → prepare / execute", "复用原H/R引擎，两来源四组运行", "Reuse the H/R engine for both sources and four groups"),
        ("natural_coverage.py → inspect_queue", "审计未入选SAM事件的原因", "Audit why SAM failures were not selected"),
        ("natural_reference.py → freeze / execute", "无YOLO框时单独做参考框四组", "Separate four-group reference-only stratum when YOLO is unavailable"),
        ("recovery_engines.py → ByteEngine.step / SamEngine.step", "执行保留/重置，记录关联与实际提示", "Apply retain/reset and log associations and actual prompts"),
        ("natural_report.py → verify_selection / build", "重算标签、评分、ByteTrack重放与分层分析", "Recompute labels, scores, ByteTrack replay and stratified analysis"),
    ]
    add("code", "程序步骤与复核", "Code steps and verification",
        table([t("文件 → 函数", "File → function"), t("职责", "Role")], [["<code>"+escape(f)+"</code>",t(zh,en)] for f,zh,en in code_rows], "natural-code")
        + "<p>" + t("52主分支通过共同前缀、纠正框、固定原ID与重置审计；全部A分支独立CPU重放一致，B提示与检测缓存逐项核对。20个预指定复跑分支的预测和评分复现，不增加样本数。共享检测缓存不保证后续SAM实际接受的提示相同。",
                         "All 52 main branches pass prefix, correction, fixed-ID and reset audits. Every A branch replays exactly on CPU; B prompt inputs are checked against cached detections. Predictions and scores repeat in 20 preselected validation branches, which add no samples. Shared detector caches do not guarantee identical accepted future SAM prompts.")
        + "</p><details><summary>" + t("源码参考与下载", "Source references and downloads") + "</summary><p>"
        + " · ".join(link(c["url"],c["name"]) for c in data["code"])
        + "</p><p>" + t("这些是当前源码参考，哈希在manifest中；不冒充不可变推理快照。原始推理快照仍在实验归档。",
                         "These are current source references with hashes in the manifest, not immutable inference snapshots. Original inference snapshots remain in the experiment archives.")
        + '</p><a href="' + PREFIX + 'paired-scores.csv.txt" download="natural-paired-scores.csv">' + t("下载78条配对读数CSV", "Download 78 paired-window readings (CSV)") + "</a> · "
        + link(PREFIX+"manifest.json", t("公开结果与指纹", "Public results and fingerprints")) + "</details>")
    add("limits", "能说明什么，还不能说明什么", "What the evidence does and does not establish",
        "<p>" + t("已有自然案例同时支持保留有益与重置有益；最近连续低分不足以直接决定清空历史。框来源与后续关联/提示反馈也会改变结果。目前是开发机制研究，不是随机事件频率、五类总体排名或正式保留集结论。正式AP、端到端速度与保留评估尚未完成；没有据此推出自动重置策略。",
                         "Natural cases now support both beneficial retention and beneficial reset; recent low scores alone do not justify clearing history. Box sources and later association/prompt feedback also matter. This remains a development mechanism study, not random-event prevalence, a five-class ranking or held-out evidence. Formal AP, end-to-end timing and held-out evaluation remain unfinished; no automatic reset policy has been established.")
        + "</p><p>" + " · ".join(link(slug+suffix+".html",t(zh,en)) for slug,zh,en in (
            ("recovery-cohort","回看旧16段","Earlier 16-event study"),("recovery-long","回看骑手与猫","Rider/cat follow-up"),
            ("experiments","原对照方案","Original controlled protocol"),("handbook","模型与指标学习","Model and metric lessons"))) + "</p>")
    return blocks


def write_natural_pages(output, import_assets=False):
    output = Path(output)
    path = output / PREFIX / "manifest.json"
    data = import_results(output) if import_assets else (read(path) if path.is_file() else None)
    template = (WEB / "study.html").read_text(encoding="utf-8")
    css = "".join((WEB/n).read_text(encoding="utf-8") for n in ("tutorial.css","study.css","recovery.css"))
    css += ".natural-flow{display:flex;flex-wrap:wrap;gap:1rem;padding-left:1.5rem}.natural-flow li{flex:1;min-width:180px;padding:1rem;background:var(--panel)}.natural-event{border:1px solid var(--line);border-radius:8px;padding:1rem;margin:1rem 0}.natural-event summary{cursor:pointer;font-weight:700}.natural-event video,.natural-event img{width:100%;height:auto;max-width:100%}.natural-finding{border-left:3px solid var(--accent);padding-left:1rem;margin:1.5rem 0}"
    for language,filename in zip(("zh","en"),PAGES):
        t = lambda zh,en:pick(language,zh,en)
        suffix = ".en" if language=="en" else ""
        blocks = content(data,language) if data else [("status",t("未导入实测","No imported measurements"),"<p>"+t("尚未导入已验证自然失败实验；页面不启动推理。","No verified natural-failure evidence has been imported; this page does not start inference.")+"</p>")]
        intro = "<p>"+t("修正版基线 → 旧16段的维持/风险证据 → 持续自然失败补充。","Corrected baselines → maintenance/risk evidence from 16 events → persistent natural failures.")+"</p>"
        if data:
            intro += "<p>"+t("本地RTX3080 · 7事件 · 52主分支 · 20复跑验证分支 · 13个四组对照视频","Local RTX3080 · 7 events · 52 main branches · 20 repeat-only branches · 13 four-group videos")+"</p>"
        values = {"LANG":t("zh-CN","en"),"TITLE":t("自然失败后，历史应该保留还是重置？","After natural failure: retain or reset history?"),
                  "INTRO":intro,"HOME":"index"+suffix+".html","OTHER":"recovery-natural"+("" if suffix else ".en")+".html",
                  "CSS":css,"JS":(WEB/"study.js").read_text(encoding="utf-8"),
                  "NAV":"".join(link("#"+k,title) for k,title,_ in blocks),"BODY":"".join(section(k,title,body) for k,title,body in blocks),
                  "SWITCH":t("English","中文"),"BACK":t("项目总览","Project overview"),"MENU":t("本页目录","On this page"),
                  "THEME":t("切换主题","Theme"),"SKIP":t("跳到正文","Skip to content"),"TRAIL":t("真实实验 · 自然失败恢复","Real experiments · natural-failure recovery"),
                  "FOOT":t("只读实测记录；不含人为污染；页面不运行模型。","Saved measurements only; artificial history pollution excluded; no model runs from this page.")}
        text = re.sub(r"@@([A-Z_]+)@@",lambda m:values[m[1]],template)
        (output/filename).write_text(decorate_page(text,language,"recovery-natural", output),encoding="utf-8")


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    write_natural_pages(parser.parse_args().output,import_assets=True)
