<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { ArrowLeft, ChatDotRound, Flag, Opportunity, Position, Promotion, RefreshLeft, Notebook } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import TeachingRobot from './TeachingRobot.vue'
import { useTeachingChat, type Topic } from './useTeachingChat'

const {topic,messages,draft,busy,thinking,mood,canSend,saveError,send,stop,reset,selectTopic}=useTeachingChat()
const transcript=ref<HTMLElement>(),input=ref<HTMLTextAreaElement>(),follow=ref(true)
const topics=[
  {id:'plan' as Topic,label:'我想做个计划',hint:'把任务变成几个小步骤',icon:Flag},
  {id:'stuck' as Topic,label:'我有点卡住了',hint:'一起找找可以试的办法',icon:Opportunity},
  {id:'reflect' as Topic,label:'我想回顾一下',hint:'说说发现和下一次的想法',icon:Notebook},
]
const starters:Record<Topic,string[]>={
  plan:['我不知道从哪里开始','帮我把任务分成几步','我想先确定学习目标'],
  stuck:['这一步我没看懂','我试过了，但结果不一样','我该怎样检查数据？'],
  reflect:['我想说说今天的发现','怎么检查自己的结果？','下次可以怎样做得更好？'],
}
async function scroll(){await nextTick();if(follow.value&&transcript.value)transcript.value.scrollTop=transcript.value.scrollHeight}
watch(()=>messages.value.at(-1)?.text,scroll,{immediate:true})
watch(thinking,scroll)
function onScroll(){const el=transcript.value;if(el)follow.value=el.scrollHeight-el.scrollTop-el.clientHeight<100}
function submit(text=draft.value){if(!text.trim()||busy.value||text.length>2000)return;follow.value=true;send(text);nextTick(()=>input.value?.focus())}
function enter(event:KeyboardEvent){if(event.shiftKey||event.isComposing||event.keyCode===229)return;event.preventDefault();submit()}
function choose(value:Topic){selectTopic(value);nextTick(()=>input.value?.focus())}
async function restart(){
  if(messages.value.some(m=>m.role==='student')){
    try{await ElMessageBox.confirm('重新开始会清空这段示例对话。要继续吗？','重新开始',{confirmButtonText:'重新开始',cancelButtonText:'继续聊',type:'info'})}catch{return}
  }
  reset();follow.value=true;await scroll();input.value?.focus()
}
</script>

<template>
  <div class="teaching-page">
    <header class="teaching-header">
      <RouterLink class="teaching-brand" to="/" aria-label="Orbit 项目首页"><span class="teaching-brand-mark"><el-icon><Position/></el-icon></span>orbit<span class="teaching-brand-divider"/><span class="teaching-page-label">教学 Agent</span></RouterLink>
      <RouterLink class="teaching-home-link" to="/"><el-icon><ArrowLeft/></el-icon>返回项目首页</RouterLink>
    </header>

    <main class="teaching-layout">
      <aside class="teaching-companion">
        <div class="companion-intro"><span class="companion-eyebrow">一起想，一起学</span><h1>嗨，我是小知<span> ✦</span></h1><p>你的学习搭子，陪你找到下一步。</p></div>
        <div class="robot-stage"><span class="robot-speech">{{thinking?'让我想一想……':busy?'我们一步一步来！':'今天想一起探索什么？'}}</span><TeachingRobot :mood="mood"/></div>
        <div class="topic-section"><h2>从这里开始</h2><button v-for="item in topics" :key="item.id" class="topic-button" :class="{selected:topic===item.id}" :aria-pressed="topic===item.id" @click="choose(item.id)"><span class="topic-icon"><el-icon><component :is="item.icon"/></el-icon></span><span><strong>{{item.label}}</strong><small>{{item.hint}}</small></span><span class="topic-arrow">↗</span></button></div>
        <p class="companion-note">不着急，我们先迈出一小步。</p>
      </aside>

      <section class="teaching-chat" aria-label="与小知对话">
        <header class="teaching-chat-header"><div class="chat-title"><span class="chat-title-icon"><el-icon><ChatDotRound/></el-icon></span><div><h2>和小知聊一聊</h2><p>把问题说出来，思路就开始了。</p></div></div><button class="chat-restart" :disabled="busy" @click="restart"><el-icon><RefreshLeft/></el-icon><span>重新开始</span></button></header>
        <div class="teaching-demo-banner"><span class="demo-badge">示例对话</span><span>当前使用预设示例回复，尚未接入真实 AI。</span></div>
        <div ref="transcript" class="teaching-transcript" role="log" aria-label="对话记录" :aria-live="busy?'off':'polite'" @scroll="onScroll">
          <div class="conversation-divider"><span>让学习从一个问题开始</span></div>
          <article v-for="message in messages" :key="message.id" class="teaching-message" :class="message.role">
            <div v-if="message.role==='assistant'" class="message-avatar"><TeachingRobot compact/></div>
            <div class="message-main"><span class="message-name">{{message.role==='assistant'?'小知':'我'}}</span><div class="message-bubble"><p>{{message.text}}</p><span v-if="message.paused" class="message-paused">示例回复已暂停</span></div></div>
            <span v-if="message.role==='student'" class="student-avatar">我</span>
          </article>
          <div v-if="thinking" class="typing-indicator" role="status" aria-label="小知正在准备示例回复"><span/><span/><span/></div>
          <div v-if="messages.length===1" class="conversation-welcome"><span class="welcome-star">✦</span><p>不知道怎么开口？试试下面的小问题。</p></div>
        </div>
        <footer class="teaching-composer">
          <div class="starter-prompts" aria-label="快捷提问"><button v-for="text in starters[topic]" :key="text" :disabled="busy" @click="submit(text)">{{text}}<span>↗</span></button></div>
          <form class="composer-box" @submit.prevent="submit()"><label class="sr-only" for="teaching-input">和小知说说你的问题</label><textarea id="teaching-input" ref="input" v-model="draft" maxlength="2000" rows="2" placeholder="我正在做……，我想知道……" @keydown.enter="enter"/><div class="composer-bottom"><span class="composer-key-hint">Enter 发送 · Shift + Enter 换行</span><button v-if="busy" type="button" class="chat-stop" @click="stop"><span/>暂停回复</button><button v-else type="submit" class="chat-send" :disabled="!canSend">发送<el-icon><Promotion/></el-icon></button></div></form>
          <p v-if="saveError" class="chat-save-error" role="status">{{saveError}}</p><p v-else class="chat-local-note">示例对话仅保存在当前浏览器中</p>
        </footer>
      </section>
    </main>
  </div>
