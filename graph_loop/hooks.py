"""Primary lifecycle adapters and Spotify-derived Shunt routing.
Routing ported from Spotify Shunt 0.2.0 (Apache-2.0), modified for native CLI tools,
modern hook output, instruction exemptions, exact cwd, and targeted head/tail reads.
"""
import json, os, re, shlex, subprocess, sys
from pathlib import Path
from .common import *
from . import runtime

INSTRUCTIONS={'AGENTS.md','CLAUDE.md','SKILL.md','GEMINI.md'}

def routing(repo,event):
    args=event.get('tool_input',{});name=event.get('tool_name','').lower()
    if not isinstance(args,dict):return None
    threshold=os.environ.get('SHUNT_MIN_LINES','350')
    minimum=int(threshold) if threshold.isdigit() else 350
    def large(raw):
        if not isinstance(raw,str) or not raw:return None
        path=(repo/os.path.expandvars(os.path.expanduser(raw))).resolve()
        if path.name in INSTRUCTIONS or path.suffix.lower() in ('.pdf','.png','.jpg','.jpeg','.gif','.webp'):return None
        try:
            with path.open('rb') as f:lines=sum(chunk.count(b'\n') for chunk in iter(lambda:f.read(65536),b''))
        except (OSError,ValueError):return None
        if lines>minimum:return f'shunt: File is {lines} lines (threshold: {minimum}). Use bulk-reader; use offset/limit for exact editing context.'
        return None
    if name in ('read','read_file'):
        if any(args.get(k) is not None for k in ('offset','limit','start_line','end_line','startLine','endLine')):return None
        return large(args.get('file_path',args.get('filePath',args.get('path'))))
    if name in ('bash','exec_command','shell'):
        command=args.get('command',args.get('cmd',''))
        if not isinstance(command,str) or '|' in command or '>' in command:return None
        try:tokens=shlex.split(command)
        except ValueError:return None
        if not tokens or tokens[0] not in ('cat','head','tail','less','more'):return None
        remaining=tokens[1:]
        if tokens[0] in ('head','tail'):
            for i,t in enumerate(remaining):
                if re.fullmatch(r'-\d+',t) or (t in ('-n','-c','--lines','--bytes') and i+1<len(remaining) and remaining[i+1].isdigit()):return None
        for token in remaining:
            if token.startswith('-'):continue
            reason=large(token)
            if reason:return reason
    return None

def receipt_source(ctx,repo,event):
    args=event.get('tool_input',{});name=event.get('tool_name','').lower()
    if name not in ('read','read_file') or not isinstance(args,dict):return None
    raw=args.get('file_path',args.get('filePath',args.get('path')))
    if not raw:return None
    path=source_path(repo,raw)
    lines=len(path.read_text().splitlines());start=args.get('offset',args.get('start_line',1))
    # Native read offsets in the supported APIs are one-based; do not invent an end beyond the file.
    start=max(1,start or 1);end=min(lines,start+(args.get('limit') or lines)-1)
    return {'path':str(path.relative_to(repo)),'hash':sha(path.read_bytes()),'start':start,'end':end}

