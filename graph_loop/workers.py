"""Spotify Shunt's one-shot modes over native CLI or LiteLLM transports.
Derived from spotify/portal-ai-plugins/plugins/shunt at aa252eb21df5bbf32b0beb45f84a2c03341ccad8.
Modified: Portal/AiKA transport replaced; complete input/output bounds and atomic new-file publication.
Apache-2.0; see licenses/spotify-shunt-APACHE-2.0.txt and NOTICE.
"""
from __future__ import annotations
import html, json, os, re, subprocess, sys, tempfile, tomllib, uuid
from pathlib import Path
from urllib.request import Request, urlopen
from .common import *
from .install import provider_options

MAX_INPUT=60000
MAX_OUTPUT=64000

def selection(ctx,harness,task):
    if harness not in ('opencode','codex','claude') or task not in TASKS:raise ValueError('Invalid harness or worker task')
    cfg=provider_options(ctx,harness);worker=cfg.get('workers',{}).get(task,{})
    model=worker.get('model',cfg.get('main_model'))
    if not model and cfg.get('provider','native')=='native' and getattr(ctx,'active_repo',None):
        current=load(ctx.local(ctx.active_repo)/'primary-models'/f'{harness}.json',{}).get('model')
        if isinstance(current,str):model=current
        elif isinstance(current,dict) and current.get('providerID') and current.get('id'):model=current['providerID']+'/'+current['id']
    if not model and harness=='claude' and task in ('bulk-reader','code-writer'):
        model='haiku' if task=='bulk-reader' else 'sonnet'
    requested=worker.get('effort',TASKS[task]);caps=cfg.get('model_capabilities',{}).get(model,{})
    effort=requested if requested in caps.get('efforts',[]) else None
    variant=worker.get('variant') if worker.get('variant') in caps.get('variants',[]) else None
    if variant and not (harness=='opencode' and cfg.get('provider','native')=='native'):
        raise ValueError('Variant overrides are supported only by native OpenCode; configure a supported effort for other transports')
    if harness=='opencode' and cfg.get('provider','native')=='native':effort=None
    return {**cfg,'model':model,'effort':effort,'variant':variant,'requested_effort':requested}

def process(argv,prompt,cwd,env,timeout,output):
    with (output/'stdout').open('wb') as out,(output/'stderr').open('wb') as err:
        p=subprocess.Popen(argv,cwd=cwd,env=env,stdin=subprocess.PIPE,stdout=out,stderr=err,start_new_session=True)
        try:p.communicate(prompt.encode(),timeout=timeout)
        except subprocess.TimeoutExpired:
            import signal
            os.killpg(p.pid,signal.SIGKILL);p.communicate();raise ValueError('Worker timed out')
    if p.returncode:raise ValueError('Worker failed with exit '+str(p.returncode)+'; see '+str(output))
    data=(output/'stdout').read_bytes()
    if len(data)>1000000:raise ValueError('Worker transport output exceeded 1 MB')
    return data.decode('utf-8')

