<script setup lang="ts">
import {computed,ref,watch} from 'vue'
import CenterExperiment from './CenterExperiment.vue'
import AlgorithmSteps from './AlgorithmSteps.vue'
import ExcelExperiment from './ExcelExperiment.vue'
import {useTeachingLearning} from './useTeachingLearning'
import {canEnter,recordCalculation,recordStepOrder,recordExploration} from './learningState'
import type {ActivityId} from './activities'
import type {Calculation,CalculationSubmission} from './calculation'
import type {Analysis,ExplorationSubmission} from './exploration'
import {saveSorting,recordActivityEntry} from './telemetry'
import StateMeasurement from '../teaching-shared/StateMeasurement.vue'
import SelfReport from '../teaching-shared/SelfReport.vue'

const {state,activity,current,records,complete,enter:enterActivity,persist}=useTeachingLearning()
const className=ref(''),studentNumber=ref(''),saving=ref(false),error=ref('')
const selfReportOpen=ref(false)
const sortingCorrect=ref<boolean|null>(null),reviewing=ref(false)
const taskBusy=ref(false)
const reflection=ref<{activityId:ActivityId;submissionId:string;measured:boolean}|null>(null)
function beginReflection(activityId:ActivityId,submissionId:string){reflection.value={activityId,submissionId,measured:false};window.scrollTo({top:0,behavior:'smooth'})}
function measurementSaved(){if(reflection.value)reflection.value.measured=true}
function continueReflection(){
  if(!reflection.value?.measured)return
  if(reflection.value.activityId==='explore_2d'){reviewing.value=true;return}
  go(reflection.value.activityId==='group_books'?'explain_algorithm':'explore_2d')
}
const registered=computed(()=>!!state.value.student)
const titles:Record<ActivityId,string>={group_books:'活动1：给五本书分组',explain_algorithm:'活动2：整理分组的方法',explore_2d:'活动3：探索二维分组'}
const instructions:Record<ActivityId,string>={group_books:'选择两个开始的中心，逐轮比较距离和分组。分组稳定后，填写两组数量和最后的中心，提交后进入活动2。',explain_algorithm:'把四张卡片按先后顺序排列并提交。排序正确后，可以进入活动3。',explore_2d:'上传Excel表格，选择两列数据并运行分组，再填写两组数量和特点，完成最后的交付。'}
async function identify(){
  if(saving.value)return
  error.value=''
  if(!className.value.trim()||!studentNumber.value.trim()){error.value='请填写班级和学号。';return}
  saving.value=true
  try{
    const response=await fetch('/api/projects/teaching-agent/student',{method:'POST',headers:{'Content-Type':'application/json','X-Session-ID':state.value.sessionId},body:JSON.stringify({class_name:className.value.trim(),student_number:studentNumber.value.trim(),source_route:'learning-activities'})})
    const data=await response.json()
    if(!response.ok)throw new Error(typeof data?.detail==='string'?data.detail:'保存失败，请重试。')
    state.value.student={className:data.class_name,studentNumber:data.student_number};persist();selfReportOpen.value=true
  }catch(e){error.value=e instanceof Error?e.message:'连接失败，请重试。'}finally{saving.value=false}
}
function selfReportSaved(){selfReportOpen.value=false}
function calculated(result:Calculation){current.value.operation={status:result.converged?'completed':'pending',source:'backend',result:result as unknown as Record<string,unknown>,updatedAt:new Date().toISOString()};persist()}
function calculationSubmitted(saved:CalculationSubmission){recordCalculation(state.value,saved,false);persist();beginReflection('group_books',saved.id)}
async function submitOrder(order:string[]){
  if(saving.value)return
  saving.value=true;error.value='';sortingCorrect.value=null
  try{const saved=await saveSorting(state.value.sessionId,order);recordStepOrder(state.value,order,saved);sortingCorrect.value=saved.payload.correct;persist();if(saved.payload.correct)beginReflection('explain_algorithm',saved.id)}
  catch(e){error.value=e instanceof Error?e.message:'保存失败，请重试。'}finally{saving.value=false}
}
function explorationChanged(){current.value.operation={status:'pending',source:'backend',result:null,updatedAt:null}}
function explorationCalculated(result:Analysis){current.value.operation={status:'completed',source:'backend',result:result as unknown as Record<string,unknown>,updatedAt:new Date().toISOString()};persist()}
function explorationSubmitted(saved:ExplorationSubmission){recordExploration(state.value,saved,current.value.operation.result as unknown as Analysis);persist();beginReflection('explore_2d',saved.id)}
function go(id:ActivityId){if(saving.value||taskBusy.value||(reflection.value&&!reflection.value.measured))return;if(enterActivity(id)){reflection.value=null;error.value='';sortingCorrect.value=null;window.scrollTo({top:0,behavior:'smooth'})}}
watch(()=>[registered.value,selfReportOpen.value,state.value.sessionId,state.value.activeActivityId],()=>{if(registered.value&&!selfReportOpen.value)void recordActivityEntry(state.value.sessionId,state.value.activeActivityId)})
</script>

