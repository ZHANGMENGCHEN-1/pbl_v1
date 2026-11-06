<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { LearningPlan, PlanCardInput } from './types'
const props=defineProps<{baseline?:LearningPlan|null;phase:'before'|'during';busy:boolean;canClose:boolean}>()
const emit=defineEmits<{submit:[value:PlanCardInput];close:[]}>()
const strategy=ref(''),check=ref(''),reason=ref('')
const strategies=[{id:'read_first',text:'先看清任务和材料，再开始操作。'},{id:'try_first',text:'先试一次，再根据结果决定下一步。'},{id:'reuse_first',text:'先参考上次的做法，再决定怎么做。'}]
const checks=[{id:'requirements',text:'对照任务要求，检查有没有完成。'},{id:'evidence',text:'回看数据和操作过程，检查结果有没有依据。'},{id:'comparison',text:'换一种做法试试，比较结果是否一致。'}]
const reasons=[{id:'unmet_expectation',text:'上次这样做，没达到我的预期。'},{id:'found_problem',text:'上次发现了问题，这次想换个办法。'},{id:'different_task',text:'这次的任务不同，需要换个办法。'}]
const changed=computed(()=>!!props.baseline&&(strategy.value!==props.baseline.strategy||check.value!==props.baseline.check))
const valid=computed(()=>!!strategy.value&&!!check.value&&(!changed.value||!!reason.value))
watch(()=>props.baseline,p=>{strategy.value=p?.strategy||'';check.value=p?.check||'';reason.value=''},{immediate:true})
watch([strategy,check],()=>{reason.value=''})
function submit(){if(valid.value&&!props.busy)emit('submit',{strategy:strategy.value,check:check.value,reason:changed.value?reason.value:null,phase:props.phase,base_version:props.baseline?.version||0})}
</script>
<template>
  <form class="plan-card" @submit.prevent="submit">
    <section v-if="baseline" class="plan-previous"><b>上次的计划</b><p>{{baseline.strategy_label}}</p><p>{{baseline.check_label}}</p><span>这次还按这个计划做吗？可以直接沿用，也可以修改。</span></section>
    <fieldset :disabled="busy"><legend>① 开始任务前，我准备怎么做？</legend><label v-for="o in strategies" :key="o.id" :class="{chosen:strategy===o.id}"><input v-model="strategy" type="radio" name="plan-strategy" :value="o.id"/><span>{{o.text}}</span></label></fieldset>
    <fieldset :disabled="busy"><legend>② 得到结果后，我准备怎么检查？</legend><label v-for="o in checks" :key="o.id" :class="{chosen:check===o.id}"><input v-model="check" type="radio" name="plan-check" :value="o.id"/><span>{{o.text}}</span></label></fieldset>
    <fieldset v-if="changed" class="plan-reason" :disabled="busy"><legend>③ 这次为什么修改计划？</legend><label v-for="o in reasons" :key="o.id" :class="{chosen:reason===o.id}"><input v-model="reason" type="radio" name="plan-reason" :value="o.id"/><span>{{o.text}}</span></label></fieldset>
    <div class="plan-card-actions"><el-button v-if="canClose" :disabled="busy" @click="emit('close')">关闭</el-button><el-button type="primary" native-type="submit" :loading="busy" :disabled="!valid">{{phase==='during'?'保存计划':baseline&&!changed?'沿用计划，开始实验':'确认计划，开始实验'}}</el-button></div>
  </form>
</template>
<style scoped>
.plan-card{color:#475269;font-size:16px}.plan-previous{background:#f6f2fc;border:1px solid #e2d7f2;padding:14px 18px;border-radius:10px;margin:18px 0}.plan-previous p{margin:8px 0;line-height:1.65}.plan-previous span{font-size:14px;color:#746884;line-height:1.7}.plan-card fieldset{border:0;padding:0;margin:22px 0}.plan-card legend{font-size:17px;font-weight:700;margin-bottom:12px}.plan-card label{display:flex;align-items:center;gap:12px;padding:12px 16px;margin:8px 0;border:1px solid #e2e4ec;border-radius:9px;cursor:pointer;line-height:1.65}.plan-card label.chosen{background:#f5f1fc;border-color:#ab91d4;color:#66468f}.plan-card input{accent-color:#7954be;width:17px;height:17px;flex-shrink:0}.plan-card-actions{display:flex;gap:12px;justify-content:flex-end;margin-top:22px}.plan-reason{border-top:1px solid #eee!important;padding-top:16px!important}
</style>
