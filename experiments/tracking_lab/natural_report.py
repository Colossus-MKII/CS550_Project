"""Read-only natural-failure analysis: never combine maintenance with recovery.

per_event() reuses the established independent scorer, ByteTrack replay and
SAM prompt audits. This wrapper adds model-specific pre-correction labels,
uncorrected controls, and 8/20/30-step tables for the NEW supplement only.
No model inference, website update, server, upload or old-result modification.
"""

import argparse
from collections import Counter
from html import escape
import os
from pathlib import Path

from .common import digest, load_predictions, write_json
from .dataset import load_ground_truth, read_manifest
from .natural_events import failure_label, fixed_id_curve, read_json
from .recovery_cohort_report import per_event, aggregate
from .recovery_report import write_csv


def verify_selection(event, data_root):
    """Recompute the frozen natural-prefix labels, without using H/R outputs."""
    source = Path(event["baseline_folder"])
    _, rows, _ = read_manifest(data_root, [event["video_id"]])
    gt = load_ground_truth(data_root, rows[0])
    for model in ("A0", "B0"):
        predictions = load_predictions(source / str(event["video_id"]) / model)
        values, pid, _ = fixed_id_curve(gt, predictions, event["gt_id"], event["category"])
        t = event["frame"]
        assert pid == event["anchors"][model]["prediction_id"]
        assert values[t-2:t+1] == event["recent_three_iou"][model]
        assert failure_label(values, t) == event["labels"][model]
    assert all(any(o.identity == event["gt_id"] for o in gt[t])
               for t in range(event["frame"]+1, event["frame"]+31))


def display(value):
    return "—" if value is None else str(value)


