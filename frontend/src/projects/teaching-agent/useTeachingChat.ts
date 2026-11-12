import { computed,onBeforeUnmount,ref,watch,type Ref } from 'vue'
import { appendMessage,type TeachingSession } from './learningState'
import {readChatStream} from './chatStream'

/** One real model request per question; state transitions remain in platform code. */
export function useTeachingChat(state:Ref<TeachingSession>,persist:()=>void,phase:()=> 'dialogue'|'task'=()=> 'task'){
  const messages=computed(()=>state.value.messages)
  const draft=computed({get:()=>state.value.activities[state.value.activeActivityId].draft.question,set:(value:string)=>{state.value.activities[state.value.activeActivityId].draft.question=value}})
  const busy=ref(false),thinking=ref(false),error=ref('')
  let active:{controller:AbortController;messageId:number;session:string;chatId?:string}|null=null,lastQuestion=''
  const mood=computed(()=>thinking.value?'thinking':busy.value?'talking':'ready')
  const canSend=computed(()=>!!draft.value.trim()&&!busy.value&&draft.value.length<=2000)
  async function send(text=draft.value){
    const input=text.trim(),id=state.value.activeActivityId,session=state.value.sessionId,current=state.value.activities[id]
    if(!input||input.length>2000||busy.value)return
    const context={phase:phase(),step_id:id==='group_books'?current.operation.result?.id??null:null,
      analysis_id:id==='explore_2d'?current.operation.result?.id??null:null,
      dataset_id:current.draft.datasetId,features:current.draft.features.filter(Boolean),
      initial_centers:current.draft.centers,step_order:id==='explain_algorithm'?current.draft.stepOrder:[]}
    appendMessage(state.value,{role:'student',activityId:id,kind:'chat',text:input})
    appendMessage(state.value,{role:'assistant',activityId:id,kind:'chat',text:'',status:'streaming'})
    const messageId=state.value.messages.at(-1)!.id,request:{controller:AbortController;messageId:number;session:string;chatId?:string}={controller:new AbortController(),messageId,session}
    active=request;lastQuestion=input;draft.value='';busy.value=true;thinking.value=true;error.value='';persist()
    const target=()=>state.value.messages.find(m=>m.id===messageId)
    let completed=false
    try{
      let response:Response
      try{response=await fetch('/api/projects/teaching-agent/chat',{method:'POST',headers:{'Content-Type':'application/json','X-Session-ID':session},body:JSON.stringify({activity_id:id,question:input,context}),signal:request.controller.signal})}
      catch(e){if(request.controller.signal.aborted)throw e;throw new Error('连接不上小知，请稍后重试，或请老师检查网络。')}
      if(!response.ok){const data=await response.json().catch(()=>null);throw new Error(typeof data?.detail==='string'?data.detail:'小知暂时无法回复，请检查模型连接后重试。')}
      await readChatStream(response,event=>{
        if(active!==request)return
        const message=target();if(!message)return
        if(event.type==='start'&&event.data.chat_id)request.chatId=event.data.chat_id
        if(event.type==='delta'&&event.data.text){message.text+=event.data.text;thinking.value=false}
        if(event.type==='error')throw new Error(event.data.message||'这次回复没有完成，请稍后重试。')
        if(event.type==='done'){completed=true;message.status='completed'}
      })
      if(!completed&&!request.controller.signal.aborted)throw new Error('小知的回复没有完成，请重新提问。')
    }catch(e){
      if(active===request&&!request.controller.signal.aborted){const text=e instanceof Error?e.message:'小知暂时无法回复，请稍后重试。';error.value=text;const message=target();if(message){message.status='error';message.error=text}}
    }finally{if(active===request){active=null;busy.value=false;thinking.value=false;persist()}}
  }
  function stop(explicit=false){
    if(!active)return
    const request=active;active=null;request.controller.abort()
    if(explicit&&request.chatId)void fetch(`/api/projects/teaching-agent/chat/${request.chatId}/pause`,{method:'POST',headers:{'X-Session-ID':request.session},keepalive:true}).catch(()=>{})
    const message=state.value.messages.find(m=>m.id===request.messageId)
    if(message){message.paused=true;message.status='paused'}
    busy.value=false;thinking.value=false;persist()
  }
  function retry(){if(lastQuestion&&!busy.value)void send(lastQuestion)}
  // Cancel outdated answers when a new activity/file/calculation replaces their context.
  watch(()=>{const s=state.value,a=s.activities[s.activeActivityId];return [s.sessionId,s.activeActivityId,a.operation.result?.id,a.draft.datasetId,a.draft.features.join('|'),a.draft.stepOrder.join('|')].join(':')},()=>{stop();error.value=''},{flush:'sync'})
  onBeforeUnmount(()=>stop())
  return {messages,draft,busy,thinking,mood,canSend,send,stop,error,retry}
}
