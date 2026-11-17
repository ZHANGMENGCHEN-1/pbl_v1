<script setup lang="ts">
import {computed,ref} from 'vue'
import {submissionBody,submissionSaved} from '../teaching-agent/telemetry'

const props=defineProps<{sessionId:string}>()
const emit=defineEmits<{saved:[{id:string;ratings:Record<string,number>}]}>()
const scoreLabels=['非常不同意','不太同意','一般','比较同意','非常同意']
const questions=[
  {key:'value_importance',text:'对我来说，学好这节课的内容很重要。'},
  {key:'interest',text:'我对这节课的学习内容很感兴趣。'},
  {key:'knowledge_importance',text:'对我来说，弄懂这节课的知识很重要。'},
  {key:'performance_efficacy',text:'我相信我能在这节课上有良好表现。'},
  {key:'difficult_knowledge_efficacy',text:'我相信自己能够理解这节课中最难的知识。'},
  {key:'overall_efficacy',text:'考虑到这节课的难度、老师的指导和自己的能力，我相信自己能够学好这节课的内容。'},
]
const ratings=ref<Record<string,number>>({}),saving=ref(false),error=ref('')
const startedAt=new Date().toISOString(),startedTick=performance.now()
function rate(key:string,event:Event){
  if(saving.value)return
  ratings.value[key]=Number((event.target as HTMLInputElement).value)
  error.value=''
}
const answered=computed(()=>questions.filter(question=>(ratings.value[question.key]??0)>=1).length)
const complete=computed(()=>answered.value===questions.length)
async function save(){
  if(saving.value)return
  if(!complete.value){error.value='请完成全部六道题后再提交。';return}
  saving.value=true;error.value=''
  const request=submissionBody(props.sessionId,'self-report',{ratings:{...ratings.value},started_at:startedAt,response_duration_ms:Math.round(Math.max(0,performance.now()-startedTick)),response_mode:'slider-5point-v1',questionnaire_version:'learning-self-report-v1'})
  try{
    const response=await fetch('/api/projects/teaching-agent/self-report',{method:'POST',headers:{'Content-Type':'application/json','X-Session-ID':props.sessionId},body:JSON.stringify(request.body)})
    const data=await response.json().catch(()=>null)
    if(!response.ok)throw new Error(typeof data?.detail==='string'?data.detail:'自我报告保存失败，请重试。')
    submissionSaved(request.key);emit('saved',data)
  }catch(e){error.value=e instanceof Error?e.message:'连接失败，请重试。'}finally{saving.value=false}
}
</script>

<template>
  <el-dialog :model-value="true" title="课前自我报告" width="min(720px, 94vw)" :show-close="false" :close-on-click-modal="false" :close-on-press-escape="false" align-center class="self-report-dialog">
    <form class="self-report" @submit.prevent="save">
      <p class="self-report-intro">以下描述没有对错。请根据你现在的真实想法拖动滑块作答：最左端表示“非常不同意”，最右端表示“非常同意”。</p>
      <fieldset v-for="(question,index) in questions" :key="question.key" :disabled="saving">
        <legend><span>{{index+1}}</span>{{question.text}}</legend>
        <input class="rating-slider" type="range" min="1" max="5" step="1" :value="ratings[question.key]??3" :aria-label="question.text" :aria-valuetext="ratings[question.key]?`${ratings[question.key]}分，${scoreLabels[ratings[question.key]!-1]}`:'尚未作答'" :style="{'--rating-fill':`${((ratings[question.key]??1)-1)*25}%`}" @input="rate(question.key,$event)" @change="rate(question.key,$event)">
        <div class="scale-guide"><span>非常不同意</span><strong>{{ratings[question.key]?scoreLabels[ratings[question.key]!-1]:'拖动选择'}}</strong><span>非常同意</span></div>
      </fieldset>
      <p v-if="error" class="self-report-error" role="alert">{{error}}</p>
      <div class="self-report-actions"><span>{{answered}} / {{questions.length}} 已作答</span><button type="submit" :disabled="saving||!complete">{{saving?'正在保存…':'提交并继续'}}</button></div>
    </form>
  </el-dialog>
</template>

<style scoped>
.self-report{color:#49345f;font-size:15px;line-height:1.7}.self-report-intro{margin:0 0 18px;padding:12px 14px;border-radius:12px;background:#f7f2fc;color:#67418b;font-size:14px}.self-report fieldset{margin:0 0 18px;border:0;padding:0;min-width:0}.self-report legend{display:flex;gap:9px;align-items:flex-start;font-size:15px;font-weight:600;line-height:1.6}.self-report legend span{display:grid;place-items:center;flex:0 0 24px;height:24px;border-radius:50%;background:#eee4fa;color:#67418b;font-size:13px}.rating-slider{appearance:none;display:block;box-sizing:border-box;width:100%;height:8px;border:0;border-radius:999px;margin:16px 0 8px;padding:0;background:linear-gradient(to right,#8052b1 0%,#8052b1 var(--rating-fill),#e5dbee var(--rating-fill),#e5dbee 100%);cursor:pointer;touch-action:pan-y}.rating-slider::-webkit-slider-thumb{appearance:none;width:24px;height:24px;border-radius:50%;background:#8052b1;border:3px solid white;box-shadow:0 1px 7px #67418b50}.rating-slider::-moz-range-thumb{width:19px;height:19px;border-radius:50%;background:#8052b1;border:3px solid white;box-shadow:0 1px 7px #67418b50}.rating-slider:focus-visible{outline:3px solid #b69ad9;outline-offset:7px}.scale-guide{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#73528d;font-size:12px;line-height:1.5}.scale-guide strong{color:#67418b;font-size:13px}.self-report fieldset:disabled{opacity:.6}.self-report-error{color:#a14635;margin:0 0 12px}.self-report-actions{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-top:22px;padding-top:16px;border-top:1px solid #ece5f3;color:#8d749d;font-size:13px}.self-report-actions button{border:0;border-radius:10px;background:#8052b1;color:white;padding:10px 18px;font:inherit;font-weight:600;cursor:pointer}.self-report-actions button:disabled{opacity:.5;cursor:default}:global(.self-report-dialog .el-dialog__body){max-height:72vh;overflow:auto;padding-top:8px}@media(max-width:450px){.self-report{font-size:14px}.self-report legend{font-size:14px}.scale-guide{font-size:11px}.self-report-actions{align-items:flex-end;flex-direction:column}.self-report-actions button{width:100%}}
</style>
