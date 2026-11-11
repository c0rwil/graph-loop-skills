"""Owned installation plans; dry-run is entirely read-only."""
from __future__ import annotations
import copy, json, os, re, shlex, shutil, subprocess, sys, time, tomllib, venv
from pathlib import Path
from .common import *

MARKER='graph-loop-skills'

def locations(home,isolated=False):
    def path(env,default):
        value=Path(os.environ.get(env,str(default))).expanduser().resolve()
        if isolated and not value.is_relative_to(home):
            if default.resolve().is_relative_to(home):return default.resolve()
            raise ValueError('Configuration directory escapes isolated home through a symlink')
        return value
    return {'codex':path('CODEX_HOME',home/'.codex'),
            'claude':path('CLAUDE_CONFIG_DIR',home/'.claude'),
            'opencode':path('OPENCODE_CONFIG_DIR',path('XDG_CONFIG_HOME',home/'.config')/'opencode')}

def block(text,tag,body=None):
    start=f'# {MARKER}:{tag}:start';end=f'# {MARKER}:{tag}:end'
    pattern=re.compile(re.escape(start)+r'.*?'+re.escape(end)+r'\n?',re.S)
    replacement=start+'\n'+body.rstrip()+'\n'+end+'\n' if body is not None else ''
    return pattern.sub(lambda _:replacement,text) if pattern.search(text) else text.rstrip()+'\n'+replacement

def stamp(path):
    if path.is_symlink():return 'link:'+os.readlink(path)
    if path.is_file():return 'file:'+sha(path.read_bytes())
    if path.exists():return 'directory'
    return None

