"""Small shared IO, validation and exact-checkout primitives (stdlib)."""
from __future__ import annotations
import contextlib, hashlib, json, os, re, subprocess, tempfile, time
from pathlib import Path
from urllib.parse import urlsplit

SOURCE = Path(__file__).resolve().parents[1]
SKILLS = ('graphify','graph-loop','ponytail','ponytail-review','shunt','bulk-reader','code-writer')
TASKS = {'bulk-reader':'low','code-writer':'medium','document-extractor':'medium','evidence-curator':'low'}

def now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
def sha(data): return hashlib.sha256(data).hexdigest()
def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}',value):
        raise ValueError('Invalid identifier; use letters, numbers, dots, dashes or underscores')
    return value

def load(path, default=None):
    path=Path(path)
    return parse_json(path.read_text()) if path.exists() else default

def parse_json(text):
    # JSONC settings: replace comments with whitespace without touching quoted URLs.
    out=[];i=0;quoted=False;escaped=False
    while i<len(text):
        c=text[i]
        if quoted:
            out.append(c)
            if escaped:escaped=False
            elif c=='\\':escaped=True
            elif c=='"':quoted=False
            i+=1;continue
        if c=='"':quoted=True;out.append(c);i+=1;continue
        if text.startswith('//',i):
            end=text.find('\n',i);end=len(text) if end<0 else end
            out.append(' '*(end-i));i=end;continue
        if text.startswith('/*',i):
            end=text.find('*/',i+2)
            if end<0:raise ValueError('Unterminated JSONC comment')
            out.append(' '*(end+2-i));i=end+2;continue
        if c==',':
            j=i+1
            while j<len(text) and text[j].isspace():j+=1
            if j<len(text) and text[j] in '}]':i+=1;continue
        out.append(c);i+=1
    clean=''.join(out);out=[];quoted=False;escaped=False
    for i,c in enumerate(clean):
        if quoted:
            out.append(c)
            if escaped:escaped=False
            elif c=='\\':escaped=True
            elif c=='"':quoted=False
            continue
        if c=='"':quoted=True
        if c==',':
            j=i+1
            while j<len(clean) and clean[j].isspace():j+=1
            if j<len(clean) and clean[j] in '}]':continue
        out.append(c)
    return json.loads(''.join(out))

def atomic(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    payload=data.encode() if isinstance(data,str) else data
    fd,name=tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f: f.write(payload);f.flush();os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)

def save(path, value): atomic(path,json.dumps(value,indent=2,ensure_ascii=False)+'\n')

@contextlib.contextmanager
def lock(path):
    import fcntl
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        try: yield
        finally: fcntl.flock(f,fcntl.LOCK_UN)

def git(repo,*args):
    r=subprocess.run(['git','-C',str(repo),*args],capture_output=True)
    if r.returncode: raise ValueError(r.stderr.decode(errors='replace').strip())
    return r.stdout

def checkout(repo):
    return Path(os.fsdecode(git(Path(repo).expanduser().resolve(),'rev-parse','--show-toplevel')).strip()).resolve()

def source_path(repo, value):
    if not isinstance(value,str) or not value or '\0' in value: raise ValueError('Invalid source path')
    candidate=(repo/value).resolve()
    if not candidate.is_relative_to(repo) or candidate==repo: raise ValueError('Source path escapes checkout')
    return candidate

def snapshot(repo):
    result={}
    for raw in sorted(set(git(repo,'ls-files','--cached','--others','--exclude-standard','-z').split(b'\0'))):
        if not raw: continue
        name=os.fsdecode(raw);p=repo/name
        if p.is_symlink(): result[name]={'kind':'symlink','hash':sha(os.fsencode(os.readlink(p)))}
        elif p.is_file(): result[name]={'kind':'file','hash':sha(p.read_bytes()),'mode':p.stat().st_mode&0o7777}
    return result

def provenance(repo):
    repo=checkout(repo)
    try: head=git(repo,'rev-parse','HEAD').decode().strip()
    except ValueError: head=None
    branch=git(repo,'symbolic-ref','--short','-q','HEAD').decode().strip() if head is None else subprocess.run(
        ['git','-C',str(repo),'branch','--show-current'],capture_output=True,text=True).stdout.strip()
    files=snapshot(repo)
    return {'id':sha(os.fsencode(str(repo)))[:24],'checkout':str(repo),
        'git_common_dir':git(repo,'rev-parse','--path-format=absolute','--git-common-dir').decode().strip(),
        'branch':branch,'head':head,'source_state':sha(canonical(files).encode()),
        'dirty':bool(git(repo,'status','--porcelain','--untracked-files=normal'))}

def validate_config(value):
    if not isinstance(value,dict): raise ValueError('Configuration must be an object')
    allowed={'provider','gateway','credential_env','main_model','workers','platforms','model_capabilities','docs'}
    if set(value)-allowed: raise ValueError('Unknown or secret-valued configuration fields: '+','.join(set(value)-allowed))
    def no_secrets(obj):
        if isinstance(obj,dict):
            for k,v in obj.items():
                if re.search(r'(?i)(api.?key|token|password|secret|credential)$',k):
                    raise ValueError('Store only credential_env names, never credential values')
                no_secrets(v)
        elif isinstance(obj,list):
            for v in obj:no_secrets(v)
        elif isinstance(obj,str) and (re.search(r'(?i)\bBearer\s+\S+|\bsk-[A-Za-z0-9_-]{10,}',obj)):
            raise ValueError('Credential-looking values are forbidden')
    no_secrets(value)
    if value.get('provider','native') not in ('native','litellm'): raise ValueError('Choose native or litellm')
    if value.get('main_model') is not None and (not isinstance(value['main_model'],str) or not 1<=len(value['main_model'])<=250):raise ValueError('main_model must be an exact alias string')
    if value.get('gateway'):
        u=urlsplit(value['gateway'])
        if u.port is not None and not 1<=u.port<=65535:raise ValueError('Invalid gateway port')
        if any(c.isspace() for c in value['gateway']):raise ValueError('Gateway URL must not contain whitespace')
        if u.scheme not in ('https','http') or not u.hostname or u.username or u.password or u.query or u.fragment:
            raise ValueError('Gateway URL must have no credentials, query or fragment')
    env=value.get('credential_env','LITELLM_API_KEY')
    if not re.fullmatch(r'[A-Z_][A-Z0-9_]*',env): raise ValueError('credential_env must be an environment-variable name')
    for h,config in value.get('platforms',{}).items():
        if h not in ('opencode','codex','claude'):raise ValueError('Unknown platform')
        validate_config({**{k:v for k,v in value.items() if k!='platforms'},**config})
    if value.get('provider')=='litellm' and (not value.get('gateway') or not value.get('main_model')):
        raise ValueError('LiteLLM requires gateway and exact main_model alias')
    for kind,config in value.get('workers',{}).items():
        if kind not in TASKS or not isinstance(config,dict) or set(config)-{'model','effort','variant'}:
            raise ValueError('Invalid worker configuration')
    return value

class Context:
    def __init__(self,state=None,home=None):
        self.home=Path(home).expanduser().resolve() if home else Path.home().resolve()
        state=state or os.environ.get('GRAPH_LOOP_STATE_DIR')
        self.state=Path(state).expanduser().resolve() if state else self.home/'.local/state/graph-loop'
    def config(self):return load(self.state/'config.json',{})
    def local(self,repo):return self.state/'checkouts'/provenance(repo)['id']
    def emit(self,repo,kind,error):
        save(self.local(repo)/'pending'/('error-'+identifier(kind)+'.json'),{'kind':kind,'error':str(error),'at':now()})
