"""Bilingual, evidence-backed correction notice shared by experiment pages."""

from .study import link, pick


def revision_notice(evidence, language, full=False):
    audit = evidence.get("correction") if evidence else None
    if not audit:
        return ""
    t = lambda zh, en: pick(language, zh, en)
    suffix = ".en" if language == "en" else ""
    text = (
        '<aside class="notice" id="baseline-correction"><strong>'
        + t(
            "基线修订：已修复 SAM CPU 卸载同步错误",
            "Baseline correction: SAM CPU-offload synchronization fixed",
        )
        + "</strong><p>"
    )
    text += t(
        f"已重新推理、评分并生成视频。旧 B0 有 {audit['changed_B0_frames']}/{audit['total_frames']} 个导出帧输出受影响，均为周期提示帧；A0 与 YOLO 输出逐像素未变。",
        f"Inference, scoring and videos were regenerated. B0 outputs changed on {audit['changed_B0_frames']}/{audit['total_frames']} exported frames, all periodic prompt steps; A0 and YOLO outputs are pixel-identical.",
    )
    text += (
        "</p><p>"
        + t(
            "撤回骑手 2686/25 的严重漂移、马 2718/35 消失被归因于记忆的解释。它们属于实现错误证据，不能用于证明历史记忆有害。",
            "Withdrawn: attributing severe rider drift at 2686/25 and the missing horse at 2718/35 to memory. These were implementation artifacts, not evidence that history is harmful.",
        )
        + "</p>"
    )
    if not full:
        return (
            text
            + link(
                "results" + suffix + ".html#revision",
                t("查看修订对照与验证 →", "Review correction and verification →"),
            )
            + "</aside>"
        )
    text += (
        '<div class="table-wrap"><table><thead><tr><th>'
        + t("版本", "Version")
        + "</th><th>HOTA</th><th>IDF1</th><th>FP</th><th>FN</th><th>IDSW</th></tr></thead><tbody>"
    )
    for label, source, method in [
        (t("A0（未变）", "A0 (unchanged)"), "new_metrics", "A0"),
        (t("B0 旧版（不再引用）", "B0 legacy (superseded)"), "old_metrics", "B0"),
        (t("B0 修正版", "B0 corrected"), "new_metrics", "B0"),
    ]:
        scores = audit[source][method]["macro"]
        text += (
            "<tr><th>"
            + label
            + "</th>"
            + "".join(
                "<td>"
                + (f"{scores[k]*100:.2f}" if k in ("HOTA", "IDF1") else str(scores[k]))
                + "</td>"
                for k in ("HOTA", "IDF1", "FP", "FN", "IDSW")
            )
            + "</tr>"
        )
    text += "</tbody></table></div><ul>"
    for row in audit["examples"]:
        text += f'<li>{row["video"]}/{row["frame"]} · GT {row["gt_id"]} · B0 ID {row["prediction_id"]}: mask IoU {row["old_mask_iou"]:.3f} → {row["new_mask_iou"]:.3f}</li>'
    text += (
        "</ul><p>"
        + t(
            "同步发生在 GPU→CPU 拷贝完成之后、CPU 合并读取之前。旧验证只重算已保存预测，无法排除此类推理错误；新版还做了独立完整神经推理复跑，五段所有 YOLO/A0/B0 实例、ID、框和 mask 完全一致。观察到其他 186 帧未变，不代表此类竞争在任何环境都不会传播。",
            "The fence completes GPU→CPU copies before CPU consolidation reads. Legacy verification rescored saved predictions and could not detect this inference error. A separate complete neural-inference repeat now matches every YOLO/A0/B0 instance, ID, box and mask on all five clips. The other 186 frames matched; this does not guarantee such races cannot propagate in other settings.",
        )
        + "</p><p>"
    )
    text += link(
        evidence["prefix"] + "correction-audit.json",
        t("逐帧差异与复跑记录", "Frame differences and inference-repeat audit"),
    )
    if evidence.get("legacy_manifest"):
        text += " · " + link(
            evidence["legacy_manifest"],
            t("旧运行清单（仅供追溯）", "Legacy manifest (audit only)"),
        )
    return (
        text
        + '</p><p class="small">'
        + t(
            "旧文件保留；本页默认显示独立修正版。未修改模型权重、算法参数或 Proposal。",
            "Legacy files are preserved; the default view uses a separate corrected run. Model weights, algorithm settings and proposals were not changed.",
        )
        + "</p></aside>"
    )