class Plan:
    def __init__(self,ctx,replace=False):
        self.ctx=ctx;self.replace=replace;self.old=load(ctx.state/'install.json',{'entries':[]})
        self.entries=[];self.actions=[];self.conflicts=[];self.warnings=[]
    def previous(self,path,kind,key=None):
        return next((e for e in self.old['entries'] if e['path']==str(path) and e['kind']==kind and e.get('key')==key),None)
    def file(self,path,data=None,target=None):
        path=Path(path);kind='link' if target else 'file';prior=self.previous(path,kind)
        expected='link:'+os.path.relpath(target,path.parent) if target else 'file:'+sha(data.encode())
        actual=stamp(path)
        original=prior.get('backup') if prior else None
        if actual and actual!=expected and (not prior or actual!=prior['stamp']):
            if not self.replace:self.conflicts.append(str(path));return
            original=str(self.ctx.state/'backups'/str(time.time_ns())/path.name)
            self.actions.append(('backup',path,Path(original)))
        if actual!=expected:self.actions.append((kind,path,target if target else data))
        self.entries.append({'kind':kind,'path':str(path),'stamp':expected,'backup':original})
    def structured(self,path,transform,key):
        path=Path(path);original=path.read_text() if path.exists() else ''
        data=transform(original)
        prior=self.previous(path,'block',key)
        # Track the owned block, not the full file: unrelated later edits are retained.
        start=f'# {MARKER}:{key}:start';end=f'# {MARKER}:{key}:end'
        pattern=re.compile(re.escape(start)+r'.*?'+re.escape(end)+r'\n?',re.S)
        current=pattern.search(original);new=pattern.search(data)
        if current and (not prior or current.group()!=prior['owned']):
            if not self.replace:self.conflicts.append(str(path)+':'+key);return
            self.actions.append(('backup-copy',path,self.ctx.state/'backups'/str(time.time_ns())/path.name))
        if data!=original:self.actions.append(('file',path,data))
        self.entries.append({'kind':'block','path':str(path),'key':key,'owned':new.group() if new else '',
                             'original':prior['original'] if prior else (current.group() if current else '')})
    def json(self,path,key,value):
        path=Path(path);data=load(path,{})
        prior=self.previous(path,'json',key);parts=key.split('/');parent=data
        for name in parts[:-1]:
            if name not in parent:parent[name]={}
            if not isinstance(parent[name],dict):self.conflicts.append(str(path)+':'+key);return
            parent=parent[name]
        name=parts[-1];exists=name in parent;current=parent.get(name)
        if exists and current!=value and (not prior or current!=prior['owned']):
            if not self.replace:self.conflicts.append(str(path)+':'+key);return
            self.actions.append(('backup-copy',path,self.ctx.state/'backups'/str(time.time_ns())/path.name))
        if current!=value:parent[name]=value
        # Multiple changes to one JSON file compose in memory.
        old_action=next((a for a in self.actions if a[0]=='json' and a[1]==path),None)
        if old_action:
            self.actions.remove(old_action)
            old_data=old_action[2];p=old_data
            for part in parts[:-1]:p=p.setdefault(part,{})
            p[name]=value;data=old_data
        if not exists or current!=value or old_action:self.actions.append(('json',path,data))
        self.entries.append({'kind':'json','path':str(path),'key':key,'owned':value,
            'had_original':prior['had_original'] if prior else exists,'original':prior.get('original') if prior else current})
    def list_item(self,path,key,value):
        path=Path(path);data=load(path,{})
        values=data.setdefault(key,[])
        if not isinstance(values,list):raise ValueError('Expected configuration array: '+key)
        if value not in values:values.append(value)
        old_action=next((a for a in self.actions if a[0]=='json' and a[1]==path),None)
        if old_action:
            self.actions.remove(old_action);combined=old_action[2];combined[key]=values;data=combined
        self.actions.append(('json',path,data))
        self.entries.append({'kind':'list','path':str(path),'key':key,'owned':value})
    def hooks(self,path,command,events):
        path=Path(path);data=load(path,{})
        for event in events:
            key='hooks/'+event
            groups=data.get('hooks',{}).get(event,[])
            prior=self.previous(path,'hook',key)
            owned=prior.get('owned') if prior else None
            clean=[g for g in groups if g!=owned]
            value={'hooks':[{'type':'command','command':command,'timeout':300}]}
            if value not in clean:clean.append(value)
            data.setdefault('hooks',{})[event]=clean
            self.entries.append({'kind':'hook','path':str(path),'key':key,'owned':value})
        self.actions.append(('json',path,data))
    def execute(self):
        if self.conflicts:raise ValueError('Conflicts (use --replace for preserved backups): '+', '.join(self.conflicts))
        for kind,path,value in self.actions:
            path.parent.mkdir(parents=True,exist_ok=True)
            if kind in ('backup','backup-copy'):
                value.parent.mkdir(parents=True,exist_ok=True)
                if kind=='backup':shutil.move(str(path),str(value))
                elif path.is_file():shutil.copy2(path,value)
            elif kind=='link':
                if path.is_symlink():path.unlink()
                path.symlink_to(os.path.relpath(value,path.parent),target_is_directory=Path(value).is_dir())
            elif kind=='json':save(path,value)
            else:atomic(path,value)
        keys={(e['kind'],e['path'],e.get('key')) for e in self.entries}
        retained=[e for e in self.old['entries'] if (e['kind'],e['path'],e.get('key')) not in keys]
        save(self.ctx.state/'install.json',{'entries':retained+self.entries,'source':str(SOURCE),'at':now()})

def provider_options(ctx,harness):
    cfg=ctx.config();choice={**cfg.get('provider',{}),**cfg.get('provider',{}).get('platforms',{}).get(harness,{})}
    return choice

