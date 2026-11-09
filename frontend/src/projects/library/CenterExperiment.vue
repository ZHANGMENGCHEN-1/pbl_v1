<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from './api'
import type { Analysis, Dataset, Result } from './types'

const props=defineProps<{revision:number; ready:boolean}>()
const emit=defineEmits<{result:[value:Result]; completed:[]}>()
const data=ref<Dataset>(), result=ref<Result>(), history=ref<Analysis[]>([]), busy=ref(false)
const centers=ref([2,11]), previous=ref(''), selecting=ref(0)
const iteration=computed(()=>result.value?.iterations[0])
const fmt=(v:number)=>Number(v.toFixed(3)).toString()
const x=(v:number)=>65+v*43
async function load(){
  busy.value=true
  try{
    data.value=await api<Dataset>(`/activities/group_books/tools/inspect_dataset?revision=${props.revision}`,'POST')
  }catch(e){ElMessage.error((e as Error).message)}finally{busy.value=false}
}
function restore(a:Analysis){result.value=a.result;previous.value=a.id;centers.value=a.result.centers.map(c=>c[0]);emit('result',a.result)}
function reset(){result.value=undefined;previous.value='';selecting.value=0;history.value=[]}
function randomize(){reset();const a=Math.floor(Math.random()*21);let b=Math.floor(Math.random()*20);if(b>=a)b++;centers.value=[a,b]}
function pick(e:MouseEvent){if(previous.value||busy.value)return;const rect=e.currentTarget instanceof Element?e.currentTarget.getBoundingClientRect():undefined;if(!rect)return;const v=Math.max(0,Math.min(20,Math.round((((e.clientX-rect.left)/rect.width)*1000-65)/43*10)/10));centers.value[selecting.value]=v;selecting.value=1-selecting.value}
async function calculate(){
  busy.value=true
  try{
    const value=await api<Result>(`/activities/group_books/center-steps?revision=${props.revision}`,'POST',{centers:centers.value,previous_step_id:previous.value||null})
    result.value=value;previous.value=value.analysis_id;centers.value=value.centers.map(c=>c[0]);emit('result',value)
    history.value.unshift({id:value.analysis_id,revision:props.revision,kind:'step',result:value,run_id:null,created:new Date().toISOString()})
    if(value.converged)emit('completed')
  }catch(e){ElMessage.error((e as Error).message)}finally{busy.value=false}
}
onMounted(()=>{if(props.ready)load()})
</script>

