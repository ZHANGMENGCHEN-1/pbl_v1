export interface ChatEvent {type:string;data:{chat_id?:string;text?:string;message?:string;status?:string;limited?:boolean}}

/** Parse SSE lines across arbitrary network/UTF-8 boundaries; ignore heartbeat comments. */
export async function readChatStream(response:Response,onEvent:(event:ChatEvent)=>void){
  if(!response.body||!response.headers.get('content-type')?.includes('text/event-stream'))throw new Error('没有收到流式回复，请检查后端连接。')
  const reader=response.body.getReader(),decoder=new TextDecoder()
  let pending='',data:string[]=[],finished=false
  function line(value:string){
    value=value.replace(/\r$/,'')
    if(value===''){
      if(!data.length)return
      const event=JSON.parse(data.join('\n')) as ChatEvent;data=[]
      if(!event||typeof event.type!=='string'||!event.data)throw new Error('回复格式不正确，请重新提问。')
      onEvent(event)
      if(event.type==='done'||event.type==='error')finished=true
    }else if(value.startsWith('data:'))data.push(value.slice(5).trimStart())
  }
  try{
    while(!finished){
      const {done,value}=await reader.read()
      pending+=done?decoder.decode():decoder.decode(value,{stream:true})
      let index:number
      while((index=pending.indexOf('\n'))!==-1){const value=pending.slice(0,index);pending=pending.slice(index+1);line(value);if(finished)break}
      if(done){if(pending)line(pending);if(data.length)line('');break}
    }
    if(!finished)throw new Error('回复连接中断了，你可以重新提问。')
  }finally{await reader.cancel().catch(()=>{});reader.releaseLock()}
}
