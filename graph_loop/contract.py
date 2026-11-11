"""One shared behavior contract across explicit workspace members."""
from graphlib import TopologicalSorter
from .common import *
from .runtime import run_check

KINDS={'api','event','schema','generated-client','configuration','dependency'}

def align(ctx,name,run=False):
    cfg=load(ctx.state/'workspaces'/identifier(name)/'workspace.json')
    if not cfg or not cfg.get('spec'):raise ValueError('Workspace needs one explicit alias:shared-spec path')
    members={m['alias']:Path(m['path']) for m in cfg['members']}
    alias,path=cfg['spec'].split(':',1);spec=load(source_path(members[alias],path))
    identifier(spec['id']);criteria=spec.get('acceptance',[])
    if not criteria or len({c['id'] for c in criteria})!=len(criteria):raise ValueError('Acceptance IDs must be unique and nonempty')
    order={a:set() for a in members}
    for change in spec.get('changes',[]):
        if change.get('kind') not in KINDS or change.get('producer') not in members or not change.get('compatibility'):
            raise ValueError('Each change needs a supported kind, producer and compatibility expectation')
        for consumer in change.get('consumers',[]):
            if consumer not in members:raise ValueError('Unknown consumer')
        for predecessor in change.get('rollout_after',[]):
            if predecessor not in members:raise ValueError('Unknown rollout dependency')
            order[change['producer']].add(predecessor)
    rollout=list(TopologicalSorter(order).static_order());results=[]
    for criterion in criteria:
        identifier(criterion['id'])
        if not criterion.get('description') or not criterion.get('repositories'):raise ValueError('Criterion requires behavior and repository verification ownership')
        for alias,argv in criterion['repositories'].items():
            if alias not in members:raise ValueError('Criterion references an unknown repository')
            result={'criterion':criterion['id'],'repository':alias,'command':argv,'status':'pending'}
            if run:
                r=run_check(ctx,members[alias],argv,criterion=criterion['id']);result.update({'receipt':r['id'],'exit_code':r['exit_code'],
                    'status':'passed' if r['verified'] and r['exit_code']==0 else 'failed'})
            results.append(result)
    report={'contract':spec['id'],'spec_hash':sha(canonical(spec).encode()),'rollout_order':rollout,
        'verification':results,'deployment_compatibility':'not established by checkout evidence','at':now()}
    if run:save(ctx.state/'workspaces'/name/'contract-evidence.json',report)
    return report