<template>
  <div class="center-experiment" v-loading="busy">
    <div class="center-heading"><h2>把五本书分成两组</h2></div>
    <p>每本书下面的数字是借阅次数。先选两个中心，再看看怎么分组。</p>
    <el-table v-if="data" :data="data.preview" border><el-table-column prop="name" label="书名"/><el-table-column prop="borrow_count" label="借阅次数" width="130"/></el-table>
    <section class="center-interaction-card"><h3 class="interaction-title">先选两个中心点</h3>
    <div class="center-controls"><el-radio-group v-model="selecting" :disabled="!!previous"><el-radio-button :value="0">中心点1</el-radio-button><el-radio-button :value="1">中心点2</el-radio-button></el-radio-group><el-input-number v-for="(_,i) in centers" :key="i" v-model="centers[i]!" :aria-label="'中心点'+(i+1)" :min="0" :max="20" :step=".1" :disabled="!!previous||busy"/><el-button :disabled="busy" @click="randomize">随机选择</el-button><el-button :disabled="busy" @click="reset">重新选点</el-button></div>
    <p>{{previous?'数轴显示本轮分组与更新后的中心。':'点击数轴设置所选中心点，也可以直接输入数值。'}}</p>
    <svg class="center-axis" viewBox="0 0 1000 190" role="img" aria-label="借阅次数一维数轴，点击选择中心点" @click="pick">
      <line x1="65" y1="100" x2="925" y2="100" stroke="#adb5c6" stroke-width="2"/>
      <g v-for="n in 21" :key="n"><line :x1="x(n-1)" y1="100" :x2="x(n-1)" y2="107" stroke="#adb5c6"/><text :x="x(n-1)" y="127" text-anchor="middle">{{n-1}}</text></g>
      <g v-for="(row,i) in data?.preview" :key="row.id"><circle :cx="x(row.borrow_count)" cy="100" r="8" :fill="result?(result.labels[i]===0?'#7c5ce0':'#169d93'):'#697586'"/><text :x="x(row.borrow_count)" :y="i%2?42:66" text-anchor="middle">{{row.name}}</text></g>
      <g v-for="(c,i) in centers" :key="i" :fill="i===0?'#7c5ce0':'#169d93'"><path :d="`M ${x(c)} 83 l -7 -14 h 14 Z`"/><text :x="x(c)" :y="151+i*23" text-anchor="middle">中心{{i+1}}：{{fmt(c)}}</text></g>
    </svg>
    <div class="center-controls"><el-button type="primary" :loading="busy" :disabled="!data||!ready||centers[0]===centers[1]||result?.converged" @click="calculate">{{previous?'用新中心，再算一轮':'计算一轮'}}</el-button><el-tag v-if="result">第 {{result.round}} 轮</el-tag></div>
    <template v-if="result&&iteration">
      <h3>本轮距离与分组</h3>
      <el-table :data="result.records.map((r,i)=>({...r,d1:iteration!.distances[i]![0],d2:iteration!.distances[i]![1],group:result!.labels[i]!+1}))" border><el-table-column prop="name" label="书名"/><el-table-column prop="borrow_count" label="借阅次数"/><el-table-column :label="'距中心1（'+fmt(iteration.centers_before[0]![0]!)+ '）'"><template #default="s">{{fmt(s.row.d1)}}</template></el-table-column><el-table-column :label="'距中心2（'+fmt(iteration.centers_before[1]![0]!)+ '）'"><template #default="s">{{fmt(s.row.d2)}}</template></el-table-column><el-table-column prop="group" label="所属组"/></el-table>
      <h3>根据分组更新中心点</h3>
      <p v-for="(c,i) in result.centers" :key="i">中心点{{i+1}}：（{{result.records.filter((_,j)=>result!.labels[j]===i).map(r=>r.borrow_count).join(' + ')||'空组，保留原中心'}}<template v-if="result.groups[i]!.count">） ÷ {{result.groups[i]!.count}}</template> = {{fmt(c[0]!)}}</p>
      <el-alert v-for="w in result.warnings" :key="w" :title="w" type="warning" :closable="false"/>
      <p>计算时保留完整数值，显示的中心可能是近似数。</p>
    </template>
    <el-select v-if="history.length" placeholder="回看计算记录" @change="restore(history.find(a=>a.id===$event)!)"><el-option v-for="a in history" :key="a.id" :value="a.id" :label="'第'+a.result.round+'轮 · '+new Date(a.created).toLocaleTimeString()"/></el-select>
    </section>
  </div>
</template>

<style scoped>
.center-experiment{padding:24px 32px;max-width:1200px;margin:auto;font-size:16px;color:#475269}.center-heading,.center-controls{display:flex;align-items:center;gap:14px;flex-wrap:wrap}.center-heading{justify-content:space-between}.center-heading h2{font-size:20px;color:#7453aa}.center-experiment p{line-height:1.8}.center-controls{margin:20px 0}.center-axis{width:100%;min-height:190px;background:#faf9fe;border:1px solid #e8e1f3;border-radius:12px;cursor:crosshair}.center-axis text{font-size:15px}.center-experiment h3{font-size:17px;margin-top:26px}
.center-interaction-card{margin-top:28px;padding:24px;border:1px solid #ded4f2;border-radius:16px;background:#fff;box-shadow:0 5px 22px #7453aa0b;border-top:4px solid #8b6bc8}.center-interaction-card .interaction-title{margin:0 0 20px;color:#7453aa;font-size:18px}.center-interaction-card .el-select{margin-top:16px;width:100%}
</style>
