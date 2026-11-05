import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, runStream } from './api'
import type { Activity, Analysis, Dataset, DatasetOption, Learning, LibraryConfig, LibraryRun, NodeId, Project, Result, ToolId } from './types'
import type { Trace } from '../../shared/types'

export const toolIds: ToolId[] = ['inspect_dataset', 'run_kmeans_analysis']

export function useLibrary() {
  const project = ref<Project>(), learning = ref<Learning>(), config = ref<LibraryConfig>(), dataset = ref<Dataset>()
  const datasetOptions = ref<DatasetOption[]>([])
  const loading = ref(true), error = ref(''), active = ref(0), busy = ref(false), saving = ref(false), running = ref(false), collapsed = ref(true)
  const selected = ref<NodeId>('brain'), revision = ref(0), saved = ref(''), analyses = ref<Analysis[]>([]), runs = ref<LibraryRun[]>([])
  const selectedId = ref(''), finalRun = ref('')
  const form = ref<Record<string, any>>({}), input = ref(''), events = ref<Trace[]>([]), runStatus = ref(''), historyOpen = ref(false), savedSnapshot = ref<unknown>()
  const states = reactive<Record<NodeId, string>>({brain:'',inspect_dataset:'',run_kmeans_analysis:''})
  let controller: AbortController | undefined
  const activity = computed(() => learning.value?.activities[active.value])
  const id = computed(() => activity.value?.id || 'group_books')
  const dirty = computed(() => !!config.value && saved.value !== JSON.stringify(config.value))
  const result = computed(() => analyses.value.find(a => a.id === selectedId.value)?.result)
  const finalEvidence=computed(()=>analyses.value.find(a=>a.kind==='full'&&a.run_id===finalRun.value&&a.revision===revision.value))
  const latestAnswer = computed(() => events.value.findLast(e => e.type === 'final')?.data.answer as string | undefined)
  const permitted = computed(() => activity.value?.tools || [])
  const completedRuns = computed(() => runs.value.filter(r => r.status === 'completed' && r.revision === revision.value))
  const statusNames: Record<string,string> = {completed:'已完成',error:'失败',running:'运行中',cancelled:'已停止',interrupted:'已中断'}
  const traceNames: Record<string,string> = {run_start:'学生任务',llm_start:'智能体处理中',llm_end:'模型已响应',tool_call:'调用工具',tool_result:'工具结果',tool_error:'工具错误',error:'运行错误'}
  function fail(e: unknown) { ElMessage.error((e as Error).message || '请求失败') }
  function labelAnalysis(a: Analysis) { return `${a.kind === 'step' ? '第'+a.result.round+'轮' : a.result.experiment.features.length+'维 · K='+a.result.experiment.k} · 配置v${a.revision} · ${new Date(a.created).toLocaleTimeString('zh-CN',{hour12:false})}` }
  function pretty(value: unknown) { if (typeof value === 'string') { try { return JSON.stringify(JSON.parse(value),null,2) } catch { return value } } return JSON.stringify(value,null,2) }
  function resetStates() { for (const k of Object.keys(states) as NodeId[]) states[k] = '' }
  async function refreshEvidence() {
    const [a,r] = await Promise.all([api<Analysis[]>(`/activities/${id.value}/analyses`),api<LibraryRun[]>(`/runs?activity_id=${id.value}`)])
    analyses.value=a; runs.value=r
    if (!a.some(a=>a.id===selectedId.value)) selectedId.value=a[0]?.id || ''
  }
  async function loadActivity() {
    busy.value=true; error.value=''
    try {
      const [c,d,options] = await Promise.all([api<{config:LibraryConfig;revision:number}>(`/config?activity_id=${id.value}`),api<Dataset>(`/activities/${id.value}/dataset`),api<DatasetOption[]>(`/activities/${id.value}/datasets`)])
      datasetOptions.value=options
      config.value=c.config; revision.value=c.revision; saved.value=JSON.stringify(c.config); dataset.value=d
      await refreshEvidence()
      const payload=activity.value?.draft && Object.keys(activity.value.draft).length ? activity.value.draft : activity.value?.submission?.payload || {}
      form.value={...JSON.parse(JSON.stringify(payload)),plan:activity.value?.plan?.text || payload.plan || ''}; finalRun.value=payload.run_id || completedRuns.value[0]?.id || ''
      selectedId.value=analyses.value.some(a=>a.id===payload.analysis_id) ? payload.analysis_id : analyses.value[0]?.id || ''
      events.value=[]; savedSnapshot.value=undefined; runStatus.value=''; selected.value='brain'; resetStates(); example()
      if(active.value>=2&&finalRun.value)await reviewRun(finalRun.value,true)
    } catch(e) { error.value=(e as Error).message; fail(e) } finally { busy.value=false }
  }
  async function load() {
    loading.value=true; error.value=''
    try {
      const [p,l] = await Promise.all([api<Project>(''),api<Learning>('/learning')]); project.value=p; learning.value=l
      active.value=Math.min(l.completed,3); await loadActivity()
    } catch(e) { error.value=(e as Error).message } finally { loading.value=false }
  }
  async function saveConfig() {
    if (!config.value || active.value===0) return !dirty.value
    saving.value=true
    try {
      const c=await api<{config:LibraryConfig;revision:number}>(`/config?activity_id=${id.value}&revision=${revision.value}`,'PUT',config.value)
      config.value=c.config; revision.value=c.revision; saved.value=JSON.stringify(c.config); 
      await refreshEvidence(); ElMessage.success('配置已保存'); return true
    } catch(e) { fail(e); return false } finally { saving.value=false }
  }
  function payload() { return {...form.value,analysis_id:selectedId.value,run_id:finalRun.value} }
  async function saveDraft(silent=false) {
    try { await api(`/activities/${id.value}/draft`,'PUT',{payload:payload()}); if(!silent) ElMessage.success('交付草稿已保存'); return true }
    catch(e) { fail(e); return false }
  }
  async function submitPlan(text:string) {
    saving.value=true
    try {
      learning.value=await api<Learning>(`/activities/${id.value}/plan`,'POST',{text})
      form.value.plan=learning.value.activities[active.value]?.plan?.text||text.trim(); collapsed.value=true
      ElMessage.success('学习计划已保存，开始实验'); return true
    } catch(e) { fail(e); return false } finally { saving.value=false }
  }
  async function switchActivity(index:number) {
    if(running.value || busy.value || saving.value || index===active.value) return
    if(learning.value?.activities[index]?.status==='locked') { ElMessage.warning('请先提交上一活动'); return }
    if(dirty.value && !(await saveConfig())) return
    if(!(await saveDraft(true))) return
    active.value=index; await loadActivity()
  }
  async function submit() {
    if(dirty.value && !(await saveConfig())) return false
    busy.value=true
    try {
      learning.value=await api<Learning>(`/activities/${id.value}/submit`,'POST',{payload:payload()})
      ElMessage.success(active.value===3 ? '采购方案与反思已提交' : '交付已提交，下一活动已解锁')
      active.value=Math.min(active.value+1,3); await loadActivity(); return true
    } catch(e) { fail(e); return false } finally { busy.value=false }
  }
  async function analyze() {
    if(dirty.value && !(await saveConfig())) return
    busy.value=true; states.run_kmeans_analysis='running'
    try { const value=await api<Result>(`/activities/${id.value}/analyses?revision=${revision.value}`,'POST'); await refreshEvidence(); selectedId.value=value.analysis_id; states.run_kmeans_analysis='success' }
    catch(e) { states.run_kmeans_analysis='error'; fail(e) } finally { busy.value=false }
  }
  async function selectDataset(datasetId:string) {
    if(!config.value||busy.value||running.value||saving.value)return
    const option=datasetOptions.value.find(d=>d.id===datasetId)
    if(!option)return
    const previous=config.value.experiment.dataset_id
    busy.value=true
    try {
      const metadata=await api<Dataset>(`/activities/${id.value}/dataset?dataset_id=${encodeURIComponent(datasetId)}`)
      config.value.experiment.dataset_id=datasetId
      config.value.experiment.features=option.fields.map(f=>f.id)
      dataset.value=metadata;selectedId.value=''
      states.inspect_dataset='';states.run_kmeans_analysis=''
    }catch(e){config.value.experiment.dataset_id=previous;fail(e)}finally{busy.value=false}
  }
  async function inspectData() {
    if(dirty.value && !(await saveConfig())) return false
    busy.value=true
    const eventId=Date.now()
    receive({id:eventId,run_id:'',type:'tool_call',timestamp:new Date().toISOString(),data:{node:'inspect_dataset',tool:'inspect_dataset',input:{dataset_id:config.value?.experiment.dataset_id,preview_rows:30}}})
    try {
      dataset.value=await api<Dataset>(`/activities/${id.value}/tools/inspect_dataset?revision=${revision.value}`,'POST')
      receive({id:eventId+1,run_id:'',type:'tool_result',timestamp:new Date().toISOString(),data:{node:'inspect_dataset',tool:'inspect_dataset',status:'success',output:dataset.value}})
      return true
    } catch(e) {
      receive({id:eventId+1,run_id:'',type:'tool_error',timestamp:new Date().toISOString(),data:{node:'inspect_dataset',message:(e as Error).message}})
      fail(e);return false
    } finally {busy.value=false}
  }
  function example() {
    input.value=active.value===1 ? '请先读取五本书的借阅次数，再按照我设置的七个步骤说明如何分成2组，解释哪些步骤需要重复以及何时停止。' : active.value===2 ? '请先查看150条二维借阅数据，再调用完整聚类工具，按借阅次数和借阅时长分成2组。告诉我每组多少条，总数是否为150。' : '请读取100条学生阅读兴趣调查并调用完整聚类工具，根据组中心和人数决定买什么类型的书、各买多少册，合计1000册，说明分配依据与样本局限，不编造具体书名。'
  }
  function receive(event:Trace) {
    events.value.push(event)
    const node=event.data.node as NodeId
    if(node in states) {
      if(['llm_start','tool_call'].includes(event.type)) states[node]='running'
      if(['llm_end','tool_result','final'].includes(event.type)) states[node]=event.data.status==='error' ? 'error' : 'success'
      if(event.type==='tool_error') states[node]='error'
    }
    if(event.type==='error') states.brain='error'
    if(event.type==='done') runStatus.value=event.data.status
    if(event.type==='final'&&event.data.decision){form.value.purchases=JSON.parse(JSON.stringify(event.data.decision.purchases));form.value.rationale=event.data.decision.rationale}
    if(event.type==='tool_result'&&event.data.tool==='inspect_dataset'&&event.data.status!=='error') {
      try {
        const value=typeof event.data.output==='string'?JSON.parse(event.data.output):event.data.output
        if(value?.id===config.value?.experiment.dataset_id&&value.loaded&&Array.isArray(value.preview)) {
          if(!dataset.value?.loaded||dataset.value.version!==value.version||dataset.value.preview.length<=value.preview.length)dataset.value=value
        }
      } catch { /* Keep the previous successful tool result on malformed output. */ }
    }
  }
  async function run() {
    if(!input.value.trim() || running.value || active.value===0) return
    if(dirty.value && !(await saveConfig())) return
    running.value=true; events.value=[]; savedSnapshot.value=undefined; runStatus.value='running'; resetStates(); controller=new AbortController()
    try { await runStream({activity_id:id.value,revision:revision.value,input:input.value},controller.signal,receive) }
    catch(e) { runStatus.value='error'; receive({id:Date.now(),run_id:'',type:'error',timestamp:new Date().toISOString(),data:{message:(e as Error).name==='AbortError'?'运行已停止':(e as Error).message}}) }
    finally { running.value=false; for(const key of Object.keys(states) as NodeId[]) if(states[key]==='running') states[key]=''; try {await refreshEvidence(); finalRun.value=runStatus.value==='completed'?events.value[0]?.run_id||'':''} catch(e) {fail(e)} }
  }
  async function reviewRun(runId:string,keepDraft=false) {
    try {
      const value=await api<{events:Trace[];config:unknown;status:string}>(`/runs/${runId}`)
      events.value=value.events;runStatus.value=value.status;savedSnapshot.value=value.config;finalRun.value=runId;resetStates()
      const decision=value.events.findLast(e=>e.type==='final')?.data.decision
      if(decision&&(!keepDraft||!Array.isArray(form.value.purchases))){form.value.purchases=JSON.parse(JSON.stringify(decision.purchases));form.value.rationale=decision.rationale}
    }catch(e){fail(e)}
  }
  async function showRun(runId:string){await reviewRun(runId);historyOpen.value=false}
  function stop() { controller?.abort() }
  function leave(e:BeforeUnloadEvent) { if(dirty.value || running.value) e.preventDefault() }
  onMounted(()=>{load();window.addEventListener('beforeunload',leave)})
  onBeforeUnmount(()=>{stop();window.removeEventListener('beforeunload',leave)})
  return {project,learning,config,dataset,datasetOptions,selectDataset,loading,error,active,busy,saving,running,collapsed,selected,revision,dirty,analyses,runs,selectedId,finalRun,form,input,events,runStatus,historyOpen,savedSnapshot,states,activity,id,result,finalEvidence,latestAnswer,permitted,completedRuns,statusNames,traceNames,labelAnalysis,pretty,load,saveConfig,saveDraft,submitPlan,switchActivity,submit,analyze,inspectData,example,run,reviewRun,showRun,stop}
}
