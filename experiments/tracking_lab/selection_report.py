"""Offline, human-reviewable event list: source RGB/GT, NOT H/R outcomes.

Event specifications are hand-reviewed scene choices. This builder attaches
read-only baseline eligibility and refuses to authorize intervention execution.
It does not serve/publish a website and does not overwrite previous reports.
"""

import argparse
from collections import Counter
from html import escape
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .common import digest, load_predictions, mask_iou, write_json
from .dataset import load_ground_truth, read_manifest


SCENES = {
    "stable": "稳定对照",
    "motion": "运动突变",
    "competition": "检测竞争",
    "occlusion": "遮挡",
}


def detection_panel(data_root, video_id, gt_id, frame, baseline_folder, output):
    """Actual t0 GT boxes beside cached detector boxes, without an intervention."""
    videos, records, _ = read_manifest(data_root, [video_id])
    video = videos[0]
    truths = load_ground_truth(data_root, records[0])[frame]
    predictions = load_predictions(Path(baseline_folder) / str(video_id) / "YOLO")[
        frame
    ]
    canvas = Image.new("RGB", (960, 390), (18, 25, 31))
    for col, (objects, label) in enumerate(
        ((truths, "GT | designated target green"), (predictions, "YOLO cache | orange"))
    ):
        image = Image.open(video.rgb_paths[frame]).convert("RGB")
        draw = ImageDraw.Draw(image)
        for obj in objects:
            color = (
                (60, 240, 140)
                if col == 0 and obj.identity == gt_id
                else ((120, 185, 240) if col == 0 else (255, 175, 70))
            )
            draw.rectangle(tuple(map(int, obj.box)), outline=color, width=2)
            draw.text(
                (int(obj.box[0]), max(0, int(obj.box[1]) - 12)),
                f"{obj.category} {obj.identity}" + (f" {obj.score:.2f}" if col else ""),
                fill=color,
            )
        image.thumbnail((480, 350))
        canvas.paste(image, (col * 480, 35))
        ImageDraw.Draw(canvas).text(
            (col * 480 + 6, 8),
            label,
            fill="white",
            font=ImageFont.load_default(size=17),
        )
    canvas.save(output, quality=94)


def baseline_followup(data_root, row, baseline_folder):
    """Describe original automatic predictions; do NOT simulate an intervention."""
    video_id, t = row["video_id"], row["frame"]
    _, records, _ = read_manifest(data_root, [video_id])
    gt = load_ground_truth(data_root, records[0])
    result = {}
    for method in ("A0", "B0"):
        predicted = load_predictions(Path(baseline_folder) / str(video_id) / method)
        anchor = row["anchors"][method]
        values = []
        absent = []
        for step in range(t + 1, t + 31):
            truth = next((o for o in gt[step] if o.identity == row["gt_id"]), None)
            output = next(
                (
                    o
                    for o in predicted[step]
                    if anchor and o.identity == anchor["prediction_id"]
                ),
                None,
            )
            if truth:
                values.append(
                    {
                        "frame": step,
                        "mask_iou": (
                            mask_iou(truth.mask, output.mask) if output else 0.0
                        ),
                    }
                )
            else:
                absent.append(step)
        result[method] = {
            "GT_visible_steps": len(values),
            "GT_absent_steps": absent,
            "qualified_fixed_id_steps": sum(v["mask_iou"] >= 0.5 for v in values),
            "values": values,
        }
    return result