def write_readable(output, plan, frozen, pairs, aggregates):
    """A compact local report; videos remain in each experiment's archive."""
    lines = [
        "自然持续失败后的保留／重置补充实验",
        f"{len(plan['events'])}个事件，{plan['actual_branches']}个主分支；另{plan['repeat_branches']}个分支仅用于独立复跑。",
        "仅开发集、本地RTX3080、固定权重、原生历史；不含人为污染。框来源：" + ", ".join(plan["conditions"]),
        "纠正当步不计分。IoU>=0.5，连续3个GT可见步骤确认；固定前缀原ID。",
        "30步完整可见是选样条件，不保证原生或干预后的预测正确。",
        "失败/维持标签由每个模型各自的纠正前预测确定，不能整段视频统一叫恢复。",
        "N/H/R分别为未纠正/保留/重置；纠正收益与重置增量分开看。",
        "YOLO/参考是框来源，不预设参考框在所有场景都更好。",
        "后续YOLO缓存相同，但闭环SAM实际接受的提示可以不同。",
        "本批按自然失败富集选样，不估计真实场景失败率，不与旧16段合并投票。",
        "",
    ]
    cards = []
    for selected in frozen["events"]:
        eid = selected["event_id"]
        row = next(r for r in plan["events"] if r["event_id"] == eid)
        lines += [f"{eid}: video {selected['video_id']} / GT{selected['gt_id']} / t{selected['frame']}",
                  f"  前史标签 A={selected['labels']['A0']}; B={selected['labels']['B0']}; 与旧16段视频重复={selected['reused_video_from_16']}"]
        table = []
        for p in [p for p in pairs if p["event_id"] == eid]:
            n,h,r = p["uncorrected"],p["H"],p["R"]
            if p["window"] == 30:
                lines.append(f"  {p['model']}/{p['condition']}: N/H/R={n['correct_visible_steps']}/{h['correct_visible_steps']}/{r['correct_visible_steps']} /30; H/R确认偏移={display(h['recovery_confirmed_offset'])}/{display(r['recovery_confirmed_offset'])}; H/R复发={h['relapses']}/{r['relapses']}; H/R首次删除={display(p['H_diagnostics']['first_state_deletion_offset'])}/{display(p['R_diagnostics']['first_state_deletion_offset'])}")
            table.append("<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in (
                p["model"]+" / "+p["condition"],p["pre_event_label"],p["window"],
                n["correct_visible_steps"],h["correct_visible_steps"],r["correct_visible_steps"],
                f"{p['R_minus_H_mean_mask_iou']:+.4f}",
                display(h["recovery_confirmed_offset"])+" / "+display(r["recovery_confirmed_offset"]),
                str(h["terminal_three_step_success"])+" / "+str(r["terminal_three_step_success"])
            )) + "</tr>")
        media = []
        for condition in plan["conditions"]:
            movie = Path(row["folder"]) / "visuals" / f"{selected['name']}-{condition}-four-groups.mp4"
            if not movie.is_file():
                raise FileNotFoundError(movie)
            link = Path(os.path.relpath(movie, output)).as_posix()
            zoom = f"{eid}-{condition}-zoom-plus8.png"
            media.append(f'<details><summary>{condition} · 四组视频与固定+8步局部图</summary><video controls preload="none" src="{escape(link)}"></video><img loading="lazy" src="{zoom}"></details>')
        recent = escape(str(selected["recent_three_iou"]))
        cards.append(f'<section id="{eid}"><h2>{eid} · video {selected["video_id"]} · GT{selected["gt_id"]} · t{selected["frame"]}</h2><p>前3步原ID IoU：{recent}</p><p>A={selected["labels"]["A0"]}；B={selected["labels"]["B0"]}。旧16段出现过该视频：{selected["reused_video_from_16"]}，不作为跨批独立视频。</p><div class="scroll"><table><tr><th>模型/框</th><th>前史标签</th><th>窗口</th><th>未纠正正确步</th><th>H正确步</th><th>R正确步</th><th>R−H平均IoU</th><th>H/R首次3步确认偏移</th><th>H/R末3步正确</th></tr>{"".join(table)}</table></div>{"".join(media)}</section>')
    lines += ["", "分组汇总（失败与维持分开；选样偏倚存在）："]
    for a in aggregates:
        if a["window"] == 30:
            lines.append(f"  {a['pre_event_label']} {a['model']}/{a['condition']}: n={a['independent_event_units']}; H更多={a['H_more_correct_steps']}, R更多={a['R_more_correct_steps']}, 持平={a['threshold_count_ties']}")
    lines += ["", "复跑：" + str(plan["repeat_verification"]),
              "", "单来源条件不能补算缺失来源；失败与维持标签分别解释，跨批研究结论见总读数。",
              "完整逐帧诊断见results.json；原预测、干预审计和视频均保存在cohort各事件目录。",
              "本次不改变proposal/网站，不提交Git或课程作业。"]
    (output / "READ_RESULTS_ZH.txt").write_text("\n".join(lines)+"\n", encoding="utf-8")
    intro = "<br>".join(escape(s) for s in lines[:11])
    html = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>自然失败H/R补充实验</title><style>body{{max-width:1200px;margin:32px auto;padding:0 20px;font:16px/1.7 system-ui;background:#111a20;color:#eaf1f4}}a{{color:#a6dfcf}}section{{margin-top:32px;border-top:1px solid #50606a}}table{{width:100%;border-collapse:collapse;font-size:14px}}td,th{{padding:8px;text-align:left;border-bottom:1px solid #40505c}}.scroll{{overflow:auto}}video,img{{width:100%;height:auto}}details{{margin:16px 0}}</style><h1>自然失败H/R补充实验</h1><p>{intro}</p><p>persistent_failure=持续失败；maintenance=连续正确的维持对照；recently_unstable=最近不稳定；transient_failure=当步失败但未连续3步。</p><p><a href="READ_RESULTS_ZH.txt">中文读数</a> · <a href="paired-8-20-30.csv">全部配对表</a> · <a href="results.json">逐帧诊断</a> · <a href="verification.json">校验记录</a></p>{"".join(cards)}</html>'''
    (output / "RESULTS_ZH.html").write_text(html, encoding="utf-8")


def build(cohort, output):
    cohort, output = Path(cohort), Path(output)
    if output.exists():
        raise FileExistsError("Use a new analysis directory")
    plan = read_json(cohort / "cohort.json")
    if plan["status"] != "completed" or plan["actual_branches"] != len(plan["events"])*4*len(plan["conditions"]):
        raise ValueError("Require a complete verified cohort")
    assert digest(cohort / "frozen-events.json") == plan["frozen_selection_sha256"]
    frozen = read_json(cohort / "frozen-events.json")
    assert plan["repeat_verification"]["status"] == "passed"
    output.mkdir(parents=True)
    pairs, checks = [], []
    for row in plan["events"]:
        selected = next(e for e in frozen["events"] if e["event_id"] == row["event_id"])
        verify_selection(selected, Path(plan["data_root"]))
        event_pairs, verified = per_event(row, plan, selected, output)
        for p in event_pairs:
            p["pre_event_label"] = selected["labels"][p["model"]+"0"]
            p["reused_video_from_16"] = selected["reused_video_from_16"]
        pairs += event_pairs
        checks.append({"event_id": row["event_id"], **verified})
        print("Analyzed", row["event_id"], 6*len(plan["conditions"]), "paired window readings", flush=True)
    aggregates = []
    for label in sorted({p["pre_event_label"] for p in pairs}):
        for a in aggregate([p for p in pairs if p["pre_event_label"] == label]):
            aggregates.append({"pre_event_label": label, **a})
    result = {
        "status": "completed", "cohort": str(cohort.resolve()),
        "cohort_sha256": digest(cohort / "cohort.json"),
        "primary_events": len(plan["events"]), "branches": plan["actual_branches"],
        "paired_windows": len(pairs), "pair_results": pairs, "aggregates": aggregates,
        "native_prefix_labels": dict(Counter(p["pre_event_label"] for p in pairs if p["window"]==30 and p["condition"]==plan["conditions"][0])),
        "limitations": frozen["limitations"], "source_sha256": digest(Path(__file__)),
    }
    write_json(output / "results.json", result)
    write_json(output / "verification.json", {
        "status": "passed", "events": checks, "prefix_failure_labels_recomputed": True,
        "independent_Byte_replays": True, "native_SAM_prompt_audit": True,
        "repeat": plan["repeat_verification"],
    })
    write_csv(output / "paired-8-20-30.csv", [{
        **{k:p[k] for k in ("event_id","video_id","model","condition","window","pre_event_label","reused_video_from_16","R_minus_H_correct_steps","R_minus_H_mean_mask_iou")},
        **{label+"_"+k:v for label in ("uncorrected","H","R") for k,v in p[label].items()}
    } for p in pairs])
    write_csv(output / "aggregates.csv", aggregates)
    write_readable(output, plan, frozen, pairs, aggregates)
    print("Natural analysis completed:", output, flush=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cohort", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args(argv)
    build(a.cohort, a.output)


if __name__ == "__main__":
    main()
