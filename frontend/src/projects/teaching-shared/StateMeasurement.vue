<script setup lang="ts">
import {computed,ref} from 'vue'
import {submissionBody,submissionSaved} from '../teaching-agent/telemetry'
import type {ActivityId} from '../teaching-agent/activities'

const props=withDefaults(defineProps<{sessionId:string;activityId:ActivityId;submissionId:string;withRobot?:boolean}>(),{withRobot:true})
const emit=defineEmits<{saved:[{id:string;ratings:Record<string,number>}]}>()
const questions=[
  {key:'difficulty',text:'刚才，我觉得学习内容有点难理解。'},
  {key:'boredom',text:'刚才，我觉得这项学习活动很无聊。'},
  {key:'frustration',text:'刚才，遇到困难让我感到沮丧。'},
  {key:'self_efficacy',text:'我觉得自己能够完成接下来的学习任务。'},
]
const ratings=ref<Record<string,number>>({}),saving=ref(false),error=ref('')
const scoreLabels=['','非常不同意','不同意','既不同意也不反对','同意','非常同意']
function rate(key:string,event:Event){
  if(saving.value)return
  ratings.value[key]=Number((event.target as HTMLInputElement).value)
  error.value=''
}
const complete=computed(()=>questions.every(q=>(ratings.value[q.key]??0)>=1&&(ratings.value[q.key]??0)<=5))
const activityNumber=computed(()=>({group_books:1,explain_algorithm:2,explore_2d:3}[props.activityId]))
async function save(){
  if(saving.value)return
  if(!complete.value){error.value='请为四个问题分别选择一个分数。';return}
  saving.value=true;error.value=''
  const request=submissionBody(props.sessionId,'state-measurements',{submission_id:props.submissionId,ratings:{...ratings.value}})
  try{
    const response=await fetch('/api/projects/teaching-agent/state-measurements',{method:'POST',headers:{'Content-Type':'application/json','X-Session-ID':props.sessionId},body:JSON.stringify(request.body)})
    const data=await response.json().catch(()=>null)
    if(!response.ok)throw new Error(typeof data?.detail==='string'?data.detail:'评分保存失败，请重试。')
    submissionSaved(request.key);emit('saved',data)
  }catch(e){error.value=e instanceof Error?e.message:'连接失败，请重试。'}finally{saving.value=false}
}
</script>

<template>
  <el-dialog :model-value="true" :title="`活动${activityNumber}：你的感受怎么样？`" width="min(680px, 94vw)" :show-close="false" :close-on-click-modal="false" :close-on-press-escape="false" align-center>
    <form class="state-measurement" @submit.prevent="save">
      <fieldset v-for="(question,index) in questions" :key="question.key" :disabled="saving">
        <legend>{{index+1}}. {{question.text}}</legend>
        <input class="rating-slider" type="range" min="1" max="5" step="1" :value="ratings[question.key]??3" :aria-label="question.text" :aria-valuetext="ratings[question.key]?scoreLabels[ratings[question.key]!]:'尚未作答，拖动或点击滑块选择'" :style="{'--rating-fill':`${((ratings[question.key]??1)-1)*25}%`}" @input="rate(question.key,$event)" @change="rate(question.key,$event)" @pointerup="rate(question.key,$event)" @keydown.enter.prevent="rate(question.key,$event)" @keydown.space.prevent="rate(question.key,$event)">
        <div class="slider-ticks" aria-hidden="true"><span v-for="point in 5" :key="point">{{point}}</span></div>
        <div class="slider-anchors"><span>非常不同意</span><span>非常同意</span></div>
      </fieldset>
      <p v-if="error" class="measurement-error" role="alert">{{error}}</p>
      <div class="measurement-actions"><button type="submit" :disabled="saving">{{saving?'正在保存…':withRobot?'保存并与小知交流':'保存学习感受'}}</button></div>
    </form>
  </el-dialog>
</template>

<style scoped>
.state-measurement{color:#49345f;font-size:15px;line-height:1.7}.state-measurement fieldset{margin:24px 0;border:0;padding:0;min-width:0}.state-measurement legend{font-size:15px;font-weight:600;margin-bottom:8px}.rating-slider{appearance:none;display:block;box-sizing:border-box;width:100%;height:8px;border:0;border-radius:999px;margin:14px 0 12px;padding:0;background:linear-gradient(to right,#8052b1 0%,#8052b1 var(--rating-fill),#e5dbee var(--rating-fill),#e5dbee 100%);cursor:pointer;touch-action:pan-y}.rating-slider::-webkit-slider-thumb{appearance:none;width:23px;height:23px;border-radius:50%;background:#8052b1;border:3px solid white;box-shadow:0 1px 7px #67418b50}.rating-slider::-moz-range-thumb{width:18px;height:18px;border-radius:50%;background:#8052b1;border:3px solid white;box-shadow:0 1px 7px #67418b50}.rating-slider:focus-visible{outline:3px solid #b69ad9;outline-offset:7px}.slider-ticks,.slider-anchors{display:flex;justify-content:space-between;font-size:12px;color:#8a7c96}.slider-ticks{padding:0 7px;margin-bottom:4px}.slider-anchors{font-size:13px;color:#73528d}.state-measurement fieldset:disabled{opacity:.6}.measurement-actions{display:flex;justify-content:flex-end;margin-top:20px}.measurement-actions button{background:#8052b1;color:white;border:0;border-radius:10px;padding:12px 18px;font:inherit;cursor:pointer}.measurement-actions button:disabled{opacity:.5;cursor:default}.measurement-error{color:#a14635}
</style>
