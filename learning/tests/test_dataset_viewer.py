"""Real-data preview fidelity, bilingual rendering and graceful missing assets."""
import json
import re

import numpy as np
from PIL import Image
import pytest

from tracking_lab.prepare import export_sample
from learning.dataset_page import PAGES, write_dataset_pages
from learning.tests.test_study import Page


def fixture_sample(tmp_path):
    video = np.arange(2*3*4*3, dtype=np.uint8).reshape(2,3,4,3)
    masks = np.zeros((2,3,4,2),dtype=np.uint8)
    masks[0,0,:2,0] = 26
    masks[1,1:,1:,1] = 9
    record = {'video_id':2686,'shard':'example.tar','tracks':[
        {'channel':0,'category_id':26,'category':'person','areas':[2,0]},
        {'channel':1,'category_id':9,'category':'dog','areas':[0,6]}]}
    return video,masks,record




def test_missing_samples_still_render_bilingual_guide(tmp_path):
    write_dataset_pages(tmp_path)
    pages=[(tmp_path/name).read_text(encoding='utf-8') for name in PAGES]
    assert Page(pages[0]).ids == Page(pages[1]).ids
    for text in pages:
        assert not Page(text).sources
        assert 'id="coverage"' in text and '226' in text
        assert 'id="dataset-data"' not in text
        assert '@@' not in text
    visible=re.sub(r'<(script|style)\b[^>]*>.*?</\1>','',pages[1],flags=re.S)
    visible=re.sub(r'<[^>]+>','',visible).replace('中文','')
    assert not re.search(r'[\u4e00-\u9fff]',visible)


def test_sample_manifest_embedded_safely_with_local_assets(tmp_path):
    video,masks,record=fixture_sample(tmp_path)
    folder=tmp_path/'dataset-samples'
    sample=export_sample(video,masks,record,folder,'person')
    manifest={'samples':[sample],'unsafe':'</script><script>bad()</script>'}
    (folder/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    write_dataset_pages(tmp_path)
    pages=[(tmp_path/name).read_text(encoding='utf-8') for name in PAGES]
    assert Page(pages[0]).ids == Page(pages[1]).ids
    for text in pages:
        assert '</script><script>bad()' not in text
        payload=re.search(r'<script id="dataset-data" type="application/json">(.*?)</script>',text,re.S)[1]
        assert json.loads(payload)==manifest
        assert len(Page(text).ids)==len(set(Page(text).ids))
        assert all((tmp_path/src).is_file() for src in Page(text).sources)


def test_refresh_preserves_dataset_pages(tmp_path):
    from learning.report import refresh_report
    (tmp_path/'summary.json').write_text('{}',encoding='utf-8')
    for name in PAGES: (tmp_path/name).write_text('OLD '+name,encoding='utf-8')
    refresh_report(tmp_path)
    for name in PAGES:
        backups=list(tmp_path.glob(name[:-5]+'.before-refresh-*.html'))
        assert len(backups)==1 and backups[0].read_text(encoding='utf-8')=='OLD '+name
