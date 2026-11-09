<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { Reading, Lock, Check, ArrowLeft, ArrowRight, Setting, Position, VideoPlay } from '@element-plus/icons-vue'
import AgentNode from '../../shared/components/AgentNode.vue'
import { ElMessage } from 'element-plus'
import AnalysisViewer from './AnalysisViewer.vue'
import DeliveryPanel from './DeliveryPanel.vue'
import RunOutput from './RunOutput.vue'
import CenterExperiment from './CenterExperiment.vue'
import PromptSteps from './PromptSteps.vue'
import PlanCard from './PlanCard.vue'
import StudentResults from './StudentResults.vue'
import { api } from './api'
import type { LearningPlan, Result, PlanCardInput } from './types'
import { useLibrary, toolIds } from './useLibrary'
import type { NodeId } from './types'
import './library.css'

const {project,learning,config,dataset,datasetOptions,selectDataset,loading,error,active,busy,saving,running,collapsed,selected,revision,dirty,analyses,runs,selectedId,finalRun,form,input,events,runStatus,historyOpen,savedSnapshot,states,activity,id,result,finalEvidence,latestAnswer,permitted,completedRuns,statusNames,load,saveConfig,saveDraft,submitPlan,switchActivity,submit,inspectData,example,run,reviewRun,showRun,stop}=useLibrary()
const view=ref<'canvas'|'prompt'>('canvas'), trace=ref<HTMLElement>(), canvas=ref<HTMLElement>()
const leftWidth=ref(295), rightWidth=ref(310), bottomHeight=ref(350)

const planOpen=ref(false), deliveryOpen=ref(false), toolDataOpen=ref(false)
const deliveryPanel=ref<InstanceType<typeof DeliveryPanel>>()
const currentPlanActivity=ref('')
const recordsOpen=ref(false), recordsTab=ref<'plans'|'submissions'>('plans'), recordsLoading=ref(false), recordsError=ref('')
const planHistory=ref<LearningPlan[]>([])
async function openRecords(tab:'plans'|'submissions'){
  recordsTab.value=tab;recordsOpen.value=true;recordsLoading.value=true;recordsError.value=''
  try{
    if(tab==='plans')planHistory.value=await api<LearningPlan[]>('/plan-history')

  }catch(e){recordsError.value=(e as Error).message}finally{recordsLoading.value=false}
}
function editCurrentPlan(){recordsOpen.value=false;openPlan()}

const stableOpen=ref(false)
const receiptOpen=ref(false), receiptIndex=ref(0), receiptPayload=ref<Record<string,any>>({})
const needsPlan=computed(()=>!!activity.value&&currentPlanActivity.value!==id.value)
let guideBeforeDelivery=true
let preparedActivity=''
watch([loading,busy,id],()=>{
  if(loading.value||busy.value||!activity.value||!config.value||preparedActivity===id.value)return
  preparedActivity=id.value; collapsed.value=active.value<2; deliveryOpen.value=false
  currentPlanActivity.value=''
  planOpen.value=needsPlan.value
},{immediate:true})
async function openPlan(){if(deliveryOpen.value&&!(await saveDraft(true)))return;deliveryOpen.value=false;planOpen.value=true}
async function confirmPlan(body:PlanCardInput){
  const starting=needsPlan.value
  if(await submitPlan(body)){
    currentPlanActivity.value=id.value;planOpen.value=false
    if(starting){collapsed.value=active.value<2;view.value=active.value===1?'prompt':'canvas';selected.value=active.value===1?'brain':'inspect_dataset'}
  }
}
function centerResult(value:Result){if(form.value.analysis_id&&form.value.analysis_id!==value.analysis_id)delete form.value.student_result;if(!analyses.value.some(a=>a.id===value.analysis_id))analyses.value.unshift({id:value.analysis_id,revision:revision.value,kind:'step',result:value,run_id:null,created:new Date().toISOString()});selectedId.value=value.analysis_id;form.value.analysis_id=value.analysis_id}
function preparePurchaseRows(){if(!form.value.purchases?.length){const groups=finalEvidence.value?.result.groups||[];form.value.purchases=groups.filter(g=>g.count>0).map(g=>({group:g.label,type:'',quantity:undefined}))}}
function prepareFirstResult(){if(active.value===0&&!form.value.student_result)form.value.student_result={counts:[undefined,undefined],centers:[undefined,undefined]}}
function confirmStable(){stableOpen.value=false;openDelivery()}
async function continueAfterReceipt(){if(receiptIndex.value===3){receiptOpen.value=false;return}await switchActivity(receiptIndex.value+1);if(active.value===receiptIndex.value+1)receiptOpen.value=false}
async function openDelivery(){
  if(needsPlan.value){await openPlan();return}
  if(active.value>=2&&dirty.value){ElMessage.info('设置改过了，请先重新运行助手，再填写结果。');return}
  if(active.value===0&&!result.value?.converged){ElMessage.info('先继续计算，等分组稳定后再填写结果。');return}
  if(active.value>=2&&!finalEvidence.value){ElMessage.info('先写下任务，让助手运行一次，再填写结果。');return}
  if(active.value===1&&dirty.value&&!(await saveConfig()))return
  prepareFirstResult();if(active.value===3)preparePurchaseRows()
  if(!deliveryOpen.value)guideBeforeDelivery=collapsed.value
  deliveryOpen.value=true;collapsed.value=true
  await nextTick();trace.value?.scrollTo({top:0})
}

