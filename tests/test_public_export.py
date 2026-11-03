from copy import deepcopy
import importlib.util
import json
import shutil
import pytest
from pathlib import Path
from zipfile import ZipFile

from blindspot.config import ROOT
from blindspot.public_snapshot import public_summary


def test_public_summary_omits_operational_preferences_and_preserves_science():
    original=json.loads((ROOT/'data/final-panel-public.json').read_text())
    original.update(token_budget_extension={'reported_remaining_credit':150.0},estimated_credit_remaining=40.0)
    before=deepcopy(original);public=public_summary(original)
    assert original==before
    assert 'token_budget_extension' not in public and 'estimated_credit_remaining' not in public
    assert public['models']==original['models'] and public['new_calls']==original['new_calls']
    assert public['new_accounted_usd']==original['new_accounted_usd']


@pytest.mark.skipif(shutil.which('git') is None,reason='Git is required for the public-export boundary check')
def test_clean_export_excludes_private_files_even_outside_an_existing_git_index(tmp_path):
    spec=importlib.util.spec_from_file_location('prepare_public',ROOT/'tools/prepare_public.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    source=tmp_path/'source';source.mkdir();(source/'data').mkdir()
    (source/'.gitignore').write_text((ROOT/'.gitignore').read_text())
    for name in ['.env','.env.production','DEMO_SCRIPT.md','COST_SUMMARY.md','SUBMISSION_NOTES.md']:
        (source/name).write_text('private test fixture')
    (source/'.env.example').write_text('META_API_KEY=')
    (source/'run.py').write_text('# public source')
    (source/'data/final-study-review.zip').write_bytes(b'private ledger fixture')
    original={'models':[],'new_calls':2676,'token_budget_extension':{'reported_remaining_credit':150.0},'estimated_credit_remaining':40.0}
    (source/'data/final-panel-results.json').write_text(json.dumps(original))
    output=tmp_path/'public.zip';names=module.build_public_archive(source,output)
    assert '.env.example' in names and 'run.py' in names and 'data/final-panel-public.json' in names
    assert not any(n in names for n in ['.env','.env.production','DEMO_SCRIPT.md','data/final-study-review.zip','data/final-panel-results.json'])
    with ZipFile(output) as archive:
        public=json.loads(archive.read('blindspot/data/final-panel-public.json'))
        assert public['new_calls']==2676 and 'estimated_credit_remaining' not in public
