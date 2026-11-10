<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { Reading, Lock, Check, ArrowLeft, ArrowRight, Setting, Connection, Position, Clock, VideoPlay } from '@element-plus/icons-vue'
import AgentNode from '../../shared/components/AgentNode.vue'
import AnalysisViewer from './AnalysisViewer.vue'
import CenterExperiment from './CenterExperiment.vue'
import PromptSteps from './PromptSteps.vue'
import PlanCard from './PlanCard.vue'
import StudentResults from './StudentResults.vue'
import { api } from './api'
import type { LearningPlan, Result, PlanCardInput } from './types'
import { useLibrary, toolIds } from './useLibrary'
import type { NodeId } from './types'
import './library.css'

const {project,learning,config,dataset,datasetOptions,selectDataset,loading,error,active,busy,saving,running,collapsed,selected,revision,dirty,analyses,runs,selectedId,finalRun,form,input,events,runStatus,historyOpen,savedSnapshot,states,activity,id,result,finalEvidence,latestAnswer,permitted,completedRuns,statusNames,traceNames,labelAnalysis,pretty,load,saveConfig,saveDraft,submitPlan,switchActivity,submit,inspectData,example,run,reviewRun,showRun,stop}=useLibrary()
const view=ref<'canvas'|'prompt'>('canvas'), trace=ref<HTMLElement>(), canvas=ref<HTMLElement>()
const leftWidth=ref(325), rightWidth=ref(335), bottomHeight=ref(310)

const planOpen=ref(false), deliveryOpen=ref(false), toolDataOpen=ref(false)
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
const deliveryTitle=computed(()=>['提交分组成果','提交系统指令','提交两组数量','提交成果与反思'][active.value])
let preparedActivity=''
watch([loading,busy,id],()=>{
  if(loading.value||busy.value||!activity.value||!config.value||preparedActivity===id.value)return
  preparedActivity=id.value; collapsed.value=active.value<2; deliveryOpen.value=false
  currentPlanActivity.value=''
  planOpen.value=needsPlan.value
},{immediate:true})
function openPlan(){deliveryOpen.value=false;planOpen.value=true}
async function confirmPlan(body:PlanCardInput){
  const starting=needsPlan.value
  if(await submitPlan(body)){
    currentPlanActivity.value=id.value;planOpen.value=false
    if(starting){collapsed.value=active.value<2;view.value=active.value===1?'prompt':'canvas';selected.value=active.value===1?'brain':'inspect_dataset'}
  }
}
function centerResult(value:Result){if(form.value.analysis_id&&form.value.analysis_id!==value.analysis_id)delete form.value.student_result;if(!analyses.value.some(a=>a.id===value.analysis_id))analyses.value.unshift({id:value.analysis_id,revision:revision.value,kind:'step',result:value,run_id:null,created:new Date().toISOString()});selectedId.value=value.analysis_id;form.value.analysis_id=value.analysis_id}
function preparePurchaseRows(){const groups=finalEvidence.value?.result.groups||[];form.value.purchases=groups.filter(g=>g.count>0).map(g=>({group:g.label,type:'',quantity:undefined}))}
function prepareFirstResult(){if(active.value===0&&!form.value.student_result)form.value.student_result={counts:[undefined,undefined],centers:[undefined,undefined]}}
function confirmStable(){stableOpen.value=false;openDelivery()}
async function continueAfterReceipt(){if(receiptIndex.value===3){receiptOpen.value=false;return}await switchActivity(receiptIndex.value+1);if(active.value===receiptIndex.value+1)receiptOpen.value=false}
function openDelivery(){if(needsPlan.value){openPlan();return}prepareFirstResult();deliveryOpen.value=true}

async function beforeDeliveryClose(done:()=>void){if(busy.value||running.value||saving.value)return;if(await saveDraft(true))done()}
async function closeDelivery(){await beforeDeliveryClose(()=>{deliveryOpen.value=false})}
async function submitDelivery(){if(active.value===3&&!purchaseTextReady.value)return;if(await submit(false)){receiptIndex.value=active.value;receiptPayload.value=JSON.parse(JSON.stringify(activity.value?.submission?.payload||{}));deliveryOpen.value=false;receiptOpen.value=true}}
async function runAndReview(){if(needsPlan.value){openPlan();return}await run()}


