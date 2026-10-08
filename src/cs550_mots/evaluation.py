"""VIS prediction export only: numerical benchmark metrics come from official tools."""

from .records import decode_rle, group_tracks


def export_vis(records, video_id, frame_count, category_map):
    if isinstance(video_id, bool) or not isinstance(video_id, int) or video_id < 1:
        raise ValueError("video_id must be a positive benchmark video ID")
    tracks = group_tracks(records, frame_count, category_map)
    try:
        import numpy as np
        from pycocotools import mask as coco_mask
    except ImportError as exc:
        raise RuntimeError("VIS export requires: python -m pip install -e '.[evaluation]'") from exc
    predictions = []
    for track in tracks.values():
        segmentations = []
        for rle in track["segmentations"]:
            if rle is None:
                segmentations.append(None)
                continue
            compressed = coco_mask.encode(np.asfortranarray(decode_rle(rle), dtype=np.uint8))
            compressed["counts"] = compressed["counts"].decode("ascii")
            segmentations.append(compressed)
        predictions.append({"video_id": video_id, "category_id": track["category_id"],
                            "score": sum(track["scores"]) / len(track["scores"]),
                            "segmentations": segmentations})
    return predictions