<template>
  <div class="activities-page">
<header class="activities-header"><div aria-hidden="true"></div><span>图书分类学习活动</span><button v-if="registered" @click="reviewing=true">查看学习记录</button></header>
    <main>
      <section v-if="!registered" class="registration" aria-label="填写学习信息">
        <span class="eyebrow">图书分类 · 三个学习活动</span><h1>准备开始学习</h1><p>从五本书的分组出发，整理计算方法，再探索二维数据。</p>
        <form @submit.prevent="identify"><label for="student-class">班级<input id="student-class" v-model="className" maxlength="80" placeholder="例如：七年级1班" required :disabled="saving"></label><label for="student-number">学号<input id="student-number" v-model="studentNumber" maxlength="40" placeholder="请输入学号" required :disabled="saving"></label><p v-if="error" role="alert">{{error}}</p><button class="primary" :disabled="saving">{{saving?'正在保存…':'确认并继续'}}</button></form>
      </section>
      <template v-else>
        <div class="student-info">{{state.student!.className}} · 学号 {{state.student!.studentNumber}}</div>
        <nav class="activity-tabs" aria-label="学习活动"><button v-for="item in records" :key="item.id" :disabled="saving||taskBusy||item.id==='explain_algorithm'||!canEnter(state,item.id)" :aria-current="activity.id===item.id?'step':undefined" @click="go(item.id)">{{titles[item.id]}}<span v-if="item.state.submissions.some(s=>s.kind==='learning_result'&&(item.id!=='explain_algorithm'||s.payload.sorting?.correct))"> ✓</span></button></nav>
        <section v-if="reflection" class="reflection-focus" aria-label="活动回顾"><span v-if="!(reflection.activityId==='explore_2d'&&reflection.measured)">活动后的学习感受</span><h1>{{titles[reflection.activityId]}}已提交</h1><p>{{reflection.measured?(reflection.activityId==='explore_2d'?'接下来按老师要求完成活动四，并提交学习任务单。':'你的学习感受已经记录。可以回顾刚才的过程，再继续学习。'):'请先完成刚才学习感受的四题测量。'}}</p><button v-show="reflection.activityId!=='group_books'" class="primary" :disabled="!reflection.measured" @click="continueReflection">{{reflection.activityId==='group_books'?'继续前往活动2':reflection.activityId==='explain_algorithm'?'继续前往活动3':'查看学习记录'}}</button></section>
        <template v-else>
        <section class="activity-heading"><h1>{{titles[activity.id]}}</h1><p>{{instructions[activity.id]}}</p></section>
        <CenterExperiment v-if="activity.id==='group_books'" :session-id="state.sessionId" :draft="current.draft" @busy="taskBusy=$event" @result="calculated" @submitted="calculationSubmitted" @restored="saved=>{recordCalculation(state,saved,false);persist()}"/>
        <template v-else-if="activity.id==='explain_algorithm'"><AlgorithmSteps :draft="current.draft" :disabled="saving" :submitted-correct="sortingCorrect" @submit="submitOrder"/><p v-if="current.submissions.at(-1)?.payload.sorting" class="sorting-feedback" role="status">{{current.submissions.at(-1)!.payload.sorting!.feedback}}</p><div class="next-activity"><button v-if="canEnter(state,'explore_2d')" class="primary" :disabled="saving" @click="go('explore_2d')">进入活动3 →</button></div></template>
        <ExcelExperiment v-else :session-id="state.sessionId" :draft="current.draft" @busy="taskBusy=$event" @changed="explorationChanged" @result="explorationCalculated" @submitted="explorationSubmitted"/>
        <p v-if="error" role="alert">{{error}}</p>
        <section v-if="complete" class="completion" role="status"><strong>三个活动都已完成！</strong><p>你的学习交付已保存，可以查看学习记录或返回前面的活动继续尝试。</p></section>
        </template>
      </template>
    </main>
    <StateMeasurement v-if="reflection&&!reflection.measured" :key="reflection.submissionId" :session-id="state.sessionId" :activity-id="reflection.activityId" :submission-id="reflection.submissionId" :with-robot="false" @saved="measurementSaved"/>
    <SelfReport v-if="selfReportOpen" :session-id="state.sessionId" @saved="selfReportSaved"/>
    <el-drawer v-model="reviewing" title="学习记录" direction="rtl" size="min(560px, 92vw)" class="activity-records-drawer">
        <section class="learning-records" aria-label="学习记录"><h2>本次学习记录</h2><article v-for="item in records" :key="item.id"><h3>{{titles[item.id]}}</h3><p v-if="!item.state.submissions.length">还没有提交。</p><div v-for="record in item.state.submissions" :key="record.id" class="record"><time>{{new Date(record.createdAt).toLocaleString('zh-CN')}}</time><p v-if="record.payload.calculation">我的填写：两组各{{record.payload.calculation.payload.student_result.counts.join('、')}}本；中心{{record.payload.calculation.payload.student_result.centers.join('、')}}。</p><template v-if="record.payload.sorting"><p>我的排序：{{record.payload.sorting.order.join(' → ')}}</p><p>{{record.payload.sorting.feedback}}</p></template><template v-if="record.payload.exploration"><p>两组数量：{{record.payload.exploration.payload.student_result.counts.join('、')}}。</p><p>{{record.payload.exploration.payload.student_result.description}}</p></template></div></article></section>
    </el-drawer>
  </div>
