"""Offline learning report; embedded local videos, no external JS or services."""
from html import escape
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import shutil

import cv2
import numpy as np

from .common import VideoWriter, label_frame
from .proposal import prepare_proposals
from .study import PAGES as STUDY_PAGES, write_study_pages
from .dataset_page import PAGES as DATASET_PAGES, write_dataset_pages, homepage_summary
from .pilot_page import PAGES as RESULT_PAGES, write_results_pages
from .program_page import PAGES as PROGRAM_PAGES, write_program_pages
from .recovery_page import PAGES as RECOVERY_PAGES, write_recovery_pages
from .recovery_long_data import PAGES as LONG_RECOVERY_PAGES
from .recovery_long_page import write_long_pages
from .recovery_cohort_page import write_cohort_pages
from .navigation import decorate_page
from .workbench import PAGES as WORKBENCH_PAGES, HANDBOOK_PAGES, write_workbench

LESSONS = [
    ("01_boxes", "01 · YOLO：在哪里、是什么？", "逐帧预测目标框、类别和置信度。这里隐藏了掩码；用的是同一个 YOLO11s-seg 模型，不是另一个检测模型。", "框包含背景。物体不动也可以被检测；YOLO 不是运动检测器。数字置信度不是分割准确率。"),
    ("02_masks", "02 · YOLO segmentation：哪些像素属于它？", "把同一次 YOLO 预测中的像素掩码显示出来。它可以在每一帧找目标，但这一课没有跨帧身份关联。", "观察边缘是否漏掉腿、尾巴或薄物体。相同类别的颜色相同，不代表是同一个实例。"),
    ("03_bytetrack", "03 · ByteTrack：是不是刚才那个？", "在 YOLO 检测之上关联相邻帧，给目标分配持续的 ID；掩码仍然由 YOLO 产生。ByteTrack 不是另一个分割大模型。", "观察遮挡和交叉后 ID 是否改变或串人。ID 不变也不保证身份正确；消失后再次出现可能成为新 ID。"),
    ("04_sam2", "04 · SAM 2.1：指定它，然后传播轮廓", "用第一帧的框指定目标；SAM 2.1 Hiera Tiny 利用视频记忆传播目标掩码。自动模式的框和类别来自 YOLO，手动模式只知道你选了一个目标。", "观察分割边界与遮挡后的漂移。此学习版只初始化第一帧：后来进入的对象不会被自动发现。它还不是 proposal 的完整自动系统。")
]


def make_comparison(output: Path, clip):
    keys = [key for key, *_ in LESSONS]
    captures = {key: cv2.VideoCapture(str(output / f"{key}.mp4"))
                for key in keys if (output / f"{key}.mp4").exists()}
    width, height = clip["size"]
    rendered_height = height + 48
    try:
        with VideoWriter(output / "comparison.mp4", (width * 2, rendered_height * 2), clip["fps"]) as writer:
            for index in range(clip["frames"]):
                panels = []
                for key in keys:
                    if key in captures:
                        ok, frame = captures[key].read()
                        if not ok:
                            raise RuntimeError(f"Incomplete lesson output: {key}, frame {index}")
                    else:
                        frame = label_frame(np.zeros((height, width, 3), np.uint8), f"{key}: not run (see report)", index)
                    panels.append(frame)
                merged = np.vstack([np.hstack(panels[:2]), np.hstack(panels[2:])])
                writer.write(merged)
                if index == clip["frames"] // 2:
                    cv2.imwrite(str(output / "comparison.jpg"), merged)
    finally:
        for capture in captures.values():
            capture.release()


WEB = Path(__file__).with_name("web")
SOURCES = ("yolo_lessons.py", "sam2_lesson.py", "common.py", "run.py")

