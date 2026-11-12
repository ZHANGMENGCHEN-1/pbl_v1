<script setup lang="ts">
import { computed,nextTick,onBeforeUnmount,onMounted,ref,watch } from 'vue'
import { ArrowLeft,MoreFilled,Promotion } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import TeachingRobot from './TeachingRobot.vue'
import ExcelExperiment from './ExcelExperiment.vue'
import type {Analysis,ExplorationSubmission} from './exploration'
import AlgorithmSteps from './AlgorithmSteps.vue'
import CenterExperiment from './CenterExperiment.vue'
import type {Calculation,CalculationSubmission} from './calculation'
import {recordCalculation,recordStepOrder,recordExploration} from './learningState'
import { useTeachingLearning } from './useTeachingLearning'
import { useTeachingChat } from './useTeachingChat'
import { canEnter } from './learningState'
import {algorithmSteps} from './sorting'
import type { ActivityId } from './activities'
import {saveSorting,recordActivityEntry} from './telemetry'

const {state,activity,current,count,complete,records,saveError,persist,enter:enterActivity,reset}=useTeachingLearning()
const {messages,draft,busy,thinking,mood,canSend,send,stop,error:chatError,retry:retryChat}=useTeachingChat(state,persist,()=>operationOpen.value?'task':'dialogue')
const calculationHint=ref(''),explorationHint=ref('')
function explorationChanged(){explorationHint.value='';boundary.value=messages.value.at(-1)?.id||0;state.value.activities.explore_2d.operation={status:'pending',source:'backend',result:null,updatedAt:null}}
function explorationCalculated(result:Analysis){state.value.activities.explore_2d.operation={status:'completed',source:'backend',result:result as unknown as Record<string,unknown>,updatedAt:new Date().toISOString()};explorationHint.value=`先看看两种颜色的点各在哪里：哪一组更靠右，哪一组更靠上？试着用自己的话说说两组有什么不同。`;boundary.value=messages.value.at(-1)?.id||0}
function explorationSubmitted(saved:ExplorationSubmission){const result=state.value.activities.explore_2d.operation.result as unknown as Analysis;recordExploration(state.value,saved,result);persist()}
function calculated(result:Calculation){current.value.operation={status:result.converged?'completed':'pending',source:'backend',result:result as unknown as Record<string,unknown>,updatedAt:new Date().toISOString()};calculationHint.value=result.converged?'两组的书和中心都不再变化了。你可以看着计算过程，自己写下两组的数量和最后的中心。':`这一轮分好了！把这一组中每本书的借阅次数加起来，再除以这一组有几本书，就得到新的中心。`;boundary.value=messages.value.at(-1)?.id||0;persist()}
function calculationSubmitted(saved:CalculationSubmission){recordCalculation(state.value,saved);persist();operationOpen.value=false;calculationHint.value='';boundary.value=messages.value.at(-1)?.id||0;window.scrollTo({top:0,behavior:'smooth'})}
const entry=ref<'hello'|'story'|'learning'>('hello'),bubbleVisible=ref(false),operationOpen=ref(false)
const className=ref(''),studentNumber=ref(''),identitySaving=ref(false),identityError=ref('')
const sortingSaving=ref(false),sortingError=ref(''),sortingCorrect=ref<boolean|null>(null)
async function identify(){
  if(identitySaving.value)return
  identityError.value=''
  if(!className.value.trim()||!studentNumber.value.trim()){identityError.value='请填写班级和学号。';return}
  identitySaving.value=true
  try{
    const response=await fetch('/api/projects/teaching-agent/student',{method:'POST',headers:{'Content-Type':'application/json','X-Session-ID':state.value.sessionId},body:JSON.stringify({class_name:className.value.trim(),student_number:studentNumber.value.trim()})})
    const data=await response.json()
    if(!response.ok)throw new Error(typeof data?.detail==='string'?data.detail:'保存失败，请重试。')
    state.value.student={className:data.class_name,studentNumber:data.student_number}
    persist();entry.value='story'
  }catch(e){identityError.value=e instanceof Error?e.message:'连接失败，请重试。'}finally{identitySaving.value=false}
}
// With the task closed, return to the same conversation composition as the opening.
const dialogueFocus=computed(()=>entry.value==='learning'&&!operationOpen.value)
const recordsOpen=ref(false),historyOpen=ref(false),input=ref<HTMLTextAreaElement>()
const robot=ref<InstanceType<typeof TeachingRobot>>()
const boundary=ref(messages.value.at(-1)?.id||0)
let welcomeTimer:ReturnType<typeof setTimeout>|undefined
onMounted(()=>{welcomeTimer=setTimeout(()=>{bubbleVisible.value=true},350)})
onBeforeUnmount(()=>{if(welcomeTimer)clearTimeout(welcomeTimer)})
const latestReply=computed(()=>messages.value.findLast(m=>m.role==='assistant'&&m.kind==='chat'&&m.activityId===activity.value.id&&m.id>boundary.value&&(m.text||m.paused||m.error)))
const speech=computed(()=>{
  if(entry.value==='hello')return '你好，我是小知。\n今天，我陪你一起帮图书馆想办法。'
  if(entry.value==='story')return '图书馆想把借得多和借得少的书分开。\n我们先看看五本书，一起试试怎样分组，好吗？'
  if(activity.value.id==='explore_2d'&&explorationHint.value)return explorationHint.value
  if(activity.value.id==='group_books'&&calculationHint.value)return calculationHint.value
  return activity.value.introduction
})
const operationLabel=computed(()=>['看看这五本书','看看这四个步骤','准备一张表格'][activity.value.number-1])
function start(){entry.value='learning';operationOpen.value=true;boundary.value=messages.value.at(-1)?.id||0}
function submit(text=draft.value){if(!text.trim()||busy.value||text.length>2000)return;send(text);nextTick(()=>input.value?.focus())}
function enter(event:KeyboardEvent){if(event.shiftKey||event.isComposing||event.keyCode===229)return;event.preventDefault();submit()}
function openTask(){boundary.value=messages.value.at(-1)?.id||0;operationOpen.value=true}
async function submitOrder(order:string[]){
  if(sortingSaving.value)return
  stop();sortingSaving.value=true;sortingError.value='';sortingCorrect.value=null
  try{const saved=await saveSorting(state.value.sessionId,order);boundary.value=messages.value.at(-1)?.id||0;recordStepOrder(state.value,order,saved);sortingCorrect.value=saved.payload.correct;persist()}
  catch(e){sortingError.value=e instanceof Error?e.message:'排序保存失败，请重试。'}finally{sortingSaving.value=false}
}
function continueToThree(){if(enterActivity('explore_2d')){operationOpen.value=false;window.scrollTo({top:0,behavior:'smooth'})}}

