"""Bounded stdio MCP JSON-RPC transport, no SDK or daemon."""
import json,sys
from .api import TOOLS,call

def serve(ctx):
    for line in iter(lambda:sys.stdin.readline(1000001),''):
        if len(line.encode())>1000000:
            print(json.dumps({'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Request exceeds 1 MB'}}),flush=True);continue
        request=None
        try:
            request=json.loads(line)
            if not isinstance(request,dict) or request.get('jsonrpc')!='2.0' or not isinstance(request.get('method'),str):raise ValueError('Invalid JSON-RPC request')
            if 'id' not in request:continue
            method=request['method'];params=request.get('params',{})
            if method=='initialize':
                result={'protocolVersion':'2024-11-05','capabilities':{'tools':{}},'serverInfo':{'name':'graph-loop','version':'2.0.0'}}
            elif method=='ping':result={}
            elif method=='tools/list':result={'tools':[{'name':name,'description':desc,'inputSchema':schema} for name,(desc,schema) in TOOLS.items()]}
            elif method=='tools/call':
                try:
                    answer=call(ctx,params['name'],params.get('arguments',{}))
                    result={'content':[{'type':'text','text':json.dumps(answer,ensure_ascii=False)}],'isError':False}
                except Exception as exc:result={'content':[{'type':'text','text':str(exc)[:2000]}],'isError':True}
            else:
                print(json.dumps({'jsonrpc':'2.0','id':request['id'],'error':{'code':-32601,'message':'Method not found'}}),flush=True);continue
            print(json.dumps({'jsonrpc':'2.0','id':request['id'],'result':result}),flush=True)
        except Exception as exc:
            print(json.dumps({'jsonrpc':'2.0','id':request.get('id') if isinstance(request,dict) else None,'error':{'code':-32700 if request is None else -32600,'message':str(exc)[:1000]}}),flush=True)
