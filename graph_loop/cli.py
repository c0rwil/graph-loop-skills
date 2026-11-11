"""Portable command line entrypoint."""
import argparse,json,os,sys,subprocess
from pathlib import Path
from .common import *
from . import api,install,hooks,runtime,workers,mcp

def parser():
    p=argparse.ArgumentParser(description='Graph Loop Skills: seven portable skills, one shared runtime.')
    p.add_argument('--state-dir');p.add_argument('--home');p.add_argument('--repo',default='.')
    sub=p.add_subparsers(dest='command',required=True)
    s=sub.add_parser('install');s.add_argument('--platform',nargs='+',choices=['opencode','codex','claude','all'],required=True)
    s.add_argument('--provider',choices=['native','litellm']);s.add_argument('--gateway');s.add_argument('--credential-env');s.add_argument('--main-model')
    s.add_argument('--worker-model',action='append',default=[]);s.add_argument('--worker-effort',action='append',default=[])
    s.add_argument('--config',type=Path);s.add_argument('--skills-dir');s.add_argument('--graphify');s.add_argument('--skip-deps',action='store_true');s.add_argument('--replace',action='store_true');s.add_argument('--dry-run',action='store_true')
    s=sub.add_parser('uninstall');s.add_argument('--dry-run',action='store_true')
    sub.add_parser('doctor');sub.add_parser('mcp');sub.add_parser('tools')
    s=sub.add_parser('invoke');s.add_argument('name');s.add_argument('--input',default='-')
    s=sub.add_parser('hook');s.add_argument('--harness',choices=['opencode','codex','claude'],required=True)
    sub.add_parser('git-hooks');sub.add_parser('git-refresh')
    s=sub.add_parser('refresh');s.add_argument('--harness',default='codex');s.add_argument('--code-only',action='store_true');s.add_argument('--allow-shrink',action='store_true')
    sub.add_parser('status')
    s=sub.add_parser('workspace');s.add_argument('action',choices=['register','merge','align']);s.add_argument('name');s.add_argument('members',nargs='*');s.add_argument('--spec');s.add_argument('--run',action='store_true')
    for command in ('query','path','explain'):
        s=sub.add_parser(command);s.add_argument('terms',nargs='+');s.add_argument('--workspace');s.add_argument('--harness',default='codex')
    s=sub.add_parser('read');s.add_argument('path');s.add_argument('--start',type=int,default=1);s.add_argument('--end',type=int)
    s=sub.add_parser('check');s.add_argument('--criterion');s.add_argument('--timeout',type=int,default=120);s.add_argument('argv',nargs=argparse.REMAINDER)
    s=sub.add_parser('finding');s.add_argument('--text',required=True);s.add_argument('--receipts',nargs='+',required=True);s.add_argument('--outcome',default='useful');s.add_argument('--correction');s.add_argument('--corrects')
    s=sub.add_parser('bulk-read');s.add_argument('--question',required=True);s.add_argument('--paths',nargs='+',required=True);s.add_argument('--harness',default=os.environ.get('SHUNT_HARNESS','codex'))
    s=sub.add_parser('code-write');s.add_argument('--spec',required=True);s.add_argument('--reference',required=True);s.add_argument('--target');s.add_argument('--harness',default=os.environ.get('SHUNT_HARNESS','codex'))
    s=sub.add_parser('prompt');s.add_argument('name');s.add_argument('--request');s.add_argument('--spec')
    s=sub.add_parser('launch');s.add_argument('harness',choices=['opencode','codex','claude']);s.add_argument('argv',nargs=argparse.REMAINDER)
    return p

def stdin_object():
    raw=sys.stdin.read(1000001)
    if len(raw.encode())>1000000:raise ValueError('Input exceeds 1 MB')
    value=json.loads(raw)
    if not isinstance(value,dict):raise ValueError('Expected a JSON object')
    return value

