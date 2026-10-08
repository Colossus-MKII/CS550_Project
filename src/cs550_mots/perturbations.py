"""Deterministic appearance perturbations that preserve frame geometry."""

import io
import math


def validate_perturbation(spec):
    kinds = {"clean", "blur", "brightness", "jpeg"}
    if spec.get("kind") not in kinds:
        raise ValueError(f"kind must be one of {sorted(kinds)}")
    kind = spec["kind"]
    expected = {"clean": {"kind"}, "blur": {"kind", "radius"},
                "brightness": {"kind", "factor"}, "jpeg": {"kind", "quality"}}[kind]
    if set(spec) != expected:
        raise ValueError(f"{kind} requires exactly {sorted(expected)}")
    if kind in {"blur", "brightness"}:
        key = "radius" if kind == "blur" else "factor"
        value = spec[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{key} must be finite and positive")
    if kind == "jpeg":
        value = spec["quality"]
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100:
            raise ValueError("quality must be an integer in [1, 100]")
    return spec


def apply_perturbation(image, spec):
    validate_perturbation(spec)
    from PIL import Image, ImageEnhance, ImageFilter

    image = image.convert("RGB")
    if spec["kind"] == "clean":
        return image.copy()
    if spec["kind"] == "blur":
        return image.filter(ImageFilter.GaussianBlur(radius=spec["radius"]))
    if spec["kind"] == "brightness":
        return ImageEnhance.Brightness(image).enhance(spec["factor"])
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=spec["quality"], subsampling=2)
    buffer.seek(0)
    with Image.open(buffer) as decoded:
        return decoded.convert("RGB").copy()

