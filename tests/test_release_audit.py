import json
from tools.audit_public import audit_files,audit_markdown_links


def test_audit_rejects_possible_secrets_and_paths_without_echoing_values(tmp_path):
    token='ghp_'+('x'*36)  # Construct a synthetic token; no actual credential.
    local_path='/'+'home/'+'example-user/private.txt'
    (tmp_path/'config.txt').write_text(token+'\n'+local_path)
    (tmp_path/'private.json').write_text(json.dumps({'access_token':'synthetic'}))
    findings=audit_files(tmp_path,['config.txt','private.json'])
    assert {item['type'] for item in findings}=={
        'Possible credential token or authorization value','Local absolute filesystem path','Private operational JSON field'}
    serialized=json.dumps(findings)
    assert token not in serialized and local_path not in serialized and 'synthetic' not in serialized


def test_document_links_must_exist_in_the_public_file_set(tmp_path):
    (tmp_path/'README.md').write_text('[Public](RESULTS.md) [Private](creator.md)')
    (tmp_path/'RESULTS.md').write_text('Scientific results')
    (tmp_path/'creator.md').write_text('Local notes')
    findings=audit_markdown_links(tmp_path,['README.md','RESULTS.md'])
    assert findings==[{'file':'README.md','type':'Broken or excluded local documentation link'}]