def main():
    args=parser().parse_args();ctx=Context(args.state_dir,args.home)
    try:
        c=args.command
        if c=='install':
            cfg=load(args.config,{}) if args.config else {}
            for k in ('provider','gateway','credential_env','main_model'):
                v=getattr(args,k)
                if v is not None:cfg[k]=v
            if not cfg.get('provider'):raise ValueError('Choose --provider native or litellm')
            for field,values in [('model',args.worker_model),('effort',args.worker_effort)]:
                for raw in values:
                    task,value=raw.split('=',1);cfg.setdefault('workers',{}).setdefault(task,{})[field]=value
            result=install.install(ctx,args.platform,cfg,args.skills_dir,args.graphify,args.skip_deps,bool(args.home),args.replace,args.dry_run)
        elif c=='uninstall':
            if not args.dry_run:hooks.restore_git_hooks(ctx)
            result=install.uninstall(ctx,args.dry_run)
        elif c=='doctor':result=install.doctor(ctx)
        elif c=='tools':result={k:{'description':v[0],'inputSchema':v[1]} for k,v in api.TOOLS.items()}
        elif c=='mcp':mcp.serve(ctx);return 0
        elif c=='invoke':
            payload=stdin_object() if args.input=='-' else json.loads(args.input)
            result=api.call(ctx,args.name,payload)
        elif c=='hook':
            event=stdin_object()
            try:result=hooks.lifecycle(ctx,event.get('cwd',args.repo),args.harness,event)
            except Exception as exc:
                try:ctx.emit(checkout(event.get('cwd',args.repo)),'lifecycle',exc)
                except Exception:pass
                result={'systemMessage':'Graph Loop pending: '+str(exc)[:1000]}
        elif c=='git-hooks':result=hooks.git_hooks(ctx,args.repo)
        elif c=='git-refresh':
            repo=checkout(args.repo)
            if not (ctx.local(repo)/'registered.json').exists():return 0
            result=runtime.refresh(ctx,repo,semantic=False)
        elif c=='refresh':result=runtime.refresh(ctx,args.repo,args.harness,not args.code_only,args.allow_shrink)
        elif c=='status':result=runtime.status(ctx,args.repo)
        elif c=='workspace':
            if args.action=='register':result=runtime.register(ctx,args.name,args.members,args.spec)
            elif args.action=='merge':result=runtime.merge_workspace(ctx,args.name)
            else:result=api.call(ctx,'align_contract',{'name':args.name,'run':args.run})
        elif c in ('query','path','explain'):result=runtime.query(ctx,args.repo,c,args.terms,args.harness,args.workspace)
        elif c=='read':result=runtime.exact_read(ctx,args.repo,args.path,args.start,args.end)
        elif c=='check':
            argv=args.argv[1:] if args.argv and args.argv[0]=='--' else args.argv
            result=api.call(ctx,'check',{'repo':args.repo,'argv':argv,'timeout':args.timeout,**({'criterion':args.criterion} if args.criterion else {})})
        elif c=='finding':result=api.call(ctx,'finding',{k:v for k,v in {'repo':args.repo,'text':args.text,'receipts':args.receipts,'outcome':args.outcome,'correction':args.correction,'corrects':args.corrects}.items() if v is not None})
        elif c=='bulk-read':result=api.call(ctx,'bulk_read',{'repo':args.repo,'paths':args.paths,'question':args.question,'harness':args.harness});print(result['text']);return 0
        elif c=='code-write':
            result=api.call(ctx,'code_write',{k:v for k,v in {'repo':args.repo,'reference':args.reference,'spec':args.spec,'harness':args.harness,'target':args.target}.items() if v is not None})
            if result.get('text') is not None:print(result['text'],end='');return 0
        elif c=='prompt':result=api.call(ctx,'prompt',{k:v for k,v in {'name':args.name,'request':args.request,'spec':args.spec}.items() if v is not None})
        elif c=='launch':return workers.launch(ctx,args.harness,args.argv[1:] if args.argv and args.argv[0]=='--' else args.argv)
        print(json.dumps(result,indent=2,ensure_ascii=False))
        if c=='check' and (result['exit_code']!=0 or not result['verified']):return 1
        return 0
    except (ValueError,KeyError,TypeError,OSError,subprocess.SubprocessError) as exc:
        print('graph-loop: '+str(exc)[:3000],file=sys.stderr);return 1
