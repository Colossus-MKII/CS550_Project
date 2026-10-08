import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from cs550_mots.cli import _perturb_folder
from cs550_mots.perturbations import apply_perturbation, validate_perturbation


class PerturbationTest(unittest.TestCase):
    def test_brightness_has_known_values_and_geometry(self):
        image = Image.new("RGB", (5, 3), (100, 200, 40))
        result = apply_perturbation(image, {"kind": "brightness", "factor": 0.75})
        self.assertEqual(result.size, image.size)
        self.assertEqual(result.getpixel((1, 1)), (75, 150, 30))
        self.assertEqual(image.getpixel((1, 1)), (100, 200, 40))

    def test_blur_and_jpeg_are_deterministic_and_change_pixels(self):
        image = Image.new("RGB", (16, 16))
        for y in range(16):
            for x in range(16):
                image.putpixel((x, y), ((x * 19) % 256, (y * 29) % 256, ((x + y) * 53) % 256))
        for spec in ({"kind": "blur", "radius": 1.0}, {"kind": "jpeg", "quality": 30}):
            result = apply_perturbation(image, spec)
            self.assertEqual(result.size, image.size)
            self.assertEqual(result.tobytes(), apply_perturbation(image, spec).tobytes())
            self.assertNotEqual(result.tobytes(), image.tobytes())

    def test_invalid_specs_rejected(self):
        invalid = ({"kind": "jpeg", "quality": 0}, {"kind": "jpeg", "quality": 1.5},
                   {"kind": "brightness", "factor": float("nan")},
                   {"kind": "blur", "radius": -1}, {"kind": "brightness"},
                   {"kind": "blur", "radius": 1, "extra": 2})
        for spec in invalid:
            with self.assertRaises(ValueError):
                validate_perturbation(spec)

    def test_folder_keeps_order_and_prevents_overwriting(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            source.mkdir()
            Image.new("RGB", (4, 2), "red").save(source / "002.png")
            Image.new("RGB", (4, 2), "blue").save(source / "001.png")
            output = Path(temporary) / "output"
            result = _perturb_folder(source, output, {"kind": "clean"})
            self.assertEqual(result["frame_count"], 2)
            manifest = json.loads((output / "perturbation.json").read_text())
            self.assertEqual(manifest["frames"][0]["source_filename"], "001.png")
            with Image.open(output / "00000000.png") as image:
                self.assertEqual(image.getpixel((0, 0)), (0, 0, 255))
            with self.assertRaisesRegex(ValueError, "empty"):
                _perturb_folder(source, output, {"kind": "clean"})
            with self.assertRaisesRegex(ValueError, "inside"):
                _perturb_folder(source, source / "output", {"kind": "clean"})

    def test_study_perturbation_specs_are_valid(self):
        config = json.loads((Path(__file__).resolve().parents[1] / "configs/study.json").read_text())
        for spec in config["perturbations"]:
            validate_perturbation(spec)


if __name__ == "__main__":
    unittest.main()

