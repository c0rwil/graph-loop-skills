"""One validated tool contract shared by CLI, MCP, and native OpenCode tools."""
from .common import *
from . import runtime,workers,contract

def obj(properties,required=()):return {'type':'object','properties':properties,'required':list(required),'additionalProperties':False}
def string(**kw):return {'type':'string','minLength':1,'maxLength':8000,**kw}
def array(items,**kw):return {'type':'array','items':items,'maxItems':50,**kw}
REPO=string();HARNESS=string(enum=['opencode','codex','claude'])
TOOLS={
'workspace_register':('Register explicit aliased Git checkouts and one optional shared spec.',obj({'name':string(),'members':array(string(),minItems=1),'spec':string()},['name','members'])),
'graph_refresh':('Refresh one checkout and its registered workspace graphs.',obj({'repo':REPO,'harness':HARNESS,'allow_shrink':{'type':'boolean'},'semantic':{'type':'boolean'}},['repo'])),
'graph_status':('Inspect graph freshness, pending documents and errors.',obj({'repo':REPO},['repo'])),
'graph_query':('Query relationships; results are unverified navigation observations.',obj({'repo':REPO,'kind':string(enum=['query','path','explain']),'terms':array(string(),minItems=1,maxItems=2),'workspace':string(),'harness':HARNESS},['repo','kind','terms'])),
'source_read':('Read exact source lines and issue a verified, hash-bound receipt.',obj({'repo':REPO,'path':string(),'start':{'type':'integer','minimum':1},'end':{'type':'integer','minimum':1},'session':string(),'tool':string()},['repo','path'])),
'check':('Execute one argv check and retain explicit exit/output evidence.',obj({'repo':REPO,'argv':array(string(),minItems=1),'timeout':{'type':'integer','minimum':1,'maximum':3600},'criterion':string(),'session':string(),'tool':string()},['repo','argv'])),
'finding':('Save an agent-authored conclusion from existing current verified receipts; reflect deterministically.',obj({'repo':REPO,'text':string(maxLength=4000),'receipts':array(string(),minItems=1,maxItems=20),'outcome':string(enum=['useful','dead_end','corrected']),'correction':string(),'corrects':string()},['repo','text','receipts'])),
'bulk_read':('Spotify Shunt independent bulk analysis of complete declared files.',obj({'repo':REPO,'paths':array(string(),minItems=1,maxItems=20),'question':string(maxLength=4000),'harness':HARNESS},['repo','paths','question','harness'])),
'code_write':('Spotify Shunt reference-matched generation; optional target MUST be new.',obj({'repo':REPO,'reference':string(),'spec':string(),'harness':HARNESS,'target':string()},['repo','reference','spec','harness'])),
'align_contract':('Validate or execute per-repository acceptance for the shared behavior contract.',obj({'name':string(),'run':{'type':'boolean'}},['name'])),
'prompt':('Render a portable kickoff, alignment or completion prompt.',obj({'name':string(enum=['kickoff','align','finish','graphify','workspace','bulk-reader','code-writer']),'request':string(),'spec':string()},['name'])),
'doctor':('Inspect installation ownership, provider choice and dependencies without exposing credentials.',obj({})),
}

def validate(schema,value):
    types={'object':dict,'array':list,'string':str,'integer':int,'boolean':bool}
    t=schema['type']
    if not isinstance(value,types[t]) or (t=='integer' and isinstance(value,bool)):raise ValueError('Expected '+t)
    if 'enum' in schema and value not in schema['enum']:raise ValueError('Value not in allowed choices')
    if t=='object':
        if set(schema.get('required',[]))-set(value):raise ValueError('Missing required fields')
        if set(value)-set(schema['properties']):raise ValueError('Unknown input fields')
        for k,v in value.items():validate(schema['properties'][k],v)
    if t=='array':
        if not schema.get('minItems',0)<=len(value)<=schema.get('maxItems',100):raise ValueError('Array length out of bounds')
        for item in value:validate(schema['items'],item)
    if t=='string' and not schema.get('minLength',0)<=len(value)<=schema.get('maxLength',100000):raise ValueError('String length out of bounds')
    if t=='integer' and not schema.get('minimum',-1e10)<=value<=schema.get('maximum',1e10):raise ValueError('Integer out of bounds')

def call(ctx,name,args):
    if name not in TOOLS:raise ValueError('Unknown tool')
    validate(TOOLS[name][1],args);args=dict(args)
    repo=checkout(args.pop('repo')) if 'repo' in args else None
    if repo is not None:ctx.active_repo=repo
    if name=='workspace_register':return runtime.register(ctx,**args)
    if name=='graph_refresh':return runtime.refresh(ctx,repo,**args)
    if name=='graph_status':return runtime.status(ctx,repo)
    if name=='graph_query':return runtime.query(ctx,repo,**args)
    if name=='source_read':return runtime.exact_read(ctx,repo,**args)
    if name=='check':return runtime.run_check(ctx,repo,**args)
    if name=='finding':return runtime.finding(ctx,repo,**args)
    if name=='bulk_read':return workers.bulk_read(ctx,repo,**args)
    if name=='code_write':return workers.code_write(ctx,repo,**args)
    if name=='align_contract':return contract.align(ctx,**args)
    if name=='doctor':
        from .install import doctor
        return doctor(ctx)
    if name=='prompt':
        text=(SOURCE/'prompts'/(args['name']+'.md')).read_text()
        return {'text':text.replace('$REQUEST',args.get('request','')).replace('$SPEC',args.get('spec',''))}
