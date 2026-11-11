import assert from 'node:assert/strict'
import fs from 'node:fs'
import ts from '../frontend/node_modules/typescript/lib/typescript.js'
const source=fs.readFileSync(new URL('../frontend/src/projects/teaching-agent/chatStream.ts',import.meta.url),'utf8')
const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
const module={exports:{}}
new Function('module','exports',code)(module,module.exports)
const {readChatStream}=module.exports
function response(text,oneByte=true){const bytes=new TextEncoder().encode(text);return new Response(new ReadableStream({start(c){if(oneByte)for(const byte of bytes)c.enqueue(Uint8Array.of(byte));else c.enqueue(bytes);c.close()}}),{headers:{'Content-Type':'text/event-stream'}})}
const received=[]
await readChatStream(response(': keep-alive\r\n\r\ndata: {"type":"start","data":{}}\r\n\r\ndata: {"type":"delta","data":{"text":"你好🌙"}}\r\n\r\ndata: {"type":"done","data":{"status":"completed"}}\r\n\r\n'),e=>received.push(e))
assert.deepEqual(received.map(e=>e.type),['start','delta','done'])
assert.equal(received[1].data.text,'你好🌙')
await assert.rejects(()=>readChatStream(response('data: {"type":"delta","data":{"text":"未完成"}}\n\n'),()=>{}),/中断/)
await assert.rejects(()=>readChatStream(new Response('{}'),()=>{}),/流式/)
await assert.rejects(()=>readChatStream(response('data: {"type":"error","data":{"message":"连接错误"}}\n\n'),e=>{throw new Error(e.data.message)}),/连接错误/)
console.log('Passed: byte-split Unicode, CRLF SSE, heartbeat, partial disconnect, upstream error and invalid response.')