</template>

<style scoped>
.reflection-focus{max-width:720px;margin:8vh auto;padding:36px;background:white;border:1px solid #d9c8e9;border-radius:22px;box-shadow:0 10px 40px #69449612}.reflection-focus>span{font-size:14px;color:#8052b1}.reflection-focus h1{font-size:24px}.reflection-focus button{margin-top:20px}
.activities-header>span{text-align:center;min-width:0}.activities-header>button{justify-self:end;white-space:nowrap}@media(max-width:650px){.activities-header>button{padding:8px 10px;font-size:14px}}
.activities-page{min-height:100dvh;background:#f7f8fc;color:#49345f;font-size:16px;line-height:1.8}.activities-header{position:sticky;top:0;z-index:50;display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;justify-content:space-between;gap:16px;padding:20px 32px;border-bottom:1px solid #e6deee;background:white}.activities-header a{color:#73528d;text-decoration:none}.activities-header>span{font-weight:700}main{max-width:1180px;margin:auto;padding:32px 24px 80px}button,input{font:inherit}button{cursor:pointer;border:1px solid #c7b4dc;border-radius:10px;background:white;color:#67418b;padding:9px 16px}button:disabled{cursor:default;opacity:.45}.primary{background:#8052b1;color:white;border-color:#8052b1}.registration{max-width:550px;margin:8vh auto;padding:32px;background:white;border:1px solid #d9c8e9;border-radius:22px;box-shadow:0 10px 40px #69449612}.eyebrow{color:#8052b1;font-size:14px}.registration h1{margin:12px 0}.registration>p{color:#74627f}.registration form{display:grid;gap:18px;margin-top:26px}.registration label{font-weight:600}.registration input{box-sizing:border-box;display:block;width:100%;padding:12px;margin-top:8px;border:1px solid #b69ad9;border-radius:10px;color:#49345f}.registration .primary{justify-self:end}.student-info{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;font-size:14px;color:#74627f;margin-bottom:20px}.activity-tabs{display:flex;gap:12px;flex-wrap:wrap}.activity-tabs button[aria-current=step]{background:#8052b1;color:white;border-color:#8052b1}.activity-heading{margin:28px 0 20px}.activity-heading h1{font-size:25px;margin:0 0 8px}.activity-heading p{margin:0;color:#74627f}.next-activity{display:flex;justify-content:flex-end;margin-top:20px}.sorting-feedback,.completion{padding:20px 24px;background:#eef7f2;border:1px solid #c9e1d4;border-radius:14px;margin-top:20px}.learning-records{color:#49345f;font-size:16px;line-height:1.8}.learning-records h2{margin-top:0;font-size:20px}.learning-records article{padding:12px 0;border-bottom:1px solid #ece5f3}.learning-records p{overflow-wrap:anywhere}.record{border-top:1px solid #ece5f3;padding:12px 0}.record time{color:#74627f;font-size:13px}[role=alert]{color:#a14635}button:focus-visible,a:focus-visible,input:focus-visible{outline:3px solid #a78bc9;outline-offset:3px}@media(max-width:650px){.activities-header{padding:16px;gap:8px}.activities-header>span{font-size:14px}main{padding:24px 16px 60px}.registration{padding:24px;margin-top:5vh}.activity-tabs{gap:8px}.activity-tabs button{flex:1 1 100%;text-align:left}.activity-heading h1{font-size:22px}}
</style>
