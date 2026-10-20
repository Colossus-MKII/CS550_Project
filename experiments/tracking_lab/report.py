"""Build a local Chinese review page, curves and error videos from SAVED outputs.

Usage: python -m tracking_lab.report --output runs/<run> --data-root data/stage1
This command can be rerun after layout edits WITHOUT rerunning either model.
"""

import argparse
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import shutil

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from . import PACKAGE_ROOT
from .runtime import resolve_data_root
from .common import digest, load_predictions, write_json
from .dataset import load_ground_truth, read_manifest
from .render import VideoWriter, comparison


def score_table(metrics):
    headers = "<tr><th>方法 / 类别</th><th>HOTA</th><th>DetA</th><th>AssA</th><th>IDF1</th><th>FP</th><th>FN</th><th>IDSW</th></tr>"
    rows = []
    for method, scores in metrics.items():
        for category, value in [
            ("五类等权", scores["macro"]),
            *((key, row["scores"]) for key, row in scores["per_class"].items()),
        ]:
            row = f"<tr><th>{method} · {escape(category)}</th>"
            row += "".join(
                f"<td>{100*value[k]:.1f}</td>" for k in ("HOTA", "DetA", "AssA", "IDF1")
            )
            row += (
                "".join(f"<td>{value[k]}</td>" for k in ("FP", "FN", "IDSW")) + "</tr>"
            )
            rows.append(row)
    return (
        '<div class="table-wrap"><table><thead>'
        + headers
        + "</thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def build(output, data_root=None):
    output = Path(output).resolve()
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    if summary["status"] not in ("inference_and_scoring_completed", "completed"):
        raise RuntimeError("Inference/scoring is incomplete")
    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    samples = resolve_data_root(output, summary, data_root)
    ids = summary["selection"]["video_ids"]
    videos, records, _ = read_manifest(samples, ids)
    code = output / "code"
    code.mkdir(exist_ok=True)
    # Preserve exact sources used by inference, even if the working code changes.
    # Never overwrite an existing snapshot with a post-run revision.
    for name, expected in summary["source_files"].items():
        target = code / (name + ".txt")
        if target.exists():
            if digest(target) != expected:
                raise RuntimeError("Inference source snapshot changed")
        else:
            source = PACKAGE_ROOT / name
            if digest(source) != expected:
                raise RuntimeError(f"Source changed before snapshot: {name}")
            shutil.copyfile(source, target)
    payload = {"videos": []}
    curves = []
    video_sections = []
    frame_total = 0
    for video, record in zip(videos, records):
        folder = output / str(video.video_id)
        visuals = folder / "visuals"
        visuals.mkdir(exist_ok=True)
        gt = load_ground_truth(samples, record)
        a = load_predictions(folder / "A0")
        b = load_predictions(folder / "B0")
        da = json.loads((folder / "A0/diagnostics.json").read_text(encoding="utf-8"))
        db = json.loads((folder / "B0/diagnostics.json").read_text(encoding="utf-8"))
        if not len(gt) == len(a) == len(b):
            raise ValueError("Cannot visualize unequal sequence lengths")
        writer = VideoWriter(
            folder / "comparison.mp4",
            (video.width * 2, (video.height + 32) * 3),
            summary["configuration"]["browse_fps"],
        )
        try:
            for t, path in enumerate(video.rgb_paths):
                rgb = cv2.imread(str(path))
                view = comparison(
                    rgb, gt[t], a[t], b[t], t, da["frames"][t], db["frames"][t]
                )
                if not cv2.imwrite(
                    str(visuals / f"{t:05d}.jpg"), view, [cv2.IMWRITE_JPEG_QUALITY, 92]
                ):
                    raise OSError("Could not write error image")
                writer.write(view)
        finally:
            writer.close()
        frame_total += len(gt)
        figure, axis = plt.subplots(figsize=(10, 2.7), layout="constrained")
        for method, d, color in [("A0", da, "#246daa"), ("B0", db, "#b05f21")]:
            axis.plot(
                range(len(gt)),
                [
                    (
                        r["mean_best_mask_iou"]
                        if r["mean_best_mask_iou"] is not None
                        else np.nan
                    )
                    for r in d["frames"]
                ],
                label=method,
                color=color,
                lw=1.7,
            )
        axis.set(
            xlabel="Exported frame index (not original-video time)",
            ylabel="Mean best mask IoU",
            ylim=(-0.03, 1.03),
            title=f"Video {video.video_id} | localization only, identity ignored",
        )
        axis.grid(alpha=0.2)
        axis.legend(loc="lower left", ncols=2)
        figure.savefig(folder / "iou-curve.png", dpi=140)
        plt.close(figure)
        candidates = sorted(
            range(len(gt)),
            key=lambda t: (
                da["frames"][t]["FN"]
                + db["frames"][t]["FN"]
                + da["frames"][t]["FP"]
                + db["frames"][t]["FP"]
                + 3
                * (
                    da["frames"][t]["diagnostic_id_changes"]
                    + db["frames"][t]["diagnostic_id_changes"]
                )
            ),
            reverse=True,
        )[:3]
        payload["videos"].append(
            {
                "id": video.video_id,
                "frames": len(gt),
                "focus": record["focus"],
                "A0": da["frames"],
                "B0": db["frames"],
                "worst_frames": candidates,
                "events": json.loads(
                    (folder / "B0/event-log.json").read_text(encoding="utf-8")
                ),
            }
        )
        links = " · ".join(
            f'<button data-jump-video="{video.video_id}" data-jump-frame="{t}">帧 {t}</button>'
            for t in candidates
        )
        video_sections.append(
            f'<section id="video-{video.video_id}"><h3>视频 {video.video_id} · {escape(record["focus"])}</h3><p>{len(gt)} 帧 · {links}</p><img src="{video.video_id}/iou-curve.png" alt="两套基线的逐帧定位 IoU 曲线" loading="lazy"><details><summary>播放六格对比视频（浏览 5 fps）</summary><video controls preload="none" src="{video.video_id}/comparison.mp4" poster="{video.video_id}/visuals/00000.jpg"></video></details></section>'
        )
    source_links = " · ".join(
        f'<a href="code/{escape(name)}.txt">{escape(name)}</a>'
        for name in summary["source_files"]
    )
    data = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    template = (PACKAGE_ROOT / "report.html").read_text(encoding="utf-8")
    values = {
        "SCORES": score_table(metrics),
        "RUN": escape(output.name),
        "VIDEOS": "".join(video_sections),
        "OPTIONS": "".join(
            f'<option value="{v["id"]}">{v["id"]} · {escape(v["focus"])}</option>'
            for v in payload["videos"]
        ),
        "FIRST": str(ids[0]),
        "SOURCES": source_links,
        "DATA": data,
        "JS": (PACKAGE_ROOT / "report.js").read_text(encoding="utf-8"),
        "YOLO_MEMORY": f'{summary["yolo_peak_allocated_mib"]:.0f}',
        "SAM_MEMORY": f'{summary["sam_peak_allocated_mib"]:.0f}',
    }
    for key, value in values.items():
        template = template.replace("@@" + key + "@@", value)
    (output / "index.html").write_text(template, encoding="utf-8")
    write_json(output / "viewer-data.json", payload)
    summary["status"] = "completed"
    summary["report_created_utc"] = datetime.now(timezone.utc).isoformat()
    summary["visualized_frames"] = frame_total
    summary["render_environment"] = {
        "matplotlib": matplotlib.__version__,
        "opencv": cv2.__version__,
    }
    summary["report_source_sha256"] = {
        name: digest(PACKAGE_ROOT / name)
        for name in ("report.py", "render.py", "report.html", "report.js")
    }
    write_json(output / "summary.json", summary)
    print("Report:", output / "index.html", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--data-root", type=Path, help="Override input location after moving a run"
    )
    args = parser.parse_args(argv)
    build(args.output, args.data_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
