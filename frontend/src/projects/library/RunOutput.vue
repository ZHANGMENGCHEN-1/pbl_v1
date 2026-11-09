<script setup lang="ts">
import { computed } from 'vue'
import type { Trace } from '../../shared/types'
const props=defineProps<{events:Trace[];answer?:string;running:boolean;snapshot?:unknown}>()
const results=computed(()=>props.events.filter(e=>e.type==='tool_result'))
const errors=computed(()=>props.events.filter(e=>['error','tool_error'].includes(e.type)))
const decision=computed(()=>props.events.findLast(e=>e.type==='final')?.data.decision)
function output(e:Trace){try{return typeof e.data.output==='string'?JSON.parse(e.data.output):e.data.output}catch{return null}}
function summary(e:Trace){
  const value=output(e)
  if(e.data.status==='error')return '这次没有成功，请看下面的提示。'
  if(e.data.tool==='inspect_dataset')return value?.row_count!==undefined?`读到了${value.row_count}条记录。`:'已查看数据。'
  if(value?.groups)return value.groups.map((g:any)=>`第${g.label+1}组：${g.count}条`).join('；')+'。'
  return '计算完成。'
}
</script>
<template>
  <div class="student-run-output" aria-live="polite">
    <el-empty v-if="!events.length" :image-size="45" description="先写任务，再点“开始运行”"/>
    <div v-for="e in results" :key="e.id" class="tool-evidence"><b>{{e.data.tool==='inspect_dataset'?'数据查看工具':'聚类分析工具'}}</b><span>{{summary(e)}}</span></div>
    <article v-if="answer" class="final-answer"><b>助手的回答</b><p>{{answer}}</p></article>
    <el-table v-if="decision" :data="decision.purchases" size="small" class="agent-purchase-reference"><el-table-column prop="type" label="助手建议买的书"/><el-table-column prop="quantity" label="数量（册）" width="115"/></el-table>
    <p v-if="running" class="student-running"><span class="spinner"/>助手正在处理，请稍等……</p>
    <el-alert v-for="e in errors" :key="e.id" :title="e.data.message||'这次运行没有成功，请重试。'" type="error" :closable="false"/>
    <details v-if="events.length" class="advanced-settings run-details"><summary>查看详细过程</summary><pre v-if="snapshot">{{JSON.stringify(snapshot,null,2)}}</pre><div v-for="e in events.filter(e=>!['done','llm_delta','final'].includes(e.type))" :key="e.id"><b>{{e.type==='tool_call'?'调用工具':e.type==='tool_result'?'工具返回':e.type==='llm_start'?'助手开始思考':e.type==='llm_end'?'助手完成思考':e.type==='run_start'?'我的任务':'运行提示'}}</b><pre>{{JSON.stringify(e.data,null,2)}}</pre></div></details>
  </div>
</template>
