<script setup lang="ts">
import {computed} from 'vue'
import type {Analysis} from './exploration'
import {axisScale} from './axisScale'
const props=defineProps<{result:Analysis}>()
const colors=['#9972c5','#279c93']
const scales=computed(()=>[0,1].map(axis=>axisScale(props.result.points.map(p=>p.coordinates[axis]!))))
function pos(value:number,axis:number){const {min,max}=scales.value[axis]!;const ratio=(value-min)/(max-min);return axis===0?80+ratio*580:350-ratio*300}
const fmt=(n:number)=>Number(n.toFixed(3)).toLocaleString('zh-CN',{maximumFractionDigits:3})
</script>
<template>
 <section class="scatter-view" aria-label="分组散点图">
  <svg viewBox="0 0 720 440" role="img" :aria-label="`${result.features[0]!.name}与${result.features[1]!.name}的分组散点图`">
   <g v-for="value in scales[0]!.ticks" :key="`x-${value}`" class="chart-grid"><line :x1="pos(value,0)" y1="50" :x2="pos(value,0)" y2="350"/><text :x="pos(value,0)" y="376" text-anchor="middle">{{fmt(value)}}</text></g>
   <g v-for="value in scales[1]!.ticks" :key="`y-${value}`" class="chart-grid"><line x1="80" :y1="pos(value,1)" x2="660" :y2="pos(value,1)"/><text x="70" :y="pos(value,1)+4" text-anchor="end">{{fmt(value)}}</text></g>
   <line :x1="pos(0,0)" y1="50" :x2="pos(0,0)" y2="350" stroke="#a895bb"/><line x1="80" :y1="pos(0,1)" x2="660" :y2="pos(0,1)" stroke="#a895bb"/>
   <text x="370" y="420" text-anchor="middle" class="axis-name">{{result.features[0]!.name}}</text><text transform="translate(19 200) rotate(-90)" text-anchor="middle" class="axis-name">{{result.features[1]!.name}}</text>
   <circle v-for="p in result.points" :key="p.row" :cx="pos(p.coordinates[0]!,0)" :cy="pos(p.coordinates[1]!,1)" r="4.5" :fill="colors[p.group]" fill-opacity=".7" stroke="white" stroke-width=".5"><title>{{result.features[0]!.name}} {{fmt(p.coordinates[0]!)}}；{{result.features[1]!.name}} {{fmt(p.coordinates[1]!)}}；第{{p.group+1}}组</title></circle>
   <g v-for="g in result.groups" :key="g.group"><path :d="`M${pos(g.center[0]!,0)} ${pos(g.center[1]!,1)-9} l9 9 -9 9 -9 -9z`" :fill="colors[g.group]" stroke="#473755" stroke-width="2"><title>第{{g.group+1}}组中心（{{g.center.map(fmt).join('，')}}）</title></path></g>
  </svg>
  <div class="group-legend"><p v-for="g in result.groups" :key="g.group"><span :style="{background:colors[g.group]}"/>第{{g.group+1}}组：{{g.count}}条；中心（{{g.center.map(fmt).join('，')}}）</p></div>
  <p class="chart-help">一个圆点代表一条参与计算的记录，菱形代表这一组的中心。</p>
 </section>
</template>
<style scoped>
svg{width:100%;display:block;overflow:visible;font-family:inherit}.chart-grid line{stroke:#eee8f4}.chart-grid text{font-size:12px;fill:#8a779a}.axis-name{font-size:16px;fill:#665174}.data-point{cursor:pointer}.group-legend p{margin:8px 0;font-size:15px;line-height:1.8}.group-legend span{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:8px}.chart-help{font-size:14px;color:#8a779a;line-height:1.8}.record-select{font-size:14px;display:block;margin-top:18px}select{display:block;width:100%;box-sizing:border-box;margin-top:6px;padding:9px;border:1px solid #ded1e9;border-radius:8px;background:white;color:#665174;font-size:14px}.original-record{display:grid;grid-template-columns:minmax(60px,1fr) minmax(80px,2fr);gap:8px;font-size:14px;line-height:1.8}.original-record dd{margin:0;overflow-wrap:anywhere}
</style>
