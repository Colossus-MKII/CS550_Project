"""Verify every exported RGB and binary alpha asset against its manifest."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def verify(folder):
    manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    rgb_count = mask_count = 0
    for sample in manifest['samples']:
        base = folder/str(sample['id'])
        for frame in range(sample['frames']):
            filename = f'{frame:05d}.png'
            rgb = np.asarray(Image.open(base/'rgb'/filename))
            assert rgb.shape == (sample['height'],sample['width'],3)
            assert rgb.dtype == np.uint8
            rgb_count += 1
            for channel in sample['channels']:
                mask = np.asarray(Image.open(base/f'mask-{channel["index"]}'/filename))
                assert mask.shape == (sample['height'],sample['width'],4)
                assert np.count_nonzero(mask[...,3]) == channel['areas'][frame]
                assert np.all(np.isin(mask[...,3],[0,255]))
                assert np.all(mask[...,:3] == 255)
                mask_count += 1
    return {'status':'passed','rgb_frames':rgb_count,'channel_masks':mask_count,
            'preview_bytes':sum(f.stat().st_size for f in folder.rglob('*') if f.is_file())}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    print(json.dumps(verify(parser.parse_args().folder)))
