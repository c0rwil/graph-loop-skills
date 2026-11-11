#!/usr/bin/env python3
"""Opt-in paid/native smoke: no auth copying or user configuration edits."""
import argparse,ast,json,os,subprocess,sys,tempfile
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from graph_loop.common import Context,save
from graph_loop import runtime,workers
p=argparse.ArgumentParser();p.add_argument('--harness',nargs='+',choices=['codex','claude','opencode'],default=['codex','claude','opencode']);p.add_argument('--graphify',required=True);p.add_argument('--directory');args=p.parse_args()
base=Path(args.directory).resolve() if args.directory else Path(tempfile.mkdtemp(prefix='graph-loop-live-')).resolve();base.mkdir(parents=True,exist_ok=True)
repo=base/'repository';repo.mkdir(exist_ok=True)
if not (repo/'.git').exists():subprocess.run(['git','init','-q',str(repo)],check=True)
(repo/'reference.py').write_text('def reference():\n    return 7\n')
(repo/'behavior.md').write_text('The generated function returns the integer seven.\n')
ctx=Context(base/'state');save(ctx.state/'config.json',{'graphify':str(Path(args.graphify).resolve()),'provider':{'provider':'native'}})
report={'directory':str(base),'workers':[],'checks':[]}
for harness in args.harness:
 print('Testing native '+harness,flush=True)
 try:
  answer=workers.bulk_read(ctx,repo,['reference.py'],'What integer is returned? Cite its source line.',harness)
  target=harness+'_generated.py'
  workers.code_write(ctx,repo,'reference.py','Generate exactly def generated(): returning 7. Match the two-line reference; no imports or other statements.',harness,target)
  tree=ast.parse((repo/target).read_text())
  assert len(tree.body)==1 and isinstance(tree.body[0],ast.FunctionDef) and tree.body[0].name=='generated'
  assert len(tree.body[0].body)==1 and isinstance(tree.body[0].body[0],ast.Return) and isinstance(tree.body[0].body[0].value,ast.Constant) and tree.body[0].body[0].value.value==7
  report['workers'].append({'harness':harness,'reader':'passed','writer':'passed','source_cited':'reference.py' in answer['text']})
 except Exception as exc:report['workers'].append({'harness':harness,'error':str(exc)})
for result in report['workers']:
 if result.get('writer')=='passed':
  harness=result['harness'];r=runtime.run_check(ctx,repo,[sys.executable,'-B','-c',f'import {harness}_generated as m; assert m.generated()==7'],criterion='generated-'+harness)
  report['checks'].append({'harness':harness,'receipt':r['id'],'exit_code':r['exit_code'],'verified':r['verified']})
try:
 runtime.refresh(ctx,repo,'claude');report['semantic_refresh']='passed';report['semantic_pending']=runtime.status(ctx,repo)['meta']['pending_documents']
 source=runtime.exact_read(ctx,repo,'reference.py',1,2)
 results=runtime.curate(ctx,repo,'claude','The reference and all successful generated functions return 7, as shown by explicit acceptance checks.')
 report['automatic_curator_findings']=len(results)
except Exception as exc:report['semantic_or_curator_error']=str(exc)
save(base/'report.json',report);print(json.dumps(report,indent=2),flush=True)
raise SystemExit(0 if all(r.get('writer')=='passed' for r in report['workers']) and all(r['verified'] and r['exit_code']==0 for r in report['checks']) and not report.get('semantic_or_curator_error') else 1)