function review(id:ActivityId){if(busy.value)return;stop();if(enterActivity(id)){recordsOpen.value=false;entry.value='learning';operationOpen.value=false;boundary.value=messages.value.at(-1)?.id||0}}
watch(()=>activity.value.id,()=>{boundary.value=messages.value.at(-1)?.id||0})
watch(()=>[entry.value,state.value.activeActivityId,state.value.sessionId],()=>{if(entry.value==='learning'&&state.value.student)void recordActivityEntry(state.value.sessionId,state.value.activeActivityId)})
async function restart(){
  try{await ElMessageBox.confirm('要重新开始这次体验吗？','重新开始',{confirmButtonText:'重新开始',cancelButtonText:'继续学习'})}catch{return}
  stop();reset();entry.value='hello';operationOpen.value=false;boundary.value=messages.value.at(-1)?.id||0
}
function menu(command:string){
  if(command==='records')recordsOpen.value=true
  if(command==='history')historyOpen.value=true
  if(command==='restart')restart()
  if(command==='robot')robot.value?.reset()
  if(command==='about')ElMessageBox.alert('活动1由后台真实计算并保存结果。自由提问使用真实模型流式回复，开场和任务提示为预设教学说明。活动2支持拖动排序，反馈由固定规则生成。活动3使用上传的Excel真实计算和作图，小知会结合本次实际结果解释。','功能说明',{confirmButtonText:'知道了'}).catch(()=>{})
}
</script>

