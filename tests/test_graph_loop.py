import importlib.util,json,os,shlex,shutil,subprocess,sys,tempfile,threading,unittest
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from unittest.mock import patch
from graph_loop.common import *
from graph_loop import install,runtime,workers,hooks,api

GRAPHIFY=os.environ.get('GRAPH_LOOP_GRAPHIFY',shutil.which('graphify') or '')

class Loop(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='graph loop validation ');self.addCleanup(self.tmp.cleanup)
  self.base=Path(self.tmp.name).resolve();self.home=self.base/'home';self.home.mkdir();self.ctx=Context(self.home/'state',self.home)
  self.repo=self.base/'repo';self.repo.mkdir();git(self.repo,'init','-qb','main');git(self.repo,'config','user.name','test');git(self.repo,'config','user.email','test@example.invalid')
  (self.repo/'app.py').write_text('def value():\n    return 7\n\ndef caller():\n    return value()\n')
  (self.repo/'.gitignore').write_text('__pycache__/\n');git(self.repo,'add','.');git(self.repo,'commit','-qm','initial')
  save(self.ctx.state/'config.json',{'graphify':GRAPHIFY,'provider':{'provider':'native'}})
 def install(self,platforms=('all',),provider=None,**kw):
  return install.install(self.ctx,list(platforms),provider or {'provider':'native'},graphify_path=GRAPHIFY,skip_deps=True,isolated=True,**kw)
 def test_exactly_seven(self):self.assertEqual({p.parent.name for p in (SOURCE/'skills').glob('*/SKILL.md')},set(SKILLS))
 def test_six_installs_and_idempotence(self):
  for h in ('codex','claude','opencode'):
   for provider in ({'provider':'native'},{'provider':'litellm','gateway':'https://gateway.example.invalid/v1','main_model':'exact/alias'}):
    with self.subTest(h=h,provider=provider):
     self.install((h,),provider);before={str(p):p.read_bytes() for p in self.home.rglob('*') if p.is_file() and not p.is_symlink() and p.name not in ('install.json','install.lock')}
     self.install((h,),provider);after={str(p):p.read_bytes() for p in self.home.rglob('*') if p.is_file() and not p.is_symlink() and p.name not in ('install.json','install.lock')}
     self.assertEqual(before,after)
     install.uninstall(self.ctx)
 def test_dry_run_changes_nothing(self):
  before=sorted(str(p) for p in self.base.rglob('*'));r=self.install(dry_run=True);self.assertTrue(r['dry_run']);self.assertEqual(before,sorted(str(p) for p in self.base.rglob('*')))
 def test_preserve_existing_settings_later_edits_and_platform_ownership(self):
  settings=self.home/'.claude/settings.json';save(settings,{'model':'user-model','hooks':{'Stop':[{'hooks':[{'type':'command','command':'echo user'}]}]}})
  self.install(('codex',));self.install(('claude',));data=load(settings);data['later']='keep';save(settings,data)
  install.uninstall(self.ctx);self.assertEqual(load(settings),{'model':'user-model','later':'keep','hooks':{'Stop':[{'hooks':[{'type':'command','command':'echo user'}]}],'SessionStart':[],'UserPromptSubmit':[],'PreToolUse':[],'PostToolUse':[]}})
  self.assertFalse((self.home/'.agents/skills/graph-loop').exists())
 def test_conflict_backup_and_changed_owned_file(self):
  path=self.home/'.agents/skills/ponytail';path.mkdir(parents=True);(path/'mine').write_text('original')
  with self.assertRaisesRegex(ValueError,'Conflicts'):self.install(('codex',))
  self.install(('codex',),replace=True);self.assertTrue(path.is_symlink());install.uninstall(self.ctx);self.assertEqual((path/'mine').read_text(),'original')
 def test_isolated_symlink_escape(self):
  outside=self.base/'outside';outside.mkdir();(self.home/'.codex').symlink_to(outside,target_is_directory=True)
  with self.assertRaisesRegex(ValueError,'escapes'):self.install(('codex',))
  self.assertEqual(list(outside.iterdir()),[])
 def test_provider_validation_alias_inheritance_and_secrets(self):
  validate_config({'provider':'litellm','gateway':'https://gateway.example.invalid/v1','main_model':'main','platforms':{'codex':{'main_model':'exact-codex'}}})
  for bad in ({'provider':'litellm','gateway':'https://user:password@example.invalid/v1','main_model':'x'}, {'api_key':'not-a-credential'}, {'credential_env':'not an env'}):
   with self.assertRaises(ValueError):validate_config(bad)
 def test_native_switch_preserves_user_provider_defaults(self):
  path=self.home/'.codex/config.toml';path.parent.mkdir();path.write_text('model = "user-model"\n')
  self.install(('codex',),{'provider':'litellm','gateway':'https://gateway.example.invalid/v1','main_model':'exact'})
  self.install(('codex',),{'provider':'native'});self.assertIn('model = "user-model"',path.read_text());self.assertEqual(self.ctx.config()['provider']['provider'],'native')
 def test_graph_identity_merge_failure_preservation_and_shrink(self):
  other=self.base/'other';git(self.repo,'worktree','add','-qb','other',str(other))
  runtime.refresh(self.ctx,self.repo,semantic=False);runtime.refresh(self.ctx,other,semantic=False)
  runtime.register(self.ctx,'product',['one='+str(self.repo),'two='+str(other)])
  r=runtime.merge_workspace(self.ctx,'product');self.assertNotEqual(r['inputs'][0]['id'],r['inputs'][1]['id'])
  graph=load(self.ctx.state/'workspaces/product/graph.json');self.assertEqual(len({n['id'] for n in graph['nodes']}),len(graph['nodes']))
  self.assertTrue(all('branch' in m and 'head' in m and 'source_state' in m and 'input_graph_hash' in m for m in r['inputs']))
  original=(self.ctx.state/'workspaces/product/graph.json').read_bytes();(other/'new.py').write_text('def new(): return 8\n')
  with self.assertRaisesRegex(ValueError,'Stale'):runtime.merge_workspace(self.ctx,'product')
  self.assertEqual((self.ctx.state/'workspaces/product/graph.json').read_bytes(),original)
  old=(self.ctx.local(self.repo)/'graph.json').read_bytes();(self.repo/'app.py').write_text('')
  with self.assertRaisesRegex(ValueError,'shrink'):runtime.refresh(self.ctx,self.repo,semantic=False)
  self.assertEqual((self.ctx.local(self.repo)/'graph.json').read_bytes(),old)
 def test_receipts_stale_mode_pipeline_and_finding_dedup(self):
  source=runtime.exact_read(self.ctx,self.repo,'app.py',1,2);check=runtime.run_check(self.ctx,self.repo,[sys.executable,'-c','assert 1==1'])
  self.assertTrue(check['verified']);self.assertEqual(check['exit_code'],0)
  runtime.refresh(self.ctx,self.repo,semantic=False)
  first=runtime.finding(self.ctx,self.repo,'Verified value',[source['id'],check['id']]);second=runtime.finding(self.ctx,self.repo,'Reworded same evidence',[check['id'],source['id']])
  self.assertEqual(first['id'],second['id']);self.assertTrue((self.ctx.local(self.repo)/'LESSONS.md').exists())
  with self.assertRaises(ValueError):runtime.finding(self.ctx,self.repo,'Correction',[source['id']],'corrected')
  pipeline=runtime.run_check(self.ctx,self.repo,['sh','-c','false | true']);self.assertFalse(pipeline['verified'])
  (self.repo/'app.py').chmod(0o755)
  with self.assertRaisesRegex(ValueError,'stale'):runtime.current_receipt(self.ctx,self.repo,source['id'])
 def test_native_hook_denied_read_and_mutating_check_not_verified(self):
  event={'hook_event_name':'PreToolUse','tool_name':'Read','tool_use_id':'read','session_id':'s','tool_input':{'file_path':'app.py'}}
  hooks.lifecycle(self.ctx,self.repo,'codex',event);hooks.lifecycle(self.ctx,self.repo,'codex',{**event,'hook_event_name':'PostToolUse','tool_response':{'is_error':True,'error':'Read denied'}})
  self.assertEqual(list((self.ctx.local(self.repo)/'receipts').glob('*.json')),[])
  event={'hook_event_name':'PreToolUse','tool_name':'Bash','tool_use_id':'check','session_id':'s','tool_input':{'command':'python check.py'}}
  hooks.lifecycle(self.ctx,self.repo,'codex',event);(self.repo/'app.py').write_text('changed\n')
  hooks.lifecycle(self.ctx,self.repo,'codex',{**event,'hook_event_name':'PostToolUse','tool_response':{'exit_code':0,'output':'ok'}})
  r=load(next((self.ctx.local(self.repo)/'receipts').glob('*.json')));self.assertFalse(r['verified'])
 def test_documents_complete_coverage_reuse_stale_and_pending(self):
  p=self.repo/'spec.md';p.write_text('A complete behavior contract.\n')
  def extract(ctx,harness,task,prompt,**kw):
   batch=json.loads(prompt.split('\n',1)[1]);self.assertEqual(batch[0]['text'],p.read_text());item=batch[0]
   return canonical({'coverage':[{'path':item['path'],'source_hash':item['source_hash'],'line_start':1,'line_end':item['lines']}],
    'nodes':[{'id':'behavior','label':'behavior','path':item['path'],'line':1,'source_hash':item['source_hash']}],'links':[]})
  with patch('graph_loop.workers.text',side_effect=extract) as mock:
   runtime.refresh(self.ctx,self.repo);runtime.refresh(self.ctx,self.repo);self.assertEqual(mock.call_count,1)
  with self.assertRaises(ValueError):runtime.check_semantic({'coverage':[]},[])
  p.write_text('Changed complete contract.\n')
  with patch('graph_loop.workers.text',return_value='{"coverage":[]}'):
   with self.assertRaisesRegex(ValueError,'pending'):runtime.refresh(self.ctx,self.repo)
  self.assertTrue(load(self.ctx.local(self.repo)/'pending/documents.json')['pending'])
 def test_atomic_new_file_and_parent_swap(self):
  (self.repo/'out').mkdir()
  with patch('graph_loop.workers.text',return_value='def generated(): return 7\n'):
   workers.code_write(self.ctx,self.repo,'app.py','Generate','codex','out/new.py')
   with self.assertRaises(ValueError):workers.code_write(self.ctx,self.repo,'app.py','Generate','codex','out/new.py')
  outside=self.base/'external';outside.mkdir()
  def swap(*a,**kw):
   (self.repo/'out').rename(self.repo/'old');(self.repo/'out').symlink_to(outside,target_is_directory=True);return 'payload'
  with patch('graph_loop.workers.text',side_effect=swap):
   with self.assertRaises((ValueError,OSError)):workers.code_write(self.ctx,self.repo,'app.py','Generate','codex','out/escape.py')
  self.assertFalse((outside/'escape.py').exists())
 def test_worker_complete_inputs_and_reference_validation(self):
  with patch('graph_loop.workers.text',return_value='- app.py:2 returns 7') as mock:
   r=workers.bulk_read(self.ctx,self.repo,['app.py'],'What value?','claude');self.assertIn((self.repo/'app.py').read_text(),mock.call_args.args[3]);self.assertFalse(r['verified'])
  with self.assertRaises(ValueError):workers.code_write(self.ctx,self.repo,'../outside','Generate','codex')
 def test_api_rejects_unknown_fields_paths_and_types(self):
  for name,args in [('source_read',{'repo':str(self.repo),'path':'../secret'}),('check',{'repo':str(self.repo),'argv':['true'],'timeout':True}),('doctor',{'secret':'x'})]:
   with self.assertRaises(ValueError):api.call(self.ctx,name,args)
 def test_mcp_initialization_tools_and_error_contract(self):
  requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05'}},{'jsonrpc':'2.0','method':'notifications/initialized'},{'jsonrpc':'2.0','id':2,'method':'tools/list'}, {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'source_read','arguments':{'repo':str(self.repo),'path':'../escape'}}}]
  r=subprocess.run([sys.executable,str(SOURCE/'gl.py'),'--state-dir',str(self.ctx.state),'mcp'],input='\n'.join(json.dumps(v) for v in requests)+'\n',capture_output=True,text=True)
  outputs=[json.loads(line) for line in r.stdout.splitlines()];self.assertEqual(len(outputs),3);self.assertIn('capabilities',outputs[0]['result']);self.assertEqual(len(outputs[1]['result']['tools']),len(api.TOOLS));self.assertTrue(outputs[2]['result']['isError'])
 def test_spotify_upstream_routing_cases(self):
  routing_tmp=tempfile.TemporaryDirectory(prefix='spotify-routing-');self.addCleanup(routing_tmp.cleanup);fixtures=Path(routing_tmp.name).resolve()
  for filename in ('hook-evals.json','bash-hook-evals.json'):
   for case in load(SOURCE/'tests/upstream'/filename)['evals']:
    raw=canonical(case['input']).replace('{{FIXTURES}}',str(fixtures));event=json.loads(raw);event['tool_name']='Read' if filename=='hook-evals.json' else 'Bash'
    fixture=case.get('fixture');args=event['tool_input']
    if fixture:
     name=args.get('file_path')
     if not name:
      try:name=next(t for t in shlex.split(args.get('command',''))[1:] if t.startswith(str(fixtures)))
      except (StopIteration,ValueError):name=None
     if name and str(name).startswith(str(fixtures)):(Path(name)).write_text('line\n'*fixture['lines'])
    with patch.dict(os.environ,case.get('env',{})):
     actual='block' if hooks.routing(self.repo,event) else 'allow'
    expected=case['expected_decision']
    if case['name']=='head-with-count':expected='allow' # Deliberate targeted-read improvement over Spotify's parser.
    self.assertEqual(actual,expected,(filename,case['name']))

 def test_git_hook_preserves_original_and_restores(self):
  path=self.repo/'.git/hooks/post-commit';original='#!/bin/sh\necho original > '+shlex.quote(str(self.base/'hook-output'))+'\n'
  path.write_text(original);path.chmod(0o755);hooks.git_hooks(self.ctx,self.repo)
  (self.repo/'new.py').write_text('def other(): return 8\n');git(self.repo,'add','.');git(self.repo,'commit','-qm','with hook')
  self.assertEqual((self.base/'hook-output').read_text().strip(),'original')
  self.assertTrue((self.ctx.local(self.repo)/'graph.json').exists());hooks.restore_git_hooks(self.ctx);self.assertEqual(path.read_text(),original)
 def test_shared_contract_verification_and_cycles(self):
  spec={'id':'shared','changes':[{'kind':'api','producer':'one','consumers':[],'compatibility':'additive','rollout_after':[]}],
        'acceptance':[{'id':'behavior-1','description':'Returns seven','repositories':{'one':[sys.executable,'-c','assert 7 == 7']}}]}
  save(self.repo/'contract.json',spec);runtime.register(self.ctx,'shared',['one='+str(self.repo)],'one:contract.json')
  report=api.call(self.ctx,'align_contract',{'name':'shared','run':True});self.assertEqual(report['verification'][0]['status'],'passed');self.assertEqual(report['deployment_compatibility'],'not established by checkout evidence')
 def test_output_timeout_and_model_failure_contract(self):
  from graph_loop.workers import process
  output=self.base/'process';output.mkdir()
  with self.assertRaisesRegex(ValueError,'timed out'):process([sys.executable,'-c','import time;time.sleep(10)'],'',output,dict(os.environ),0.05,output)
  with patch('graph_loop.workers.process',return_value='{"subtype":"success","result":"incomplete","stop_reason":"max_tokens"}'):
   with self.assertRaisesRegex(ValueError,'truncated'):workers.text(self.ctx,'claude','bulk-reader','source')
 def test_jsonc_and_custom_home_paths(self):
  root=self.home/'custom config/opencode';root.mkdir(parents=True)
  path=root/'opencode.jsonc';path.write_text('{/* comment */"model":"user/model","plugins":["unrelated", /* trailing */],"providers":{"kept":{"settings":{"baseURL":"https://example.invalid/v1"}}}, // trailing comment\n}')
  with patch.dict(os.environ,{'OPENCODE_CONFIG_DIR':str(root)}):self.install(('opencode',))
  data=load(path);self.assertEqual(data['model'],'user/model');self.assertIn('unrelated',data['plugins']);self.assertIn('kept',data['providers'])
  install.uninstall(self.ctx);self.assertEqual(load(path)['plugins'],['unrelated'])
 def test_reflection_retry_and_no_duplicate_memory(self):
  source=runtime.exact_read(self.ctx,self.repo,'app.py',1,2)
  real_run=subprocess.run
  def fail_reflect(argv,**kwargs):
   if len(argv)>1 and argv[1]=='reflect':return subprocess.CompletedProcess(argv,1,stdout='',stderr='fixture reflection failure')
   return real_run(argv,**kwargs)
  with patch('graph_loop.runtime.subprocess.run',side_effect=fail_reflect):
   with self.assertRaisesRegex(ValueError,'reflection failed'):runtime.finding(self.ctx,self.repo,'value',[source['id']])
  runtime.finding(self.ctx,self.repo,'same observation reworded',[source['id']])
  self.assertEqual(len(list((self.ctx.local(self.repo)/'memory').glob('*.md'))),1)
  argv=[sys.executable,'-c','import time;print(time.time_ns())']
  one=runtime.run_check(self.ctx,self.repo,argv);two=runtime.run_check(self.ctx,self.repo,argv)
  self.assertNotEqual(one['output_hash'],two['output_hash'])
  first=runtime.finding(self.ctx,self.repo,'check passes',[one['id']]);second=runtime.finding(self.ctx,self.repo,'same check reworded',[two['id']])
  self.assertEqual(first['id'],second['id'])

 def test_changed_install_roots_remain_owned(self):
  one=self.home/'central one';two=self.home/'central two'
  install.install(self.ctx,['codex'],{'provider':'native'},skills_dir=one,graphify_path=GRAPHIFY,skip_deps=True,isolated=True)
  install.install(self.ctx,['codex'],{'provider':'native'},skills_dir=two,graphify_path=GRAPHIFY,skip_deps=True,isolated=True)
  install.uninstall(self.ctx)
  self.assertFalse(any(one.iterdir()));self.assertFalse(any(two.iterdir()))
 def test_three_document_batch_updates_one_without_false_shrink(self):
  for name in ('one.md','two.md','three.md'):(self.repo/name).write_text(name+' original\n')
  def extract(ctx,harness,task,prompt,**kw):
   batch=json.loads(prompt.split('\n',1)[1])
   return canonical({'coverage':[{'path':i['path'],'source_hash':i['source_hash'],'line_start':1,'line_end':i['lines']} for i in batch],
    'nodes':[{'id':i['path'],'label':i['path'],'path':i['path'],'line':1,'source_hash':i['source_hash']} for i in batch],'links':[]})
  with patch('graph_loop.workers.text',side_effect=extract) as model:
   runtime.refresh(self.ctx,self.repo);(self.repo/'one.md').write_text('one.md changed\n');runtime.refresh(self.ctx,self.repo)
   self.assertEqual(model.call_count,2);self.assertEqual(load(self.ctx.local(self.repo)/'pending/documents.json')['pending'],[])

 def test_cached_edges_never_rebind_to_changed_endpoint(self):
  (self.repo/'a.md').write_text('A calls Old B.\n');(self.repo/'b.md').write_text('Old B.\n')
  def extract(ctx,harness,task,prompt,**kw):
   batch=json.loads(prompt.split('\n',1)[1]);items={i['path']:i for i in batch}
   nodes=[{'id':i['path'],'label':i['text'],'path':i['path'],'line':1,'source_hash':i['source_hash']} for i in batch]
   links=[]
   if 'a.md' in items and 'b.md' in items:links=[{'source':'a.md','target':'b.md','path':'a.md','source_hash':items['a.md']['source_hash'],'evidence':'A calls Old B.','relation':'calls'}]
   return canonical({'coverage':[{'path':i['path'],'source_hash':i['source_hash'],'line_start':1,'line_end':i['lines']} for i in batch],'nodes':nodes,'links':links})
  with patch('graph_loop.workers.text',side_effect=extract):
   runtime.refresh(self.ctx,self.repo);(self.repo/'b.md').write_text('Unrelated New B.\n');runtime.refresh(self.ctx,self.repo)
  graph=load(self.ctx.local(self.repo)/'graph.json')
  self.assertFalse(any(e.get('evidence')=='A calls Old B.' for e in graph['links']))
 def test_native_worker_flag_and_tool_action_contracts(self):
  answer=canonical({'subtype':'success','result':'<graph-loop-answer>answer</graph-loop-answer>','stop_reason':'end_turn'})
  with patch('graph_loop.workers.process',return_value=answer) as process:
   self.assertEqual(workers.text(self.ctx,'claude','bulk-reader','complete input'),'answer')
   argv=process.call_args.args[0];self.assertEqual(argv[argv.index('--tools')+1],'');self.assertIn('--strict-mcp-config',argv);self.assertIn('{"disableAllHooks":true}',argv)
  events='\n'.join([canonical({'type':'item.completed','item':{'type':'command_execution'}}),canonical({'type':'turn.completed'})])
  with patch('graph_loop.workers.process',return_value=events):
   with self.assertRaisesRegex(ValueError,'unsupported'):workers.text(self.ctx,'codex','bulk-reader','complete input')

 def test_source_reread_after_unrelated_edit_does_not_add_corroboration(self):
  first=runtime.exact_read(self.ctx,self.repo,'app.py',1,2);finding=runtime.finding(self.ctx,self.repo,'value is seven',[first['id']])
  (self.repo/'other.py').write_text('unrelated=1\n')
  latest=runtime.exact_read(self.ctx,self.repo,'app.py',1,2);again=runtime.finding(self.ctx,self.repo,'same value rephrased',[latest['id']])
  self.assertEqual(finding['id'],again['id']);self.assertEqual(again['receipts'],[latest['id']]);self.assertEqual(len(list((self.ctx.local(self.repo)/'memory').glob('*.md'))),1)
 def test_corrected_outcome_requires_real_text_and_deduplicates_rewording(self):
  receipt=runtime.exact_read(self.ctx,self.repo,'app.py',1,2);prior=runtime.finding(self.ctx,self.repo,'earlier observation',[receipt['id']])
  with self.assertRaises(ValueError):runtime.finding(self.ctx,self.repo,'correction',[receipt['id']],'corrected','  ',prior['id'])
  one=runtime.finding(self.ctx,self.repo,'correction',[receipt['id']],'corrected','It returns seven',prior['id'])
  two=runtime.finding(self.ctx,self.repo,'rephrasing',[receipt['id']],'corrected','The value returned is 7',prior['id'])
  self.assertEqual(one['id'],two['id'])

 def test_reread_is_available_to_new_session_without_new_evidence(self):
  one=runtime.exact_read(self.ctx,self.repo,'app.py',1,2,'one','read-one');two=runtime.exact_read(self.ctx,self.repo,'app.py',1,2,'two','read-two')
  self.assertEqual(one['id'],two['id']);self.assertEqual(len(two['observations']),2)
  with patch('graph_loop.workers.text',return_value='{"findings":[]}') as curator:
   self.assertEqual(runtime.curate(self.ctx,self.repo,'claude','Current source observation','two'),[]);self.assertEqual(curator.call_count,1)

