"""Read SAVED 16-event H/R runs; verify, rescore 8/20/30 and explain failures.

No inference/training here. Workflow: build() -> per_event() -> pair() -> HTML.
Do not call an already-correct control an error-recovery success. Separate
active poor masks, missing association outputs, target deletion and invisible
GT. Compare H/R within a model/box condition; never rank pooled memory types.
"""

import argparse
from collections import Counter, defaultdict
from html import escape
import json
from pathlib import Path
import statistics

import numpy as np

from .common import box_iou, digest, load_predictions, mask_iou, write_json
from .recovery_long_report import checkpoint_score, different_frames
from .recovery import assert_same_predictions
from .recovery_report import verify_recovery, write_csv


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def lifecycle_state(trace, frame, identity, method):
    """Presence in a retained state container is NOT mask/identity correctness."""
    row = trace[frame]
    if method == "B":
        return "active" if identity in row["active_ids"] else "deleted"
    state = next((s for s in row["states"] if s["id"] == identity), None)
    return (
        {1: "tracked", 2: "lost", 3: "removed"}.get(state["state"], "other")
        if state
        else "deleted"
    )


def target_prompts(trace, identity, correction):
    """Actual supplied target prompts, excluding the controlled correction."""
    return [
        {"frame": r["frame"], **p}
        for r in trace[correction + 1 :]
        for p in r.get("prompt_inputs", [])
        if p["id"] == identity
    ]


def prompt_api_schedule(trace, correction, identity=None):
    """SAM receives frame/object/box, NOT detector score or detector row ID."""
    return [
        {"frame": r["frame"], "id": p["id"], "box_xyxy": p["box_xyxy"]}
        for r in trace[correction + 1 :]
        for p in r.get("prompt_inputs", [])
        if identity is None or p["id"] == identity
    ]


def audit_prompts(trace, record, detections):
    """Assert all recorded native SAM boxes are the actual cached observations."""
    for r in trace:
        for p in r.get("prompt_inputs", []):
            if p["source"] == "controlled_correction":
                expected = record["correction"]
                np.testing.assert_array_equal(
                    np.asarray(p["box_xyxy"], np.float32),
                    np.asarray(expected["box"], np.float32),
                )
                assert (
                    p["id"] == record["prediction_id"]
                    and p["score"] == expected["score"]
                )
            else:
                detection = next(
                    d
                    for d in detections[r["frame"]]
                    if d.identity == p["detector_index"]
                )
                assert p["score"] == detection.score
                np.testing.assert_array_equal(np.asarray(p["box_xyxy"]), detection.box)


def assignment_for_target(trace_row, identity):
    rows = []
    for category in trace_row.get("assignments", []):
        for stage in category["stages"]:
            for i, track in enumerate(stage["tracks"]):
                if track["external_id"] != identity:
                    continue
                match = next((j for a, j in stage["matches"] if a == i), None)
                rows.append(
                    {
                        "stage": stage["stage"],
                        "threshold": stage["threshold"],
                        "detections": stage["detections"],
                        "assignment_costs": stage["assignment_cost"][i],
                        "assigned_detector_index": (
                            stage["detections"][match]["detector_index"]
                            if match is not None
                            else None
                        ),
                    }
                )
    return rows


def different_KF_state_steps(first, second, identity, start):
    """Manipulation check, not a geometric score: KF history can differ even
    when both branches associate the same detector mask and look identical.
    """
    changed = []
    for t in range(start, min(len(first), len(second))):
        left = next((s for s in first[t]["states"] if s["id"] == identity), None)
        right = next((s for s in second[t]["states"] if s["id"] == identity), None)
        if (left is None) != (right is None) or (
            left is not None
            and any(
                not np.array_equal(left[k], right[k]) for k in ("mean", "covariance")
            )
        ):
            changed.append(t - start)
    return changed


