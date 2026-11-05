<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { Cpu, Moon, Sunny, Position, VideoPlay, Check, ArrowLeft, ArrowRight, Close, Refresh, Clock, Setting, Connection, Reading, Warning } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import AgentNode from '../../shared/components/AgentNode.vue'
import { request, streamRun } from './api'
import type { Config, NodeId, Project, Run, Trace } from './types'

const project = ref<Project>(), config = ref<Config>(), saved = ref(''), loading = ref(true), loadError = ref(''), configured = ref(false)
const selected = ref<NodeId>('brain'), step = ref(0), completed = ref<number[]>([])
const learningCollapsed = ref(false)
const saving = ref(false), running = ref(false), input = ref(''), events = ref<Trace[]>([]), runs = ref<Run[]>([])
const historyOpen = ref(false), historyLoading = ref(false), runStatus = ref(''), snapshot = ref<Config>(), viewingHistory = ref(false)
const traceBox = ref<HTMLElement>(), layout = ref<HTMLElement>(), leftWidth = ref(320), rightWidth = ref(340), executionHeight = ref(300)
const flowWrapper = ref<HTMLElement>()
const { fitView } = useVueFlow()
let canvasObserver: ResizeObserver | undefined
let fitTimer: ReturnType<typeof setTimeout> | undefined
watch(flowWrapper, element => {
  canvasObserver?.disconnect()
  if (fitTimer) clearTimeout(fitTimer)
  if (!element) return
  canvasObserver = new ResizeObserver(() => {
    if (fitTimer) clearTimeout(fitTimer)
    fitTimer = setTimeout(() => fitView({ padding: 0.12, duration: 150 }), 100)
  })
  canvasObserver.observe(element)
}, { flush: 'post' })
const states = reactive<Record<NodeId, string>>({ brain: '', weather: '', astronomy: '' })
let controller: AbortController | undefined
const dirty = computed(() => !!config.value && JSON.stringify(config.value) !== saved.value)
const progress = computed(() => Math.round(completed.value.length / (project.value?.steps.length || 4) * 100))
const nodes = computed(() => !config.value ? [] : [
  { id: 'brain', type: 'agent', position: { x: 30, y: 135 }, data: { label: '智能体大脑', model: config.value.model, enabled: true, status: states.brain, selected: selected.value === 'brain' } },
  { id: 'weather', type: 'agent', position: { x: 380, y: 35 }, data: { label: '天气查询工具', enabled: config.value.weather.enabled, status: states.weather, selected: selected.value === 'weather' } },
  { id: 'astronomy', type: 'agent', position: { x: 380, y: 235 }, data: { label: '天体查询工具', enabled: config.value.astronomy.enabled, status: states.astronomy, selected: selected.value === 'astronomy' } },
])
const edges = computed(() => (['weather', 'astronomy'] as const).map(id => ({ id: `brain-${id}`, source: 'brain', target: id, type: 'smoothstep', animated: states[id] === 'running', style: { stroke: states[id] === 'running' ? '#7c5ce7' : config.value?.[id].enabled ? '#b5add3' : '#dce0e8', strokeWidth: states[id] === 'running' ? 3 : 1.6, strokeDasharray: config.value?.[id].enabled ? '0' : '5 5' } })))
const currentTool = computed(() => selected.value === 'brain' ? undefined : project.value?.tools[selected.value])
const finalAnswer = computed(() => events.value.findLast(e => e.type === 'final')?.data.answer as string | undefined)
const traceEvents = computed(() => events.value.filter(e => !['done', 'llm_end', 'final'].includes(e.type)))
const statusText: Record<string, string> = { completed: '已完成', running: '运行中', error: '运行失败', cancelled: '已取消', interrupted: '已中断' }
const eventNames: Record<string, string> = { run_start: '用户任务', llm_start: 'LLM 执行状态', tool_call: '工具调用', tool_result: '工具返回', tool_error: '工具错误', error: '运行错误' }
function formatTime(value: string) { return new Date(value).toLocaleString('zh-CN', { hour12: false }) }
function pretty(value: unknown) { if (typeof value === 'string') { try { return JSON.stringify(JSON.parse(value), null, 2) } catch { return value } } return JSON.stringify(value, null, 2) }
async function load() {
  loading.value = true; loadError.value = ''
  try {
    const [p, c, h, health, activities] = await Promise.all([request<Project>(''), request<Config>('/config'), request<Run[]>('/runs'), request<{ llm_configured: boolean }>('/api/health'), request<{action: string; data: {step: number}}[]>('/activities')])
    project.value = p; config.value = c; saved.value = JSON.stringify(c); runs.value = h; configured.value = health.llm_configured
    completed.value = [...new Set(activities.filter(a => a.action === 'learning_step_completed').map(a => a.data.step))]
    if (h[0]) await showRun(h[0].id)
  } catch (e) { loadError.value = (e as Error).message } finally { loading.value = false }
}
async function save() {
  if (!config.value || !config.value.system_prompt.trim()) { ElMessage.warning('请填写 System Prompt'); return false }
  saving.value = true
  const value = structuredClone(config.value ? JSON.parse(JSON.stringify(config.value)) : {}) as Config
  try { await request('/config', 'PUT', value); saved.value = JSON.stringify(value); ElMessage.success('配置已保存'); return true }
  catch (e) { ElMessage.error((e as Error).message); return false } finally { saving.value = false }
}
async function markComplete() {
  try { await request('/activities', 'POST', { action: 'learning_step_completed', step: step.value }); if (!completed.value.includes(step.value)) completed.value.push(step.value); if (step.value < 3) step.value++ }
  catch (e) { ElMessage.error((e as Error).message) }
}
function resetStates() { states.brain = ''; states.weather = ''; states.astronomy = '' }
function receive(event: Trace) {
  events.value.push(event)
  const node = event.data.node as NodeId
  if (node && node in states) {
    if (['llm_start', 'tool_call'].includes(event.type)) states[node] = 'running'
    if (['llm_end', 'tool_result', 'final'].includes(event.type)) states[node] = event.data.status === 'error' ? 'error' : 'success'
    if (event.type === 'tool_error') states[node] = 'error'
  }
  if (event.type === 'error') { states.brain = 'error'; for (const id of ['weather', 'astronomy'] as const) if (states[id] === 'running') states[id] = 'error' }
  if (event.type === 'done') runStatus.value = event.data.status
  nextTick(() => { if (traceBox.value) traceBox.value.scrollTop = traceBox.value.scrollHeight })
}
async function run() {
  if (!input.value.trim() || running.value || !config.value) return
  if (dirty.value && !(await save())) return
  running.value = true; viewingHistory.value = false; events.value = []; resetStates(); runStatus.value = 'running'; snapshot.value = undefined
  controller = new AbortController()
  try { await streamRun({ input: input.value.trim(), config: config.value }, controller.signal, receive) }
  catch (e) { const cancelled = (e as Error).name === 'AbortError'; runStatus.value = cancelled ? 'cancelled' : 'error'; receive({ id: Date.now(), run_id: '', type: 'error', timestamp: new Date().toISOString(), data: { message: cancelled ? '已停止本次运行' : (e as Error).message } }) }
  finally { running.value = false; for (const id of ['brain', 'weather', 'astronomy'] as const) if (states[id] === 'running') states[id] = ''; await refreshHistory() }
}
async function refreshHistory() { try { runs.value = await request<Run[]>('/runs') } catch (e) { ElMessage.error((e as Error).message) } }
async function showRun(id: string) {
  if (running.value) return
  historyLoading.value = true
  try {
    const result = await request<Run & {events: Trace[]; config: Config}>(`/runs/${id}`)
    events.value = result.events; runStatus.value = result.status; snapshot.value = result.config; viewingHistory.value = true; resetStates(); historyOpen.value = false
  } catch (e) { ElMessage.error((e as Error).message) } finally { historyLoading.value = false }
}
function example() { const d = new Date(); d.setDate(d.getDate() + 1); const date = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; input.value = `我计划 ${date} 北京时间 20:00（UTC+08:00）在北京使用双筒望远镜，比较月球、木星和土星的观测条件。请按需调用天气和天文工具，列出工具实际返回的数据、来源和缺失字段；若没有地平高度、方位角或天气依据，请说明无法确认实际可见性。请区分 Open-Meteo 天气预报和 NASA/JPL Horizons 计算星历，不要称为现场实测。` }
let stopResize: (() => void) | undefined
function resize(kind: 'left' | 'right' | 'bottom', e: PointerEvent) {
  const startX = e.clientX, startY = e.clientY, start = kind === 'left' ? leftWidth.value : kind === 'right' ? rightWidth.value : executionHeight.value
  const move = (event: PointerEvent) => {
    if (kind === 'left') leftWidth.value = Math.max(235, Math.min(380, start + event.clientX - startX))
    if (kind === 'right') rightWidth.value = Math.max(270, Math.min(420, start + startX - event.clientX))
    if (kind === 'bottom') executionHeight.value = Math.max(210, Math.min((layout.value?.clientHeight || 800) - 250, start + startY - event.clientY))
  }
  const stop = () => { document.removeEventListener('pointermove', move); document.removeEventListener('pointerup', stop); document.body.style.userSelect = ''; stopResize = undefined }
  document.body.style.userSelect = 'none'; document.addEventListener('pointermove', move); document.addEventListener('pointerup', stop); stopResize = stop
}
function beforeLeave(e: BeforeUnloadEvent) { if (dirty.value || running.value) e.preventDefault() }
onMounted(() => { load(); window.addEventListener('beforeunload', beforeLeave) })
onBeforeUnmount(() => { controller?.abort(); stopResize?.(); canvasObserver?.disconnect(); if (fitTimer) clearTimeout(fitTimer); window.removeEventListener('beforeunload', beforeLeave) })
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand"><span class="brand-mark"><el-icon><Position/></el-icon></span>orbit<span class="brand-separator"/><span class="workspace-name">智能体学习空间</span></div>
      <div class="top-actions"><RouterLink class="project-route-link" to="/">项目首页</RouterLink><RouterLink class="project-route-link" to="/projects/library-recommendation">图书馆项目</RouterLink><div v-if="project && config && !loading && !loadError" class="project-actions"><span class="save-state" :class="{dirty}"><i/>{{ dirty ? '有未保存的修改' : '配置已同步' }}</span><el-button :icon="Clock" :disabled="running" @click="historyOpen = true; refreshHistory()">运行历史 <span class="count">{{ runs.length }}</span></el-button><el-button type="primary" :loading="saving" :disabled="running || !dirty" @click="save">保存配置</el-button></div><span class="avatar">S</span></div>
    </header>
    <div v-if="loading" class="loading-screen"><el-skeleton :rows="8" animated/><p>正在准备你的学习空间…</p></div>
    <div v-else-if="loadError" class="empty-screen"><el-icon><Warning/></el-icon><h2>暂时无法连接工作台</h2><p>{{ loadError }}</p><p>请确认 FastAPI 后端已在 8000 端口启动。</p><el-button type="primary" @click="load">重新连接</el-button></div>
    <template v-else-if="project && config">
      <main ref="layout" class="workspace" :class="{'learning-collapsed': learningCollapsed}" :style="{'--left-width': leftWidth + 'px', '--right-width': rightWidth + 'px', '--execution-height': executionHeight + 'px'}">
        <aside class="learning-panel">
          <div v-if="!learningCollapsed" class="panel-heading"><el-icon><Reading/></el-icon><strong>学习指南</strong><button class="sidebar-toggle" aria-label="收起学习指南" aria-controls="learning-content" :aria-expanded="true" title="收起学习指南" @click="learningCollapsed = true"><el-icon><ArrowLeft/></el-icon></button></div>
          <button v-else class="learning-rail" aria-label="展开学习指南" aria-controls="learning-content" :aria-expanded="false" title="展开学习指南" @click="learningCollapsed = false"><el-icon><Reading/></el-icon><span>学习指南</span><el-icon><ArrowRight/></el-icon></button>
          <div id="learning-content" v-show="!learningCollapsed" class="learning-scroll"><div class="learning-intro"><span class="eyebrow">PROJECT 1</span><h2>月球与行星观测</h2></div>
          <div class="learning-progress"><div><span>学习进度</span><b>{{ completed.length }} / {{ project.steps.length }}</b></div><el-progress :percentage="progress" :show-text="false" :stroke-width="5" color="#7c5ce7"/></div>
          <nav class="step-list" aria-label="学习步骤"><button v-for="(s, i) in project.steps" :key="s.title" :class="{current: step === i, finished: completed.includes(i)}" @click="step = i"><span class="step-number"><el-icon v-if="completed.includes(i)"><Check/></el-icon><template v-else>{{ String(i+1).padStart(2,'0') }}</template></span><span><strong>{{ s.title }}</strong></span><el-icon v-if="step === i"><ArrowRight/></el-icon></button></nav>
          <article class="lesson-card"><h3>{{ project.steps[step].title }}</h3><p>{{ project.steps[step].body }}</p><div class="try-it"><b>动手试一试</b><p>{{ project.steps[step].instruction }}</p></div><el-button :type="completed.includes(step) ? 'default' : 'primary'" plain @click="markComplete"><el-icon><Check/></el-icon>{{ completed.includes(step) ? '已完成 · 继续学习' : '完成这一步' }}</el-button></article>
          <details class="goals"><summary>你将学会什么</summary><p v-for="goal in project.objectives" :key="goal">✓ {{ goal }}</p></details></div>
          
        </aside>
        <div v-show="!learningCollapsed" class="resizer vertical left-resizer" role="separator" aria-label="调整学习面板宽度" @pointerdown="resize('left', $event)"/>
        <section class="canvas-panel">
          <div class="canvas-toolbar"><div><el-icon><Connection/></el-icon><strong>Agent 画布</strong></div></div>
          <div ref="flowWrapper" class="flow-wrapper"><VueFlow :nodes="nodes" :edges="edges" :nodes-draggable="false" :nodes-connectable="false" :delete-key-code="null" :min-zoom="0.35" :max-zoom="1.5" fit-view-on-init :fit-view-params="{padding: 0.12}" @node-click="selected = $event.node.id as NodeId"><Background pattern-color="#d6dae5" :gap="20" :size="1"/><Controls :show-interactive="false"/><template #node-agent="props"><AgentNode v-bind="props"/></template></VueFlow>
          <div v-if="running" class="canvas-note"><span class="status-dot"/>正在运行</div></div>
          <div class="canvas-legend"><a href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer">Open-Meteo</a><a href="https://ssd.jpl.nasa.gov/horizons/" target="_blank" rel="noopener noreferrer">NASA/JPL</a></div>
        </section>
        <div class="resizer vertical right-resizer" role="separator" aria-label="调整配置面板宽度" @pointerdown="resize('right', $event)"/>
        <aside class="configuration-panel"><div class="panel-heading"><el-icon><Setting/></el-icon><strong>节点配置</strong></div><div class="config-scroll"><div class="config-node-title"><span class="node-icon" :class="selected"><el-icon><Cpu v-if="selected === 'brain'"/><Sunny v-else-if="selected === 'weather'"/><Moon v-else/></el-icon></span><div><h2>{{ selected === 'brain' ? '智能体大脑' : currentTool?.name }}</h2></div></div>
          <el-form v-if="selected === 'brain'" label-position="top" :disabled="running || saving">
            <el-form-item label="Model"><el-select v-model="config.model" aria-label="选择模型"><el-option v-for="m in project.models" :key="m" :label="m" :value="m"/></el-select></el-form-item>
            <el-form-item><template #label><div class="field-label">System Prompt <span>{{ config.system_prompt.length }} / 12000</span></div></template><el-input v-model="config.system_prompt" type="textarea" :rows="8" :maxlength="12000" resize="vertical" placeholder="描述 Agent 的角色、任务和行为边界"/></el-form-item>
            <el-form-item><template #label><div class="field-label">Temperature <b>{{ config.temperature.toFixed(1) }}</b></div></template><el-slider v-model="config.temperature" :min="0" :max="2" :step="0.1" aria-label="Temperature"/><div class="slider-labels"><span>更稳定</span><span>更有创造力</span></div></el-form-item>
          </el-form>
          <template v-else-if="currentTool"><p class="tool-description">{{ currentTool.description }}</p><div class="enable-box"><div><b>启用工具</b></div><el-switch v-model="config[selected].enabled" :disabled="running || saving" :aria-label="'启用 ' + currentTool.name"/></div><el-form label-position="top" :disabled="running || saving"><el-form-item v-if="selected === 'weather'" label="温度单位"><el-select v-model="config.weather.units"><el-option label="摄氏度 °C" value="celsius"/><el-option label="华氏度 °F" value="fahrenheit"/></el-select></el-form-item><el-form-item v-else label="观测设备"><el-select v-model="config.astronomy.equipment"><el-option label="肉眼观测" value="naked_eye"/><el-option label="双筒望远镜" value="binoculars"/><el-option label="天文望远镜" value="telescope"/></el-select></el-form-item></el-form><h3 class="section-label">工具输入参数</h3><div v-for="param in currentTool.parameters" :key="param.name" class="parameter"><div><code>{{ param.name }}</code><span>{{ param.type }}</span></div><p>{{ param.description }}</p></div></template>
          
        </div></aside>
        <div class="resizer horizontal" role="separator" aria-label="调整执行面板高度" @pointerdown="resize('bottom', $event)"/>
        <section class="execution-panel"><div class="execution-toolbar"><div><el-icon><VideoPlay/></el-icon><strong>实验运行</strong><span v-if="runStatus" class="run-badge" :class="runStatus">{{ viewingHistory ? '历史 · ' : '' }}{{ statusText[runStatus] || runStatus }}</span></div></div>
          <div class="execution-body"><div class="test-input"><div class="input-label"><b>给 Agent 一个任务</b><button :disabled="running" @click="example">试试示例 ↗</button></div><el-input v-model="input" type="textarea" :rows="3" :maxlength="6000" :disabled="running" resize="none" placeholder="例如：明晚北京时间 20:00，在北京能观测月球、木星或土星吗？请说明数据依据。" @keydown.ctrl.enter.prevent="run"/><div class="run-controls"><span>{{ running ? '正在等待模型与工具执行…' : 'Ctrl + Enter 运行' }}</span><el-button v-if="running" :icon="Close" @click="controller?.abort()">停止</el-button><el-button v-else type="primary" :icon="VideoPlay" :disabled="!input.trim() || saving || !config.system_prompt.trim()" @click="run">Run Agent</el-button></div><div v-if="!configured" class="api-notice"><el-icon><Warning/></el-icon><span>尚未配置模型密钥。在 backend/.env 设置后重启后端。</span></div></div>
          <div ref="traceBox" class="trace-output" aria-live="polite"><div v-if="!events.length" class="trace-empty"><span class="empty-illustration"><el-icon><Connection/></el-icon></span><h3>运行后查看结果</h3></div><template v-else><details v-if="snapshot" class="snapshot"><summary>查看本次配置快照 · {{ snapshot.model }}</summary><pre>{{ pretty(snapshot) }}</pre></details><div v-for="event in traceEvents" :key="event.id" class="trace-event" :class="event.type"><span class="trace-dot"/><div class="event-content"><div class="event-heading"><b>{{ eventNames[event.type] || event.type }}</b><code v-if="event.data.tool">{{ event.data.tool }}</code><time>{{ new Date(event.timestamp).toLocaleTimeString('zh-CN', {hour12:false}) }}</time></div><p v-if="event.type === 'run_start'">{{ event.data.input }}</p><p v-else-if="event.data.message">{{ event.data.message }}</p><details v-else :open="event.type === 'tool_call'"><summary>{{ event.type === 'tool_call' ? '输入参数' : '查看返回结果与数据来源' }}</summary><pre>{{ pretty(event.data.input ?? event.data.output) }}</pre></details></div></div><article v-if="finalAnswer" class="final-answer"><div><span>✦</span><b>Agent 最终回答</b></div><p>{{ finalAnswer }}</p></article><div v-if="running" class="running-indicator"><span class="spinner"/>Agent 正在执行…</div><div v-else-if="runStatus === 'interrupted'" class="info-note">后端重启中断了此运行，已保留此前事件，请重新运行。</div></template></div></div>
        </section>
      </main>
    </template>
    <el-drawer v-model="historyOpen" title="运行历史" size="440px"><el-button :icon="Refresh" text @click="refreshHistory">刷新记录</el-button><el-empty v-if="!runs.length" description="还没有运行记录，开始你的第一次实验吧"/><div v-loading="historyLoading"><button v-for="r in runs" :key="r.id" class="history-item" :disabled="historyLoading" @click="showRun(r.id)"><div><time>{{ formatTime(r.created) }}</time><span class="run-badge" :class="r.status">{{ statusText[r.status] }}</span></div><p>{{ r.input }}</p></button></div></el-drawer>
  </div>
</template>
