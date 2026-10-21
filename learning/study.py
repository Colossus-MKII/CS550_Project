"""Bilingual reference pages, built as offline HTML with native MathML."""
from html import escape
from pathlib import Path
import re
from .navigation import decorate_page

from latex2mathml.converter import convert

WEB = Path(__file__).with_name("web")
PAGES = ("math.html", "math.en.html", "research.html", "research.en.html", "experiments.html", "experiments.en.html")
SAM_REV = "2b90b9f5ceec907a1c18123530e92e794ad901a4"
EVAL_REV = "12c8791b303e0a0b50f753af204249e622d0281a"


def pick(language, zh, en):
    return en if language == "en" else zh


def link(url, label):
    return f'<a href="{escape(url, quote=True)}">{escape(label)}</a>'


def source(kind, path, label):
    roots = {
        "yolo": "https://github.com/ultralytics/ultralytics/blob/v8.3.221/ultralytics/",
        "sam": f"https://github.com/facebookresearch/sam2/blob/{SAM_REV}/",
        "eval": f"https://github.com/JonathonLuiten/TrackEval/blob/{EVAL_REV}/trackeval/metrics/",
    }
    return link(roots[kind] + path, label)


def equation(tex):
    # Build time only. Readers need neither JS, a CDN nor a math-rendering package.
    mathml = convert(tex, display="block")
    mathml = mathml.replace("<mrow>", '<semantics><mrow>', 1)
    mathml = mathml.replace("</math>", f'<annotation encoding="application/x-tex">{escape(tex)}</annotation></semantics></math>')
    return f'<div class="equation" tabindex="0">{mathml}</div>'


def section(key, title, body, back=None):
    backlink = f'<p class="small">{back}</p>' if back else ""
    return f'<section id="{key}" class="chapter"><h2>{title}</h2>{body}{backlink}</section>'


def write_study_pages(output):
    from .study_math import content as mathematics
    from .study_history import content as history
    from .study_experiments import content as experiments
    from .recovery_page import recovery_link
    from .recovery_long_page import long_link

    output = Path(output)
    template = (WEB / "study.html").read_text(encoding="utf-8")
    css = (WEB / "tutorial.css").read_text(encoding="utf-8") + (WEB / "study.css").read_text(encoding="utf-8")
    script = (WEB / "study.js").read_text(encoding="utf-8")
    for language in ("zh", "en"):
        suffix = ".en" if language == "en" else ""
        home = f"handbook{suffix}.html"
        for slug, builder in (("math", mathematics), ("research", history), ("experiments", experiments)):
            title, intro, sections = builder(language, home)
            if slug == "experiments":
                measured = recovery_link(output, language)
                if measured:
                    intro += '<p class="notice">' + pick(language, '本页解释对照设计；骑手失败与猫稳定对照已完成实测。', 'This page explains the design; rider-failure and stable-cat measurements are complete.') + ' ' + measured + '</p>'
                extension = long_link(output,language)
                if extension:
                    intro += '<p>'+pick(language,'已完成后续：同一事件的30步主实验与单次刷新消融，8步读数保留。','Completed follow-up: the same events over 30 steps plus a skip-one-refresh ablation; eight-step readings are preserved.')+' '+extension+'</p>'
            nav = link("#start", pick(language, "页面概览", "Page overview"))
            nav += "".join(link("#" + key, label) for key, label, _ in sections)
            values = {
                "LANG": "en" if language == "en" else "zh-CN", "TITLE": title,
                "INTRO": intro, "HOME": f"index{suffix}.html",
                "CSS": css + ((WEB / "experiments.css").read_text(encoding="utf-8") if slug == "experiments" else ""),
                "JS": script + ((WEB / "experiments.js").read_text(encoding="utf-8") if slug == "experiments" else ""),
                "NAV": nav, "BODY": "".join(body for _, _, body in sections),
                "OTHER": f'{slug}{"" if language == "en" else ".en"}.html',
                "SWITCH": pick(language, "English", "中文"),
                "BACK": pick(language, "返回学习主线", "Back to the handbook"),
                "MENU": pick(language, "本页目录", "On this page"),
                "THEME": pick(language, "切换主题", "Theme"),
                "SKIP": pick(language, "跳到正文", "Skip to content"),
                "TRAIL": pick(language, "研究与实验" if slug == "experiments" else "深入阅读", "Research and experiments" if slug == "experiments" else "Further study"),
                "FOOT": pick(language, "内容更新：2026-10-15。正式实验以锁定版本、配置和统一评估器为准。", "Updated 2026-10-15. Formal experiments must pin versions, configurations and the evaluator."),
            }
            rendered = re.sub(r"@@([A-Z_]+)@@", lambda m: values[m[1]], template)
            (output / f"{slug}{suffix}.html").write_text(decorate_page(rendered, language, slug), encoding="utf-8")
