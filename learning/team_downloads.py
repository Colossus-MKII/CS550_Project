"""Present verified existing resource packages; never build or run experiments."""

from html import escape
import json
from pathlib import Path
import re

from .program_page import table
from .study import link, pick

DIRECTORY = "downloads/cs550-pilot-20261028/"
ALLOWED = {"pilot-data.zip", "model-checkpoints.zip", "pilot128-outputs.zip", "ytvis2021_resized.zip"}


def read_resources(output):
    path = Path(output) / DIRECTORY / "manifest.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("status") != "ready" or {f["name"] for f in data["files"]} != ALLOWED:
        raise ValueError("Only complete, verified resource packages may be advertised")
    for f in data["files"]:
        if not re.fullmatch(r"[a-f0-9]{64}", f["sha256"]):
            raise ValueError("Missing package hash")
        archive = path.parent / f["name"]
        if not archive.is_file() or archive.stat().st_size != f["bytes"]:
            raise ValueError("Package is absent or has changed size: " + f["name"])
    return data


def download_link(output, language):
    if read_resources(output) is None:
        return ""
    suffix = ".en" if language == "en" else ""
    return link("documents" + suffix + ".html#team-assets",
                pick(language, "下载组内数据、权重与128分支pilot资源 →", "Download shared data, checkpoints and 128-branch pilot resources →"))


def content(output, language):
    data = read_resources(output)
    if data is None:
        return ""
    t = lambda zh, en: pick(language, zh, en)
    labels = {
        "pilot-data.zip": ("pilot原图与GT（32段完整筛查导出）", "Pilot RGB + GT (complete 32-video screening export)"),
        "model-checkpoints.zip": ("两份原版模型权重与版本记录", "Two original model checkpoints and version records"),
        "pilot128-outputs.zip": ("128主分支、16复跑分支、基线缓存及源码参考", "128 main branches, 16 repeat-only branches, baseline caches and source references"),
        "ytvis2021_resized.zip": ("完整原始数据ZIP（可选，字节未改变）", "Full original dataset ZIP (optional, byte-identical)"),
    }
    files = {f["name"]: f for f in data["files"]}
    rows = []
    for name in ("pilot-data.zip", "model-checkpoints.zip", "pilot128-outputs.zip", "ytvis2021_resized.zip"):
        f = files[name]
        size = f["bytes"]
        amount = f"{size/1024**3:.2f} GiB" if size >= 1024**3 else f"{size/1024**2:.1f} MiB"
        anchor = f'<a href="{DIRECTORY}{name}" download="{name}">{escape(name)}</a>'
        rows.append([t(*labels[name]), anchor, f"{amount}<br><small>{size:,} bytes</small>"])
    body = "<p class='notice'>" + t(
        "只复用现有pilot，下载前三个包即可；它们合起来不到1 GiB。完整原始数据约26.4 GiB，供后续经确认的完整benchmark按需使用。现成32段输入不是完整200段划分。",
        "To reuse the existing pilot, download only the first three packages (under 1 GiB combined). The full upstream dataset is about 26.4 GiB and is optional for later approved benchmark work. The 32 prepared videos are not the full 200-video split.") + "</p>"
    body += table([t("内容", "Contents"), t("直接下载", "Direct download"), t("实际大小", "Actual size")], rows, "team-assets-files")
    body += "<p>" + t(
        "将前三个包解压到同一个空目录，它们共用cs550-resources顶层文件夹。原始数据ZIP保持上游结构，另行解压。原始文件只读打包，没有重新推理或训练；不含密码、.venv、Git历史或已删除的人为错误实验。",
        "Extract the first three into the same empty directory; they share a cs550-resources top-level folder. Extract the original upstream dataset separately. Sources were read only: no inference or training was rerun. Passwords, .venv, Git history and deleted artificial-error experiments are excluded.") + "</p>"
    body += "<p>" + " · ".join(link(DIRECTORY + name, t(zh, en)) for name, zh, en in (
        ("README.txt", "解压与复用说明（英文）", "Extraction and reuse instructions"),
        ("MODEL_VERSIONS.json", "精确模型与环境版本", "Exact model and runtime versions"),
        ("SHA256SUMS.txt", "SHA256校验值", "SHA256 checksums"),
        ("manifest.json", "完整包清单", "Complete package manifest"))) + "</p>"
    body += "<details><summary>" + t("校验、路径与使用边界", "Verification, paths and scope") + "</summary><p>" + t(
        "新ZIP已逐文件计算SHA256并检查CRC；完整原始ZIP与已审计文件的SHA256完全一致。下载后请核对SHA256。运行记录保留原机器绝对路径用于溯源，不要直接执行这些路径；先看README中的路径复用说明。128主分支与16验证分支不能混作独立样本，数据划分和正式评估边界不变。",
        "New ZIPs have per-member SHA256 inventories and passed CRC checks. The full original ZIP matches the audited upstream SHA256. Verify checksums after downloading. Original run records preserve source-machine absolute paths for provenance: do not execute those paths blindly; read the reuse notes first. The 128 main and 16 verification branches are not independent samples; split and formal-evaluation boundaries are unchanged.") + "</p><p>" + t(
        "站点沿用公开只读HTTP，没有登录验证或HTTPS。支持分段请求与断点续传；原始包较大，请按需下载。这里是组内开发资源复用入口，不是课程提交入口。",
        "This remains the existing public read-only HTTP site, without authentication or HTTPS. Byte ranges/resumable transfers are supported; download the large upstream archive only if needed. This is a teammate development-resource mirror, not a coursework-submission endpoint.") + "</p></details>"
    return body
