"""Audit candidate public-source files without printing possible secret values."""
import json
from pathlib import Path
import re

PRIVATE_JSON_FIELDS={'api_key','meta_api_key','fireworks_api_key','openai_api_key','authorization',
                     'access_token','refresh_token','account_namespace','api_key_hash',
                     'reported_remaining_credit','estimated_credit_remaining','token_budget_extension'}
TEXT_SUFFIXES={'.py','.js','.mjs','.json','.md','.txt','.csv','.html','.css','.svg','.toml','.yaml','.yml'}
TOKEN_PATTERNS=[
    re.compile(r'\bsk-[A-Za-z0-9_-]{24,}\b'),
    re.compile(r'\bgh[pousr]_[A-Za-z0-9]{24,}\b'),
    re.compile(r'\bgithub_pat_[A-Za-z0-9_]{30,}\b'),
    re.compile(r'\bAKIA[A-Z0-9]{16}\b'),
    re.compile(r'\bAIza[A-Za-z0-9_-]{25,}\b'),
    re.compile(r'\bBearer[ \t]+[A-Za-z0-9._~+/=-]{24,}'),
    re.compile(r'''(?i)\b(?:api_key|meta_api_key|access_token|refresh_token)\s*[:=]\s*['"][A-Za-z0-9_./+=-]{24,}['"]'''),
]
LOCAL_PATH=re.compile(r'''(?<![A-Za-z0-9_])[A-Za-z]:[\\/][^\s'"<>]+|/(?:workspace|home|Users|mnt/data|tmp|var/tmp)/[^\s'"<>]+''')
EMAIL=re.compile(r'(?<![\w.+-])[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
OPERATIONAL_NOTE=re.compile(r'(?i)(?:remaining\s+(?:credit|balance)|credit\s+remaining)\s*[:=]?\s*\$?\s*\d+(?:\.\d+)?')
PRIVATE_SUFFIXES={'.zip','.sqlite','.sqlite3','.db','.pem','.key','.mp4','.mov','.webm','.pyc'}


def _private_json(value):
    if isinstance(value,dict):
        return any((key.lower() in PRIVATE_JSON_FIELDS and bool(item)) or _private_json(item) for key,item in value.items())
    if isinstance(value,list):return any(_private_json(item) for item in value)
    return False


def audit_files(root,files):
    """Return file/type findings only. Scientific costs and source placeholders are valid."""
    root=Path(root);findings=[]
    def flag(name,kind):
        item={'file':name,'type':kind}
        if item not in findings:findings.append(item)
    for name in files:
        path=root/name;leaf=path.name.lower()
        if ((leaf.startswith('.env') and leaf!='.env.example') or path.suffix.lower() in PRIVATE_SUFFIXES
            or any(part.lower() in {'var','private','recordings','.git','.cache','node_modules','.playwright'} for part in Path(name).parts)
            or re.search(r'(?i)(cookies|storage[-_]?state|session[-_]?state)',leaf)):
            flag(name,'Private/runtime filename');continue
        data=path.read_bytes()
        if path.suffix.lower()=='.png':continue  # Generated scientific figures are intentional assets.
        try:text=data.decode('utf-8')
        except UnicodeDecodeError:
            flag(name,'Unreviewed binary asset');continue
        if any(pattern.search(text) for pattern in TOKEN_PATTERNS):flag(name,'Possible credential token or authorization value')
        if LOCAL_PATH.search(text):flag(name,'Local absolute filesystem path')
        if EMAIL.search(text):flag(name,'Email address requiring review')
        if path.suffix.lower() in {'.md','.txt'} and OPERATIONAL_NOTE.search(text):flag(name,'Personal credit-balance note')
        if path.suffix.lower()=='.json':
            try:
                if _private_json(json.loads(text)):flag(name,'Private operational JSON field')
            except ValueError:flag(name,'Invalid JSON')
        if path.suffix.lower()=='.md':
            if re.search(r'\b(?:TODO|FIXME)\b',text):flag(name,'Unfinished user-facing documentation')
            if re.search(r'https?://(?:example\.com|(?:www\.)?your[-_\w]*\.)|github\.com/(?:your[-_\w]*|OWNER)(?:/|\b)',text,re.I):
                flag(name,'Placeholder URL')
    return findings


def audit_markdown_links(root,files):
    root=Path(root);available=set(files);findings=[]
    for name in files:
        if not name.endswith('.md'):continue
        text=(root/name).read_text(encoding='utf-8')
        for raw in re.findall(r'\]\(([^)]+)\)',text):
            target=raw.strip().strip('<>').split(' "',1)[0]
            if not target or target.startswith(('#','https:','http:','mailto:')):continue
            target=target.split('#',1)[0]
            resolved=((root/name).parent/target).resolve()
            try:relative=resolved.relative_to(root.resolve()).as_posix()
            except ValueError:
                findings.append({'file':name,'type':'Documentation link outside the public source'});continue
            if relative not in available and not (resolved.is_dir() and any(p.startswith(relative.rstrip('/')+'/') for p in available)):
                item={'file':name,'type':'Broken or excluded local documentation link'}
                if item not in findings:findings.append(item)
    return findings