function beforePlanClose(done:()=>void){if(!needsPlan.value&&!saving.value&&!busy.value)done()}
async function callDataTool(){if(await inspectData())toolDataOpen.value=true}
function updatePrompt(steps:string[],prompt:string){if(config.value){config.value.prompt_steps=steps;config.value.system_prompt=prompt}}

const {fitView}=useVueFlow({id:'library-flow'})
let observer:ResizeObserver|undefined, timer:ReturnType<typeof setTimeout>|undefined, stopResize:(()=>void)|undefined
watch(canvas, element=>{ observer?.disconnect(); if(timer)clearTimeout(timer); if(element){observer=new ResizeObserver(()=>{if(timer)clearTimeout(timer);timer=setTimeout(()=>fitView({padding:.15,duration:150}),100)});observer.observe(element)} },{flush:'post'})
watch(()=>events.value.length,async()=>{await nextTick();if(trace.value)trace.value.scrollTop=trace.value.scrollHeight})
watch(id,()=>{view.value=active.value===1?'prompt':'canvas';toolDataOpen.value=false})
const nodes=computed(()=>!config.value || !project.value ? [] : [
  {id:'brain',type:'agent',position:{x:20,y:195},data:{label:'计算助手大脑',model:config.value.model,enabled:true,status:states.brain,selected:selected.value==='brain'}},
  ...toolIds.map((tool,i)=>({id:tool,type:'agent',position:{x:390,y:i*175+20},data:{label:project.value!.tools[tool].name,enabled:permitted.value.includes(tool)&&config.value![tool].enabled,locked:!permitted.value.includes(tool),status:states[tool],selected:selected.value===tool}})),
])
const edges=computed(()=>toolIds.map(tool=>({id:'brain-'+tool,source:'brain',target:tool,type:'smoothstep',animated:states[tool]==='running',style:{stroke:states[tool]==='running'?'#7855cb':permitted.value.includes(tool)&&config.value?.[tool].enabled?'#b7abd1':'#d5d8e1',strokeWidth:states[tool]==='running'?3:1.5,strokeDasharray:permitted.value.includes(tool)?'0':'5 5'}})))
const receiptAnalysis=computed(()=>analyses.value.find(a=>a.kind==='full'&&a.id===receiptPayload.value.analysis_id&&a.run_id===receiptPayload.value.run_id))
const tool=computed(()=>selected.value==='brain'?undefined:project.value?.tools[selected.value])
const agentDecision=computed(()=>events.value.findLast(e=>e.type==='final')?.data.decision)
const purchaseTextReady=computed(()=>[form.value.rationale,form.value.reflection].every(text=>Array.from(String(text||'').replace(/\s/g,'')).length>=10))
const total=computed(()=>(form.value.purchases || []).reduce((sum:number,p:{quantity:number})=>sum+Number(p.quantity || 0),0))
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
    <header class="topbar"><div class="brand"><span class="brand-mark"><el-icon><Position/></el-icon></span>orbit<span class="brand-separator"/><span class="workspace-name">图书馆采购推荐</span></div><div class="top-actions"><RouterLink class="project-route-link" to="/">项目首页</RouterLink><RouterLink class="project-route-link" to="/projects/astronomy-lab">天文项目</RouterLink><el-button :icon="Clock" :disabled="running||busy" @click="historyOpen=true">运行历史</el-button><el-button type="primary" :disabled="needsPlan||!dirty||active===0||running||busy" :loading="saving" @click="saveConfig">保存配置</el-button></div></header>
    <div v-if="loading" class="loading-screen"><el-skeleton :rows="8" animated/></div>
    <div v-else-if="error" class="empty-screen"><h2>无法加载图书馆项目</h2><p>{{ error }}</p><el-button type="primary" @click="load">重新加载</el-button></div>
    <main v-else-if="learning&&config&&project&&activity" class="library-layout" :class="{collapsed,'center-mode':active===0,'no-execution':active===1}" :style="{'--study-width':leftWidth+'px','--settings-width':rightWidth+'px','--run-height':bottomHeight+'px'}">
      <aside class="library-learning">
        <div v-if="collapsed" class="library-focus-rail"><button aria-label="查看学习指南" title="查看学习指南" @click="collapsed=false"><el-icon><Reading/></el-icon><span>学习指南</span></button><div class="library-activity-shortcuts"><button v-for="(a,i) in learning.activities" :key="a.id" :aria-label="a.title" :title="a.title" :class="{current:active===i}" :disabled="a.status==='locked'||running||busy" @click="switchActivity(i)"><el-icon v-if="a.status==='locked'"><Lock/></el-icon><template v-else>{{i+1}}</template></button></div></div>
        <div v-show="!collapsed" class="panel-heading"><template v-if="!collapsed"><el-icon><Reading/></el-icon><strong>学习指南</strong></template><button class="sidebar-toggle" :aria-label="collapsed?'展开学习指南':'收起学习指南'" @click="collapsed=!collapsed"><el-icon><ArrowRight v-if="collapsed"/><ArrowLeft v-else/></el-icon></button></div>
        <div v-show="!collapsed" class="library-learning-scroll" v-loading="busy">
          <span class="eyebrow">PROJECT 2</span><h1>图书馆采购推荐</h1>
          <div class="library-progress"><span>活动进度 {{ learning.completed }} / 4</span><el-progress :percentage="learning.completed*25" :show-text="false" :stroke-width="5"/></div>
          <nav class="library-activities" aria-label="图书馆学习活动"><button v-for="(a,i) in learning.activities" :key="a.id" :class="{current:active===i,locked:a.status==='locked'}" :disabled="a.status==='locked'||running||busy" @click="switchActivity(i)"><span class="activity-index"><el-icon v-if="a.status==='locked'"><Lock/></el-icon><el-icon v-else-if="a.status==='submitted'"><Check/></el-icon><template v-else>{{i+1}}</template></span><span>{{a.title}}</span></button></nav>
          <article class="library-lesson"><span class="phase-label">{{activity.phase}}</span><h2>{{activity.title}}</h2><p>{{activity.body}}</p><div class="try-it"><b>动手试一试</b><p>{{activity.instruction}}</p></div></article>

        </div>
      </aside>
      <div v-show="!collapsed" class="library-divider library-left-divider" role="separator" aria-label="调整学习面板宽度" @pointerdown="resize('left',$event)"/>
      <section class="library-lab">
        <div class="library-lab-toolbar"><strong v-if="active===0">一维数轴实验</strong><div v-else class="lab-tabs"><button v-if="active===1" :class="{active:view==='prompt'}" @click="view='prompt';selected='brain'">Prompt 步骤排序</button><button :class="{active:view==='canvas'}" @click="view='canvas'">Agent 画布</button></div></div>
        <CenterExperiment v-if="active===0&&!needsPlan" :revision="revision" :ready="!needsPlan" @result="centerResult" @completed="stableOpen=true"/>
        <div v-if="active===1&&view==='prompt'&&!needsPlan&&project.prompt_scaffold" class="library-lab-scroll"><PromptSteps :scaffold="project.prompt_scaffold" :steps="config.prompt_steps||[]" :disabled="busy||running||saving" @change="updatePrompt"/></div>
        <div v-show="active!==0&&view==='canvas'" ref="canvas" class="library-flow"><VueFlow id="library-flow" :nodes="nodes" :edges="edges" :nodes-draggable="false" :nodes-connectable="false" :delete-key-code="null" :min-zoom="0.3" :max-zoom="1.5" fit-view-on-init :fit-view-params="{padding:.15}" @node-click="selected=$event.node.id as NodeId;if(active===1&&selected==='brain')view='prompt'"><Background :gap="20" pattern-color="#d6dae5"/><Controls :show-interactive="false"/><template #node-agent="props"><AgentNode v-bind="props"/></template></VueFlow></div>

      </section>
      <div class="library-divider library-right-divider" role="separator" aria-label="调整配置面板宽度" @pointerdown="resize('right',$event)"/>
      <aside class="library-settings"><div class="panel-heading"><el-icon><Setting/></el-icon><strong>节点配置</strong></div><div class="library-settings-scroll"><h2>{{selected==='brain'?'计算助手大脑':tool?.name}}</h2><el-alert v-if="active===0" title="活动一先独立计算，提交后开放 Prompt 配置" type="info" :closable="false"/>
        <el-form v-if="selected==='brain'" label-position="top" :disabled="needsPlan||active===0||running||busy||saving"><el-form-item label="Model"><el-select v-model="config.model"><el-option v-for="m in project.models" :key="m" :label="m" :value="m"/></el-select></el-form-item><el-form-item label="系统指令"><el-input v-model="config.system_prompt" type="textarea" :rows="12" :maxlength="12000" resize="vertical" :readonly="active===1"/><p v-if="active===1" class="library-parameters">在中间排列七个模块，Prompt 会自动补全。</p></el-form-item><el-form-item v-if="active>=2" label="本活动任务要求（沿用前面的算法步骤）"><el-input v-model="config.task_prompt" type="textarea" :rows="6" resize="vertical"/></el-form-item><el-form-item :label="'Temperature · '+config.temperature.toFixed(1)"><el-slider v-model="config.temperature" :min="0" :max="2" :step=".1"/></el-form-item></el-form>
        <template v-else-if="tool"><p class="tool-description">{{tool.description}}</p><el-alert v-if="!permitted.includes(selected)" title="这个工具将在后续活动开放" type="info" :closable="false"/><div class="enable-box"><b>启用工具</b><el-switch v-model="config[selected].enabled" :disabled="needsPlan||active===0||!permitted.includes(selected)||running||busy||saving" :aria-label="'启用'+tool.name"/></div><p class="library-parameters">调用参数：{{tool.parameters}}</p><el-form v-if="selected==='inspect_dataset'" label-position="top" :disabled="needsPlan||busy||running||saving"><el-form-item label="选择数据表"><el-select :model-value="config.experiment.dataset_id" :disabled="datasetOptions.length<2" aria-label="选择数据表" @change="selectDataset"><el-option v-for="d in datasetOptions" :key="d.id" :label="d.name+' · '+d.dimensions+'维'" :value="d.id"/></el-select></el-form-item><p v-if="dataset" class="library-parameters">{{dataset.row_count}} 条记录 · {{dataset.fields.length}} 个数值字段</p></el-form><el-form v-if="selected==='run_kmeans_analysis'" label-position="top" :disabled="needsPlan||active<2||running||busy||saving"><el-form-item label="数据表"><el-select :model-value="config.experiment.dataset_id" :disabled="datasetOptions.length<2" aria-label="分析数据表" @change="selectDataset"><el-option v-for="d in datasetOptions" :key="d.id" :label="d.name+' · '+d.dimensions+'维'" :value="d.id"/></el-select></el-form-item><el-form-item label="分析特征"><el-checkbox-group v-model="config.experiment.features"><el-checkbox v-for="f in dataset?.fields" :key="f.id" :value="f.id">{{f.label}}</el-checkbox></el-checkbox-group></el-form-item><el-form-item label="K · 分组数量"><el-input-number v-model="config.experiment.k" :min="2" :max="active===2?2:4" :disabled="active===2"/></el-form-item><el-form-item label="标准化"><el-select v-model="config.experiment.scaling"><el-option label="使用原始数值" value="none"/><el-option label="各维度标准化" value="standard"/></el-select></el-form-item><el-form-item label="随机种子"><el-input-number v-model="config.experiment.seed" :min="0" :max="100000"/></el-form-item></el-form><div class="practice-actions"><template v-if="selected==='inspect_dataset'"><el-button type="primary" :disabled="needsPlan||busy||running||saving||!config.inspect_dataset.enabled" @click="callDataTool">调用数据查看工具</el-button><el-button :disabled="!dataset?.loaded||busy||running" @click="toolDataOpen=true">查看上次返回</el-button></template></div></template>
        <p class="config-version">配置 v{{revision}}{{dirty?' · 尚未保存':''}}</p>
      </div></aside>
      <div v-if="active>=2" class="library-divider library-bottom-divider" role="separator" aria-label="调整执行面板高度" @pointerdown="resize('bottom',$event)"/>
      <section v-if="active>=2" class="library-execution"><div class="execution-toolbar"><div><el-icon><VideoPlay/></el-icon><strong>实验运行</strong><span v-if="runStatus" class="run-badge" :class="runStatus">{{statusNames[runStatus]||runStatus}}</span></div></div><div class="library-execution-body"><div class="test-input"><div class="input-label"><b>给智能体一个任务</b><button :disabled="running" @click="example">试试示例</button></div><el-alert v-if="active===0" title="活动二开放智能体运行，现在先独立预测并核对" :closable="false" type="info"/><el-input v-else v-model="input" type="textarea" :rows="3" :disabled="running||busy" resize="none" placeholder="你可以试着问：请调用聚类工具帮我完成......" @keydown.ctrl.enter.prevent="runAndReview"/><div v-if="active>0" class="run-controls"><span>Ctrl + Enter</span><el-button v-if="running" @click="stop">停止</el-button><el-button v-else type="primary" :disabled="needsPlan||busy||saving||!input.trim()" :icon="VideoPlay" @click="runAndReview">运行智能体</el-button></div></div><div ref="trace" class="trace-output"><el-empty v-if="!events.length" :image-size="50" description="运行后查看工具调用与回答"/><template v-else><details v-if="savedSnapshot"><summary>本次运行配置</summary><pre>{{pretty(savedSnapshot)}}</pre></details><div v-for="e in events.filter(e=>!['done','final','llm_end','llm_delta'].includes(e.type))" :key="e.id" class="trace-event" :class="e.type"><span class="trace-dot"/><div class="event-content"><div class="event-heading"><b>{{traceNames[e.type]||e.type}}</b><code v-if="e.data.tool">{{project.tools[e.data.tool as keyof typeof project.tools]?.name||e.data.tool}}</code><time>{{new Date(e.timestamp).toLocaleTimeString('zh-CN',{hour12:false})}}</time></div><p v-if="e.data.message||e.data.input&&e.type==='run_start'">{{e.data.message||e.data.input}}</p><details v-else><summary>查看{{e.type==='tool_call'?'输入':'结果'}}</summary><pre>{{pretty(e.data.input??e.data.output)}}</pre></details></div></div><article v-if="latestAnswer" class="final-answer"><b>智能体回答</b><p>{{latestAnswer}}</p></article></template></div></div></section>
    </main>


    <el-dialog v-if="dataset?.loaded" v-model="toolDataOpen" class="library-phase-dialog library-tool-data-dialog" title="数据查看工具 · 返回结果" width="820px" align-center draggable append-to-body :close-on-click-modal="false">
        <div class="library-tool-data"><template v-if="dataset"><div class="analysis-heading"><el-tag v-if="dataset.demo" type="warning">演示数据</el-tag></div><p class="analysis-source">共 {{dataset.row_count}} 条记录，本次返回前 {{dataset.preview.length}} 条。分析工具使用整张表的有效数据。</p><p v-for="f in dataset.fields" :key="f.id" class="field-description"><b>{{f.label}}</b>：{{f.unit}}</p><el-alert v-if="dataset.issues.length" title="存在数据缺失或异常，分析结果会列明排除项" type="warning" :closable="false"/><el-table :data="dataset.preview" max-height="320"><el-table-column prop="name" label="样本" min-width="135"/><el-table-column v-for="f in dataset.fields" :key="f.id" :prop="f.id" :label="f.label" min-width="100"/></el-table>