async function beforeDeliveryClose(done:()=>void){if(busy.value||running.value||saving.value)return;if(await saveDraft(true))done()}
async function closeDelivery(){await beforeDeliveryClose(()=>{deliveryOpen.value=false;collapsed.value=guideBeforeDelivery})}
async function submitDelivery(){if(!deliveryPanel.value?.valid||(active.value===3&&!purchaseTextReady.value))return;if(await submit(false)){receiptIndex.value=active.value;receiptPayload.value=JSON.parse(JSON.stringify(activity.value?.submission?.payload||{}));deliveryOpen.value=false;collapsed.value=guideBeforeDelivery;receiptOpen.value=true}}
async function runAndReview(){if(needsPlan.value){openPlan();return}await run()}


function beforePlanClose(done:()=>void){if(!needsPlan.value&&!saving.value&&!busy.value)done()}
async function callDataTool(){if(await inspectData())toolDataOpen.value=true}
function updatePrompt(steps:string[],prompt:string){if(config.value){config.value.prompt_steps=steps;config.value.system_prompt=prompt}}

const {fitView}=useVueFlow({id:'library-flow'})
let observer:ResizeObserver|undefined, timer:ReturnType<typeof setTimeout>|undefined, stopResize:(()=>void)|undefined
watch(canvas, element=>{ observer?.disconnect(); if(timer)clearTimeout(timer); if(element){observer=new ResizeObserver(()=>{if(timer)clearTimeout(timer);timer=setTimeout(()=>fitView({padding:.15,duration:150}),100)});observer.observe(element)} },{flush:'post'})
watch(()=>latestAnswer.value,async()=>{if(deliveryOpen.value)return;await nextTick();if(trace.value)trace.value.scrollTop=trace.value.scrollHeight})
watch(id,()=>{view.value=active.value===1?'prompt':'canvas';toolDataOpen.value=false})
const nodes=computed(()=>!config.value || !project.value ? [] : [
  {id:'brain',type:'agent',position:{x:20,y:195},data:{label:'计算助手大脑',hint:'按你排好的步骤做事',enabled:true,status:states.brain,selected:selected.value==='brain'}},
  ...toolIds.map((tool,i)=>({id:tool,type:'agent',position:{x:390,y:i*175+20},data:{label:project.value!.tools[tool].name,enabled:permitted.value.includes(tool)&&config.value![tool].enabled,locked:!permitted.value.includes(tool),status:states[tool],selected:selected.value===tool}})),
])
const edges=computed(()=>toolIds.map(tool=>({id:'brain-'+tool,source:'brain',target:tool,type:'smoothstep',animated:states[tool]==='running',style:{stroke:states[tool]==='running'?'#7855cb':permitted.value.includes(tool)&&config.value?.[tool].enabled?'#b7abd1':'#d5d8e1',strokeWidth:states[tool]==='running'?3:1.5,strokeDasharray:permitted.value.includes(tool)?'0':'5 5'}})))
const receiptAnalysis=computed(()=>analyses.value.find(a=>a.kind==='full'&&a.id===receiptPayload.value.analysis_id&&a.run_id===receiptPayload.value.run_id))
const tool=computed(()=>selected.value==='brain'?undefined:project.value?.tools[selected.value])
const purchaseTextReady=computed(()=>[form.value.rationale,form.value.reflection].every(text=>Array.from(String(text||'').replace(/\s/g,'')).length>=10))
function resize(which:'left'|'right'|'bottom',e:PointerEvent){
  const x=e.clientX,y=e.clientY,start=which==='left'?leftWidth.value:which==='right'?rightWidth.value:bottomHeight.value
  const move=(ev:PointerEvent)=>{if(which==='left')leftWidth.value=Math.max(280,Math.min(480,start+ev.clientX-x));if(which==='right')rightWidth.value=Math.max(295,Math.min(450,start+x-ev.clientX));if(which==='bottom')bottomHeight.value=Math.max(250,Math.min(window.innerHeight-350,start+y-ev.clientY))}
  const end=()=>{document.removeEventListener('pointermove',move);document.removeEventListener('pointerup',end);document.body.style.userSelect='';stopResize=undefined}
  document.body.style.userSelect='none';document.addEventListener('pointermove',move);document.addEventListener('pointerup',end);stopResize=end
}
onBeforeUnmount(()=>{observer?.disconnect();if(timer)clearTimeout(timer);stopResize?.()})
</script>