def gateway(ctx,harness,chosen,prompt,timeout):
    key=os.environ.get(chosen.get('credential_env','LITELLM_API_KEY'))
    if not key:raise ValueError('Missing credential environment variable '+chosen.get('credential_env','LITELLM_API_KEY'))
    base=chosen['gateway'].rstrip('/');model=chosen['model'];effort=chosen['effort']
    headers={'Content-Type':'application/json'}
    if harness=='codex':
        path='/responses';body={'model':model,'input':prompt,'max_output_tokens':12000};headers['Authorization']='Bearer '+key
        if effort:body['reasoning']={'effort':effort}
    elif harness=='claude':
        # Gateway URL is its Anthropic-compatible root; avoid /v1/v1/messages.
        path='/messages' if base.endswith('/v1') else '/v1/messages'
        body={'model':model,'messages':[{'role':'user','content':prompt}],'max_tokens':12000}
        headers.update({'x-api-key':key,'anthropic-version':'2023-06-01'})
        if effort:body['output_config']={'effort':effort}
    else:
        path='/chat/completions';body={'model':model,'messages':[{'role':'user','content':prompt}],'max_tokens':12000};headers['Authorization']='Bearer '+key
        if effort:body['reasoning_effort']=effort
    request=Request(base+path,data=canonical(body).encode(),headers=headers)
    with urlopen(request,timeout=timeout) as response:
        data=response.read(1000001)
    if len(data)>1000000:raise ValueError('Gateway response exceeded bound')
    obj=json.loads(data)
    if obj.get('error'):raise ValueError('Gateway model failure')
    if harness=='codex':
        if obj.get('status')!='completed' or obj.get('incomplete_details'):raise ValueError('Incomplete Responses result')
        if any(o.get('type') not in ('message','reasoning') for o in obj.get('output',[])):raise ValueError('Unsupported worker tool action')
        return ''.join(part.get('text','') for o in obj.get('output',[]) for part in o.get('content',[]) if part.get('type')=='output_text')
    if harness=='claude':
        if obj.get('stop_reason') not in ('end_turn','stop_sequence') or any(p.get('type')=='tool_use' for p in obj.get('content',[])):
            raise ValueError('Truncated or tool-using Messages result')
        return ''.join(p.get('text','') for p in obj.get('content',[]) if p.get('type')=='text')
    choice=obj.get('choices',[{}])[0]
    if choice.get('finish_reason')!='stop' or choice.get('message',{}).get('tool_calls'):raise ValueError('Truncated or tool-using Chat Completions result')
    return choice.get('message',{}).get('content','')