def branch_diagnostics(gt, predicted, trace, detections, event, record):
    """Descriptions from actual states/detections; GT never changes inference."""
    pid, gid, start = record["prediction_id"], event["gt_id"], event["frame"]
    method = record["group"][0]
    details = []
    for t in range(start + 1, start + 31):
        truth = next((o for o in gt[t] if o.identity == gid), None)
        target = next((o for o in predicted[t] if o.identity == pid), None)
        quality = (
            mask_iou(truth.mask, target.mask)
            if truth and target and target.category == truth.category
            else 0.0
        )
        state = lifecycle_state(trace, t, pid, method)
        same_class = [o for o in predicted[t] if truth and o.category == truth.category]
        alternatives = [o for o in same_class if o.identity != pid]
        other = max(
            alternatives, key=lambda o: mask_iou(truth.mask, o.mask), default=None
        )
        observations = [
            o for o in detections[t] if truth and o.category == truth.category
        ]
        best_observation = max(
            observations, key=lambda o: mask_iou(truth.mask, o.mask), default=None
        )
        best_detector = (
            mask_iou(truth.mask, best_observation.mask) if best_observation else 0.0
        )
        if truth is None:
            kind = "GT_invisible_output" if target else "GT_invisible_no_output"
        elif state in {"deleted", "removed"}:
            kind = "target_state_deleted"
        elif quality >= 0.5:
            kind = "correct_fixed_id"
        elif method == "A" and best_detector >= 0.5:
            kind = "A_correct_detection_but_fixed_id_failed"
        elif not target:
            kind = "retained_state_without_mask"
        else:
            kind = "retained_state_low_mask_iou"
        details.append(
            {
                "frame": t,
                "offset": t - start,
                "visible": truth is not None,
                "state": state,
                "output_present": target is not None,
                "mask_iou": quality if truth else None,
                "kind": kind,
                "best_detector_mask_iou": best_detector if truth else None,
                "best_detector_index": (
                    best_observation.identity if best_observation else None
                ),
                "best_detector_score": (
                    best_observation.score if best_observation else None
                ),
                "best_detector_band_at_frozen_025": (
                    ("high" if best_observation.score >= 0.25 else "low")
                    if best_observation
                    else None
                ),
                "other_qualifying_id": (
                    other.identity
                    if other and mask_iou(truth.mask, other.mask) >= 0.5
                    else None
                ),
                "target_assignments": (
                    assignment_for_target(trace[t], pid)
                    if method == "A" and quality < 0.5 and truth
                    else []
                ),
                "retire_action": any(
                    a.get("id") == pid and a["action"] == "retire"
                    for a in trace[t].get("actions", [])
                ),
            }
        )
    return {
        "counts": dict(Counter(r["kind"] for r in details)),
        "first_state_deletion_offset": next(
            (r["offset"] for r in details if r["state"] in {"deleted", "removed"}), None
        ),
        "first_wrong_fixed_id_with_correct_detection": next(
            (
                r["offset"]
                for r in details
                if r["kind"] == "A_correct_detection_but_fixed_id_failed"
            ),
            None,
        ),
        "frames": details,
    }