<template>
  <div class="app-shell library-workspace">
    <header class="topbar"><div class="brand"><span class="brand-mark"><el-icon><Position/></el-icon></span>orbit<span class="brand-separator"/><span class="workspace-name">图书馆采购推荐</span></div><div class="top-actions"><RouterLink class="project-route-link" to="/">项目首页</RouterLink><RouterLink class="project-route-link" to="/projects/astronomy-lab">天文项目</RouterLink><el-button v-if="active>0&&!deliveryOpen" type="primary" :disabled="needsPlan||!dirty||running||busy" :loading="saving" @click="saveConfig">{{active===1?'保存步骤':'保存设置'}}</el-button></div></header>
    <div v-if="loading" class="loading-screen"><el-skeleton :rows="8" animated/></div>
    <div v-else-if="error" class="empty-screen"><h2>无法加载图书馆项目</h2><p>{{ error }}</p><el-button type="primary" @click="load">重新加载</el-button></div>
    <main v-else-if="learning&&config&&project&&activity" class="library-layout" :class="{collapsed,'center-mode':active===0,'no-execution':active===1,'delivery-open':deliveryOpen,'writing-mode':deliveryOpen&&active>=2}" :style="{'--study-width':leftWidth+'px','--settings-width':(deliveryOpen?420:rightWidth)+'px','--run-height':bottomHeight+'px'}">
      <aside class="library-learning">
        <div v-if="collapsed" class="library-focus-rail"><button aria-label="查看学习指南" title="查看学习指南" @click="collapsed=false"><el-icon><Reading/></el-icon><span>学习指南</span></button><div class="library-activity-shortcuts"><button v-for="(a,i) in learning.activities" :key="a.id" :aria-label="a.title" :title="a.title" :class="{current:active===i}" :disabled="a.status==='locked'||running||busy" @click="switchActivity(i)"><el-icon v-if="a.status==='locked'"><Lock/></el-icon><template v-else>{{i+1}}</template></button></div></div>
        <div v-show="!collapsed" class="panel-heading"><template v-if="!collapsed"><el-icon><Reading/></el-icon><strong>学习指南</strong></template><button class="sidebar-toggle" :aria-label="collapsed?'展开学习指南':'收起学习指南'" @click="collapsed=!collapsed"><el-icon><ArrowRight v-if="collapsed"/><ArrowLeft v-else/></el-icon></button></div>
        <div v-show="!collapsed" class="library-learning-scroll" v-loading="busy">
          <span class="eyebrow">PROJECT 2</span><h1>图书馆采购推荐</h1>
          <div class="library-progress"><span>活动进度 {{ learning.completed }} / 4</span><el-progress :percentage="learning.completed*25" :show-text="false" :stroke-width="5"/></div>
          <nav class="library-activities" aria-label="图书馆学习活动"><button v-for="(a,i) in learning.activities" :key="a.id" :class="{current:active===i,locked:a.status==='locked'}" :disabled="a.status==='locked'||running||busy" @click="switchActivity(i)"><span class="activity-index"><el-icon v-if="a.status==='locked'"><Lock/></el-icon><el-icon v-else-if="a.status==='submitted'"><Check/></el-icon><template v-else>{{i+1}}</template></span><span>{{a.title}}</span></button></nav>
          <article class="library-lesson"><h2>{{activity.title}}</h2><div class="try-it"><p>{{activity.instruction}}</p></div></article>

        </div>
      </aside>
      <div v-show="!collapsed" class="library-divider library-left-divider" role="separator" aria-label="调整学习面板宽度" @pointerdown="resize('left',$event)"/>
      <section class="library-lab">
        <div class="library-lab-toolbar"><strong v-if="active===0">一维数轴实验</strong><div v-else class="lab-tabs"><button v-if="active===1" :class="{active:view==='prompt'}" @click="view='prompt';selected='brain'">给助手排步骤</button><button :class="{active:view==='canvas'}" @click="view='canvas'">助手和工具</button></div></div>
        <CenterExperiment v-if="active===0&&!needsPlan" :revision="revision" :ready="!needsPlan" @result="centerResult" @completed="stableOpen=true"/>
        <div v-if="active===1&&view==='prompt'&&!needsPlan&&project.prompt_scaffold" class="library-lab-scroll"><PromptSteps :scaffold="project.prompt_scaffold" :steps="config.prompt_steps||[]" :disabled="busy||running||saving" @change="updatePrompt"/></div>
        <div v-show="active!==0&&view==='canvas'" ref="canvas" class="library-flow"><VueFlow id="library-flow" :nodes="nodes" :edges="edges" :nodes-draggable="false" :nodes-connectable="false" :delete-key-code="null" :min-zoom="0.3" :max-zoom="1.5" fit-view-on-init :fit-view-params="{padding:.15}" @node-click="selected=$event.node.id as NodeId;if(active===1&&selected==='brain')view='prompt'"><Background :gap="20" pattern-color="#d6dae5"/><Controls :show-interactive="false"/><template #node-agent="props"><AgentNode v-bind="props"/></template></VueFlow></div>

      </section>
      <div class="library-divider library-right-divider" role="separator" aria-label="调整配置面板宽度" @pointerdown="resize('right',$event)"/>
      <aside v-show="!deliveryOpen" class="library-settings"><div class="panel-heading"><el-icon><Setting/></el-icon><strong>设置助手</strong></div><div class="library-settings-scroll">
        <h2>{{selected==='brain'?'助手的做事步骤':tool?.name}}</h2>
        <el-form v-if="selected==='brain'" label-position="top" :disabled="needsPlan||active===0||running||busy||saving">
          <el-form-item v-if="active===1"><el-input v-model="config.system_prompt" type="textarea" :rows="10" :maxlength="12000" resize="vertical" readonly aria-label="助手的做事步骤"/></el-form-item>
          <template v-else><p class="library-parameters">继续使用你在活动二排好的步骤。</p><details class="advanced-settings"><summary>查看或修改步骤</summary><el-input v-model="config.system_prompt" type="textarea" :rows="10" :maxlength="12000" resize="vertical" aria-label="助手的做事步骤"/></details></template>
          <details class="advanced-settings"><summary>更多设置</summary>
            <el-form-item label="模型"><el-select v-model="config.model"><el-option v-for="m in project.models" :key="m" :label="m" :value="m"/></el-select></el-form-item>
            <el-form-item v-if="active>=2" label="本次任务要求"><el-input v-model="config.task_prompt" type="textarea" :rows="5" resize="vertical"/></el-form-item>
            <el-form-item :label="'回答变化程度：'+config.temperature.toFixed(1)"><el-slider v-model="config.temperature" :min="0" :max="2" :step=".1"/></el-form-item>
          </details>
        </el-form>
        <template v-else-if="tool">
          <p class="tool-description">{{tool.description}}</p>
          <el-alert v-if="!permitted.includes(selected)" title="这个工具后面会用到。" type="info" :closable="false"/>
          <div class="enable-box"><b>使用这个工具</b><el-switch v-model="config[selected].enabled" :disabled="needsPlan||active===0||!permitted.includes(selected)||running||busy||saving" :aria-label="'启用'+tool.name"/></div>
          <el-form label-position="top" :disabled="needsPlan||active===0||busy||running||saving||!permitted.includes(selected)">
            <el-form-item label="选择数据表"><el-select :model-value="config.experiment.dataset_id" :disabled="datasetOptions.length<2" aria-label="选择数据表" @change="selectDataset"><el-option v-for="d in datasetOptions" :key="d.id" :label="d.name" :value="d.id"/></el-select></el-form-item>
            <p v-if="dataset" class="library-parameters">共 {{dataset.row_count}} 条记录</p>
            <template v-if="selected==='run_kmeans_analysis'">
              <el-form-item label="用哪两列来分组？"><el-checkbox-group v-model="config.experiment.features"><el-checkbox v-for="f in dataset?.fields" :key="f.id" :value="f.id">{{f.label}}</el-checkbox></el-checkbox-group></el-form-item>
              <el-form-item label="分成几组？"><el-input-number v-model="config.experiment.k" :min="2" :max="active===2?2:4" :disabled="active===2"/></el-form-item>
              <details class="advanced-settings"><summary>更多设置</summary><el-form-item label="数据的计算方式"><el-select v-model="config.experiment.scaling"><el-option label="使用原来的数值" value="none"/><el-option label="先统一不同列的数值尺度" value="standard"/></el-select></el-form-item><el-form-item label="随机种子"><el-input-number v-model="config.experiment.seed" :min="0" :max="100000"/></el-form-item></details>
            </template>
          </el-form>
          <div v-if="selected==='inspect_dataset'" class="practice-actions"><el-button type="primary" :disabled="needsPlan||busy||running||saving||!config.inspect_dataset.enabled" @click="callDataTool">查看这张表</el-button></div>
        </template>
        <details v-if="active>=2" class="advanced-settings workspace-extras"><summary>查看以前的运行</summary><el-button :disabled="running||busy" @click="historyOpen=true">打开运行记录</el-button></details>
      </div></aside>
      <DeliveryPanel v-if="deliveryOpen" ref="deliveryPanel" :index="active" :form="form" :config="config" :runs="completedRuns" :run-id="finalRun" :busy="busy||saving||running" :dirty="dirty" :submitted="!!activity.submission" @close="closeDelivery" @save="saveDraft()" @review="reviewRun($event)"/>
      <div v-if="active>=2" class="library-divider library-bottom-divider" role="separator" aria-label="调整执行面板高度" @pointerdown="resize('bottom',$event)"/>
      <section v-if="active>=2" class="library-execution">
        <div class="execution-toolbar"><div><el-icon><VideoPlay/></el-icon><strong>{{deliveryOpen?'对照这里的结果填写':'试一试助手'}}</strong><span v-if="runStatus" class="run-badge" :class="runStatus">{{statusNames[runStatus]||runStatus}}</span></div></div>
        <div class="library-execution-body">
          <div class="test-input"><div class="input-label"><b>告诉助手，你想做什么</b><button :disabled="running||busy" @click="example">看看例子</button></div>
            <el-input v-model="input" type="textarea" :rows="4" :disabled="running||busy" resize="none" placeholder="请把……分成……组，并告诉我……" @keydown.ctrl.enter.prevent="runAndReview"/>
            <div class="run-controls"><el-button v-if="running" @click="stop">停止</el-button><el-button v-else type="primary" :disabled="needsPlan||busy||saving||!input.trim()" :icon="VideoPlay" @click="runAndReview">开始运行</el-button></div>
          </div>
          <div ref="trace" class="trace-output"><RunOutput :events="events" :answer="latestAnswer" :running="running" :snapshot="savedSnapshot"/></div>
        </div>
      </section>
    </main>


    <el-dialog v-if="dataset?.loaded" v-model="toolDataOpen" class="library-phase-dialog library-tool-data-dialog" title="看看表里的数据" width="820px" align-center draggable append-to-body :close-on-click-modal="false">
        <div class="library-tool-data"><template v-if="dataset"><div class="analysis-heading"><el-tag v-if="dataset.demo" type="warning">演示数据</el-tag></div><p class="analysis-source">共 {{dataset.row_count}} 条记录，本次返回前 {{dataset.preview.length}} 条。分组时会使用整张表中能参与计算的数据。</p><p v-for="f in dataset.fields" :key="f.id" class="field-description"><b>{{f.label}}</b>：{{f.unit}}</p><el-alert v-if="dataset.issues.length" title="有些数据可能不能计算，请留意助手的说明。" type="warning" :closable="false"/><el-table :data="dataset.preview" max-height="320"><el-table-column prop="name" label="样本" min-width="135"/><el-table-column v-for="f in dataset.fields" :key="f.id" :prop="f.id" :label="f.label" min-width="100"/></el-table>