def text(ctx,harness,task,prompt,timeout=180):
    if timeout==180:timeout=int(os.environ.get('SHUNT_TIMEOUT_SECONDS','180'))
    if not isinstance(prompt,str) or len(prompt.encode())>200000 or not 0<timeout<=600:raise ValueError('Worker input/timeout exceeds bounds')
    chosen=selection(ctx,harness,task)
    native=chosen.get('provider','native')=='native'
    if native:prompt+='\nTransport protocol: Enclose your complete final answer in <graph-loop-answer> and </graph-loop-answer>. No text outside these tags. The closing tag MUST be last; never output it before the answer is complete.'
    job=ctx.state/'workers'/uuid.uuid4().hex;job.mkdir(parents=True)
    atomic(job/'input',prompt);record={'task':task,'harness':harness,'provider':chosen.get('provider','native'),
        'input_hash':sha(prompt.encode()),'model':chosen.get('model'),'effort':chosen.get('effort'),
        'requested_effort':chosen['requested_effort'],'variant':chosen.get('variant'),'at':now(),'status':'running'}
    save(job/'result.json',record)
    try:
        if chosen.get('provider')=='litellm':result=gateway(ctx,harness,chosen,prompt,timeout)
        else:
            env={k:v for k,v in os.environ.items() if not k.startswith('ORCA_') and k not in ('CLAUDECODE','CODEX_THREAD_ID')}
            env['GRAPH_LOOP_WORKER']='1';env['PWD']=str(job)
            if harness=='claude':
                argv=['claude','--print','--output-format','json','--no-session-persistence','--tools','',
                    '--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--settings','{"disableAllHooks":true}','--setting-sources','']
                if chosen.get('model'):argv+=['--model',chosen['model']]
                if chosen.get('effort'):argv+=['--effort',chosen['effort']]
                response=json.loads(process(argv,prompt,job,env,timeout,job))
                if response.get('is_error') or response.get('subtype')!='success' or response.get('stop_reason') not in ('end_turn','stop_sequence',None):raise ValueError('Claude failed or truncated')
                result=response.get('result','')
            elif harness=='codex':
                argv=['codex','exec','--ephemeral','--sandbox','read-only','--skip-git-repo-check','--json','-c','features.hooks=false','-c','notify=[]']
                home=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))
                user=tomllib.loads((home/'config.toml').read_text()) if (home/'config.toml').exists() else {}
                for name in user.get('mcp_servers',{}):
                    if not re.fullmatch(r'[A-Za-z0-9_-]+',name):raise ValueError('Cannot disable this nonstandard MCP name safely: '+name)
                    argv+=['-c','mcp_servers.'+name+'.enabled=false']
                if chosen.get('model'):argv+=['--model',chosen['model']]
                if chosen.get('effort'):argv+=['-c','model_reasoning_effort='+json.dumps(chosen['effort'])]
                argv+=['-'];before=snapshot(job) if (job/'.git').exists() else {p.name:sha(p.read_bytes()) for p in job.iterdir() if p.is_file()}
                raw=process(argv,prompt+'\nTool-free worker: all input is above. Do not call tools, browse files, or edit anything. Output the answer only.',job,env,timeout,job)
                events=[json.loads(line) for line in raw.splitlines() if line.strip()]
                messages=[];completed=False
                for event in events:
                    if event.get('type') in ('error','turn.failed'):raise ValueError('Codex worker failure')
                    if event.get('type')=='turn.completed':completed=True
                    item=event.get('item',{})
                    if item and item.get('type') not in ('agent_message','reasoning'):raise ValueError('Rejected unsupported Codex worker tool action')
                    if event.get('type')=='item.completed' and item.get('type')=='agent_message':messages.append(item['text'])
                if not completed:raise ValueError('Incomplete Codex worker turn')
                # Codex cannot publish generated files; also reject unexpected artifacts despite read-only sandbox.
                if any(p.name not in ('input','result.json','stdout','stderr') for p in job.iterdir()):raise ValueError('Codex worker edited its directory')
                result='\n'.join(messages)
            else:
                # The installed V2 API is transient, tool-free and authenticated by the running server.
                payload={'prompt':prompt}
                if chosen.get('model'):
                    if '/' not in chosen['model']:raise ValueError('Native OpenCode override must be provider/model')
                    provider,model=chosen['model'].split('/',1);payload['model']={'providerID':provider,'id':model}
                    if chosen.get('variant'):payload['model']['variant']=chosen['variant']
                encoded=canonical(payload)
                if len(encoded.encode())>100000:raise ValueError('OpenCode request exceeds safe CLI argument bound; split the corpus')
                raw=process(['opencode','api','POST','/api/experimental/generate/text','--data',encoded],'',job,env,timeout,job)
                obj=json.loads(raw)
                obj=obj.get('data',obj)
                result=obj.get('text','')
                if obj.get('error'):raise ValueError('OpenCode worker failed')
        if not isinstance(result,str) or not result.strip() or len(result.encode())>MAX_OUTPUT:raise ValueError('Empty, truncated or oversized worker answer')
        if native:
            match=re.fullmatch(r'\s*<graph-loop-answer>(.*)</graph-loop-answer>\s*',result,re.S)
            if not match:raise ValueError('Incomplete native answer: required completion envelope absent')
            result=match.group(1).strip()
            if not result:raise ValueError('Empty native worker answer')
        atomic(job/'answer',result);record.update({'status':'complete','output_hash':sha(result.encode()),'finished_at':now()});save(job/'result.json',record)
        return result
    except Exception as exc:
        record.update({'status':'failed','error':str(exc)[:1000],'finished_at':now()});save(job/'result.json',record);raise

def corpus(repo,paths):
    if not isinstance(paths,list) or not 1<=len(paths)<=20 or len(set(paths))!=len(paths):raise ValueError('Provide 1-20 distinct input files')
    inputs=[];total=lines=0
    for name in paths:
        p=source_path(repo,name);data=p.read_bytes();total+=len(data)
        value=data.decode('utf-8');lines+=len(value.splitlines())
        if total>MAX_INPUT or lines>4000:raise ValueError('Complete corpus exceeds 60 KB / 4000 lines; split input without summarizing')
        inputs.append({'path':str(p.relative_to(repo)),'source_hash':sha(data),'text':value})
    return inputs