def event_strip(data_root, video_id, gt_id, frame, output, steps=None):
    videos, records, _ = read_manifest(data_root, [video_id])
    video, record = videos[0], records[0]
    gt = load_ground_truth(data_root, record)
    steps = steps or [
        frame - 3,
        frame - 2,
        frame - 1,
        frame,
        frame + 1,
        frame + 3,
        frame + 10,
        frame + 20,
        frame + 30,
    ]
    steps = list(dict.fromkeys(max(0, min(len(gt) - 1, t)) for t in steps))
    tile_w, tile_h = 480, 330
    canvas = Image.new(
        "RGB", (tile_w * 3, tile_h * ((len(steps) + 2) // 3)), (18, 25, 31)
    )
    font = ImageFont.load_default(size=17)
    for i, t in enumerate(steps):
        image = Image.open(video.rgb_paths[t]).convert("RGBA")
        target = next((o for o in gt[t] if o.identity == gt_id), None)
        if target:
            overlay = np.zeros((video.height, video.width, 4), np.uint8)
            overlay[target.mask] = [50, 240, 140, 75]
            image = Image.alpha_composite(image, Image.fromarray(overlay))
            draw = ImageDraw.Draw(image)
            draw.rectangle(tuple(map(int, target.box)), outline=(50, 240, 140), width=2)
        image = image.convert("RGB")
        image.thumbnail((tile_w, tile_h - 35))
        x, y = (i % 3) * tile_w, (i // 3) * tile_h
        canvas.paste(image, (x, y + 33))
        label = (
            f"{video_id} GT{gt_id} | step {t}"
            + (" [t0]" if t == frame else "")
            + (" | GT absent" if not target else "")
        )
        ImageDraw.Draw(canvas).text(
            (x + 6, y + 7),
            label,
            fill=(255, 210, 90) if t == frame else "white",
            font=font,
        )
    canvas.save(output, quality=94)
    return steps


def retain_boundaries(spec, spec_path, events, data_root, output):
    """Keep pinned old cases separate from main counts, without interventions."""
    boundaries, cards = [], []
    for entry in spec.get("boundary_cases", []):
        source = Path(spec_path).parent / entry["source_review"]
        if digest(source) != entry["source_review_sha256"]:
            raise ValueError("Boundary source review changed")
        previous = json.loads(source.read_text(encoding="utf-8"))
        original = next(
            e for e in previous["events"] if e["event_id"] == entry["source_event_id"]
        )
        if any(e["video_id"] == original["video_id"] for e in events):
            raise ValueError("Boundary video cannot also be a primary event")
        case_id = entry["case_id"]
        if not case_id.isalnum() or any(
            e["event_id"] == case_id for e in events + boundaries
        ):
            raise ValueError("Invalid or duplicate boundary ID")
        image_name = f"{case_id}-boundary-{original['video_id']}-GT{original['gt_id']}-t{original['frame']}.jpg"
        detector_image = image_name.replace(".jpg", "-detector.jpg")
        event_strip(
            data_root,
            original["video_id"],
            original["gt_id"],
            original["frame"],
            output / image_name,
        )
        detection_panel(
            data_root,
            original["video_id"],
            original["gt_id"],
            original["frame"],
            original["baseline_folder"],
            output / detector_image,
        )
        row = {
            **original,
            "event_id": case_id,
            "previous_event_id": original["event_id"],
            "review_status": "retained_boundary_only_excluded_from_primary_counts",
            "retention_reason_zh": entry["reason_zh"],
            "source_review": str(source.resolve()),
            "source_review_sha256": digest(source),
            "evidence_image": str((output / image_name).resolve()),
            "detector_image": str((output / detector_image).resolve()),
            "included_in_primary_counts": False,
            "included_in_complete_long_window_stats": False,
            "execution_authorized": False,
            "approved": False,
            "H_R_run": False,
        }
        boundaries.append(row)
        cards.append(
            f'<section id="{case_id}"><h2>{case_id} · 边界案例 · {original["video_id"]} / GT{original["gt_id"]} / t={original["frame"]}</h2><p><strong>不计入主清单16段，也不计入完整长窗的延迟恢复统计。</strong></p><p>{escape(entry["reason_zh"])}</p><a href="{image_name}"><img loading="lazy" src="{image_name}" alt="Boundary case RGB and GT"></a><details><summary>原始自动基线的 YOLO 框</summary><img loading="lazy" src="{detector_image}" alt="Boundary GT and YOLO"></details><p><a href="#list">返回主清单</a></p></section>'
        )
    return boundaries, "".join(cards)


def build(
    spec_path, split_path, queue_path, preflight, data_root, output, manifest_path
):
    output, manifest_path = Path(output), Path(manifest_path)
    if output.exists() or manifest_path.exists():
        raise FileExistsError(
            "Review packages and event manifests must be versioned, never replaced"
        )
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    split = json.loads(Path(split_path).read_text(encoding="utf-8"))
    queue = json.loads(Path(queue_path).read_text(encoding="utf-8"))
    if queue["split_sha256"] != digest(split_path):
        raise ValueError("Split/queue mismatch")
    dev = {r["video_id"]: r for r in split["splits"]["development"]}
    if Counter(s["scene"] for s in spec["events"]) != {s: 4 for s in SCENES}:
        raise ValueError("Review requires four scene-selected events in each stratum")
    if len({s["video_id"] for s in spec["events"]}) != 16:
        raise ValueError("One primary event per new video")
    if len({dev[s["video_id"]]["group_id"] for s in spec["events"]}) != 16:
        raise ValueError("One primary event per automatically screened visual group")
    quarantined = {v for row in spec["quarantines"] for v in row["excluded_video_ids"]}
    if any(
        s["video_id"] in quarantined or s["video_id"] not in queue["video_ids"]
        for s in spec["events"]
    ):
        raise ValueError("Selected event not in eligible frozen queue")
    output.mkdir(parents=True)
    events, cards, table = [], [], []
    for index, selected in enumerate(spec["events"], 1):
        video_id, t = selected["video_id"], selected["frame"]
        source_path = Path(preflight) / f"{video_id}.json"
        source = json.loads(source_path.read_text(encoding="utf-8"))
        if source["queue_sha256"] != digest(queue_path):
            raise ValueError("Preflight/queue mismatch")
        row = next(
            r
            for r in source["events"]
            if r["gt_id"] == selected["gt_id"] and r["frame"] == t
        )
        if not (10 <= t and t + 30 < row["frames"]):
            raise ValueError("Insufficient prefix or 30-step follow-up")
        image_name = (
            f"{index:02d}-{selected['scene']}-{video_id}-GT{row['gt_id']}-t{t}.jpg"
        )
        steps = event_strip(data_root, video_id, row["gt_id"], t, output / image_name)
        detector_image = image_name.replace(".jpg", "-detector.jpg")
        detection_panel(
            data_root,
            video_id,
            row["gt_id"],
            t,
            source["baseline_folder"],
            output / detector_image,
        )
        automatic = baseline_followup(data_root, row, source["baseline_folder"])
        visible_frames = {v["frame"] for v in automatic["A0"]["values"]}
        if (
            selected.get("require_complete_GT_visible_followup")
            and len(visible_frames) != 30
        ):
            raise ValueError(
                "Replacement event requires all 30 future GT steps visible"
            )
        readouts = {
            str(h): {
                "frame": t + h,
                "GT_visible_at_endpoint": t + h in visible_frames,
                "GT_visible_in_last_3_steps": all(
                    s in visible_frames for s in range(t + h - 2, t + h + 1)
                ),
            }
            for h in (8, 20, 30)
        }
        if selected["scene"] == "stable" and any(
            v["GT_visible_steps"] != 30 or v["qualified_fixed_id_steps"] != 30
            for v in automatic.values()
        ):
            raise ValueError(
                "Stable controls must retain qualified automatic identities for all 30 visible follow-up steps"
            )
        full = (
            row["eligible_common_state"]
            and row["strong_prefix_both_ge3"]
            and row["yolo_correction"] is not None
        )
        status = (
            "both_prompt_conditions_ready" if full else "restricted_review_candidate"
        )
        event = {
            **row,
            **selected,
            "event_id": f"E{index:02d}",
            "group_id": dev[video_id]["group_id"],
            "review_status": status,
            "followup": 30,
            "evidence_steps": steps,
            "evidence_image": str((output / image_name).resolve()),
            "detector_image": str((output / detector_image).resolve()),
            "automatic_baseline_followup_NOT_HR": automatic,
            "observability_at_planned_readouts": readouts,
            "complete_GT_visible_followup": len(visible_frames) == 30,
            "readout_endpoint_limited": not all(
                v["GT_visible_at_endpoint"] for v in readouts.values()
            ),
            "preflight_sha256": digest(source_path),
            "baseline_folder": source["baseline_folder"],
            "approved": False,
            "H_R_run": False,
        }
        events.append(event)
        state = "四组 × 两种提示可准备" if full else "有限制，须审阅"
        if not all(v["GT_visible_at_endpoint"] for v in readouts.values()):
            state += "；长窗观察受限"
        ab = " / ".join(
            f"{k}: {v:.2f}"
            for k, v in row["baseline_fixed_id_mask_iou_at_correction"].items()
        )
        prefix = " / ".join(
            f"{k}: {v['qualified_frames']} 帧" for k, v in row["prefix_quality"].items()
        )
        reasons = "; ".join(row["eligibility_reasons"]) or "无旧状态资格问题"
        if not row["strong_prefix_both_ge3"]:
            reasons += "; 至少一套方法前缀不足 3 个 IoU≥0.5 的同 ID 帧"
        if row["yolo_correction"] is None:
            reasons += "; 无合格 YOLO 纠正框，仅参考框候选"
        title = f"E{index:02d} · {SCENES[selected['scene']]} · {video_id} / GT{row['gt_id']} / t={t}"
        table.append(
            f'<tr><td><a href="#E{index:02d}">E{index:02d}</a></td><td>{SCENES[selected["scene"]]}</td><td>{video_id}</td><td>{row["category"]} GT{row["gt_id"]}</td><td>{t} → {t+30}</td><td>{escape(selected["title_zh"])}</td><td>{state}</td></tr>'
        )
        cards.append(
            f'<section id="E{index:02d}"><h2>{escape(title)}</h2><h3>{escape(selected["title_zh"])}</h3><p>{escape(selected["rationale_zh"])}</p><p><strong>限制与混杂：</strong>{escape(selected["caveat_zh"])}</p><p>前缀合格帧：{prefix}；纠正当帧自动基线的固定 ID mask IoU：{ab}。这些不是 H/R 恢复结果。</p><p>{state}。{escape(reasons)}</p><a href="{image_name}"><img loading="lazy" src="{image_name}" alt="RGB and target GT evidence"></a><p>绿色半透明区域是指定目标的可见 GT；方框是其可见 mask 的外接框，不是完整被遮挡身体。t0 是计划纠正步骤；所有编号从 0 开始。</p><p><a href="#list">返回事件表</a></p></section>'
        )
        cards.append(
            f'<p>自动基线后续 30 步（非 H/R）：A0 {automatic["A0"]["qualified_fixed_id_steps"]}/{automatic["A0"]["GT_visible_steps"]}、B0 {automatic["B0"]["qualified_fixed_id_steps"]}/{automatic["B0"]["GT_visible_steps"]} 个 GT 可见步骤的固定 ID mask IoU≥0.5。</p><details><summary>查看纠正当帧：GT 与实际 YOLO 框</summary><img loading="lazy" src="{detector_image}" alt="GT vs cached YOLO detections"></details>'
        )
        if automatic["A0"]["GT_absent_steps"]:
            cards.append(
                f'<p><strong>观察限制：</strong>后续 GT 缺失步骤：{automatic["A0"]["GT_absent_steps"]}。8/20/30 步终点 GT 是否可见：{[readouts[str(h)]["GT_visible_at_endpoint"] for h in (8,20,30)]}。GT 不可见不能算恢复失败，也不能证明已恢复；可见期指标、不可见期误报和生命周期记录分开处理。</p>'
            )
    boundaries, boundary_html = retain_boundaries(
        spec, spec_path, events, data_root, output
    )
    result = {
        "schema": 1,
        "status": "awaiting_human_review_NOT_executable_HR_config",
        "approved": False,
        "H_R_run": False,
        "device_scope": "local_RTX_3080_only",
        "events": events,
        "boundary_cases": boundaries,
        "primary_event_count": len(events),
        "boundary_case_count": len(boundaries),
        "split_sha256": digest(split_path),
        "queue_sha256": digest(queue_path),
        "spec_sha256": digest(spec_path),
        "quarantines": spec["quarantines"],
        "nonselected_cases": spec["nonselected_cases"],
        "selection_policy": spec["selection_policy"],
        "report_file": str((output / "REVIEW_ZH.html").resolve()),
        "category_counts": dict(Counter(e["category"] for e in events)),
        "scene_counts": dict(Counter(e["scene"] for e in events)),
        "readiness_counts": dict(Counter(e["review_status"] for e in events)),
        "source_sha256": digest(Path(__file__)),
        "endpoint_limited_event_ids": [
            e["event_id"] for e in events if e["readout_endpoint_limited"]
        ],
        "full_GT_visible_window_count": sum(
            e["complete_GT_visible_followup"] for e in events
        ),
    }
    write_json(manifest_path, result)
    write_json(output / "events-review.json", result)
    intro = "".join(f"<li>{escape(p)}</li>" for p in spec["selection_policy"])
    audit = (
        "<section><h2>候选排除与数据质量记录</h2><ul>"
        + "".join(
            f'<li>{r["video_id"]}：{escape(r["reason_zh"])}</li>'
            for r in spec["nonselected_cases"]
        )
        + "</ul><h3>同源场景隔离</h3><ul>"
        + "".join(
            f'<li>{r["related_video_ids"]}：{escape(r["reason_zh"])}</li>'
            for r in spec["quarantines"]
        )
        + "</ul></section>"
    )
    html = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>16 个候选事件 · 审阅稿</title><style>body{{max-width:1200px;margin:36px auto;padding:0 20px;background:#10171c;color:#e8f0f4;font:16px/1.7 system-ui}}h1,h2{{line-height:1.3}}a{{color:#9fe2cd}}section{{margin:40px 0;padding-top:20px;border-top:1px solid #3e505b}}img{{width:100%;height:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:9px;border-bottom:1px solid #3e505b;text-align:left}}.scroll{{overflow:auto}}strong{{color:#ffd58c}}</style><h1>独立视频事件清单 · 待人工审阅</h1><p>120 开发 / 40 验证 / 40 评估划分已冻结。以下 16 个事件全部来自开发候选，每类 4 个、每段视频 1 个。这里只做了 RGB/GT 检查和自动 A0/B0 基线，没有运行保留/重置历史实验。</p><ul>{intro}</ul><h2 id="list">事件表</h2><p>两种提示指同一 YOLO 纠正框与同一 GT 参考框；“可准备”只表示基线资格满足，不表示结果会有差异，也不表示已获准运行。</p><div class="scroll"><table><thead><tr><th>事件</th><th>场景层</th><th>视频</th><th>目标</th><th>t0 → 窗口末步</th><th>视觉依据</th><th>资格</th></tr></thead><tbody>{''.join(table)}</tbody></table></div>{''.join(cards)}<section><h2>下一步边界</h2><p>先由你审阅这份清单。未经新的运行指令，不启动 H/R、不训练、不使用学校服务器、不更新网站或 Git。旧实验结果保留。</p></section></html>"""
    html = html.replace(
        "<section><h2>下一步边界", boundary_html + audit + "<section><h2>下一步边界"
    )
    (output / "REVIEW_ZH.html").write_text(html, encoding="utf-8")
    print(
        json.dumps(
            {
                "manifest": str(manifest_path),
                "scene_counts": result["scene_counts"],
                "readiness": result["readiness_counts"],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strip", nargs=3, type=int, metavar=("VIDEO", "GT_ID", "STEP")
    )
    for name in (
        "spec",
        "split",
        "queue",
        "preflight",
        "data-root",
        "output",
        "manifest",
    ):
        parser.add_argument("--" + name, type=Path)
    args = parser.parse_args(argv)
    if args.strip:
        if args.output.exists():
            raise FileExistsError(args.output)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        event_strip(args.data_root, *args.strip, args.output)
    else:
        build(
            args.spec,
            args.split,
            args.queue,
            args.preflight,
            args.data_root,
            args.output,
            args.manifest,
        )


if __name__ == "__main__":
    main()