def install(ctx,platforms,provider,skills_dir=None,graphify_path=None,skip_deps=False,isolated=False,replace=False,dry_run=False):
    validate_config(provider)
    dirs=locations(ctx.home,isolated);central=Path(skills_dir).expanduser().resolve() if skills_dir else (ctx.home/'.local/share/graph-loop/skills').resolve()
    if isolated and (not central.is_relative_to(ctx.home) or not ctx.state.is_relative_to(ctx.home)):
        raise ValueError('Isolated home paths must stay inside --home')
    if ctx.state.is_relative_to(SOURCE) or central.is_relative_to(SOURCE):raise ValueError('Runtime state and central skills must be outside the repository')
    selected=list(dict.fromkeys(['opencode','codex','claude'] if 'all' in platforms else platforms))
    selected=list(dict.fromkeys(ctx.config().get('platforms',[])+selected))
    if not selected or any(p not in dirs for p in selected):raise ValueError('Choose opencode, codex, claude, or all')
    plan=Plan(ctx,replace)
    for name in SKILLS:
        plan.file(central/name,target=SOURCE/'skills'/name)
    plan.file(ctx.home/'.local/bin/graph-loop',target=SOURCE/'gl.py')
    common=[sys.executable,str(SOURCE/'gl.py'),'--state-dir',str(ctx.state)]
    mcp={'command':sys.executable,'args':common[1:]+['mcp']}
    kickoff=(SOURCE/'prompts/kickoff.md').read_text().replace('$REQUEST','').replace('$SPEC','')
    for h in selected:
        folder=dirs[h]
        skills=(ctx.home/'.agents/skills') if h=='codex' else folder/'skills'
        for name in SKILLS:plan.file(skills/name,target=central/name)
        instructions=folder/('AGENTS.md' if h=='codex' else 'CLAUDE.md' if h=='claude' else 'AGENTS.md')
        plan.structured(instructions,lambda text:block(text,'workflow',kickoff),'workflow')
        command=shlex.join(common+['hook','--harness',h])
        if h=='codex':
            file=folder/'config.toml';original=file.read_text() if file.exists() else ''
            cfg=tomllib.loads(original)
            if 'graph_loop' in cfg.get('mcp_servers',{}) and MARKER not in original:
                plan.conflicts.append(str(file)+':mcp_servers.graph_loop')
            body='[mcp_servers.graph_loop]\ncommand = '+json.dumps(mcp['command'])+'\nargs = '+json.dumps(mcp['args'])
            plan.structured(file,lambda text:block(text,'mcp',body),'mcp')
            plan.hooks(folder/'hooks.json',command,['SessionStart','UserPromptSubmit','PreToolUse','PostToolUse','Stop'])
        elif h=='claude':
            plan.hooks(folder/'settings.json',command,['SessionStart','UserPromptSubmit','PreToolUse','PostToolUse','Stop'])
            # This is Claude's documented user MCP store; leave all authentication untouched.
            store=ctx.home/'.claude.json' if folder==ctx.home/'.claude' else folder/'.claude.json'
            plan.json(store,'mcpServers/graph_loop',mcp)
            for name in ('kickoff','align','finish','graphify','workspace','bulk-reader','code-writer'):
                plan.file(folder/'commands'/f'graph-loop-{name}.md',data=(SOURCE/'prompts'/f'{name}.md').read_text())
        else:
            plugin=ctx.state/'opencode-plugin'
            # No source-path assumptions in the plugin: an owned entry supplies runtime options.
            definition='import base from '+json.dumps((SOURCE/'adapters/opencode.mjs').as_uri())+';\nexport default base('+canonical({'command':common,'state':str(ctx.state)})+');\n'
            plan.file(plugin/'index.js',data=definition)
            plan.file(plugin/'package.json',data=canonical({'name':'graph-loop-skills','version':'2.0.0','type':'module','exports':{'.':'./index.js'}}))
            oc_file=folder/('opencode.jsonc' if (folder/'opencode.jsonc').exists() else 'opencode.json')
            plan.list_item(oc_file,'plugins',str(plugin))
            plan.json(oc_file,'mcp/servers/graph_loop',{'type':'local','command':common+['mcp']})
            # A separate documented config layer preserves JSONC and all existing providers.
            for name in ('kickoff','align','finish','graphify','workspace','bulk-reader','code-writer'):
                plan.file(folder/'commands'/f'graph-loop-{name}.md',data=(SOURCE/'prompts'/f'{name}.md').read_text())
    config={'provider':provider,'platforms':selected,'locations':{k:str(v) for k,v in dirs.items()},'skills_dir':str(central),
            'graphify':str(Path(graphify_path).expanduser().resolve()) if graphify_path else str(ctx.state/'venv/bin/graphify'),
            'docs':provider.get('docs',{}),'source':str(SOURCE),'home':str(ctx.home)}
    plan.file(ctx.state/'provider.json',data=json.dumps(provider,indent=2)+'\n')
    report={'platforms':selected,'provider':provider['provider'],'source':str(SOURCE),'skills':list(SKILLS),
            'state':str(ctx.state),'central_skills':str(central),'actions':[{'kind':k,'path':str(p)} for k,p,_ in plan.actions],
            'conflicts':plan.conflicts,'dry_run':dry_run,'native_defaults':'preserved; use graph-loop launch for selected provider'}
    if isolated:
        for kind,path,value in plan.actions:
            if not path.parent.resolve().is_relative_to(ctx.home) or (path.is_symlink() and not path.resolve().is_relative_to(ctx.home) and kind!='link'):raise ValueError('Installation target escapes isolated home')
    if dry_run:return report
    if plan.conflicts:raise ValueError('Conflicts (use --replace for backups): '+', '.join(plan.conflicts))
    if not skip_deps:
        if not graphify_path:
            venv.EnvBuilder(with_pip=True).create(ctx.state/'venv')
            subprocess.run([str(ctx.state/'venv/bin/python'),'-m','pip','install','-r',str(SOURCE/'requirements.txt')],check=True,capture_output=True,env={**os.environ,'HOME':str(ctx.home),'PIP_CACHE_DIR':str(ctx.state/'pip-cache')})
    if not Path(config['graphify']).is_file():raise ValueError('Provide an existing --graphify with --skip-deps')
    version=subprocess.check_output([config['graphify'],'--version'],text=True).strip()
    if version!='graphify 0.9.104':raise ValueError('Tested dependency is graphifyy==0.9.104, found '+version)
    with lock(ctx.state/'install.lock'):
        plan.execute();save(ctx.state/'config.json',config)
    return report