</template>

<style scoped>
.teaching-page{height:100dvh;min-height:600px;background:#f5f5fa;color:#34334c;display:flex;flex-direction:column;font-size:16px;overflow:hidden}
.teaching-header{height:76px;flex-shrink:0;padding:0 36px;background:#ffffffed;border-bottom:1px solid #e8e6f0;display:flex;align-items:center;justify-content:space-between;gap:20px}
.teaching-brand{display:flex;align-items:center;gap:10px;text-decoration:none;color:#292539;font-size:28px;font-weight:750;letter-spacing:-1px}
.teaching-brand-mark{display:grid;place-items:center;width:32px;height:32px;border-radius:10px;background:#7c5ce0;color:white;font-size:22px;transform:rotate(-8deg)}
.teaching-brand-divider{height:25px;width:1px;background:#e4dfef;margin:0 8px 0 16px}.teaching-page-label{font-size:16px;letter-spacing:0;font-weight:650;color:#65537e}
.teaching-home-link{display:flex;align-items:center;gap:8px;color:#7b718e;text-decoration:none;font-size:14px}.teaching-home-link:hover{color:#7855cb}
.teaching-layout{display:grid;grid-template-columns:330px minmax(0,1fr);width:100%;max-width:1370px;min-height:0;flex:1;margin:0 auto;padding:28px 32px;gap:28px}
.teaching-companion{min-height:0;overflow:auto;display:flex;flex-direction:column;padding:12px 4px 0}.companion-eyebrow{font-size:13px;letter-spacing:2px;color:#9786af}.companion-intro h1{font-size:29px;font-weight:720;line-height:1.5;color:#4d3f67;margin:12px 0 6px}.companion-intro h1 span{color:#bca7db;font-size:23px}.companion-intro>p{font-size:15px;color:#8a7e9b;line-height:1.8;margin:0}
.robot-stage{position:relative;max-width:280px;width:100%;margin:40px auto 0}.robot-speech{position:absolute;z-index:1;top:-20px;right:0;background:#fff;border:1px solid #e8e1f4;border-radius:13px 13px 13px 2px;padding:10px 14px;color:#8b78a5;font-size:13px;box-shadow:0 5px 14px #8770aa08;white-space:nowrap}
.topic-section{margin-top:4px}.topic-section h2{font-size:13px;color:#9b90aa;font-weight:500;margin:0 0 12px;letter-spacing:1px}.topic-button{display:flex;align-items:center;gap:12px;width:100%;border:1px solid transparent;background:transparent;border-radius:12px;text-align:left;padding:12px;margin:3px 0;color:#7d728d;transition:background .2s,border-color .2s}.topic-button:hover{background:#eeebf7}.topic-button.selected{background:#fff;border-color:#e7def5;box-shadow:0 4px 13px #5e398106}.topic-icon{display:grid;place-items:center;width:37px;height:37px;flex-shrink:0;border-radius:11px;background:#eae4f6;color:#967ac1;font-size:20px}.topic-button strong{display:block;font-size:15px;font-weight:650;color:#655476}.topic-button small{display:block;font-size:12px;margin-top:5px;color:#a096ad}.topic-arrow{margin-left:auto;color:#b7a6cd}.companion-note{font-size:12px;text-align:center;color:#aea3ba;margin:22px 0 0}
.teaching-chat{min-height:0;min-width:0;display:flex;flex-direction:column;background:#fff;border:1px solid #e9e4f1;border-radius:20px;box-shadow:0 8px 35px #67507506;overflow:hidden}
.teaching-chat-header{padding:22px 28px;display:flex;align-items:center;justify-content:space-between;gap:12px;border-bottom:1px solid #f0ecf5}.chat-title{display:flex;align-items:center;gap:13px}.chat-title-icon{display:grid;place-items:center;width:43px;height:43px;border-radius:13px;background:#f0eafb;color:#997bca;font-size:23px}.chat-title h2{font-size:18px;font-weight:700;color:#58456f;margin:0}.chat-title p{font-size:12px;color:#a89bb6;margin:6px 0 0}.chat-restart{display:flex;align-items:center;gap:6px;flex-shrink:0;border:0;background:transparent;font-size:13px;color:#a093ae;padding:8px}.chat-restart:hover{color:#7656b1}.chat-restart:disabled{opacity:.4}
.teaching-demo-banner{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:11px 28px;background:#fcfbfe;color:#a49aad;font-size:12px;border-bottom:1px solid #f3eff8}.demo-badge{padding:3px 8px;border-radius:5px;background:#eee7f8;color:#9479b5;white-space:nowrap}
.teaching-transcript{min-height:0;flex:1;overflow:auto;padding:0 28px 24px;scrollbar-width:thin;scrollbar-color:#e5ddf0 transparent}.conversation-divider{display:flex;align-items:center;gap:15px;color:#beb3c8;font-size:11px;justify-content:center;padding:24px 0}.conversation-divider::before,.conversation-divider::after{content:'';height:1px;width:50px;background:#efeaf5}.teaching-message{display:flex;align-items:flex-start;gap:12px;margin-bottom:24px}.message-avatar{width:40px;height:40px;flex-shrink:0;background:#f4effb;border:1px solid #e9e1f3;border-radius:13px;overflow:hidden;display:flex;align-items:center;justify-content:center}.message-main{max-width:83%;min-width:0}.message-name{display:block;color:#a399b0;font-size:12px;margin:0 0 8px 2px}.message-bubble{padding:16px 20px;background:#faf8fe;border:1px solid #eee8f6;border-radius:0 15px 15px 15px}.message-bubble p{font-size:16px;line-height:1.9;white-space:pre-wrap;overflow-wrap:anywhere;margin:0;color:#6d5c7e}.teaching-message.student{justify-content:flex-end}.student .message-name{text-align:right;margin-right:3px}.student .message-bubble{background:#8a6aca;border-color:#8a6aca;border-radius:15px 0 15px 15px}.student .message-bubble p{color:#fff}.student-avatar{display:grid;place-items:center;width:36px;height:36px;flex-shrink:0;border-radius:12px;background:#eee9f7;color:#9a84b9;font-size:13px}.message-paused{display:block;color:#aa9bb9;font-size:11px;margin-top:12px}.typing-indicator{display:flex;gap:5px;margin:0 0 24px 52px;padding:10px 0}.typing-indicator span{width:6px;height:6px;border-radius:50%;background:#b09acb;animation:typing 1s infinite}.typing-indicator span:nth-child(2){animation-delay:.15s}.typing-indicator span:nth-child(3){animation-delay:.3s}.conversation-welcome{padding:30px 0 18px;text-align:center;color:#b2a5c0;font-size:13px}.welcome-star{font-size:28px;color:#d4c4e7}.conversation-welcome p{margin-top:12px}
.teaching-composer{flex-shrink:0;padding:0 26px 12px;background:#fff}.starter-prompts{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}.starter-prompts button{display:flex;gap:12px;align-items:center;background:#fff;border:1px solid #eae2f4;border-radius:8px;padding:9px 11px;color:#9d8bb1;font-size:12px;transition:border-color .2s,color .2s}.starter-prompts button:hover{border-color:#b59bdb;color:#7855b0}.starter-prompts button:disabled{opacity:.4}.starter-prompts button span{color:#bdabce}.composer-box{padding:15px 17px 12px;border:1px solid #e6dcef;border-radius:13px;background:#fdfcfe;transition:border-color .2s,box-shadow .2s}.composer-box:focus-within{border-color:#b69ad8;box-shadow:0 0 0 3px #b69ad80b}.composer-box textarea{display:block;width:100%;border:0;outline:none;resize:none;background:transparent;font-size:16px;line-height:1.7;color:#69567b;min-height:55px;max-height:160px}.composer-box textarea::placeholder{color:#bbb0c8}.composer-bottom{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:12px}.composer-key-hint{font-size:11px;color:#c0b4ca}.chat-send,.chat-stop{display:flex;align-items:center;gap:9px;justify-content:center;min-height:36px;border:0;border-radius:8px;background:#8a6aca;color:white;padding:8px 15px;font-size:13px}.chat-send:hover{background:#7957b9}.chat-send:disabled{background:#e7e0f0;color:#bcb0cd}.chat-stop{background:#eee8f6;color:#9173b6}.chat-stop>span{width:8px;height:8px;background:currentColor;border-radius:2px}.chat-local-note,.chat-save-error{text-align:center;font-size:11px;color:#c2b8cb;margin:10px 0 0}.chat-save-error{color:#b38b6e}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
.teaching-demo-banner{color:#81718f}.demo-badge{color:#7e609f}.starter-prompts button{color:#857096}.chat-restart{color:#877594}.topic-button small{color:#8c7c9c}
button:focus-visible,a:focus-visible{outline:3px solid #b8a0de;outline-offset:3px}@keyframes typing{50%{opacity:.25;transform:translateY(-3px)}}
@media(max-height:820px) and (min-width:901px){.teaching-layout{padding-top:20px;padding-bottom:20px}.robot-stage{max-width:210px;margin-top:32px}.companion-intro h1{font-size:26px}.topic-button{padding:9px}.companion-note{margin-top:12px}.teaching-chat-header{padding:17px 24px}.conversation-welcome{padding-top:12px}}
@media(max-width:1050px){.teaching-layout{grid-template-columns:275px minmax(0,1fr);padding:22px;gap:20px}.robot-stage{max-width:245px}.starter-prompts{gap:6px}.starter-prompts button{font-size:11px;padding:8px}.teaching-chat-header{padding:20px}.teaching-demo-banner{padding-left:20px;padding-right:20px}.teaching-composer{padding-left:20px;padding-right:20px}.teaching-transcript{padding-left:20px;padding-right:20px}}
@media(max-width:900px){.teaching-page{height:auto;min-height:100dvh;overflow:visible}.teaching-header{height:68px;padding:0 20px}.teaching-layout{display:flex;flex-direction:column;padding:20px;gap:18px}.teaching-companion{overflow:visible;padding:0}.companion-intro{padding-right:100px;position:relative}.companion-intro h1{font-size:25px;margin:5px 0}.companion-intro>p{font-size:13px}.companion-eyebrow{font-size:11px}.robot-stage{position:absolute;right:24px;top:84px;width:95px;margin:0}.robot-speech,.companion-note{display:none}.topic-section{margin-top:18px;display:flex;gap:8px}.topic-section h2{display:none}.topic-button{padding:9px;gap:8px;margin:0;width:auto;flex:1}.topic-button small,.topic-arrow{display:none}.topic-button strong{font-size:12px}.topic-icon{width:28px;height:28px;font-size:16px;border-radius:9px}.teaching-chat{height:720px;min-height:560px;max-height:calc(100dvh - 90px)}.teaching-page-label{font-size:14px}.teaching-brand-divider{margin-left:7px}.teaching-home-link{font-size:12px}}
@media(max-width:520px){.teaching-layout{padding:14px;gap:16px}.teaching-header{padding:0 16px}.teaching-brand{font-size:24px;gap:7px}.teaching-brand-divider{margin-right:2px}.teaching-page-label{font-size:12px}.teaching-brand-mark{width:28px;height:28px}.teaching-home-link{font-size:11px;gap:4px}.teaching-chat{border-radius:15px;height:680px}.teaching-chat-header{padding:16px 14px}.chat-title{gap:8px}.chat-title h2{font-size:16px}.chat-title p{font-size:11px}.chat-title-icon{width:35px;height:35px;font-size:19px}.chat-restart{font-size:11px;padding:5px}.teaching-transcript{padding:0 14px 16px}.teaching-demo-banner{padding:9px 14px;font-size:10px;gap:6px}.teaching-message{gap:8px}.message-avatar{width:32px;height:32px;border-radius:10px}.message-main{max-width:84%}.message-bubble{padding:12px 14px}.message-bubble p{font-size:15px}.student-avatar{display:none}.starter-prompts button{font-size:11px}.starter-prompts button:last-child{display:none}.teaching-composer{padding:0 12px 10px}.composer-key-hint{font-size:9px}.topic-button{padding:8px 5px;gap:5px}.topic-button strong{font-size:11px}.robot-stage{right:14px}.companion-intro h1{font-size:24px}}
@media(prefers-reduced-motion:reduce){.typing-indicator span{animation:none}}
</style>
