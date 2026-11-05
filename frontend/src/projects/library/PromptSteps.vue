<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Project } from './types'

const props=defineProps<{scaffold:NonNullable<Project['prompt_scaffold']>; steps:string[]; disabled:boolean}>()
const emit=defineEmits<{change:[steps:string[],prompt:string]}>()
const dragged=ref<number>()
const order=computed(()=>props.steps.length===7?props.steps:props.scaffold.initial_order)
const block=(id:string)=>props.scaffold.blocks.find(b=>b.id===id)!
function move(from:number,to:number){
  if(props.disabled||to<0||to>=7)return
  const next=[...order.value];const [item]=next.splice(from,1);next.splice(to,0,item!)
  const prompt=props.scaffold.intro+'\n\n我的计算步骤：\n'+next.map((id,i)=>`${i+1}. ${block(id).label}。${block(id).detail||''}`).join('\n')+'\n\n'+props.scaffold.ending
  emit('change',next,prompt)
}
function drop(index:number){if(dragged.value!==undefined)move(dragged.value,index);dragged.value=undefined}
</script>

<template>
  <section class="prompt-steps-card">
    <h2>给计算助手排好步骤</h2>
    <p>像搭积木一样，拖动七个模块，或点击上移、下移。你的排列会自动填入系统指令。</p>
    <div class="prompt-role"><b>角色与任务</b><p>{{scaffold.intro}}</p></div>
    <ol class="prompt-blocks" aria-label="计算步骤排序">
      <li v-for="(id,index) in order" :key="id" :data-step="id" :draggable="!disabled" @dragstart="dragged=index" @dragend="dragged=undefined" @dragover.prevent @drop.prevent="drop(index)">
        <span class="block-number">{{index+1}}</span><span class="block-label">{{block(id).label}}</span>
        <div class="block-actions"><el-button text :disabled="disabled||index===0" :aria-label="'上移'+block(id).label" @click="move(index,index-1)">↑</el-button><el-button text :disabled="disabled||index===6" :aria-label="'下移'+block(id).label" @click="move(index,index+1)">↓</el-button></div>
      </li>
    </ol>
    <p class="iteration-hint">想一想：“进行迭代计算”需要重复哪些步骤？什么时候可以停止？</p>
    <p class="prompt-rule">角色、任务和回答要求已经写好，你只需要排列步骤，再点击“保存配置”。</p>
  </section>
</template>

<style scoped>
.prompt-steps-card{margin:24px;padding:26px;border:1px solid #ded4f2;border-top:4px solid #8b6bc8;border-radius:16px;background:white;box-shadow:0 5px 22px #7453aa0b;color:#475269;font-size:16px}.prompt-steps-card h2{font-size:20px;color:#7453aa;margin:0 0 16px}.prompt-steps-card p{line-height:1.8}.prompt-role{padding:16px 20px;background:#f7f4fc;border-radius:10px}.prompt-role p{margin:6px 0 0}.prompt-blocks{list-style:none;padding:0;display:flex;flex-direction:column;gap:12px;margin:22px 0}.prompt-blocks li{display:flex;align-items:center;gap:14px;padding:10px 14px;border:1px solid #e3d8f4;border-radius:10px;background:#fcfaff;cursor:grab;min-height:52px}.block-number{width:28px;height:28px;border-radius:8px;display:grid;place-items:center;background:#7c5ce0;color:white;flex-shrink:0}.block-label{flex:1;font-size:16px;line-height:1.6}.block-actions{display:flex;flex-shrink:0}.block-actions .el-button{font-size:20px;margin:0;padding:5px 10px}.iteration-hint{padding:12px 16px;border-left:3px solid #9f86cd;background:#faf8fe}.prompt-rule{color:#687287;font-size:15px}
</style>