def bulk_read(ctx,repo,paths,question,harness):
    repo=checkout(repo)
    if not isinstance(question,str) or not question.strip() or len(question)>4000:raise ValueError('A bounded question is required')
    inputs=corpus(repo,paths);prompt=(SOURCE/'workers/bulk-reader.md').read_text()+'\n'
    for item in inputs:prompt+='<file path="'+html.escape(item['path'],quote=True)+'">\n'+item['text']+'\n</file>\n'
    result=text(ctx,harness,'bulk-reader',prompt+'\nQuestion: '+question)
    if any(sha(source_path(repo,i['path']).read_bytes())!=i['source_hash'] for i in inputs):raise ValueError('Input changed; discard summary')
    return {'text':result,'verified':False,'inputs':[{k:v for k,v in i.items() if k!='text'} for i in inputs]}

def code_write(ctx,repo,reference,spec,harness,target=None):
    repo=checkout(repo)
    if not isinstance(spec,str) or not spec.strip() or len(spec)>8000:raise ValueError('A generation spec is required')
    inputs=corpus(repo,[reference]);destination=None
    if target:
        destination=source_path(repo,target)
        lexical=repo/target
        if destination!=lexical or destination.exists() or lexical.is_symlink() or not destination.parent.is_dir():raise ValueError('Target must be a NEW file with an existing non-symlink parent')
    result=text(ctx,harness,'code-writer',(SOURCE/'workers/code-writer.md').read_text()+'\nSpec: '+spec+'\n\nReference:\n'+inputs[0]['text'])
    # Spotify code-write strips model fence wrappers; preserve all actual code lines.
    if result.startswith('```'):
        parts=result.splitlines()
        if len(parts)<3 or parts[-1].strip()!='```':raise ValueError('Incomplete generated fence')
        result='\n'.join(parts[1:-1])+'\n'
    if sha(source_path(repo,reference).read_bytes())!=inputs[0]['source_hash']:raise ValueError('Reference changed; discard generated output')
    if destination:
        flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW
        parent_fd=os.open(repo,flags)
        tmp='.graph-loop-publish-'+uuid.uuid4().hex
        try:
            for part in Path(target).parts[:-1]:
                next_fd=os.open(part,flags,dir_fd=parent_fd);os.close(parent_fd);parent_fd=next_fd
            fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600,dir_fd=parent_fd)
            with os.fdopen(fd,'w') as f:f.write(result);f.flush();os.fsync(f.fileno())
            os.link(tmp,Path(target).name,src_dir_fd=parent_fd,dst_dir_fd=parent_fd,follow_symlinks=False)
        finally:
            try:os.unlink(tmp,dir_fd=parent_fd)
            except FileNotFoundError:pass
            os.close(parent_fd)
    return {'text':result if not target else None,'target':str(destination) if destination else None,'output_hash':sha(result.encode()),'verified':False}

def launch(ctx,harness,argv):
    cfg=provider_options(ctx,harness);env=dict(os.environ);command=[harness]
    if cfg.get('provider')=='litellm':
        model=cfg['main_model'];base=cfg['gateway'];name=cfg.get('credential_env','LITELLM_API_KEY')
        if not env.get(name):raise ValueError('Missing credential environment variable '+name)
        if harness=='codex':
            for key,value in {'model':model,'model_provider':'graph_loop','model_providers.graph_loop.name':'LiteLLM',
                'model_providers.graph_loop.base_url':base,'model_providers.graph_loop.env_key':name,
                'model_providers.graph_loop.wire_api':'responses'}.items():command+=['-c',key+'='+json.dumps(value)]
        elif harness=='claude':env.update({'ANTHROPIC_BASE_URL':base,'ANTHROPIC_AUTH_TOKEN':env[name]});command+=['--model',model]
        else:
            overlay={'providers':{'graph_loop':{'name':'Graph Loop LiteLLM','env':[name],
                'package':'@opencode/ai/providers/openai-compatible','settings':{'baseURL':base},'models':{model:{}}}},'model':'graph_loop/'+model}
            path=ctx.state/'launch/opencode.json';save(path,overlay);env['OPENCODE_CONFIG']=str(path)
    return subprocess.call(command+argv,env=env)
