<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Project } from './types'

const props=defineProps<{scaffold:NonNullable<Project['prompt_scaffold']>; steps:string[]; disabled:boolean}>()
const emit=defineEmits<{change:[steps:string[],prompt:string]}>()
const dragged=ref<number>()
const insertion=ref<number>(), announcement=ref('')
const order=computed(()=>props.steps.length===7?props.steps:props.scaffold.initial_order)
const block=(id:string)=>props.scaffold.blocks.find(b=>b.id===id)!
function move(from:number,to:number){
  if(props.disabled||to<0||to>=7||from===to)return
  const next=[...order.value];const [item]=next.splice(from,1);next.splice(to,0,item!)
  const prompt=props.scaffold.intro+'\n\n我的计算步骤：\n'+next.map((id,i)=>`${i+1}. ${block(id).label}。${block(id).detail||''}`).join('\n')+'\n\n'+props.scaffold.ending
  emit('change',next,prompt)
  announcement.value=`已移到第${to+1}步`
}
function endDrag(){dragged.value=undefined;insertion.value=undefined}
function startDrag(event:DragEvent,index:number){
  if(props.disabled||(event.target as HTMLElement).closest('button')){event.preventDefault();return}
  dragged.value=index
  if(event.dataTransfer){event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain',order.value[index]!)}
}
function over(event:DragEvent,index:number){
  if(props.disabled||dragged.value===undefined)return
  event.preventDefault()
  if(event.dataTransfer)event.dataTransfer.dropEffect='move'
  const rect=(event.currentTarget as HTMLElement).getBoundingClientRect()
  insertion.value=index+(event.clientY>=rect.top+rect.height/2?1:0)
}
function drop(event:DragEvent,index:number){
  if(dragged.value===undefined)return
  event.preventDefault()
  const from=dragged.value,slot=insertion.value??index
  move(from,slot-(from<slot?1:0));endDrag()
}
</script>

<template>
  <section class="prompt-steps-card">
    <h2>给计算助手排好步骤</h2>
    <p>拖动卡片，把先做的放上面，后做的放下面。也可以点右边的箭头。</p>
    <ol class="prompt-blocks" aria-label="计算步骤排序">
      <li v-for="(id,index) in order" :key="id" :data-step="id" :class="{moving:dragged===index,'drop-before':insertion===index,'drop-after':index===order.length-1&&insertion===order.length,'drag-disabled':disabled}" :draggable="!disabled" @dragstart="startDrag($event,index)" @dragend="endDrag" @dragover="over($event,index)" @drop="drop($event,index)">
        <span class="drag-handle" title="按住拖动" aria-hidden="true">⠿</span><span class="block-number">{{index+1}}</span><span class="block-label">{{block(id).label}}</span>
        <div class="block-actions"><el-button text :disabled="disabled||index===0" :aria-label="'上移'+block(id).label" @click="move(index,index-1)">↑</el-button><el-button text :disabled="disabled||index===6" :aria-label="'下移'+block(id).label" @click="move(index,index+1)">↓</el-button></div>
      </li>
    </ol>
    <span class="drag-announcement" aria-live="polite">{{announcement}}</span>
    <p class="iteration-hint">想一想：哪些步骤要重复？什么时候可以停下来？</p>
    <p class="prompt-rule">排好后，点右下角“提交结果”。</p>
  </section>
</template>

<style scoped>
.prompt-steps-card{margin:24px;padding:26px;border:1px solid #ded4f2;border-top:4px solid #8b6bc8;border-radius:16px;background:white;box-shadow:0 5px 22px #7453aa0b;color:#475269;font-size:16px}.prompt-steps-card h2{font-size:20px;color:#7453aa;margin:0 0 16px}.prompt-steps-card p{line-height:1.8}.prompt-role{padding:16px 20px;background:#f7f4fc;border-radius:10px}.prompt-role p{margin:6px 0 0}.prompt-blocks{list-style:none;padding:0;display:flex;flex-direction:column;gap:12px;margin:22px 0}.prompt-blocks li{display:flex;align-items:center;gap:14px;padding:10px 14px;border:1px solid #e3d8f4;border-radius:10px;background:#fcfaff;cursor:grab;min-height:52px}.block-number{width:28px;height:28px;border-radius:8px;display:grid;place-items:center;background:#7c5ce0;color:white;flex-shrink:0}.block-label{flex:1;font-size:16px;line-height:1.6}.block-actions{display:flex;flex-shrink:0}.block-actions .el-button{font-size:20px;margin:0;padding:5px 10px}.iteration-hint{padding:12px 16px;border-left:3px solid #9f86cd;background:#faf8fe}.prompt-rule{color:#687287;font-size:15px}
</style>

<style scoped>
.prompt-blocks li{position:relative;user-select:none;transition:background .15s,border-color .15s,box-shadow .15s}.prompt-blocks li:hover{border-color:#aa8cdb;box-shadow:0 3px 10px #7855cb12}.prompt-blocks li.moving{opacity:.4;border-style:dashed;cursor:grabbing}.prompt-blocks li.drop-before::before,.prompt-blocks li.drop-after::after{content:'';position:absolute;left:0;right:0;height:4px;background:#8055cc;border-radius:3px;pointer-events:none}.prompt-blocks li.drop-before::before{top:-9px}.prompt-blocks li.drop-after::after{bottom:-9px}.drag-handle{color:#937bb6;font-size:28px;line-height:1;cursor:grab;flex-shrink:0}.prompt-blocks li.drag-disabled,.drag-disabled .drag-handle{cursor:not-allowed}.drag-announcement{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
</style>