EN = {
    "本次未生成此项结果，状态见运行记录。": "No output for this method in this run; see the run record.",
    "退一帧": "Previous frame", "进一帧": "Next frame", "速度": "Speed", "打开视频": "Open video",
    "复制代码": "Copy code", "查看完整代码快照 ↗": "View full source snapshot ↗",
    "运行状态": "Run status", "输入视频": "Input video", "本次帧数": "Frames in this run",
    "输入尺寸": "Input dimensions", "原视频尺寸": "Original dimensions",
    "播放帧率（不是推理 FPS）": "Playback frame rate (not inference FPS)",
    "设备": "Device", "依赖版本": "Dependency versions", "YOLO 阈值": "YOLO confidence threshold",
    "类别过滤": "Class filter", "YOLO PyTorch 峰值 allocated / MiB": "YOLO peak PyTorch allocated / MiB",
    "SAM PyTorch 峰值 allocated / MiB": "SAM peak PyTorch allocated / MiB",
    "原始运行时间": "Original run timestamp", "网页与代码快照更新时间": "Page and source snapshot updated",
    "错误（如有）": "Error (if any)", "未记录": "Not recorded", "未运行": "Not run", "无": "None",
    "同步四格：框 / mask / ByteTrack / SAM 2.1": "Synchronized comparison: boxes / masks / ByteTrack / SAM 2.1",
    "第一课 · YOLO 检测框": "Lesson 1 · YOLO bounding boxes",
    "第二课 · YOLO 像素掩码": "Lesson 2 · YOLO pixel masks",
    "第三课 · YOLO + ByteTrack": "Lesson 3 · YOLO + ByteTrack",
    "第四课 · SAM 2.1 提示传播": "Lesson 4 · SAM 2.1 prompt propagation",
    "本次第一帧提供给 SAM 的目标框": "First-frame bounding-box prompts given to SAM in this run",
    "本次初始化提示；类别标签来自提示来源。": "Initialization prompts from this run; class labels come from the prompt source. ",
    "查看坐标与来源": "View coordinates and sources", "本次没有可展示的 SAM 初始化提示。": "No SAM initialization prompts are available for this run.",
    "本次没有原始帧可供逐帧检查。": "No source frames are available for inspection in this run.",
}


def _text(value, language):
    return EN.get(value, value) if language == "en" and isinstance(value, str) else value


def _video(output, key, label, language="zh"):
    t = lambda value: _text(value, language)
    if not (output / f"{key}.mp4").is_file():
        return f'<p class="notice">{t("本次未生成此项结果，状态见运行记录。")}</p>'
    label = t(label)
    poster = f' poster="{key}.jpg"' if (output / f"{key}.jpg").is_file() else ""
    return (f'<figure class="video-block"><video id="video-{key}" controls preload="metadata" '
            f'playsinline{poster} src="{key}.mp4" aria-label="{escape(label)}"></video>'
            f'<figcaption>{escape(label)}</figcaption>'
            f'<div class="controls"><button data-step="-1" data-video="video-{key}">{t("退一帧")}</button>'
            f'<button data-step="1" data-video="video-{key}">{t("进一帧")}</button>'
            f'<label>{t("速度")} <select data-speed="video-{key}"><option value="0.25">0.25×</option>'
            '<option value="0.5">0.5×</option><option value="1" selected>1×</option></select></label>'
            f'<a href="{key}.mp4">{t("打开视频")}</a></div></figure>')


def _records(output, name, language="zh"):
    path = output / name
    if not path.is_file():
        return [], ""
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not all(isinstance(row, dict) and isinstance(row.get("frame"), int) for row in rows):
            raise ValueError("Each record needs an integer frame index")
        return rows, ""
    except (ValueError, OSError) as error:
        if language == "en":
            return [], f"Could not fully read {name}; its frame records are not displayed: {error}"
        return [], f"{name} 无法完整读取；未展示其逐帧记录：{error}"


def _code(name, start, end, language="zh"):
    t = lambda value: _text(value, language)
    lines = Path(__file__).with_name(name).read_text(encoding="utf-8").splitlines()
    code = escape("\n".join(lines[start - 1:end]))
    key = f"code-{Path(name).stem}-{start}"
    return (f'<div class="code-block"><div class="code-header"><span>{name} · L{start}–{end}</span>'
            f'<button class="copy-code" data-copy="{key}">{t("复制代码")}</button></div>'
            f'<pre><code id="{key}">{code}</code></pre>'
            f'<a class="code-source" href="code/{name}.txt">{t("查看完整代码快照 ↗")}</a></div>')


