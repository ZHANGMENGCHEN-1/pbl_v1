import { computed, onBeforeUnmount, ref } from 'vue'

export type Topic='plan'|'stuck'|'reflect'
export interface Message {id:number;role:'assistant'|'student';text:string;paused?:boolean}
const key='orbit-teaching-agent-demo-v1'
const welcome='你好呀，我是小知！你可以告诉我正在做什么，或者说说哪里卡住了。我们一起想一想，下一步可以怎么做。'
const replies:Record<Topic,string[]>={
  plan:['我们先把任务拆小一点。\n\n你这次想完成什么？准备先做哪一步？可以先用一句话告诉我。','有了第一步，再想一想：你需要哪些材料？做完以后，你准备用什么办法检查？'],
  stuck:['遇到困难时，我们先找一找卡在哪里。\n\n你正在做哪一步？已经试过什么办法？先告诉我一件就好。','我们试着只改一个地方，再看看结果有没有变化。\n\n你想先换一种做法，还是先回头检查已有的数据？'],
  reflect:['我们一起回顾一下。\n\n这次你发现了什么？有没有哪一步和你原来想的不一样？','把你的收获接在这句话后面试试：\n\n“我发现……，下次我准备……”\n\n不用写得很长，说清自己的想法就好。'],
}

/** Frontend-only demo transport. Replace the reply source with backend SSE later. */
export function useTeachingChat(){
  const topic=ref<Topic>('plan'), messages=ref<Message[]>([{id:1,role:'assistant',text:welcome}])
  const draft=ref(''), busy=ref(false), thinking=ref(false), saveError=ref('')
  let timer:ReturnType<typeof setTimeout>|undefined, sequence=1
  function persist(){
    try{localStorage.setItem(key,JSON.stringify({version:1,topic:topic.value,messages:messages.value.slice(-80)}));saveError.value=''}
    catch{saveError.value='这次对话暂时无法保存，刷新后可能丢失。'}
  }
  try{
    const saved=JSON.parse(localStorage.getItem(key)||'null')
    if(saved?.version===1&&Array.isArray(saved.messages)){
      const valid=saved.messages.filter((m:Message)=>m&&['assistant','student'].includes(m.role)&&Number.isSafeInteger(m.id)&&typeof m.text==='string'&&m.text.length<=10000).slice(-80)
      if(valid.length){messages.value=valid;sequence=Math.max(...valid.map((m:Message)=>m.id),1)}
      if(['plan','stuck','reflect'].includes(saved.topic))topic.value=saved.topic
    }
  }catch{ /* An invalid demo record does not prevent a fresh conversation. */ }
  const mood=computed(()=>thinking.value?'thinking':busy.value?'talking':'ready')
  const canSend=computed(()=>!!draft.value.trim()&&!busy.value&&draft.value.length<=2000)
  function send(text=draft.value){
    const input=text.trim()
    if(!input||input.length>2000||busy.value)return
    messages.value.push({id:++sequence,role:'student',text:input});draft.value='';busy.value=true;thinking.value=true
    const steps=replies[topic.value]
    const reply=steps[(messages.value.filter(m=>m.role==='student').length-1)%steps.length]!
    persist()
    timer=setTimeout(()=>{
      thinking.value=false
      const id=++sequence
      messages.value.push({id,role:'assistant',text:''})
      let position=0
      const tick=()=>{
        const target=messages.value.find(m=>m.id===id)
        if(!target)return
        position=Math.min(position+4,reply.length);target.text=reply.slice(0,position)
        if(position<reply.length)timer=setTimeout(tick,28)
        else{busy.value=false;timer=undefined;persist()}
      }
      tick()
    },450)
  }
  function stop(){
    if(timer)clearTimeout(timer)
    timer=undefined
    const last=messages.value.at(-1)
    if(busy.value&&last?.role==='assistant')last.paused=true
    busy.value=false;thinking.value=false;persist()
  }
  function reset(){stop();sequence=1;messages.value=[{id:1,role:'assistant',text:welcome}];draft.value='';persist()}
  function selectTopic(value:Topic){topic.value=value;persist()}
  onBeforeUnmount(()=>{if(busy.value)stop()})
  return {topic,messages,draft,busy,thinking,mood,canSend,saveError,send,stop,reset,selectTopic}
}
