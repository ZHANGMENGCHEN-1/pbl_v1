<script setup lang="ts">
import { computed } from 'vue'
import type { LibraryConfig, LibraryRun } from './types'
const props=defineProps<{index:number;form:Record<string,any>;config:LibraryConfig;runs:LibraryRun[];runId:string;busy:boolean;dirty:boolean;submitted:boolean}>()
const emit=defineEmits<{close:[];save:[];review:[id:string]}>()
const titles=['写下你的分组结果','检查助手的步骤','写下两组数量','写下你的买书方案']
const total=computed(()=>(props.form.purchases||[]).reduce((n:number,p:any)=>n+Number(p.quantity||0),0))
const countTotal=computed(()=>(props.form.group_counts||[]).reduce((n:number,g:any)=>n+Number(g.count||0),0))
const textLength=(value:unknown)=>Array.from(String(value||'').replace(/\s/g,'')).length
const valid=computed(()=>{
  const f=props.form
  if(props.index===0)return f.student_result?.counts?.length===2&&f.student_result.counts.every((n:any)=>Number.isInteger(n)&&n>=0)&&f.student_result.counts.reduce((a:number,b:number)=>a+b,0)===5&&f.student_result.centers?.length===2&&f.student_result.centers.every((n:any)=>typeof n==='number'&&Number.isFinite(n))
  if(props.index===1)return true // The backend checks the student's actual step order.
  if(!props.runId)return false
  if(props.index===2)return f.group_counts?.length===2&&f.group_counts.every((g:any)=>Number.isInteger(g.count)&&g.count>=0)&&countTotal.value===150
  return f.purchases?.length>0&&f.purchases.every((p:any)=>String(p.type||'').trim()&&Number.isInteger(p.quantity)&&p.quantity>=0)&&total.value===1000&&textLength(f.rationale)>=10&&textLength(f.reflection)>=10
})
defineExpose({valid})
</script>
<template>
  <aside class="library-delivery-panel" aria-label="填写结果">
    <header class="panel-heading"><strong>{{titles[index]}}</strong><button class="sidebar-toggle" aria-label="收起填写区" :disabled="busy" @click="emit('close')">×</button></header>
    <div class="delivery-panel-scroll">
      <p class="delivery-note">{{index>=2?'对照左边的结果，自己填写。':index===0?'对照左边的实验，自己填写。':'这些步骤会告诉助手先做什么、后做什么。'}}</p>
      <el-alert v-if="dirty" title="提交时会保存你的修改；如果改过分析设置，请先重新运行助手。" type="warning" :closable="false"/>
      <el-tag v-if="submitted" type="success">已提交，可以修改</el-tag>
      <section class="library-delivery">
        <el-form label-position="top" :disabled="busy">
          <template v-if="index===0&&form.student_result">
            <div v-for="i in 2" :key="i" class="student-result-row"><b>第{{i}}组</b>
              <el-form-item label="有几本书？"><el-input-number v-model="form.student_result.counts[i-1]" :min="0" :max="5" :precision="0" :aria-label="'第'+i+'组图书数量'"/></el-form-item>
              <el-form-item label="最后的中心是多少？"><el-input-number v-model="form.student_result.centers[i-1]" :min="0" :max="20" :step=".001" :aria-label="'第'+i+'组最终中心'"/></el-form-item>
            </div>
          </template>
          <pre v-else-if="index===1" class="prompt-delivery-preview">{{config.system_prompt}}</pre>
          <template v-else>
            <details v-if="runs.length>1" class="advanced-settings"><summary>换一次运行的结果</summary><el-select :model-value="runId" placeholder="选择一次运行" @change="emit('review',$event)"><el-option v-for="r in runs" :key="r.id" :value="r.id" :label="new Date(r.created).toLocaleString('zh-CN')"/></el-select></details>
            <template v-if="index===2">
              <div v-for="i in 2" :key="i" class="student-result-row"><b>第{{i}}组</b><el-form-item label="有多少条记录？"><el-input-number v-model="form.group_counts[i-1].count" :min="0" :max="150" :precision="0" :aria-label="'第'+i+'组记录数量'"/></el-form-item></div>
              <p class="purchase-total" :class="{valid:countTotal===150}">合计 {{countTotal}} / 150 条</p>
            </template>
            <template v-else>
              <div v-for="(p,i) in form.purchases||[]" :key="i" class="purchase-row"><b>第{{p.group+1}}组</b><el-input v-model="p.type" placeholder="买哪一类书？" :aria-label="'第'+(Number(i)+1)+'组买书类型'"/><el-input-number v-model="p.quantity" :min="0" :max="1000" :precision="0" controls-position="right" :aria-label="'第'+(Number(i)+1)+'组采购数量'"/></div>
              <p class="purchase-total" :class="{valid:total===1000}">合计 {{total}} / 1000 册</p>
              <el-form-item label="为什么这样买？"><el-input v-model="form.rationale" type="textarea" :rows="3" placeholder="我根据……来分配买书数量。"/><span class="word-count" :class="{ready:textLength(form.rationale)>=10}">{{textLength(form.rationale)}} / 至少10个字</span></el-form-item>
              <el-form-item label="做完后，你有什么发现？"><el-input v-model="form.reflection" type="textarea" :rows="3" placeholder="我发现……，下次我会……"/><span class="word-count" :class="{ready:textLength(form.reflection)>=10}">{{textLength(form.reflection)}} / 至少10个字</span></el-form-item>
            </template>
          </template>
        </el-form>
      </section>
    </div>
    <footer class="delivery-panel-footer"><el-button :disabled="busy" @click="emit('close')">先收起</el-button><el-button :disabled="busy" @click="emit('save')">保存草稿</el-button></footer>
  </aside>
</template>
