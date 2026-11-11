<script setup lang="ts">
import {computed,ref} from 'vue'
import ScatterPlot from './ScatterPlot.vue'
import {explorationRequest,type Dataset,type DataPreview,type Analysis,type ExplorationSubmission} from './exploration'
import type {ActivityDraft} from './learningState'
const props=defineProps<{sessionId:string;draft:ActivityDraft}>()
const emit=defineEmits<{result:[Analysis];submitted:[ExplorationSubmission];changed:[]}>()
const dataset=ref<Dataset|null>(null),preview=ref<DataPreview|null>(null),result=ref<Analysis|null>(null)
const busy=ref(false),error=ref(''),status=ref(''),fileInput=ref<HTMLInputElement>()
const currentView=ref<'data'|'result'>('data')
props.draft.exploration??={counts:[null,null],description:''}
const answers=computed(()=>props.draft.exploration!)
const previewColumns=computed(()=>props.draft.features.flatMap(id=>{const index=dataset.value?.columns.findIndex(c=>c.id===id)??-1;const column=dataset.value?.columns[index];return column?[{...column,index}]:[]}))
function clearResult(){result.value=null;currentView.value='data';status.value='';props.draft.exploration={counts:[null,null],description:''};emit('changed')}
async function checkSelection(){preview.value=null;if(!dataset.value||props.draft.features.length!==2||new Set(props.draft.features).size!==2||!props.draft.features.every(Boolean))return;preview.value=await explorationRequest<DataPreview>(props.sessionId,'preview',{dataset_id:dataset.value.id,features:props.draft.features})}
async function upload(event:Event){
 const input=event.target as HTMLInputElement,file=input.files?.[0];if(!file)return
 clearResult();dataset.value=null;preview.value=null;props.draft.datasetId=null;props.draft.features=[];error.value=''
 if(!file.name.toLowerCase().endsWith('.xlsx')){error.value='请选择.xlsx格式的Excel文件。';input.value='';return}
 if(file.size>5*1024*1024){error.value='文件超过5MB，请缩小表格后再上传。';input.value='';return}
 busy.value=true
 try{dataset.value=await explorationRequest<Dataset>(props.sessionId,'datasets',undefined,file);props.draft.datasetId=dataset.value.id;props.draft.features=[dataset.value.default_features[0]??'',dataset.value.default_features[1]??''];await checkSelection()}catch(e){error.value=e instanceof Error?e.message:'上传失败，请重新选择文件。'}finally{busy.value=false;input.value=''}
}
async function selectionChanged(){clearResult();error.value='';busy.value=true;try{await checkSelection()}catch(e){error.value=e instanceof Error?e.message:'预览失败，请重试。'}finally{busy.value=false}}
const ready=computed(()=>!!preview.value&&preview.value.sample_count>=2&&props.draft.features.length===2&&new Set(props.draft.features).size===2)
async function run(){if(!dataset.value||busy.value)return;clearResult();busy.value=true;error.value='';try{result.value=await explorationRequest<Analysis>(props.sessionId,'analyses',{dataset_id:dataset.value.id,features:props.draft.features});emit('result',result.value);currentView.value='result'}catch(e){error.value=e instanceof Error?e.message:'计算失败，请检查数据后重试。'}finally{busy.value=false}}
async function submit(){
 if(!result.value||busy.value)return
 const a=answers.value
 if(!a.counts.every(n=>typeof n==='number'&&Number.isInteger(n)&&n>=0)||Number(a.counts[0])+Number(a.counts[1])!==result.value.sample_count){error.value=`请填写两组数量，合计${result.value.sample_count}条。`;return}
 if(!a.description.trim()){error.value='请自己写一句两组有什么特点。';return}
 busy.value=true;error.value='';try{const saved=await explorationRequest<ExplorationSubmission>(props.sessionId,'submissions',{result_id:result.value.id,counts:a.counts,description:a.description});emit('submitted',saved);status.value='提交成功！'}catch(e){error.value=e instanceof Error?e.message:'提交失败，请重试。'}finally{busy.value=false}
}
</script>
<template>
 <section class="excel-task" aria-label="二维聚类任务">
  <h2>活动3：给表格里的记录分组</h2>
  <div class="view-tabs" role="tablist" aria-label="活动3视图"><button id="excel-data-tab" role="tab" :aria-selected="currentView==='data'" aria-controls="excel-data-panel" :disabled="busy" @click="currentView='data'">上传与运行</button><button id="excel-result-tab" role="tab" :aria-selected="currentView==='result'" aria-controls="excel-result-panel" :disabled="busy||!result" @click="currentView='result'">看看分组结果</button></div>
  <div v-show="currentView==='data'" id="excel-data-panel" role="tabpanel" aria-labelledby="excel-data-tab">
  <input ref="fileInput" type="file" accept=".xlsx" :disabled="busy" aria-label="上传Excel文件" class="file-input" @change="upload">
  <button :disabled="busy" @click="fileInput?.click()">{{busy?'正在处理…':dataset?'重新上传表格':'上传Excel'}}</button>
  <template v-if="dataset">
   <div class="dataset-heading"><strong>{{dataset.filename}}</strong><span>工作表：{{dataset.sheet}} · {{dataset.row_count}}条记录</span></div>
   <details class="preview-table" open><summary>看看上传的数据（前{{dataset.preview.length}}条）</summary><div class="table-scroll"><table><thead><tr><th v-for="(column,i) in previewColumns" :key="i">{{column.name}}</th></tr></thead><tbody><tr v-for="row in dataset.preview" :key="row.row"><td v-for="(column,i) in previewColumns" :key="i">{{row.values[column.index]??'（空）'}}</td></tr></tbody></table></div></details>
   <div class="column-selection"><label v-for="(label,i) in ['横轴用哪一列？','纵轴用哪一列？']" :key="label">{{label}}<select v-model="draft.features[i]" :aria-label="label" :disabled="busy" @change="selectionChanged"><option value="" disabled>请选择一列</option><option v-for="column in dataset.columns" :key="column.id" :value="column.id">{{column.name}}（{{column.numeric_count}}条数值）</option></select></label></div>
   <p v-if="dataset.default_features.length<2" class="data-notice">表格中没有找到两列数值。请选择要分析的列，检查数据后再运行。</p>
   <p v-if="new Set(draft.features).size!==draft.features.length" class="data-notice">横轴和纵轴需要选择不同的列。</p>
   <div v-if="preview&&(preview.excluded.length||preview.sample_count<2)" class="data-quality"><details v-if="preview.excluded.length"><summary>哪些记录没有参与？</summary><ul><li v-for="row in preview.excluded" :key="row.row">Excel第{{row.row}}行：{{row.reasons.join('；')}}</li></ul></details><p v-if="preview.sample_count<2" class="data-notice">至少需要2条完整的数值记录，请检查所选两列。</p></div>
   <button class="run-clustering" :disabled="busy||!ready" @click="run">{{busy?'正在处理…':result?'重新运行分组':'运行分组（K=2）'}}</button>
  </template>
  </div>
  <p v-if="error" class="error-message" role="alert">{{error}}</p>
  <div v-if="result" v-show="currentView==='result'" id="excel-result-panel" role="tabpanel" aria-labelledby="excel-result-tab" class="results-and-submission">
   <section class="analysis-result" aria-label="实际聚类结果"><h3>看看分组结果</h3><p>{{result.sample_count}}条记录分成两组，{{result.converged?'中心已稳定。':'中心尚未稳定。'}}</p><p v-for="warning in result.warnings" :key="warning" class="data-notice">{{warning}}</p><ScatterPlot :result="result"/><div class="reading-guide"><h4>试着说一说</h4><p>先看横轴和纵轴的名称。一个点越靠右，它的“{{result.features[0]!.name}}”就越大；越靠上，它的“{{result.features[1]!.name}}”就越大。</p><p>两种颜色的点各集中在哪里？比一比，两组在这两个数值上有什么不同？</p></div></section>
   <form class="student-submission" aria-label="提交二维分组结果" @submit.prevent="submit"><h3>写下你的发现</h3><p>看着左边的结果，自己填写。</p><label v-for="(_,i) in [0,1]" :key="i">第{{i+1}}组有几条？<input v-model.number="answers.counts[i]" type="number" min="0" :max="result.sample_count" required :disabled="busy" @input="status=''"/></label><label>用一句话说说两组有什么特点<textarea v-model="answers.description" rows="5" maxlength="500" required placeholder="看看两组在横轴和纵轴上的位置，用自己的话说一说。" :disabled="busy" @input="status=''"/></label><button :disabled="busy">提交结果</button><p v-if="status" class="success-message" role="status">{{status}}</p></form>
  </div>
 </section>