def lifecycle(ctx,repo,harness,event):
    if os.environ.get('GRAPH_LOOP_WORKER')=='1':return {}
    repo=checkout(repo);ctx.active_repo=repo;kind=event.get('hook_event_name');session=event.get('session_id','unknown');tool=event.get('tool_use_id',event.get('tool_call_id','unknown'))
    model=event.get('model')
    if model and isinstance(model,(str,dict)):
        save(ctx.local(repo)/'primary-models'/f'{harness}.json',{'model':model,'at':now()})
    event_file=ctx.local(repo)/'tool-pending'/f'{sha((str(session)+str(tool)).encode())}.json'
    if kind=='PreToolUse':
        reason=routing(repo,event)
        if reason:return {'hookSpecificOutput':{'hookEventName':kind,'permissionDecision':'deny','permissionDecisionReason':reason}}
        try:
            read=receipt_source(ctx,repo,event)
            save(event_file,{'read':read,'source_state':provenance(repo)['source_state']})
        except (ValueError,OSError,UnicodeError):pass
    elif kind=='PostToolUse':
        prior=load(event_file)
        response=event.get('tool_response',{})
        observed=response.get('file',{}).get('content',response.get('content',response.get('output',''))) if isinstance(response,dict) else response
        if isinstance(observed,list):observed=''.join(p.get('text','') for p in observed if isinstance(p,dict))
        if isinstance(observed,str):observed='\n'.join(re.sub(r'^\s*\d+(?:→|\t|\| |: ?)', '', line) for line in observed.splitlines())
        successful=isinstance(response,dict) and not response.get('is_error') and response.get('status') not in ('error','failed')
        if prior and prior.get('read') and successful:
            read=prior['read']
            try:
                current=source_path(repo,read['path'])
                expected=''.join(current.read_text().splitlines(keepends=True)[read['start']-1:read['end']])
                if sha(current.read_bytes())==read['hash'] and expected and expected.strip() in str(observed):
                    runtime.exact_read(ctx,repo,read['path'],read['start'],read['end'],session,tool)
            except (ValueError,OSError,UnicodeError):pass
            event_file.unlink(missing_ok=True)
        response=event.get('tool_response',{})
        args=event.get('tool_input',{})
        if isinstance(response,dict) and isinstance(args,dict) and event.get('tool_name','').lower() in ('bash','exec_command','shell'):
            command=args.get('command',args.get('cmd'));code=response.get('exit_code')
            if isinstance(command,str):
                output=response.get('output',response.get('stdout',''))
                runtime.receipt(ctx,repo,'check',{'argv':[command],'cwd':str(repo),'exit_code':code,
                    'source_state':provenance(repo)['source_state'],'output_hash':sha(str(output).encode()),
                    'excerpt':str(output)[:4000],'session_id':session,'tool_call_id':tool},
                    isinstance(code,int) and not isinstance(code,bool) and '|' not in command and bool(prior)
                    and prior['source_state']==provenance(repo)['source_state'])
    elif kind in ('SessionStart','UserPromptSubmit'):
        runtime.refresh(ctx,repo,harness)
        return {'hookSpecificOutput':{'hookEventName':kind,'additionalContext':(SOURCE/'prompts/kickoff.md').read_text().replace('$REQUEST','').replace('$SPEC','')[:5000]}}
    elif kind in ('Stop','Idle'):
        runtime.refresh(ctx,repo,harness)
        conclusion=event.get('last_assistant_message','')
        if conclusion:runtime.curate(ctx,repo,harness,conclusion,session)
    return {}

def git_hooks(ctx,repo):
    repo=checkout(repo);directory=ctx.local(repo);manifest=load(directory/'git-hooks.json',[])
    known={v['path']:v for v in manifest};entries=[]
    hooks=Path(git(repo,'rev-parse','--git-path','hooks').decode().strip())
    if not hooks.is_absolute():hooks=repo/hooks
    hooks.mkdir(parents=True,exist_ok=True)
    command=shlex.join([sys.executable,str(SOURCE/'gl.py'),'--state-dir',str(ctx.state),'git-refresh'])
    for name in ('post-commit','post-checkout','post-merge','post-rewrite'):
        path=hooks/name;prior=known.get(str(path));backup=directory/'original-git-hooks'/name
        if prior and path.is_file() and sha(path.read_bytes())!=read['hash']:raise ValueError('Git hook edited after installation: '+str(path))
        if not prior and (path.exists() or path.is_symlink()):
            import shutil
            backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,backup)
        script='#!/bin/sh\n# graph-loop-skills owned post hook\nstatus=0\n'
        if backup.exists():script+=shlex.quote(str(backup))+' "$@" || status=$?\n'
        script+=command+' >/dev/null 2>&1 || true\nexit "$status"\n'
        atomic(path,script);path.chmod(0o755)
        entries.append({'path':str(path),'hash':sha(script.encode()),'backup':str(backup) if backup.exists() else None})
    save(directory/'git-hooks.json',entries)
    save(directory/'registered.json',provenance(repo))
    return {'hooks':[e['path'] for e in entries]}

def restore_git_hooks(ctx):
    import shutil
    for manifest in (ctx.state/'checkouts').glob('*/git-hooks.json'):
        for entry in load(manifest,[]):
            path=Path(entry['path'])
            if path.is_file() and sha(path.read_bytes())==entry['hash']:
                if entry['backup']:shutil.copy2(entry['backup'],path)
                else:path.unlink()