</template></div>
      <template #footer><el-button @click="toolDataOpen=false">关闭</el-button></template>
    </el-dialog>
    <el-dialog v-if="activity&&config" v-model="planOpen" class="library-phase-dialog library-plan-dialog" :aria-label="activity.title" width="760px" align-center append-to-body :close-on-click-modal="false" :close-on-press-escape="!needsPlan&&!saving&&!busy" :show-close="false" :before-close="beforePlanClose">
      <article class="library-plan-material"><h2>{{activity.title}}</h2><p>{{activity.body}}</p></article>
      <PlanCard v-if="planOpen" :baseline="learning?.plan_card" :phase="needsPlan?'before':'during'" :busy="saving||busy" :can-close="!needsPlan" @submit="confirmPlan" @close="planOpen=false"/>
    </el-dialog>
    <el-dialog v-if="activity&&config" v-model="deliveryOpen" class="library-phase-dialog library-delivery-dialog" :title="deliveryTitle" width="860px" align-center draggable append-to-body :close-on-click-modal="false" :close-on-press-escape="!busy&&!running&&!saving" :show-close="!busy&&!running&&!saving" :before-close="beforeDeliveryClose">
      <div class="delivery-context"><span>活动 {{active+1}} / 4</span><strong>{{activity.title}}</strong></div>
      <el-alert v-if="dirty" title="配置有未保存修改；更改配置后请确认所选证据仍然有效。" type="warning" :closable="false"/>
      <div v-if="active===0" class="delivery-evidence"><label>本次计算记录</label><el-select v-model="selectedId" placeholder="选择已完成的计算"><el-option v-for="a in analyses.filter(a=>a.kind==='step')" :key="a.id" :value="a.id" :label="labelAnalysis(a)"/></el-select><p v-if="result">{{result.converged?'中心已稳定':'中心尚未稳定'}} · {{result.prediction_match?'本轮预测一致':'请核查预测与计算的差异'}}</p></div>
          <section class="library-delivery"><el-tag v-if="activity.status==='submitted'" type="success">已提交，可修改后再次交付</el-tag>
            <el-form v-if="deliveryOpen" label-position="top" :disabled="running||busy||saving">
              <template v-if="active===0&&form.student_result"><p class="delivery-note">请根据实验结果，自己填写两组数量和最终中心。</p><div v-for="i in 2" :key="i" class="student-result-row"><b>第{{i}}组</b><el-form-item label="图书数量"><el-input-number v-model="form.student_result.counts[i-1]" :min="0" :max="5" :precision="0" :aria-label="'第'+i+'组图书数量'"/></el-form-item><el-form-item label="最终中心"><el-input-number v-model="form.student_result.centers[i-1]" :min="0" :max="20" :step=".1" :aria-label="'第'+i+'组最终中心'"/></el-form-item></div></template>
              <template v-else-if="active===1"><p class="delivery-note">提交你排好的七个步骤与已保存的系统指令，不需要另外填写算法和核查记录。</p><pre class="prompt-delivery-preview">{{config.system_prompt}}</pre></template>
              <template v-else-if="active===2"><p class="delivery-note">查看Agent和工具的结果后，请自己填写两组数量。</p><el-form-item label="选择已完成的Agent运行"><el-select v-model="finalRun" placeholder="需实际读取数据并完成聚类" @change="reviewRun($event)"><el-option v-for="r in completedRuns" :key="r.id" :value="r.id" :label="new Date(r.created).toLocaleString('zh-CN')"/></el-select></el-form-item><div v-for="i in 2" :key="i" class="student-result-row"><b>第{{i}}组</b><el-form-item label="记录数量"><el-input-number v-model="form.group_counts[i-1].count" :min="0" :max="150" :precision="0" :aria-label="'第'+i+'组记录数量'"/></el-form-item></div><p class="purchase-total">合计 {{(form.group_counts||[]).reduce((n:number,g:any)=>n+Number(g.count||0),0)}} / 150 条</p></template>
              <template v-else><el-form-item label="选择最终Agent运行"><el-select v-model="finalRun" placeholder="需包含真实聚类与采购建议" @change="reviewRun($event)"><el-option v-for="r in completedRuns" :key="r.id" :value="r.id" :label="new Date(r.created).toLocaleString('zh-CN')"/></el-select></el-form-item><article v-if="latestAnswer" class="final-answer"><b>Agent参考建议</b><p>{{latestAnswer}}</p><el-table v-if="agentDecision" :data="agentDecision.purchases" size="small"><el-table-column prop="type" label="Agent建议的类型"/><el-table-column prop="quantity" label="建议数量（册）"/></el-table></article><p class="delivery-note">参考Agent的建议，自己填写采购类型和数量。</p><el-button v-if="!form.purchases?.length" plain @click="preparePurchaseRows">填写采购表</el-button><div v-for="(p,i) in form.purchases||[]" :key="i" class="purchase-row"><b>第{{p.group+1}}组</b><el-input v-model="p.type" placeholder="采购类型"/><el-input-number v-model="p.quantity" :min="0" :max="1000" :step="1" :precision="0" controls-position="right" aria-label="采购数量"/></div><p class="purchase-total" :class="{valid:total===1000}">合计 {{total}} / 1000 册</p><el-form-item label="分配依据（必填，至少10个字）"><el-input v-model="form.rationale" type="textarea" :rows="3" placeholder="请自己说明：为什么这样分配采购数量？至少10个字"/></el-form-item><el-form-item label="一句话反思（必填，至少10个字）"><el-input v-model="form.reflection" type="textarea" :rows="3" placeholder="我发现…，所以调整了…；仍需要确认…"/></el-form-item></template>
            </el-form>
            <div class="delivery-actions"><el-button :disabled="busy||running||saving" @click="closeDelivery">返回实验</el-button><el-button :disabled="busy||running" @click="saveDraft()">保存草稿</el-button><el-button type="primary" :disabled="busy||running||(active===3&&!purchaseTextReady)" @click="submitDelivery">{{active===3?'提交成果与反思':'提交并解锁下一活动'}}</el-button></div>
          </section>
    </el-dialog>

    <el-dialog v-model="stableOpen" title="聚类完成" width="440px" align-center append-to-body :show-close="false" :close-on-click-modal="false" :close-on-press-escape="false" class="library-stable-dialog">
      <p>分组与中心已稳定，请填写并提交你的结果。</p>
      <template #footer><el-button type="primary" :disabled="busy||saving" @click="confirmStable">填写结果</el-button></template>
    </el-dialog>
    <el-dialog v-model="receiptOpen" title="提交成功" width="760px" align-center append-to-body :show-close="false" :close-on-click-modal="false" :close-on-press-escape="false" class="library-receipt-dialog">
      <p>活动{{receiptIndex+1}}的结果已保存。下面是你提交的内容：</p>
      <StudentResults :index="receiptIndex" :payload="receiptPayload"/><section v-if="receiptOpen&&receiptIndex>=2&&receiptAnalysis" class="submitted-visualization"><h3>本次分析的散点图</h3><p class="analysis-source">下图展示本次实际计算的分组；上方是你填写的结果。</p><AnalysisViewer :result="receiptAnalysis.result"/></section>
      <template #footer><el-button type="primary" :loading="busy" @click="continueAfterReceipt">{{receiptIndex<3?'进入活动'+(receiptIndex+2):'返回工作台'}}</el-button></template>
    </el-dialog>
    <nav v-if="learning&&!loading&&!error" class="library-floating-actions" aria-label="学习操作">
      <el-button type="primary" :disabled="busy||running||saving" @click="openDelivery">提交结果</el-button>
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
            <h3>{{learning?.activities.find(a=>a.id===plan.activity_id)?.title}} · 计划版本 {{plan.version}}</h3>
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
