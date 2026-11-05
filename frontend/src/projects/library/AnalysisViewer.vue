<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Result } from './types'
const props = defineProps<{ result: Result }>()
const iteration = ref(0)
watch(() => props.result, value => { iteration.value = value.iterations.length - 1 }, {immediate: true})
const frame = computed(() => props.result.iterations[iteration.value]!)
const palette = ['#7855cb','#27958c','#dc9b3e','#5288d3']
const centers = computed(() => frame.value.centers_after.map(row => row.map((v, i) => v * props.result.scaling_scale[i]! + props.result.scaling_mean[i]!)))
const points = computed(() => props.result.records.map((r, i) => ({ name: r.name, x: Number(r[props.result.experiment.features[0]!]), y: props.result.experiment.features.length > 1 ? Number(r[props.result.experiment.features[1]!]) : 0, label: frame.value.labels[i]! })))
const bounds = computed(() => {
  const xs = [...points.value.map(p => p.x), ...centers.value.map(c => c[0]!)], ys = [...points.value.map(p => p.y), ...centers.value.map(c => c[1] || 0)]
  return {x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys)}
})
function x(v: number) { const b = bounds.value; return 70 + (v - b.x0) / (b.x1 - b.x0 || 1) * 440 }
function y(v: number) { const b = bounds.value; return props.result.experiment.features.length === 1 ? 150 : 235 - (v - b.y0) / (b.y1 - b.y0 || 1) * 190 }
function fmt(v: number) { return Number(v.toFixed(2)) }
</script>
<template>
  <div class="analysis-viewer">
    <div class="analysis-heading"><strong>{{ result.round ? `第 ${result.round} 轮核对` : '聚类结果' }}</strong><el-tag v-if="result.round" :type="result.prediction_match ? 'success' : 'warning'">{{ result.prediction_match ? '预测一致' : '与预测不同，请核查' }}</el-tag><el-tag :type="result.converged ? 'success' : 'info'">{{ result.converged ? '中心已稳定' : '尚未收敛' }}</el-tag></div>
    <el-alert v-if="result.demo" title="教学演示数据，不代表真实学生调查" type="warning" :closable="false"/>
    <p class="analysis-source">{{ result.source }} · 有效样本 {{ result.sample_count }} · 排除 {{ result.excluded.length }} 行</p>
    <div v-if="result.iterations.length > 1" class="iteration-control"><span>迭代回放</span><el-slider v-model="iteration" :min="0" :max="result.iterations.length - 1" :step="1" show-stops/><b>{{ iteration + 1 }} / {{ result.iterations.length }}</b></div>
    <p v-if="result.experiment.features.length>2" class="analysis-source">聚类使用全部 {{result.experiment.features.length}} 个特征，下图只展示前两个特征的二维投影。</p>
    <svg viewBox="0 0 600 290" role="img" :aria-label="result.experiment.features.length === 1 ? '一维分组图' : result.experiment.features.length>2 ? '多维聚类二维投影' : '二维聚类散点图'">
      <line x1="60" y1="245" x2="550" y2="245" stroke="#bdc4d4"/><line x1="60" y1="245" x2="60" y2="30" stroke="#bdc4d4"/>
      <text x="300" y="280" text-anchor="middle">{{ result.fields[0]?.label }}（{{ result.fields[0]?.unit }}）</text><text v-if="result.fields[1]" x="65" y="20">{{ result.fields[1].label }}（{{ result.fields[1].unit }}）</text>
      <text :x="70" y="262">{{ fmt(bounds.x0) }}</text><text x="510" y="262" text-anchor="end">{{ fmt(bounds.x1) }}</text>
      <template v-if="result.fields[1]"><text x="50" y="238" text-anchor="end">{{ fmt(bounds.y0) }}</text><text x="50" y="48" text-anchor="end">{{ fmt(bounds.y1) }}</text></template>
      <circle v-for="(p,i) in points" :key="i" :cx="x(p.x)" :cy="y(p.y)" r="7" :fill="palette[p.label]" stroke="white" stroke-width="2"><title>{{ p.name }}：{{ p.x }}{{ result.fields[1] ? '，' + p.y : '' }} · 第{{ p.label + 1 }}组</title></circle>
      <text v-for="(c,i) in centers" :key="'c'+i" :x="x(c[0]!)" :y="y(c[1] || 0)+7" text-anchor="middle" class="center-marker" :fill="palette[i]"><title>第{{ i+1 }}组更新后中心：{{ c.map(fmt).join('，') }}</title>×</text>
    </svg>
    <div class="cluster-legend"><span v-for="(c,i) in centers" :key="i"><i :style="{background:palette[i]}"/>第{{ i+1 }}组 · 中心 {{ c.map(fmt).join('，') }}</span><span>× 更新后中心</span></div>
    <el-table v-if="result.round" :data="result.records.map((r,i)=>({...r, distances:frame.distances[i], group:frame.labels[i]!+1}))" size="small"><el-table-column prop="name" label="书名" min-width="140"/><el-table-column v-for="i in 2" :key="i" :label="'距中心'+i" min-width="95"><template #default="{row}">{{ fmt(row.distances[i-1]) }}</template></el-table-column><el-table-column prop="group" label="分组" width="70"/></el-table>
    <el-table v-else :data="result.groups" size="small"><el-table-column label="分组" width="80"><template #default="{row}">第{{ row.label+1 }}组</template></el-table-column><el-table-column prop="count" label="数量"/><el-table-column label="占比"><template #default="{row}">{{ (row.proportion*100).toFixed(1) }}%</template></el-table-column><el-table-column label="原始量表中心" min-width="130"><template #default="{row}">{{ row.center.map(fmt).join('，') }}</template></el-table-column></el-table>
    <p v-for="warning in frame.warnings" :key="warning" class="analysis-warning">{{ warning }}</p>
  </div>
</template>