def render_target_zoom(video, gt, loaded, event, condition, path):
    """Same +8 step and same crop for every group; no result-driven frame pick."""
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    t = event["frame"] + 8
    truth = next((o for o in gt[t] if o.identity == event["gt_id"]), None)
    rgb = Image.open(video.rgb_paths[t]).convert("RGB")
    if truth:
        cx, cy = (truth.box[:2] + truth.box[2:]) / 2
        size = max(110.0, float(max(truth.box[2:] - truth.box[:2])) * 1.7)
        crop = (
            max(0, int(cx - size / 2)),
            max(0, int(cy - size / 2)),
            min(video.width, int(cx + size / 2)),
            min(video.height, int(cy + size / 2)),
        )
    else:
        crop = (0, 0, video.width, video.height)
    panels = [("RGB", None), ("GT visible target", truth)]
    for group in ("A-H", "A-R", "B-H", "B-R"):
        predictions, _ = loaded[(condition, group)]
        # All prefix-anchored IDs remain fixed; infer the ID from event anchors.
        pid = event["anchors"][group[0] + "0"]["prediction_id"]
        obj = next((o for o in predictions[t] if o.identity == pid), None)
        quality = mask_iou(truth.mask, obj.mask) if truth and obj else 0.0
        panels.append(
            (f"{group} ID{pid} IoU {quality:.3f}" if truth else f"{group} GT N/A", obj)
        )
    canvas = Image.new("RGB", (720, 990), (17, 26, 32))
    for i, (title, obj) in enumerate(panels):
        image = rgb.convert("RGBA")
        if obj:
            overlay = np.zeros((video.height, video.width, 4), np.uint8)
            overlay[obj.mask] = [60, 240, 140, 85]
            image = Image.alpha_composite(image, Image.fromarray(overlay))
        image = ImageOps.pad(
            image.convert("RGB").crop(crop), (360, 290), color=(17, 26, 32)
        )
        x, y = (i % 2) * 360, (i // 2) * 330
        canvas.paste(image, (x, y + 35))
        ImageDraw.Draw(canvas).text(
            (x + 7, y + 6), title, fill="white", font=ImageFont.load_default(size=17)
        )
    canvas.save(path)


def replay_byte_branches(detections, event, records, loaded, config):
    """Recompute ALL available A-H/R branches on CPU, without GT inputs.

    This verifies even one-step association differences independently of the
    saved scores. A separately labelled single-source study has two A branches,
    not four; never synthesize the missing correction source. No additional
    samples, detector calls or GPU inference.
    """
    from .recovery_engines import ByteEngine, Correction

    conditions = tuple(dict.fromkeys(condition for condition, _ in records))
    engine = ByteEngine(config, association_diagnostics=True)
    t = event["frame"]
    for frame in range(t):
        objects, _ = engine.step(frame, detections[frame])
        assert_same_predictions(objects, loaded[(conditions[0], "A-H")][0][frame])
    checked = 0
    for condition in conditions:
        for reset in (False, True):
            key = (condition, "A-R" if reset else "A-H")
            rec = records[key]
            predicted, trace = loaded[key]
            supplied = rec["correction"]
            correction = Correction(
                rec["prediction_id"],
                event["category"],
                np.asarray(supplied["box"], np.float32),
                supplied["score"],
                supplied["detector_index"],
                reset,
            )
            branch = engine.fork()
            for frame in range(t, t + 31):
                objects, state = branch.step(
                    frame, detections[frame], correction if frame == t else None
                )
                assert_same_predictions(objects, predicted[frame])
                assert (
                    state == trace[frame]
                ), f"Byte replay state/assignment trace changed at {frame}"
                checked += 1
    return {
        "status": "passed",
        "branches": 2 * len(conditions),
        "branch_frames_checked": checked,
        "prefix_frames": t,
        "comparison": "all objects, masks, IDs, boxes, scores, KF states and assignment traces exact; no GT fed to replay",
    }


def per_event(row, plan, reviewed, zoom_output=None):
    root = Path(row["folder"])
    summary, videos, truths, source, verification = verify_recovery(
        root, Path(plan["data_root"])
    )
    if len(summary["events"]) != 1 or len(summary["branches"]) != 4 * len(plan["conditions"]):
        raise AssertionError("Incomplete per-event run")
    event = summary["events"][0]
    assert event["video_id"] == row["video_id"] and event["video_id"] != 2967
    gt = truths[event["video_id"]]
    detections = load_predictions(source / str(event["video_id"]) / "YOLO")
    baseline_scores = {}
    for model in ("A", "B"):
        baseline_folder = (
            source / str(event["video_id"]) / "A0"
            if model == "A"
            else root / "baseline_replay" / str(event["video_id"]) / "B0"
        )
        original = load_predictions(baseline_folder)
        anchor = {"prediction_id": reviewed["anchors"][model + "0"]["prediction_id"]}
        for window in (8, 20, 30):
            baseline_scores[(model, window)] = checkpoint_score(
                gt, original, None, event, anchor, window, summary["configuration"]
            )["summary"]
    records, scores, loaded, diagnostics = {}, {}, {}, {}
    for branch in summary["branches"]:
        folder = root / branch["folder"]
        predictions = load_predictions(folder)
        trace = read_json(folder / "state-trace.json")
        key = (branch["condition"], branch["group"])
        records[key] = branch
        loaded[key] = (predictions, trace)
        if branch["group"].startswith("B"):
            audit_prompts(trace, branch, detections)
        diagnostics[key] = branch_diagnostics(
            gt, predictions, trace, detections, event, branch
        )
        for window in (8, 20, 30):
            result = checkpoint_score(
                gt, predictions, trace, event, branch, window, summary["configuration"]
            )
            last = result["curve"][-1]
            scores[key + (window,)] = {
                **result["summary"],
                "terminal_GT_visible": last["visible"],
                "terminal_correct": last["correct"] if last["visible"] else None,
                "terminal_three_step_success": (
                    last["success_streak"] >= 3 if last["visible"] else None
                ),
            }
    pairs = []
    for condition in plan["conditions"]:
        for model in ("A", "B"):
            hkey, rkey = (condition, model + "-H"), (condition, model + "-R")
            hrecord, rrecord = records[hkey], records[rkey]
            hp, ht = loaded[hkey]
            rp, rt = loaded[rkey]
            assert hrecord["prefix_target_sha256"] == rrecord["prefix_target_sha256"]
            assert hrecord["correction"] == rrecord["correction"]
            changed = [
                f
                for f in different_frames(hp, rp, hrecord["prediction_id"])
                if f > event["frame"]
            ]
            state_changed = (
                different_KF_state_steps(
                    ht, rt, hrecord["prediction_id"], event["frame"]
                )
                if model == "A"
                else None
            )
            hprompts = (
                target_prompts(ht, hrecord["prediction_id"], event["frame"])
                if model == "B"
                else []
            )
            rprompts = (
                target_prompts(rt, rrecord["prediction_id"], event["frame"])
                if model == "B"
                else []
            )
            for window in (8, 20, 30):
                h, r = scores[hkey + (window,)], scores[rkey + (window,)]
                baseline_iou = reviewed["baseline_fixed_id_mask_iou_at_correction"][
                    model + "0"
                ]
                pairs.append(
                    {
                        "event_id": row["event_id"],
                        "event": row["name"],
                        "video_id": event["video_id"],
                        "scene": row["scene"],
                        "condition": condition,
                        "model": model,
                        "window": window,
                        "baseline_correct_at_t0": baseline_iou >= 0.5,
                        "baseline_fixed_id_mask_iou_at_t0": baseline_iou,
                        "H": h,
                        "R": r,
                        "uncorrected": baseline_scores[(model, window)],
                        "R_minus_H_correct_steps": r["correct_visible_steps"]
                        - h["correct_visible_steps"],
                        "R_minus_H_mean_mask_iou": r["mean_visible_mask_iou"]
                        - h["mean_visible_mask_iou"],
                        "designated_output_changed_steps": [
                            f - event["frame"]
                            for f in changed
                            if f <= event["frame"] + window
                        ],
                        "KF_state_changed_offsets": (
                            [s for s in state_changed if s <= window]
                            if state_changed is not None
                            else None
                        ),
                        "H_diagnostics": diagnostics[hkey] if window == 30 else None,
                        "R_diagnostics": diagnostics[rkey] if window == 30 else None,
                        "actual_target_future_prompts_identical": (
                            prompt_api_schedule(
                                ht, event["frame"], hrecord["prediction_id"]
                            )
                            == prompt_api_schedule(
                                rt, event["frame"], rrecord["prediction_id"]
                            )
                            if model == "B"
                            else None
                        ),
                        "all_objects_future_prompt_API_calls_identical": (
                            prompt_api_schedule(ht, event["frame"])
                            == prompt_api_schedule(rt, event["frame"])
                            if model == "B"
                            else None
                        ),
                        "target_prompt_audit_metadata_identical": (
                            hprompts == rprompts if model == "B" else None
                        ),
                        "H_target_prompts": (
                            hprompts if window == 30 and model == "B" else None
                        ),
                        "R_target_prompts": (
                            rprompts if window == 30 and model == "B" else None
                        ),
                    }
                )
    verification["independent_Byte_branch_replay"] = replay_byte_branches(
        detections, event, records, loaded, summary["baseline_configuration"]
    )
    if zoom_output is not None:
        for condition in plan["conditions"]:
            render_target_zoom(
                videos[0],
                gt,
                loaded,
                event,
                condition,
                Path(zoom_output) / f"{row['event_id']}-{condition}-zoom-plus8.png",
            )
    return pairs, verification


def aggregate(pairs):
    grouped = defaultdict(list)
    for row in pairs:
        grouped[(row["model"], row["condition"], row["window"])].append(row)
    result = []
    for (model, condition, window), rows in sorted(grouped.items()):
        deltas = [r["R_minus_H_correct_steps"] for r in rows]
        result.append(
            {
                "model": model,
                "condition": condition,
                "window": window,
                "independent_event_units": len(rows),
                "R_more_correct_steps": sum(d > 0 for d in deltas),
                "H_more_correct_steps": sum(d < 0 for d in deltas),
                "threshold_count_ties": sum(d == 0 for d in deltas),
                "exact_target_output_ties": sum(
                    not r["designated_output_changed_steps"] for r in rows
                ),
                "mean_R_minus_H_mask_iou": statistics.mean(
                    r["R_minus_H_mean_mask_iou"] for r in rows
                ),
                "mean_R_minus_H_correct_fraction": statistics.mean(
                    r["R"]["correct_visible_fraction"]
                    - r["H"]["correct_visible_fraction"]
                    for r in rows
                ),
                "mean_H_minus_uncorrected_fraction": statistics.mean(
                    r["H"]["correct_visible_fraction"]
                    - r["uncorrected"]["correct_visible_fraction"]
                    for r in rows
                ),
                "mean_R_minus_uncorrected_fraction": statistics.mean(
                    r["R"]["correct_visible_fraction"]
                    - r["uncorrected"]["correct_visible_fraction"]
                    for r in rows
                ),
                "H_ever_three_step_success": sum(r["H"]["recovered"] for r in rows),
                "R_ever_three_step_success": sum(r["R"]["recovered"] for r in rows),
                "H_terminal_three_step_success": sum(
                    r["H"]["terminal_three_step_success"] is True for r in rows
                ),
                "R_terminal_three_step_success": sum(
                    r["R"]["terminal_three_step_success"] is True for r in rows
                ),
            }
        )
    return result


def aggregate_strata(pairs):
    return [
        {"scene": scene, **r}
        for scene in ("stable", "motion", "competition", "occlusion")
        for r in aggregate([p for p in pairs if p["scene"] == scene])
    ]


def format_offset(value):
    return "—" if value is None else str(value)


def write_html(output, cohort, plan, review, pairs, aggregates):
    def rel(path):
        import os

        return Path(os.path.relpath(path, output)).as_posix()

    rows = []
    for r in aggregates:
        rows.append(
            f'<tr><td>{r["model"]}</td><td>{r["condition"]}</td><td>{r["window"]}</td><td>{r["R_more_correct_steps"]}</td><td>{r["H_more_correct_steps"]}</td><td>{r["threshold_count_ties"]}</td><td>{r["mean_R_minus_H_mask_iou"]:+.4f}</td><td>{r["H_terminal_three_step_success"]}/{r["R_terminal_three_step_success"]}</td></tr>'
        )
    cards = []
    for row in plan["events"]:
        selected = next(e for e in review["events"] if e["event_id"] == row["event_id"])
        table = []
        for p in [p for p in pairs if p["event_id"] == row["event_id"]]:
            h, r, u = p["H"], p["R"], p["uncorrected"]
            table.append(
                f'<tr><td>{p["model"]} / {p["condition"]}</td><td>{p["window"]}</td><td>{u["correct_visible_steps"]}/{u["visible_steps"]}</td><td>{h["correct_visible_steps"]}/{h["visible_steps"]}</td><td>{r["correct_visible_steps"]}/{r["visible_steps"]}</td><td>{p["R_minus_H_mean_mask_iou"]:+.4f}</td><td>{format_offset(h["recovery_confirmed_offset"])} / {format_offset(r["recovery_confirmed_offset"])}</td><td>{h["terminal_three_step_success"]} / {r["terminal_three_step_success"]}</td></tr>'
            )
        media = []
        for condition in plan["conditions"]:
            base = Path(row["folder"]) / "visuals" / f"{row['name']}-{condition}"
            media.append(
                f'<details><summary>{condition}：四组视频与曲线</summary><video controls preload="none" src="{rel(str(base)+"-four-groups.mp4")}"></video><img loading="lazy" src="{rel(str(base)+"-curves.png")}" alt="Fixed ID mask IoU curves"></details>'
            )
            media.append(
                f'<details><summary>{condition}：+8步目标局部放大（六格使用同一裁剪）</summary><img loading="lazy" src="{row["event_id"]}-{condition}-zoom-plus8.png" alt="Same-crop target zoom at fixed plus8 step"></details>'
            )
        details = []
        for p in [
            p for p in pairs if p["event_id"] == row["event_id"] and p["window"] == 30
        ]:
            h, r = p["H_diagnostics"], p["R_diagnostics"]
            manipulation = (
                f'KF数值不同的步骤={len(p["KF_state_changed_offsets"])}（含纠正步）；输出不同的后续步骤={len(p["designated_output_changed_steps"])}'
                if p["model"] == "A"
                else f'SAM后续目标框序列相同={p["actual_target_future_prompts_identical"]}；全部目标提示API输入序列相同={p["all_objects_future_prompt_API_calls_identical"]}；输出不同的后续步骤={len(p["designated_output_changed_steps"])}'
            )
            details.append(
                f'<li>{p["model"]}/{p["condition"]}：原基线 t0 正确={p["baseline_correct_at_t0"]}；H/R 首次旧状态删除偏移={format_offset(h["first_state_deletion_offset"])} / {format_offset(r["first_state_deletion_offset"])}；{manipulation}。</li>'
            )
        cards.append(
            f'<section id="{row["event_id"]}"><h2>{row["event_id"]} · {row["video_id"]} · {escape(selected["title_zh"])}</h2><p>GT{selected["gt_id"]}，纠正步骤 {selected["frame"]}，随后 GT 可见 {selected["visible_followup"]}/30 步。{escape(selected["caveat_zh"])}</p><div class="scroll"><table><tr><th>模型/框</th><th>窗口</th><th>H 正确/可见</th><th>R 正确/可见</th><th>R−H 平均IoU</th><th>首次3步确认偏移 H/R</th><th>窗口末3步合格 H/R</th></tr>{"".join(table)}</table></div><ul>{"".join(details)}</ul>{"".join(media)}</section>'
        )
    html = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>16 段 H/R 预实验结果</title><style>body{{max-width:1200px;margin:36px auto;padding:0 20px;background:#111a20;color:#eaf1f4;font:16px/1.7 system-ui}}a{{color:#a6dfcf}}section{{padding-top:18px;margin-top:35px;border-top:1px solid #40505c}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:8px;border-bottom:1px solid #40505c;text-align:left}}.scroll{{overflow:auto}}video,img{{width:100%;height:auto}}details{{margin:18px 0}}strong{{color:#ffd38d}}</style><h1>16 段独立视频 · 保留／重置历史对照</h1><p>128 分支：16 个主事件 × YOLO/参考两种框 × A-H/A-R/B-H/B-R。本地 RTX 3080，固定模型权重，常规提示刷新，无 skip-one。2967 边界案例未运行。</p><p>H=保留，R=重置；A=ByteTrack，B=SAM 2.1。只在同模型、同事件、同纠正框内解释 H/R 差异。A/B 的状态类型、重置操作、后续观测门控不同，不能合成“哪种记忆更好”的排名。</p><p>纠正帧不计分；窗口为之后8/20/30个导出步骤，不是秒。固定前缀ID，mask IoU≥0.5 连续3个可见步骤确认。<strong>“曾连续3步合格”不等于窗口结束仍正确；原本正确的控制例也不能称为错误恢复。</strong>GT不可见打断连续成功，单独统计输出，不计作可见帧失败。</p><p>所有分支从相同前缀快照分叉，并逐帧复核原基线；每分支仅纠正一次。共享的是后续检测缓存，SAM 后续实际接受的提示可能因状态相关匹配而不同，已逐框记录；这属于闭环机制，不能冒称完全固定后续提示的纯记忆消融。</p><h2>配对概览</h2><p>正确步骤多的一侧计一次胜例；分母是16段视频，不是128个独立样本。“持平”只指阈值正确步骤数相等，mask形状可能仍不同。人工机制选样、每层4段，不外推总体胜率。</p><div class="scroll"><table><tr><th>模型</th><th>纠正框</th><th>窗口</th><th>R更多正确</th><th>H更多正确</th><th>阈值数持平</th><th>平均 R−H IoU</th><th>末3步成功 H/R</th></tr>{"".join(rows)}</table></div><p>{" · ".join(f'<a href="#{r["event_id"]}">{r["event_id"]}</a>' for r in plan["events"])}</p>{"".join(cards)}<section><h2>数据与代码</h2><p>这是开发集机制预实验，覆盖 person、car、dog；没有 cat/horse 主事件。没有微调、iLab连接或对外上传；旧结果保留，学习网站未改。</p><p><a href="results.json">完整结果与逐帧诊断 JSON</a> · <a href="paired-8-20-30.csv">8/20/30配对表</a> · <a href="verification.json">验证记录</a></p></section></html>"""
    html = html.replace(
        "<th>H 正确/可见</th>", "<th>未纠正 正确/可见</th><th>H 正确/可见</th>"
    )
    scene_names = {
        "stable": "稳定",
        "motion": "运动变化",
        "competition": "检测竞争",
        "occlusion": "遮挡",
    }
    strata_rows = "".join(
        f'<tr><td>{scene_names[r["scene"]]}</td><td>{r["model"]}/{r["condition"]}</td><td>{r["independent_event_units"]}</td><td>{r["R_more_correct_steps"]}/{r["H_more_correct_steps"]}/{r["threshold_count_ties"]}</td><td>{r["mean_R_minus_H_mask_iou"]:+.4f}</td></tr>'
        for r in aggregate_strata(pairs)
        if r["window"] == 30
    )
    html = html.replace(
        '<section id="E01">',
        f'<details><summary>按四类场景分层查看30步结果（每层仅4段）</summary><div class="scroll"><table><tr><th>场景</th><th>模型/框</th><th>视频数</th><th>R优/H优/阈值持平</th><th>平均R−H IoU</th></tr>{strata_rows}</table></div></details><section id="E01">',
    )
    retention = read_json(Path(plan["events"][0]["folder"]) / "summary.json")[
        "baseline_configuration"
    ]["sam_retention_steps"]
    html = html.replace(
        "<h2>配对概览</h2>",
        f"<p>本批 SAM 外围目标管理策略：距上次被接受检测超过 {retention} 个导出步骤时删除目标。这不是 SAM 神经网络的记忆长度；删除后的无输出与仍活跃时的差 mask 分开统计。</p><h2>配对概览</h2>",
    )
    (output / "RESULTS_ZH.html").write_text(html, encoding="utf-8")


def build(cohort, output, repeat=None):
    cohort, output = Path(cohort), Path(output)
    if output.exists():
        raise FileExistsError("Use a new cohort analysis directory")
    plan = read_json(cohort / "cohort.json")
    if plan["status"] != "completed" or plan["actual_branches"] != 128:
        raise ValueError("Require 128 verified and rendered branches")
    output.mkdir(parents=True)
    review = read_json(cohort / "reviewed-events.json")
    assert digest(cohort / "reviewed-events.json") == plan["review_sha256"]
    all_pairs, checks = [], []
    for row in plan["events"]:
        selected = next(e for e in review["events"] if e["event_id"] == row["event_id"])
        pairs, verified = per_event(row, plan, selected, output)
        all_pairs += pairs
        checks.append({"event_id": row["event_id"], **verified})
        print("Analyze", row["event_id"], "12 paired window comparisons", flush=True)
    assert len(all_pairs) == 192 and all(p["video_id"] != 2967 for p in all_pairs)
    aggregates = aggregate(all_pairs)
    repeated = (
        read_json(Path(repeat) / "verification.json") if repeat is not None else None
    )
    if repeated is not None:
        assert repeated["status"] == "passed"
        assert {e["event_id"] for e in repeated["events"]} == {"E09", "E13"}
        assert sum(e["branches"] for e in repeated["events"]) == 16
    write_json(
        output / "results.json",
        {
            "status": "completed",
            "cohort": str(cohort.resolve()),
            "cohort_sha256": digest(cohort / "cohort.json"),
            "review_sha256": plan["review_sha256"],
            "primary_events": 16,
            "branches": 128,
            "boundary_case_2967_run": False,
            "pair_results": all_pairs,
            "aggregates": aggregates,
            "stratified_aggregates": aggregate_strata(all_pairs),
            "source_sha256": digest(Path(__file__)),
            "numerical_repeat_verification": repeated,
        },
    )
    write_csv(
        output / "paired-8-20-30.csv",
        [
            {
                **{
                    k: p[k]
                    for k in (
                        "event_id",
                        "video_id",
                        "scene",
                        "condition",
                        "model",
                        "window",
                        "baseline_correct_at_t0",
                        "R_minus_H_correct_steps",
                        "R_minus_H_mean_mask_iou",
                    )
                },
                **{
                    label + "_" + k: v
                    for label in ("uncorrected", "H", "R")
                    for k, v in p[label].items()
                },
            }
            for p in all_pairs
        ],
    )
    write_csv(output / "aggregates.csv", aggregates)
    write_json(
        output / "verification.json",
        {
            "status": "passed",
            "events": checks,
            "primary_events": 16,
            "branches": 128,
            "paired_windows": 192,
            "fixed_source_corrections_and_prefix_hashes": True,
            "recorded_native_SAM_prompt_boxes_equal_cache": True,
            "independent_rescoring": True,
            "numerical_repeat_verification": repeated,
        },
    )
    write_html(output, cohort, plan, review, all_pairs, aggregates)
    if repeated is not None:
        write_json(output / "repeat-verification.json", repeated)
        path = output / "RESULTS_ZH.html"
        html = path.read_text(encoding="utf-8").replace(
            "<h2>配对概览</h2>",
            '<p>E09与E13以原配置独立复跑：16个验证分支的ID、分数、框、mask、评分曲线及状态／提示／关联记录逐项完全相同。复跑不作为新独立样本，不计入128个主分支的统计。<a href="repeat-verification.json">数值复现记录</a></p><h2>配对概览</h2>',
        )
        path.write_text(html, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "completed",
                "events": 16,
                "branches": 128,
                "analysis": str(output.resolve()),
            }
        ),
        flush=True,
    )


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cohort", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--repeat", type=Path)
    a = p.parse_args(argv)
    build(a.cohort, a.output, a.repeat)


if __name__ == "__main__":
    main()
