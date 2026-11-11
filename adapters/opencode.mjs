// Thin native V2 adapter. Input schemas come from the shared Python MCP contract.
import { spawn } from 'node:child_process';
import { writeFile } from 'node:fs/promises';
import { join } from 'node:path';
export default function adapter(options) {
  function run(args, input = {}) {
    return new Promise((resolve, reject) => {
      const child = spawn(options.command[0], [...options.command.slice(1), ...args], { stdio: ['pipe','pipe','pipe'] });
      let out = '', err = '';
      const timer = setTimeout(() => { child.kill('SIGTERM'); reject(new Error('Graph Loop bridge timed out')); }, 300000);
      child.stdout.on('data', data => { out += data; if (out.length > 1000000) child.kill(); });
      child.stderr.on('data', data => { err = (err + data).slice(-4000); });
      child.on('error', reject);
      child.on('close', code => { clearTimeout(timer); if (code !== 0) reject(new Error(err || 'Graph Loop failed')); else { try { resolve(JSON.parse(out)); } catch(e) { reject(e); } } });
      child.stdin.end(JSON.stringify(input));
    });
  }
  return { id: 'graph-loop-skills', async setup(ctx) {
    const primary = async sessionID => !sessionID || !(await ctx.session.get({sessionID})).parentID;
    const event = async (name, extra = {}) => {
      const info=extra.session_id?await ctx.session.get({sessionID:extra.session_id}):undefined;
      const directory=info?.location?.directory||ctx.location.directory;
      const result = await run(['hook','--harness','opencode'], {cwd:directory,hook_event_name:name,...extra});
      if (result.hookSpecificOutput?.permissionDecision === 'deny') throw new Error(result.hookSpecificOutput.permissionDecisionReason);
      return result;
    };
    const schemas = await run(['tools']);
    await ctx.tool.transform(editor => {
      for (const [name, definition] of Object.entries(schemas)) editor.add({
        name:'graph_loop_' + name,description:definition.description,input:definition.inputSchema,
        execute:async input => ({content:JSON.stringify(await run(['invoke',name],input))}),
      });
    });
    await ctx.session.hook('prompt', async e => { if (await primary(e.sessionID)) await event('UserPromptSubmit',{session_id:e.sessionID}); });
    await ctx.session.hook('context', async e => {
      if (await primary(e.sessionID)) {
        await event('ModelContext',{session_id:e.sessionID,model:e.model});
        e.system.push({type:'text',text:(await run(['prompt','kickoff'])).text});
      }
    });
    await ctx.tool.hook('execute.before', async e => {
      if (await primary(e.sessionID)) await event('PreToolUse',{session_id:e.sessionID,tool_use_id:e.id,tool_name:e.tool,tool_input:e.input});
    });
    await ctx.tool.hook('execute.after', async e => {
      if (await primary(e.sessionID)) {
        const response=e.result||{status:'error',is_error:true};
        const exit=response.metadata?.exit ?? response.metadata?.metadata?.exit;
        const observed={...response,status:e.status,...(Number.isInteger(exit)?{exit_code:exit}:{}),
          output:Array.isArray(response.content)?response.content.filter(p=>p.type==='text').map(p=>p.text).join('\n'):response.content};
        await event('PostToolUse',{session_id:e.sessionID,tool_use_id:e.id,tool_name:e.tool,tool_input:e.input,tool_response:observed});
      }
    });
    await writeFile(join(options.state,'opencode-discovery.json'),JSON.stringify({version:ctx.app.version,tools:(await ctx.tool.list()).map(t=>t.id),at:new Date().toISOString()}));
    const controller = new AbortController();
    void (async () => {
      for await (const e of ctx.event.subscribe({types:['session.idle'],signal:controller.signal})) {
        const sessionID=e.data.sessionID;
        if (!(await primary(sessionID))) continue;
        const messages=await ctx.session.context({sessionID});
        const list=Array.isArray(messages)?messages:(messages.messages||[]);
        const last=[...list].reverse().find(m=>m.role==='assistant'||m.info?.role==='assistant');
        const parts=Array.isArray(last?.parts)?last.parts:Array.isArray(last?.content)?last.content:typeof last?.content==='string'?[{type:'text',text:last.content}]:[];
        const conclusion=parts.filter(p=>p.type==='text').map(p=>p.text).join('\n');
        await event('Idle',{session_id:sessionID,last_assistant_message:conclusion});
      }
    })().catch(error => { if (!controller.signal.aborted) console.error('Graph Loop idle:',error.message); });
    return () => controller.abort();
  }};
}