</template>
<style scoped>
.view-tabs{display:flex;gap:6px;padding:5px;background:#f4eff9;border-radius:12px;margin:0 0 24px;width:fit-content;max-width:100%}.excel-task .view-tabs button{background:transparent;color:#8d789e;font-size:15px;padding:9px 16px;line-height:1.7}.excel-task .view-tabs button[aria-selected=true]{background:white;color:#78539e;box-shadow:0 2px 7px #8d6cb614}.excel-task .results-and-submission{margin-top:0;padding-top:0;border-top:0}
.excel-task .run-clustering{display:block;margin-top:24px}
.excel-task .file-input{width:1px;height:1px;padding:0;margin:0;border:0;clip-path:inset(50%)}
.excel-task{padding:24px;background:white;border:1px solid #e9e0f2;border-radius:18px;font-size:16px;line-height:1.8;color:#665174}.excel-task h2{font-size:18px;margin:0 0 18px}.excel-task h3{font-size:18px;margin:0 0 12px}.excel-task p{margin:12px 0 20px}.excel-task button{border:0;border-radius:10px;background:#9070c1;color:white;padding:11px 18px;font-size:16px;cursor:pointer}.excel-task button:disabled{opacity:.5;cursor:default}.file-input{position:absolute;width:1px;height:1px;opacity:0;overflow:hidden}.excel-task .file-help{font-size:13px;line-height:1.8;color:#8b799b;margin:12px 0 20px}.dataset-heading{display:flex;flex-wrap:wrap;gap:8px 20px;margin:20px 0;overflow-wrap:anywhere}.dataset-heading span{color:#8b799b}.table-scroll{overflow:auto;max-height:290px;margin:12px 0 20px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:8px 12px;border-bottom:1px solid #eee7f4;text-align:left;min-width:90px;max-width:280px;overflow-wrap:anywhere}th{position:sticky;top:0;background:#f8f4fc}.column-selection{display:flex;gap:20px;margin-top:24px}.column-selection label{flex:1;min-width:0}.excel-task label{display:block}.excel-task select,.excel-task input,.excel-task textarea{display:block;width:100%;box-sizing:border-box;padding:10px;margin-top:8px;border:1px solid #ded1e9;border-radius:8px;font-family:inherit;color:#665174;background:white;font-size:16px}.excel-task textarea{resize:vertical;line-height:1.8}.data-quality{padding:12px 18px;background:#f8f5fc;border-radius:12px;margin:20px 0}.data-quality p{margin:0}.data-quality ul{max-height:200px;overflow:auto;margin:12px 0;padding-left:20px;font-size:14px}.data-notice,.error-message{color:#a65b42}.results-and-submission{display:grid;grid-template-columns:minmax(0,1fr) 245px;gap:24px;margin-top:32px;border-top:1px solid #e9e0f2;padding-top:24px;align-items:start}.analysis-result{min-width:0}.student-submission{padding:20px;background:#faf7fd;border:1px solid #e9e0f2;border-radius:14px}.student-submission label{margin:18px 0}.student-submission p{font-size:14px}.student-submission .success-message{color:#298d7d}.reading-guide{margin-top:24px;padding:18px;background:#f8f5fc;border-radius:12px}.reading-guide h4{font-size:16px;margin:0 0 10px}.reading-guide p{font-size:15px;margin:8px 0}summary{cursor:pointer}.error-message{padding:12px;background:#fff5ed;border-radius:10px}button:focus-visible{outline:3px solid #cab6e2;outline-offset:3px}@media(max-width:1100px){.results-and-submission{grid-template-columns:1fr}.column-selection{flex-direction:column}}@media(max-width:600px){.excel-task{padding:18px}}
</style>
