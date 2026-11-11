<script setup lang="ts">
import {computed,ref} from 'vue'
import type {ActivityDraft} from './learningState'
import {algorithmSteps,shuffledSteps,checkStepOrder} from './sorting'
const props=defineProps<{draft:ActivityDraft;disabled?:boolean}>()
const emit=defineEmits<{submit:[string[]]}>()
if(props.draft.stepOrder.length!==4||!props.draft.stepOrder.every(id=>algorithmSteps.some(s=>s.id===id)))props.draft.stepOrder=shuffledSteps()
const dragged=ref<number|null>(null),over=ref<number|null>(null)
const submittedCorrect=ref<boolean|null>(null)
const steps=computed(()=>props.draft.stepOrder.map(id=>algorithmSteps.find(s=>s.id===id)!))
function move(from:number,to:number){if(props.disabled||from===to||to<0||to>=4)return;const order=[...props.draft.stepOrder];order.splice(to,0,order.splice(from,1)[0]!);props.draft.stepOrder=order;submittedCorrect.value=null}
function submit(){submittedCorrect.value=checkStepOrder(props.draft.stepOrder).correct;emit('submit',[...props.draft.stepOrder])}
function start(event:DragEvent,index:number){if(props.disabled)return;dragged.value=index;event.dataTransfer?.setData('text/plain',String(index));if(event.dataTransfer)event.dataTransfer.effectAllowed='move'}
function drop(index:number){if(dragged.value!==null)move(dragged.value,index);dragged.value=null;over.value=null}
</script>
<template>
 <section class="algorithm-task" aria-label="算法步骤排序任务">
  <h2>活动2：总结K均值算法流程</h2>
  <p>拖动下面四张卡片，按先后顺序排一排。</p>
  <ol class="step-cards">
   <li v-for="(step,index) in steps" :key="step.id" :data-step-id="step.id" :draggable="!disabled" :class="{'drag-over':over===index,'dragging':dragged===index}" @dragstart="start($event,index)" @dragover.prevent="over=index" @drop.prevent="drop(index)" @dragend="dragged=null;over=null">
    <span class="step-position">第{{index+1}}步</span><span class="drag-handle" aria-hidden="true">⠿</span><span class="step-text">{{step.text}}</span>
    <div class="move-buttons"><button :disabled="disabled||index===0" :aria-label="`上移${step.text}`" @click="move(index,index-1)">↑</button><button :disabled="disabled||index===3" :aria-label="`下移${step.text}`" @click="move(index,index+1)">↓</button></div>
   </li>
  </ol>
  <div class="submission-row"><button class="submit-order" :disabled="disabled" @click="submit">提交排序结果</button><span v-if="submittedCorrect!==null" class="submission-status" :class="{success:submittedCorrect}" role="status">{{submittedCorrect?'提交成功！':'我再想想...'}}</span></div>
 </section>
</template>
<style scoped>
.submission-row{display:flex;align-items:center;gap:16px;flex-wrap:wrap}.submission-status{color:#92769e;font-size:16px}.submission-status.success{color:#319887}
.algorithm-task{padding:22px;background:#fff;border:1px solid #e9e0f2;border-radius:18px;color:#665174;font-size:16px;line-height:1.8}.algorithm-task h2{font-size:18px;line-height:1.8;margin:0 0 18px;font-weight:600}.algorithm-task p{margin:0 0 24px}.step-cards{display:flex;flex-direction:column;gap:18px;list-style:none;margin:0 0 28px;padding:0}.step-cards li{display:flex;align-items:center;gap:12px;min-height:78px;padding:16px 14px;box-sizing:border-box;border:1px solid #e6dcf0;background:#faf7fd;border-radius:12px;cursor:grab}.step-cards li:active{cursor:grabbing}.step-position{font-size:14px;white-space:nowrap;color:#947da8}.drag-handle{color:#b5a0ca;font-size:22px}.step-text{flex:1;min-width:0}.move-buttons{display:flex;flex-direction:column;gap:4px}.move-buttons button{border:0;background:transparent;color:#8d6caa;cursor:pointer;font-size:16px;line-height:1.2;padding:2px 6px}.move-buttons button:disabled{opacity:.25;cursor:default}.step-cards .drag-over{border-color:#9470be;background:#f1e9fa}.step-cards .dragging{opacity:.5}.submit-order{background:#9070c1;color:white;border:0;border-radius:10px;padding:11px 18px;font-size:16px;cursor:pointer}.submit-order:disabled{opacity:.5;cursor:default}button:focus-visible{outline:3px solid #cab6e2;outline-offset:3px}@media(max-width:520px){.algorithm-task{padding:18px}.step-cards li{gap:8px;padding:14px 10px}}
</style>