<template>
  <div class="teaching-page minimal-teaching">
    <header class="minimal-header"><RouterLink to="/" class="minimal-back" aria-label="返回项目首页"><el-icon><ArrowLeft/></el-icon><span>返回</span></RouterLink><div class="minimal-menu"><span class="demo-mark">AI 对话</span><el-dropdown trigger="click" @command="menu"><button class="more-button" aria-label="更多" :disabled="busy"><el-icon><MoreFilled/></el-icon></button><template #dropdown><el-dropdown-menu><el-dropdown-item command="history">对话记录</el-dropdown-item><el-dropdown-item command="records">学习记录</el-dropdown-item><el-dropdown-item command="robot">小知转回正面</el-dropdown-item><el-dropdown-item command="restart">重新开始</el-dropdown-item><el-dropdown-item command="about" divided>功能说明</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div></header>
    <main class="minimal-scene" :class="{'has-operation':operationOpen,'dialogue-focus':dialogueFocus,'wide-task':entry==='learning'&&operationOpen&&activity.id==='explore_2d'}">
      <div class="robot-stage" :class="{'has-chat-reply':entry==='learning'&&operationOpen}"><div class="robot-figure"><section v-if="entry==='learning'&&operationOpen&&(activity.id==='group_books'||explorationHint||latestReply||thinking)" class="robot-chat-bubble" aria-label="小知的话" aria-live="polite"><span class="speaker-label">小知</span><p v-if="!latestReply&&!thinking&&(activity.id==='group_books'||explorationHint)" class="task-guidance">{{speech}}</p><p v-if="latestReply?.text" class="question-reply">{{latestReply.text}}</p><small v-if="latestReply?.paused" class="chat-state" role="status">已暂停回复</small><small v-else-if="latestReply?.error" class="chat-state">回复未完成</small><span v-else-if="thinking" class="chat-state" role="status">小知正在思考…</span></section><TeachingRobot ref="robot" :mood="mood" :show-controls="false"/></div><form v-if="entry==='learning'" class="minimal-composer" @submit.prevent="submit()"><label class="composer-label" for="teaching-input">和小知说说你的问题</label><textarea id="teaching-input" ref="input" v-model="draft" rows="1" maxlength="2000" placeholder="和小知说说你的想法……" @keydown.enter="enter"/><button v-if="busy" type="button" class="send-button stop-button" aria-label="暂停回复" @click="stop(true)">■</button><button v-else class="send-button" type="submit" aria-label="发送" :disabled="!canSend"><el-icon><Promotion/></el-icon></button></form><p v-if="chatError" class="chat-error" role="alert">{{chatError}} <button :disabled="busy" @click="retryChat">重试</button></p></div>
      <div class="minimal-conversation">
        <Transition name="speech" appear><section v-if="bubbleVisible&&(entry!=='learning'||dialogueFocus)" class="xiaozhi-speech" aria-label="小知的话" aria-live="polite"><span class="speaker-label">小知</span><p>{{speech}}</p><p v-if="dialogueFocus&&latestReply?.text" class="dialogue-reply">{{latestReply.text}}</p><small v-if="dialogueFocus&&latestReply?.paused" class="chat-state" role="status">已暂停回复</small><small v-else-if="dialogueFocus&&latestReply?.error" class="chat-state">回复未完成</small><span v-else-if="dialogueFocus&&thinking" class="chat-state" role="status">小知正在思考…</span></section></Transition>
        <div v-if="bubbleVisible" class="speech-actions">
          <form v-if="entry==='hello'" class="student-identity" @submit.prevent="identify">
            <label for="student-class">班级<input id="student-class" v-model="className" maxlength="80" placeholder="例如：七年级1班" required :disabled="identitySaving"></label>
            <label for="student-number">学号<input id="student-number" v-model="studentNumber" maxlength="40" placeholder="请输入学号" required :disabled="identitySaving"></label>
            <p v-if="identityError" class="chat-error" role="alert">{{identityError}}</p>
            <button class="primary-response" :disabled="identitySaving">{{identitySaving?'正在保存…':'确认并继续'}}</button>
          </form>
          <button v-else-if="entry==='story'" class="primary-response" @click="start">进入活动1</button>
          <button v-else-if="!operationOpen&&!complete" class="primary-response" :class="{'enter-activity-two':activity.id==='explain_algorithm'}" :disabled="busy" @click="openTask">{{activity.id==='explain_algorithm'?'进入活动2':operationLabel}}</button>
        </div>
        <template v-if="entry==='learning'">
          <div v-if="operationOpen" class="minimal-operation"><CenterExperiment v-if="activity.id==='group_books'" :session-id="state.sessionId" :draft="current.draft" @result="calculated" @submitted="calculationSubmitted" @restored="saved=>{recordCalculation(state,saved,false);persist()}"/><AlgorithmSteps v-else-if="activity.id==='explain_algorithm'" :draft="current.draft" :disabled="busy||sortingSaving" :submitted-correct="sortingCorrect" @submit="submitOrder"/><ExcelExperiment v-else :session-id="state.sessionId" :draft="current.draft" @changed="explorationChanged" @result="explorationCalculated" @submitted="explorationSubmitted"/><div class="operation-actions"><button v-if="activity.id==='explain_algorithm'&&canEnter(state,'explore_2d')" class="primary-response enter-activity-two" :disabled="busy||sortingSaving" @click="continueToThree">进入活动3 →</button></div></div>

          <p v-if="saveError" class="save-error" role="status">{{saveError}}</p>
          <p v-if="sortingError" class="chat-error" role="alert">{{sortingError}}</p>
        </template>
      </div>
    </main>
    <el-drawer v-model="historyOpen" title="对话记录" size="min(560px, 92vw)" class="minimal-history"><article v-for="message in messages" :key="message.id" class="history-message" :class="message.role"><small>{{message.role==='assistant'?'小知':'我'}}</small><p>{{message.text}}</p><small v-if="message.paused">已暂停</small><small v-if="message.error">{{message.error}}</small></article></el-drawer>
    <el-drawer v-model="recordsOpen" title="学习记录" size="min(560px, 92vw)" class="teaching-records"><p class="records-explanation">活动1保存你的填写结果与实际计算结果。活动2保存每次排序及反馈，活动3保存你填写的数量与分组特点。</p><article v-for="item in records" :key="item.id" class="teaching-record-card"><h3>{{item.title}}</h3><p>{{item.state.submissions.length?(item.id==='group_books'?'已提交':'已体验'):canEnter(state,item.id)?'还没有体验':'稍后开始'}}</p><section v-for="record in item.state.submissions" :key="record.id" class="preview-submission"><time>{{new Date(record.createdAt).toLocaleString('zh-CN')}}</time><div v-if="record.payload.calculation"><p>我的填写：两组各{{record.payload.calculation.payload.student_result.counts.join('、')}}本；中心{{record.payload.calculation.payload.student_result.centers.join('、')}}。</p><details><summary>查看实际计算</summary><p>两组各{{record.payload.calculation.payload.tool_result.counts.join('、')}}本；中心{{record.payload.calculation.payload.tool_result.centers.join('、')}}。</p></details></div><div v-if="record.payload.sorting"><p>我的排序：{{record.payload.sorting.order.map(id=>algorithmSteps.find(s=>s.id===id)?.text).join(' → ')}}</p><p>{{record.payload.sorting.feedback}}</p></div><div v-if="record.payload.exploration"><p>文件：{{record.payload.exploration.payload.teaching_context.filename}}</p><p>分析列：{{record.payload.exploration.payload.features.map(f=>f.name).join('、')}}</p><p>我的填写：两组各{{record.payload.exploration.payload.student_result.counts.join('、')}}条。</p><p>{{record.payload.exploration.payload.student_result.description}}</p></div><p v-if="record.payload.note">{{record.payload.note}}</p></section><button :disabled="busy||!canEnter(state,item.id)" @click="review(item.id)">回到这里</button></article></el-drawer>
  </div>
