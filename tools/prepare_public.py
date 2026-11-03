"""Build a clean GitHub-ready source ZIP using the repository's .gitignore."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from blindspot.public_snapshot import public_summary
from tools.audit_public import audit_files,audit_markdown_links

PRIVATE_DIRECTORIES={'.git','.venv','venv','env','__pycache__','.pytest_cache','.mypy_cache','.ruff_cache',
                     'node_modules','var','private','local','upload','outputs','downloads','recordings',
                     'qa-browser','.openai','.codex','.vscode','.idea'}
PRIVATE_JSON_KEYS={'api_key','meta_api_key','fireworks_api_key','authorization','account_namespace',
                   'reported_remaining_credit','estimated_credit_remaining'}


def check_public_json(value,filename):
    if isinstance(value,dict):
        for key,item in value.items():
            if key.lower() in PRIVATE_JSON_KEYS and item:
                raise ValueError(f'Private operational field in {filename}: {key}')
            check_public_json(item,filename)
    elif isinstance(value,list):
        for item in value:check_public_json(item,filename)


def public_files(root,output):
    if not shutil.which('git'):
        raise RuntimeError('Git is needed to apply .gitignore exactly. Install Git, or use the supplied clean public ZIP.')
    candidates=[]
    for directory,dirs,files in os.walk(root):
        dirs[:]=[name for name in dirs if name not in PRIVATE_DIRECTORIES and not name.startswith('library-transfer-')
                 and not (Path(directory)/name).is_symlink()]
        for name in files:
            file=Path(directory)/name
            if file.is_symlink() or file.resolve()==output.resolve():continue
            candidates.append(file.relative_to(root).as_posix())
    # Use a temporary Git index context, so existing tracked files and global
    # ignore preferences cannot accidentally bypass the publication boundary.
    with tempfile.TemporaryDirectory(prefix='blindspot-public-') as directory:
        subprocess.run(['git','-c','init.templateDir=','init','--quiet',directory],check=True,capture_output=True)
        shutil.copyfile(root/'.gitignore',Path(directory)/'.gitignore')
        command=['git','-C',directory,'-c','core.excludesFile='+os.devnull,'check-ignore','--no-index','-z','--stdin']
        result=subprocess.run(command,input=('\0'.join(candidates)+'\0').encode(),capture_output=True)
        if result.returncode not in [0,1]:raise RuntimeError(result.stderr.decode(errors='replace'))
        ignored={name.decode() for name in result.stdout.split(b'\0') if name}
    return sorted(set(candidates)-ignored)


def build_public_archive(root,output):
    root=Path(root).resolve();output=Path(output).resolve()
    private=root/'data/final-panel-results.json';public=root/'data/final-panel-public.json'
    if private.exists():
        source=json.loads(private.read_text(encoding='utf-8'))
        public.write_text(json.dumps(public_summary(source),indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    files=public_files(root,output)
    for name in files:
        if name.endswith('.json'):
            check_public_json(json.loads((root/name).read_text(encoding='utf-8')),name)
    findings=audit_files(root,files)+audit_markdown_links(root,files)
    if findings:
        raise ValueError('Public-source audit rejected the candidate: '+json.dumps(findings))
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix(output.suffix+'.tmp')
    with ZipFile(temporary,'w',ZIP_DEFLATED,compresslevel=6) as archive:
        for name in files:archive.write(root/name,'blindspot/'+name)
    with ZipFile(temporary) as archive:
        if archive.testzip() is not None:raise RuntimeError('Public ZIP integrity check failed')
    temporary.replace(output)
    return files


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT.parent/'blindspot-public.zip')
    args=parser.parse_args()
    files=build_public_archive(ROOT,args.output)
    print(f'Public source ZIP: {args.output.resolve()} ({len(files)} files).')
    print('Local ledgers, credentials, raw review archives and creator-only drafts are excluded.')


if __name__=='__main__':main()
