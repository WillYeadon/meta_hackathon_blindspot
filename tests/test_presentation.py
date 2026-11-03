import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from blindspot.app import create_app
from blindspot.config import ROOT, Settings
from blindspot.meta import MetaClient
import blindspot.final_report as reporting


def test_saved_demo_needs_no_key_and_only_allowlisted_research_documents_are_served(tmp_path, monkeypatch):
    async def forbidden_call(*args, **kwargs):
        raise AssertionError('Viewing the saved demo must not call a model')
    monkeypatch.setattr(MetaClient, 'complete', forbidden_call)
    with TestClient(create_app(Settings(force_mock=True, seed_demo=False, db_path=str(tmp_path/'demo.sqlite3')))) as client:
        page=client.get('/')
        assert page.status_code==200 and 'Before you trust' in page.text
        assert '<details id="research-provenance"' in page.text
        assert 'legacy-workspace' not in page.text
        assert 'Original editable maps and earlier self-forecasts' not in page.text
        result=client.get('/api/final-study').json()
        assert result['mode']=='live' and result['collection_closed']
        wonder=next(m for m in result['models'] if m['id']=='wonder_high')
        assert wonder['dense']['usable']==102 and wonder['outer_anchors']['usable']==108
        for name in ['README.md','FINAL_FINDINGS.md','REPRODUCIBILITY.md','COST_SUMMARY.md']:
            response=client.get('/research/'+name)
            assert response.status_code==200 and 'text/plain' in response.headers['content-type']
        for name in ['.env','search.sqlite3','run.py','not-a-document.md','DEMO_SCRIPT.md','SUBMISSION_NOTES.md','PUBLICATION.md','SCREEN_CONTENT.md']:
            assert client.get('/research/'+name).status_code==404


@pytest.mark.parametrize('authored', [True, False])
def test_offline_integration_preserves_authored_demo_and_existing_plot_without_regeneration(tmp_path, monkeypatch, authored):
    result=json.loads((ROOT/'data/final-panel-public.json').read_text())
    distribution=tmp_path/'distribution';distribution.mkdir()
    study=tmp_path/'study';study.mkdir()
    (study/'plan.json').write_text('{}')
    for name in ['FINAL_FINDINGS.md','DEMO_SCRIPT.md','COST_SUMMARY.md']:
        (study/name).write_text('Generated '+name)
    original='<!-- SUBMISSION_DEMO_V1 -->\nAuthored narrative' if authored else 'Earlier generated narrative'
    (distribution/'DEMO_SCRIPT.md').write_text(original)
    (distribution/'README.md').write_text('<!-- FINAL_PANEL_STATUS_START -->\nold\n<!-- FINAL_PANEL_STATUS_END -->')
    (distribution/'static').mkdir()
    (distribution/'static/final-model-panel.png').write_bytes(b'previously rendered figure')
    monkeypatch.setattr(reporting, 'ROOT', distribution)
    reporting.integrate_final(study, result, copy_plot=False)
    assert (distribution/'DEMO_SCRIPT.md').read_text()==original
    assert (distribution/'FINAL_FINDINGS.md').read_text()=='Generated FINAL_FINDINGS.md'
    assert (distribution/'static/final-model-panel.png').read_bytes()==b'previously rendered figure'