def _json_script(value):
    # A JSON script element still recognizes closing HTML tags, so escape '<'.
    return json.dumps(value, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c").replace("&", "\\u0026")


def write_report(output: Path, summary):
    """Regenerate presentation only: never run models or alter saved measurements."""
    proposals = prepare_proposals(output)
    for name in ("favicon.svg", "favicon-32.png", "favicon.ico"):
        shutil.copyfile(WEB / name, Path(output) / name)
    for language in ("zh", "en"):
        _write_report(output, summary, language, proposals[language])
    write_study_pages(output)
    write_dataset_pages(output)
    write_results_pages(output)
    write_recovery_pages(output)
    write_long_pages(output)
    write_cohort_pages(output)
    write_program_pages(output)
    write_workbench(output, proposals)


def _write_report(output: Path, summary, language, proposal):
    t = lambda value: _text(value, language)
    output = Path(output)
    clip = summary.get("clip", {})
    runtime = summary.get("environment", {})
    fps = clip.get("fps", 30)
    if not isinstance(fps, (float, int)) or not math.isfinite(fps) or fps <= 0:
        fps = 30
    frame_count = clip.get("frames", 0)
    frame_count = frame_count if isinstance(frame_count, int) and 0 <= frame_count <= 10000 else 0
    available_frames = [i for i in range(frame_count) if (output / "frames" / f"{i:05d}.jpg").is_file()]
    yolo, yolo_error = _records(output, "yolo_records.jsonl", language)
    sam, sam_error = _records(output, "sam2_records.jsonl", language)
    data = {"fps": fps, "frames": available_frames, "yolo": yolo, "sam": sam,
            "run": output.name, "totalFrames": frame_count, "language": language}
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    entries = {
        "运行状态": summary.get("status", "unknown"), "输入视频": summary.get("source", "未记录"),
        "本次帧数": frame_count, "输入尺寸": clip.get("size", "未记录"),
        "原视频尺寸": clip.get("original_size", "未记录"), "播放帧率（不是推理 FPS）": clip.get("fps", "未记录"),
        "设备": runtime.get("device_name", "未记录"), "依赖版本": runtime.get("versions", "未记录"),
        "YOLO 阈值": summary.get("arguments", {}).get("conf", "未记录"),
        "类别过滤": summary.get("arguments", {}).get("classes", "未记录"),
        "YOLO PyTorch 峰值 allocated / MiB": summary.get("yolo", {}).get("cuda_peak_allocated_mib", "未运行"),
        "SAM PyTorch 峰值 allocated / MiB": summary.get("sam2", {}).get("cuda_peak_allocated_mib", "未运行"),
        "原始运行时间": summary.get("created_utc", "未记录"), "网页与代码快照更新时间": generated,
        "错误（如有）": summary.get("error", "无")}
    rows = "".join(f'<tr><th scope="row">{escape(str(t(k)))}</th><td>{escape(str(t(v)))}</td></tr>' for k, v in entries.items())
    warnings = "".join(f'<p class="notice">{escape(message)}</p>' for message in (yolo_error, sam_error) if message)
    code_dir = output / "code"
    code_dir.mkdir(exist_ok=True)
    for name in SOURCES:
        # Curated teaching source only; do not copy arbitrary workspace/credential files.
        shutil.copyfile(Path(__file__).with_name(name), code_dir / f"{name}.txt")
    source_links = "".join(f'<li><a href="code/{name}.txt">{name}</a></li>' for name in SOURCES)
    prompt = (f'<figure><img src="sam2_prompt.jpg" alt="{t("本次第一帧提供给 SAM 的目标框")}" loading="lazy">'
              f'<figcaption>{t("本次初始化提示；类别标签来自提示来源。")}<a href="sam2_prompts.json">{t("查看坐标与来源")}</a></figcaption></figure>'
              if (output / "sam2_prompt.jpg").is_file() and (output / "sam2_prompts.json").is_file()
              else f'<p class="notice">{t("本次没有可展示的 SAM 初始化提示。")}</p>')
    values = {"CSS": (WEB / "tutorial.css").read_text(encoding="utf-8") + (WEB / "study.css").read_text(encoding="utf-8") + (WEB / "experiments.css").read_text(encoding="utf-8"),
              "JS": (WEB / "tutorial.js").read_text(encoding="utf-8"), "DATA": _json_script(data),
              "DATASET_AUDIT_SUMMARY": homepage_summary(output, language),
              "COMPARISON": _video(output, "comparison", "同步四格：框 / mask / ByteTrack / SAM 2.1", language),
              "VIDEO_BOXES": _video(output, "01_boxes", "第一课 · YOLO 检测框", language),
              "VIDEO_MASKS": _video(output, "02_masks", "第二课 · YOLO 像素掩码", language),
              "VIDEO_TRACK": _video(output, "03_bytetrack", "第三课 · YOLO + ByteTrack", language),
              "VIDEO_SAM": _video(output, "04_sam2", "第四课 · SAM 2.1 提示传播", language),
              "PROMPT": prompt, "ROWS": rows, "WARNINGS": warnings, "SOURCE_LINKS": source_links,
              "RUN_NAME": escape(output.name), "GENERATED": generated,
              "PROPOSAL_BODY": proposal["html"], "PROPOSAL_PDF": proposal["pdf"],
              "PROPOSAL_SOURCE": proposal["source"], "PROPOSAL_SOURCE_NAME": proposal["source_name"],
              "PROPOSAL_HASH": proposal["hash"],
              "LATEX_BYTES": f'{proposal["latex_bytes"]:,}',
              "TEMPLATE_BYTES": f'{proposal["template_bytes"]:,}',
              "TEX_BYTES": f'{proposal["tex_bytes"]:,}',
              "SHORT_PDF": proposal["short_pdf"],
              "SHORT_SOURCE": proposal["short_source"],
              "SHORT_PDF_BYTES": f'{proposal["short_pdf_bytes"]:,}',
              "SHORT_LATEX_BYTES": f'{proposal["short_latex_bytes"]:,}',
              "SHORT_TEX_BYTES": f'{proposal["short_tex_bytes"]:,}',
              "EXPLORER_HIDDEN": "" if available_frames else "hidden",
              "EXPLORER_MISSING": "" if available_frames else f'<p class="notice">{t("本次没有原始帧可供逐帧检查。")}</p>',
              "CODE_LOAD": _code("yolo_lessons.py", 30, 35, language),
              "CODE_PREDICT": _code("yolo_lessons.py", 57, 68, language),
              "CODE_MASK": _code("yolo_lessons.py", 77, 81, language),
              "CODE_RECORDS": _code("yolo_lessons.py", 9, 19, language),
              "CODE_SAM_LOAD": _code("sam2_lesson.py", 31, 34, language),
              "CODE_SAM_PROMPT": _code("sam2_lesson.py", 46, 55, language),
              "CODE_SAM_MASK": _code("sam2_lesson.py", 59, 64, language)}
    template = (WEB / ("tutorial.en.html" if language == "en" else "tutorial.html")).read_text(encoding="utf-8")
    html = re.sub(r"@@([A-Z_]+)@@", lambda match: values[match.group(1)], template)
    missing_label = "Not generated for this run" if language == "en" else "本次未生成"
    for name in ("summary.json", "environment.txt", "yolo_records.jsonl", "sam2_records.jsonl"):
        if not (output / name).is_file():
            html = re.sub(
                rf'<a href="{re.escape(name)}">(.*?)</a>',
                lambda match: f'<span>{match[1]} · {missing_label}</span>',
                html,
            )
    html = html.replace('href="index.en.html"', 'href="handbook.en.html"').replace('href="index.html"', 'href="handbook.html"')
    (output / ("handbook.en.html" if language == "en" else "handbook.html")).write_text(decorate_page(html, language, "handbook"), encoding="utf-8")


def refresh_report(output: Path):
    """Refresh an existing run and retain its previous HTML; do not redo inference."""
    output = output.resolve()
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8-sig"))
    previous = output / "index.html"
    backup = None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    if previous.is_file():
        backup = output / f"index.before-refresh-{stamp}.html"
        shutil.copy2(previous, backup)
    english = output / "index.en.html"
    if english.is_file():
        shutil.copy2(english, output / f"index.en.before-refresh-{stamp}.html")
    extra_pages = tuple(name for name in WORKBENCH_PAGES if not name.startswith("index"))
    for name in (*STUDY_PAGES, *DATASET_PAGES, *RESULT_PAGES, *RECOVERY_PAGES, *LONG_RECOVERY_PAGES, *PROGRAM_PAGES, *HANDBOOK_PAGES, *extra_pages):
        page = output / name
        if page.is_file():
            shutil.copy2(page, output / f"{page.stem}.before-refresh-{stamp}.html")
    write_report(output, summary)
    return backup


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refresh an existing local tutorial without model inference.")
    parser.add_argument("--output", type=Path, required=True, help="Existing run folder containing summary.json")
    args = parser.parse_args()
    backup = refresh_report(args.output)
    print(f"Updated: {args.output.resolve() / 'index.html'}")
    if backup:
        print(f"Previous page preserved: {backup}")