class Gateway(unittest.TestCase):
 def test_protocols_aliases_efforts_and_truncation(self):
  captured=[]
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*a):pass
   def do_POST(self):
    body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));captured.append((self.path,body))
    if self.path.endswith('/responses'):answer={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'answer'}]}]}
    elif self.path.endswith('/messages'):answer={'stop_reason':'end_turn','content':[{'type':'text','text':'answer'}]}
    else:answer={'choices':[{'finish_reason':'stop','message':{'content':'answer'}}]}
    data=json.dumps(answer).encode();self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
  server=HTTPServer(('127.0.0.1',0),Handler);self.addCleanup(server.server_close);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();self.addCleanup(server.shutdown)
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'GRAPH_LOOP_TEST_CREDENTIAL':'test-placeholder'}):
   ctx=Context(Path(tmp)/'state');save(ctx.state/'config.json',{'provider':{'provider':'litellm','gateway':f'http://127.0.0.1:{server.server_port}/v1','credential_env':'GRAPH_LOOP_TEST_CREDENTIAL','main_model':'exact-alias','model_capabilities':{'exact-alias':{'efforts':['low','medium']}}}})
   for harness,path in [('opencode','/v1/chat/completions'),('codex','/v1/responses'),('claude','/v1/messages')]:
    self.assertEqual(workers.text(ctx,harness,'bulk-reader','question'),'answer');self.assertEqual(captured[-1][0],path);self.assertEqual(captured[-1][1]['model'],'exact-alias')
   self.assertNotIn('test-placeholder',''.join(p.read_text() for p in ctx.state.rglob('*.json')))

if __name__=='__main__':unittest.main()
