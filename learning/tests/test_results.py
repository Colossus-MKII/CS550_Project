"""Saved pilot evidence joins the same bilingual site, without model inference."""
from hashlib import sha256
import json
import re
import ast
from pathlib import Path

import pytest

from learning.pilot_page import PAGES, import_results, write_results_pages
from learning.tests.test_study import Page


def test_site_importer_is_not_an_experiment_runtime():
    import learning.pilot_page as importer
    tree=ast.parse(Path(importer.__file__).read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            assert all(alias.name.split('.')[0] not in {'tracking_lab','pilot','torch','sam2','ultralytics'} for alias in node.names)
        elif isinstance(node,ast.ImportFrom):
            assert (node.module or '').split('.')[0] not in {'tracking_lab','pilot','torch','sam2','ultralytics'}


def make_source(folder):
    folder.mkdir()
    (folder/'code').mkdir()
    raw=b'print("inference snapshot")\n'
    (folder/'code/run.py.txt').write_bytes(raw)
    summary={'status':'completed','created_utc':'2026-10-17','environment':{},'configuration':{},
        'classes':['person'],'selection':{},'weights':{},'source_files':{'run.py':sha256(raw).hexdigest()},
        'limitations':[],'videos':{'2686':{'frames':2}},'yolo_peak_allocated_mib':119,'sam_peak_allocated_mib':892,
        'samples_root':'C:/private/source/path'}
    scores={'HOTA':.5,'DetA':.4,'AssA':.6,'IDF1':.7,'FP':1,'FN':2,'IDSW':0}
    values={'summary.json':summary,'verification.json':{'status':'passed'},
        'viewer-data.json':{'videos':[{'id':2686,'frames':2,'focus':'person','worst_frames':[1],'A0':[],'B0':[],'events':[]}]},
        'metrics.json':{method:{'macro':scores,'per_class':{'person':{'scores':scores}}} for method in ['A0','B0']},
        'config.json':{},'evaluator-self-checks.json':{},'input-manifest.json':{}}
    for name,value in values.items(): (folder/name).write_text(json.dumps(value),encoding='utf-8')
    for name in ['2686/visuals/00000.jpg','2686/visuals/00001.jpg','2686/iou-curve.png','2686/comparison.mp4']:
        path=folder/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'copied evidence')
    (folder/'secret.txt').write_text('not allowlisted',encoding='utf-8')
    return summary


def test_no_run_renders_readable_fallback(tmp_path):
    write_results_pages(tmp_path)
    for name in PAGES:
        text=(tmp_path/name).read_text(encoding='utf-8')
        assert 'id="scores"' in text and '@@' not in text
        assert not Page(text).sources


def test_import_is_curated_bilingual_and_preserves_source(tmp_path):
    source=tmp_path/'verified-run';make_source(source)
    output=tmp_path/'learning';output.mkdir()
    before={str(f.relative_to(source)):f.read_bytes() for f in source.rglob('*') if f.is_file()}
    manifest=import_results(source,output)
    prefix=output/manifest['prefix']
    assert not (prefix/'secret.txt').exists()
    assert 'samples_root' not in json.loads((prefix/'summary.json').read_text(encoding='utf-8'))
    for name,expected in manifest['files'].items():
        assert sha256((prefix/name).read_bytes()).hexdigest()==expected
    pages=[(output/name).read_text(encoding='utf-8') for name in PAGES]
    assert Page(pages[0]).ids==Page(pages[1]).ids
    assert all('id="language-toggle"' in text and 'id="theme-toggle"' in text for text in pages)
    for text in pages:
        assert not re.search(r'http://(?:127\.0\.0\.1|localhost):8770',text)
        assert all((output/src).is_file() for src in Page(text).sources)
    visible=re.sub(r'<(script|style)\b[^>]*>.*?</\1>','',pages[1],flags=re.S)
    visible=re.sub(r'<[^>]+>','',visible).replace('中文','')
    assert not re.search(r'[\u4e00-\u9fff]',visible)
    assert before=={str(f.relative_to(source)):f.read_bytes() for f in source.rglob('*') if f.is_file()}


@pytest.mark.parametrize('status',['failed','invalidated_A0_mask_index_adapter'])
def test_incomplete_or_invalidated_results_are_rejected(tmp_path,status):
    source=tmp_path/'invalid';summary=make_source(source)
    summary['status']=status
    (source/'summary.json').write_text(json.dumps(summary),encoding='utf-8')
    with pytest.raises(ValueError): import_results(source,tmp_path/'learning')


def test_refresh_retains_results_and_backups(tmp_path):
    from learning.report import refresh_report
    (tmp_path/'summary.json').write_text('{}',encoding='utf-8')
    for name in PAGES: (tmp_path/name).write_text('OLD '+name,encoding='utf-8')
    refresh_report(tmp_path)
    for name in PAGES:
        assert len(list(tmp_path.glob(name[:-5]+'.before-refresh-*.html')))==1
        assert '@@' not in (tmp_path/name).read_text(encoding='utf-8')


def test_corrected_run_preserves_legacy_manifest_and_checks_audit(tmp_path):
    from learning.program_page import read_evidence

    old = tmp_path/'old-run'; make_source(old)
    new = tmp_path/'corrected-run'; make_source(new)
    output = tmp_path/'site'; output.mkdir()
    import_results(old, output)
    original = (output/'pilot-results/manifest.json').read_bytes()
    metrics = json.loads((new/'metrics.json').read_text())
    correction = {'old_run':old.name,'new_run':new.name,'old_metrics':metrics,
                  'new_metrics':metrics,'changed_B0_frames':0,'total_frames':2,
                  'examples':[], 'full_inference_repeat':{'status':'not_checked'}}
    (new/'correction-audit.json').write_text(json.dumps(correction))
    with pytest.raises(ValueError, match='complete inference repeat'):
        import_results(new, output)
    assert (output/'pilot-results/manifest.json').read_bytes() == original
    correction['full_inference_repeat']['status'] = 'passed'
    (new/'correction-audit.json').write_text(json.dumps(correction))
    import_results(new, output)
    assert (output/'pilot-results/manifest-before-sync.json').read_bytes() == original
    assert read_evidence(output)['correction'] == correction
    for name in PAGES:
        text = (output/name).read_text(encoding='utf-8')
        assert 'id="revision"' in text and 'id="baseline-correction"' in text
        assert 'manifest-before-sync.json' in text
    public_audit = output/'pilot-results/corrected-run/correction-audit.json'
    public_audit.write_text('{}')
    with pytest.raises(ValueError, match='fingerprint'):
        read_evidence(output)