def uninstall(ctx,dry_run=False):
    manifest=load(ctx.state/'install.json',{'entries':[]});restored=[];preserved=[]
    for e in reversed(manifest['entries']):
        path=Path(e['path']);kind=e['kind']
        if kind in ('file','link'):
            if stamp(path)!=e['stamp']:preserved.append(str(path));continue
            restored.append(str(path))
            if not dry_run:
                path.unlink()
                if e.get('backup') and Path(e['backup']).exists():shutil.move(e['backup'],path)
        elif kind=='block':
            text=path.read_text() if path.exists() else ''
            if e['owned'] not in text:preserved.append(str(path));continue
            restored.append(str(path)+':'+e['key'])
            if not dry_run:atomic(path,text.replace(e['owned'],e.get('original',''),1))
        elif kind in ('json','hook','list'):
            data=load(path,{});parent=data;parts=e['key'].split('/')
            try:
                for part in parts[:-1]:parent=parent[part]
                current=parent[parts[-1]]
            except (KeyError,TypeError):continue
            if kind in ('hook','list'):
                if e['owned'] in current:
                    if not dry_run:parent[parts[-1]]=[v for v in current if v!=e['owned']];save(path,data)
                    restored.append(str(path)+':'+e['key'])
                else:preserved.append(str(path)+':'+e['key'])
            elif current==e['owned']:
                restored.append(str(path)+':'+e['key'])
                if not dry_run:
                    if e['had_original']:parent[parts[-1]]=e['original']
                    else:del parent[parts[-1]]
                    save(path,data)
            else:preserved.append(str(path)+':'+e['key'])
    if not dry_run and (ctx.state/'install.json').exists():(ctx.state/'install.json').unlink()
    return {'restored':restored,'preserved_user_edits':preserved,'retained':'runtime evidence, graphs, dependency environments and backups','dry_run':dry_run}

def doctor(ctx):
    config=ctx.config();manifest=load(ctx.state/'install.json',{'entries':[]})
    return {'source':str(SOURCE),'branch':subprocess.run(['git','-C',str(SOURCE),'branch','--show-current'],capture_output=True,text=True).stdout.strip(),
        'state':str(ctx.state),'python':sys.version.split()[0],
        'harnesses':{h:shutil.which(h) for h in ('opencode','codex','claude')},
        'provider':config.get('provider',{}).get('provider'),'credential_present':bool(os.environ.get(config.get('provider',{}).get('credential_env','LITELLM_API_KEY'))),
        'modified_owned_files':[e['path'] for e in manifest['entries'] if e['kind'] in ('file','link') and stamp(Path(e['path']))!=e['stamp']],
        'graphify':config.get('graphify'),'platforms':config.get('platforms',[]),
        'trust':'Review Codex hooks in /hooks; restart harnesses; no trust hashes or credentials are copied.'}
