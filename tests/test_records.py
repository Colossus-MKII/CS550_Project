import copy
import unittest

from cs550_mots.records import decode_rle, encode_rle, group_tracks, validate_frame


def frame(index=0):
    return {"frame_idx": index, "timestamp_s": index / 30,
            "image_size": [2, 3], "objects": [{
                "object_id": 7, "category_id": 0, "category_name": "person",
                "score": 0.8, "mask": encode_rle([[0, 1, 0], [1, 1, 0]])}]}


class RecordsTest(unittest.TestCase):
    def test_coco_column_major_order(self):
        self.assertEqual(encode_rle([[0, 1, 0], [1, 1, 0]]),
                         {"size": [2, 3], "counts": [1, 3, 2]})

    def test_round_trip_empty_full_and_irregular_masks(self):
        for mask in ([[0, 0], [0, 0]], [[1, 1], [1, 1]],
                     [[1, 0, 1], [0, 1, 0], [1, 1, 0]]):
            self.assertEqual(decode_rle(encode_rle(mask)), mask)
        self.assertEqual(encode_rle([[1, 1], [1, 1]])["counts"], [0, 4])

    def test_invalid_mask_and_incomplete_rle_rejected(self):
        for mask in ([], [[0], [1, 0]], [[2]]):
            with self.assertRaises(ValueError):
                encode_rle(mask)
        for counts in ([3], [-1, 5], [True, 3]):
            with self.assertRaises(ValueError):
                decode_rle({"size": [2, 2], "counts": counts})

    def test_duplicate_id_score_and_resolution_rejected(self):
        original = frame()
        self.assertEqual(validate_frame(original), original)
        duplicate = copy.deepcopy(original)
        duplicate["objects"].append(copy.deepcopy(duplicate["objects"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_frame(duplicate)
        for score in (float("nan"), 1.01, -0.1):
            invalid = copy.deepcopy(original)
            invalid["objects"][0]["score"] = score
            with self.assertRaises(ValueError):
                validate_frame(invalid)
        invalid = copy.deepcopy(original)
        invalid["image_size"] = [3, 3]
        with self.assertRaisesRegex(ValueError, "resolution"):
            validate_frame(invalid)

    def test_track_has_explicit_absence_and_mean_inputs(self):
        missing = frame(1)
        missing["objects"] = []
        result = group_tracks([frame(), missing, frame(2)], 3, {"0": 1})
        self.assertEqual(result[7]["category_id"], 1)
        self.assertIsNone(result[7]["segmentations"][1])
        self.assertEqual(result[7]["scores"], [0.8, 0.8])

    def test_missing_frames_mapping_and_category_drift_rejected(self):
        with self.assertRaisesRegex(ValueError, "every frame"):
            group_tracks([frame()], 2, {"0": 1})
        with self.assertRaisesRegex(ValueError, "mapping"):
            group_tracks([frame()], 1, {})
        changed = frame(1)
        changed["objects"][0]["category_id"] = 2
        with self.assertRaisesRegex(ValueError, "changed category"):
            group_tracks([frame(), changed], 2, {"0": 1, "2": 2})


if __name__ == "__main__":
    unittest.main()