</template></div>
      <template #footer><el-button @click="toolDataOpen=false">关闭</el-button></template>
    </el-dialog>
    <el-dialog v-if="activity&&config" v-model="planOpen" class="library-phase-dialog library-plan-dialog" :aria-label="activity.title" width="760px" align-center append-to-body :close-on-click-modal="false" :close-on-press-escape="!needsPlan&&!saving&&!busy" :show-close="false" :before-close="beforePlanClose">
      <article class="library-plan-material"><h2>{{activity.title}}</h2><p>{{activity.body}}</p></article>
      <PlanCard v-if="planOpen" :baseline="learning?.plan_card" :phase="needsPlan?'before':'during'" :busy="saving||busy" :can-close="!needsPlan" @submit="confirmPlan" @close="planOpen=false"/>
    </el-dialog>
    <el-dialog v-model="stableOpen" title="聚类完成" width="440px" align-center append-to-body :show-close="false" :close-on-click-modal="false" :close-on-press-escape="false" class="library-stable-dialog">
      <p>分组与中心已稳定，请填写并提交你的结果。</p>
      <template #footer><el-button type="primary" :disabled="busy||saving" @click="confirmStable">填写结果</el-button></template>
    </el-dialog>
    <el-dialog v-model="receiptOpen" title="提交成功" width="760px" align-center append-to-body :show-close="false" :close-on-click-modal="false" :close-on-press-escape="false" class="library-receipt-dialog">
      <p>活动{{receiptIndex+1}}的结果已保存。</p><details v-if="receiptOpen" class="receipt-details"><summary>看看我提交的结果</summary>
      <StudentResults :index="receiptIndex" :payload="receiptPayload"/><section v-if="receiptOpen&&receiptIndex>=2&&receiptAnalysis" class="submitted-visualization"><h3>本次分析的散点图</h3><p class="analysis-source">下图展示本次实际计算的分组；上方是你填写的结果。</p><AnalysisViewer :result="receiptAnalysis.result"/></section></details>
      <template #footer><el-button type="primary" :loading="busy" @click="continueAfterReceipt">{{receiptIndex<3?'进入活动'+(receiptIndex+2):'完成，返回学习'}}</el-button></template>
    </el-dialog>
    <nav v-if="learning&&!loading&&!error" class="library-floating-actions" aria-label="学习操作">
      <el-button type="primary" :loading="busy&&deliveryOpen" :disabled="busy||running||saving||(deliveryOpen&&!deliveryPanel?.valid)" @click="deliveryOpen?submitDelivery():openDelivery()">提交结果</el-button>
      <el-button :disabled="busy||saving" @click="openRecords('plans')">查看我的计划</el-button>
      <el-button :disabled="busy||saving" @click="openRecords('submissions')">查看我的提交</el-button>
    </nav>
    <el-drawer v-model="recordsOpen" :title="recordsTab==='plans'?'我的计划':'我的提交'" size="min(760px, 92vw)" class="library-records-drawer">
      <el-alert v-if="recordsError" :title="recordsError" type="error" :closable="false"/>
      <div v-loading="recordsLoading" class="library-records-body">
        <template v-if="recordsTab==='plans'">
          <el-button type="primary" plain :disabled="running||busy||saving" @click="editCurrentPlan">查看或修改当前计划</el-button>
          <el-empty v-if="!recordsLoading&&!planHistory.length" description="还没有提交学习计划"/>
          <article v-for="plan in planHistory" :key="plan.version" class="library-record-card">
            <h3>{{learning?.activities.find(a=>a.id===plan.activity_id)?.title}} · 第{{plan.version}}次计划</h3>
            <time>{{new Date(plan.submitted_at).toLocaleString('zh-CN')}}</time>
            <p><b>我的做法：</b>{{plan.strategy_label}}</p><p><b>我的检查方法：</b>{{plan.check_label}}</p>
            <p v-if="plan.reason_label"><b>修改原因：</b>{{plan.reason_label}}</p>
          </article>
        </template>
        <template v-else>
          <el-empty v-if="!learning?.activities.some(a=>a.submission)" description="还没有提交活动结果"/>
          <article v-for="(a,i) in learning?.activities.filter(a=>a.submission)" :key="a.id" class="library-record-card">
            <h3>{{a.title}}</h3><StudentResults :index="learning!.activities.findIndex(item=>item.id===a.id)" :payload="a.submission!.payload"/>
          </article>
        </template>
      </div>
    </el-drawer>
    <el-drawer v-model="historyOpen" title="本活动运行历史" size="440px"><el-empty v-if="!runs.length" description="还没有运行记录"/><button v-for="r in runs" :key="r.id" class="history-item" @click="showRun(r.id)"><div><time>{{new Date(r.created).toLocaleString('zh-CN')}}</time><span class="run-badge">{{statusNames[r.status]}} · v{{r.revision}}</span></div><p>{{r.input}}</p></button></el-drawer>
  </div>
</template>