</template>

<style scoped>
.student-identity{width:100%;display:grid;grid-template-columns:1fr 1fr;gap:12px 16px;padding:20px;box-sizing:border-box;background:#fff;border:2px solid #b69ad9;border-radius:18px}.student-identity label{font-size:14px;font-weight:600;color:#67418b;min-width:0}.student-identity input{display:block;box-sizing:border-box;width:100%;margin-top:8px;padding:12px;border:1px solid #b69ad9;border-radius:10px;font:inherit;color:#49345f;background:#fcfaff}.student-identity input:focus{outline:2px solid #8052b1;outline-offset:2px}.student-identity p{grid-column:1/-1;margin:0;font-size:13px;line-height:1.7}.identity-hint{color:#73528d}.student-identity button{grid-column:1/-1;justify-self:end}@media(max-width:420px){.student-identity{grid-template-columns:1fr}}
.chat-state{display:block;color:#9b83ad;font-size:14px;line-height:1.8;margin-top:10px}.chat-error{font-size:14px;line-height:1.8;color:#aa6157;overflow-wrap:anywhere}.chat-error button{border:0;background:transparent;color:#8862b2;cursor:pointer;font-size:14px;padding:4px 6px}
@media(min-width:1101px){.minimal-scene.wide-task{max-width:1480px;grid-template-columns:260px minmax(0,1fr);gap:32px;padding-left:32px;padding-right:32px}}
.robot-chat-bubble .question-reply:first-child{margin-top:0;padding-top:0;border-top:0}
.enter-activity-two{position:fixed;right:32px;bottom:28px;z-index:20}
.dialogue-focus .robot-stage{position:static}.xiaozhi-speech .dialogue-reply{margin-top:20px;padding-top:18px;border-top:1px solid #eee5f5;font-size:16px;color:#8a739d}
.robot-figure{position:relative}.robot-chat-bubble{position:relative;margin-bottom:24px;left:50%;transform:translateX(-50%);width:300px;max-width:calc(100vw - 48px);box-sizing:border-box;background:white;border:1px solid #e5d8f0;border-radius:20px;padding:18px 22px;box-shadow:0 8px 28px #80629912}.robot-chat-bubble::after{content:"";position:absolute;bottom:-8px;left:50%;width:14px;height:14px;background:white;border-right:1px solid #e5d8f0;border-bottom:1px solid #e5d8f0;transform:rotate(45deg)}.robot-chat-bubble p{margin:0;font-size:16px;line-height:1.8;white-space:pre-wrap}.robot-chat-bubble .question-reply{margin-top:14px;padding-top:14px;border-top:1px solid #eee5f5;color:#8a739d}.robot-stage.has-chat-reply{padding-top:0}.has-operation .minimal-operation{margin-top:0}.has-operation .speech-actions{margin-top:0}
.teaching-page{min-height:100dvh;background:radial-gradient(ellipse at 35% 48%,#f0eaf9 0,transparent 48%),#faf9fd;color:#5e4c73;font-size:16px}.minimal-header{height:72px;display:flex;align-items:center;justify-content:space-between;padding:0 36px}.minimal-back{display:flex;align-items:center;gap:7px;color:#9b8caa;text-decoration:none;font-size:14px}.minimal-back:hover{color:#795b9b}.minimal-menu{display:flex;align-items:center;gap:14px}.demo-mark{font-size:11px;color:#b0a2bd}.more-button{display:grid;place-items:center;width:34px;height:34px;border:0;border-radius:50%;background:transparent;color:#a995ba;font-size:20px}.more-button:hover{background:#efe8f6}.minimal-scene{display:grid;grid-template-columns:340px minmax(0,530px);align-items:center;justify-content:center;gap:64px;max-width:1100px;min-height:calc(100dvh - 140px);padding:40px 36px 100px;margin:0 auto}.robot-stage{width:100%;position:sticky;top:140px;align-self:center}.minimal-conversation{min-width:0}.xiaozhi-speech{position:relative;padding:30px 34px;background:#fff;border:1px solid #ede6f5;border-radius:25px 25px 25px 5px;box-shadow:0 12px 40px #82669b09}.xiaozhi-speech::before{content:'';position:absolute;left:-13px;top:49%;width:24px;height:24px;background:white;border-left:1px solid #ede6f5;border-bottom:1px solid #ede6f5;transform:rotate(45deg)}.xiaozhi-speech p{position:relative;font-size:20px;line-height:1.95;white-space:pre-wrap;overflow-wrap:anywhere;margin:0;color:#6e577f}.speech-dots{display:block;color:#b69acb;letter-spacing:5px;margin-top:10px}.speech-actions{display:flex;gap:12px;justify-content:flex-end;margin-top:22px}.primary-response{border:0;border-radius:12px;background:#9070c1;color:white;font-size:16px;padding:12px 24px;line-height:1.7;box-shadow:0 5px 14px #8d6bb819}.primary-response:hover{background:#7e5bac}.primary-response:disabled{opacity:.5}.minimal-composer{display:flex;align-items:flex-end;gap:12px;margin-top:28px;padding:8px 3px 10px;border-bottom:1px solid #dcd1e9}.minimal-composer textarea{flex:1;min-width:0;min-height:32px;max-height:140px;resize:vertical;background:transparent;outline:none;border:0;color:#765f89;font-size:16px;line-height:1.8;padding:1px 3px}.minimal-composer textarea::placeholder{color:#b5a6c2}.send-button{display:grid;place-items:center;flex-shrink:0;width:36px;height:36px;border:0;border-radius:50%;background:#9577c0;color:white;font-size:20px}.send-button:disabled{color:#c4b5d2;background:#ece5f4}.stop-button{font-size:13px}.minimal-operation{margin-top:24px}.minimal-operation :deep(.activity-preview-card){margin:0;background:#ffffffc9;padding:20px;border-radius:16px}.operation-actions{display:flex;justify-content:space-between;gap:12px;margin-top:12px}.quiet-button{padding:8px 4px;font-size:13px;border:0;background:transparent;color:#ad9abf}.next-preview{color:#8e6baa}.quiet-button:hover{color:#705087}.save-error{font-size:12px;line-height:1.8;color:#ab7e73}.speech-enter-active{transition:opacity .5s ease,transform .5s ease}.speech-enter-from{opacity:0;transform:translateY(14px) scale(.98)}.history-message{padding:16px;border-radius:12px;background:#f8f4fc;margin-bottom:14px}.history-message.student{background:#eee6f7}.history-message small{font-size:12px;color:#aa94b9}.history-message p{font-size:16px;line-height:1.9;color:#765e88;white-space:pre-wrap;margin:8px 0}.records-explanation{font-size:13px;line-height:1.8;color:#a08eac}.teaching-record-card{padding:18px 0;border-bottom:1px solid #ece5f3}.teaching-record-card h3{font-size:16px;color:#79618c;line-height:1.7;margin:0 0 10px}.teaching-record-card>p{font-size:14px;color:#a28eb1}.teaching-record-card button{border:1px solid #e2d6ed;border-radius:8px;background:white;padding:7px 11px;color:#997cad;font-size:13px}.teaching-record-card button:disabled{opacity:.4}.preview-submission time{font-size:12px;color:#b2a0bf}.preview-submission p{font-size:14px;line-height:1.8;color:#8d749d}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}button:focus-visible,a:focus-visible{outline:3px solid #cab6e2;outline-offset:4px}
@media(min-width:901px){.has-operation{align-items:start;padding-top:70px}.has-operation .robot-stage{align-self:start}}
@media(max-width:900px){.minimal-header{height:60px;padding:0 22px}.minimal-scene{grid-template-columns:240px minmax(0,1fr);gap:32px;min-height:calc(100dvh - 80px);padding:30px 28px 80px}.xiaozhi-speech{padding:24px}.xiaozhi-speech p{font-size:18px}.robot-stage{position:static}.primary-response{font-size:15px}}
@media(max-width:650px){.minimal-scene{display:flex;flex-direction:column;gap:16px;justify-content:center;padding:18px 24px 60px;min-height:calc(100dvh - 80px)}.robot-stage{max-width:230px;margin:0 auto}.minimal-conversation{width:100%;max-width:500px}.xiaozhi-speech{padding:22px 24px;border-radius:20px}.xiaozhi-speech::before{left:45%;top:-12px;transform:rotate(135deg);width:20px;height:20px}.xiaozhi-speech p{font-size:18px;line-height:1.9}.speech-actions{margin-top:18px}.minimal-composer{margin-top:22px}.has-operation{justify-content:flex-start}.has-operation .robot-stage{max-width:350px}.has-operation .robot-figure{max-width:155px;margin:auto}.minimal-operation :deep(.activity-preview-card){padding:16px}.demo-mark{font-size:10px}}
.robot-figure:has(.robot-chat-bubble){--robot-chat-reserve:200px;padding-top:var(--robot-chat-reserve)}
.has-operation .robot-stage{box-sizing:border-box;padding-top:20px}.robot-chat-bubble{position:absolute;top:auto;bottom:calc(100% - var(--robot-chat-reserve) + 14px);margin:0}
.robot-chat-bubble,.xiaozhi-speech{background:#fff;border:2px solid #b69ad9;box-shadow:0 10px 30px #69449624}
.robot-chat-bubble::after{border-color:#b69ad9;border-width:2px}
.xiaozhi-speech::before{border-color:#b69ad9;border-width:2px}
.speaker-label{display:block;width:fit-content;margin-bottom:10px;padding:3px 10px;border-radius:8px;background:#eee4fa;color:#67418b;font-size:13px;font-weight:700;line-height:1.6}
.robot-chat-bubble p,.robot-chat-bubble .question-reply,.xiaozhi-speech p,.xiaozhi-speech .dialogue-reply{color:#49345f;overflow-wrap:anywhere}
.robot-chat-bubble .question-reply{margin-top:0;padding-top:0;border-top:0}
.minimal-composer{flex-wrap:wrap;gap:8px 10px;padding:14px 16px;background:#fff;border:2px solid #a78bc9;border-radius:18px;box-shadow:0 6px 20px #69449616;transition:border-color .18s,box-shadow .18s}
.minimal-composer:focus-within{border-color:#8052b1;box-shadow:0 0 0 4px #9364c921,0 6px 20px #69449616}
.composer-label{flex:0 0 100%;color:#67418b;font-size:13px;font-weight:700;line-height:1.6;cursor:text}
.minimal-composer textarea{color:#49345f;min-height:40px}
.minimal-composer textarea::placeholder{color:#82718f}
.send-button{width:40px;height:40px;background:#8052b1}
.send-button:disabled{color:#8c799e;background:#e9dff3}
.history-message{border:1px solid #cab5df;background:#fff;margin-right:24px}
.history-message.student{margin-right:0;margin-left:24px;background:#eee4fa;border-color:#b69ad9}
.history-message small{color:#73528d;font-weight:600}
.history-message p{color:#49345f}
@media(prefers-reduced-motion:reduce){.speech-enter-active,.minimal-composer{transition:none}}
</style>
