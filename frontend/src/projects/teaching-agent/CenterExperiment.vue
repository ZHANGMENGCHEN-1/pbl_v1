<script setup lang="ts">
import {computed,onMounted,ref} from 'vue'
import {calculationRequest,type Calculation,type CalculationSubmission} from './calculation'
import type {ActivityDraft} from './learningState'
const props=defineProps<{sessionId:string;draft:ActivityDraft}>()
const emit=defineEmits<{result:[Calculation];submitted:[CalculationSubmission];restored:[CalculationSubmission]}>()
const rounds=ref<Calculation[]>([]),selected=ref(''),loading=ref(false),error=ref(''),formOpen=ref(false)
const result=computed(()=>rounds.value.find(r=>r.id===selected.value))
const chain=computed(()=>{const list:Calculation[]=[];let r=result.value;while(r){list.unshift(r);r=rounds.value.find(x=>x.id===r!.previous_id)}return list})
const fmt=(n:number)=>Number.isInteger(n)?String(n):`≈${Number(n.toFixed(3))}`
const x=(n:number)=>30+n*22
async function load(){loading.value=true;error.value='';try{const data=await calculationRequest<{steps:Calculation[];submissions:CalculationSubmission[]}>(props.sessionId,'state');rounds.value=data.steps;selected.value=data.steps.at(-1)?.id||'';if(result.value)emit('result',result.value);for(const saved of data.submissions)emit('restored',saved)}catch(e){error.value=e instanceof Error?e.message:'连接失败，请重试。'}finally{loading.value=false}}
onMounted(load)
async function calculate(){loading.value=true;error.value='';try{const data=await calculationRequest<Calculation>(props.sessionId,'steps',result.value?{previous_id:result.value.id}:{centers:props.draft.centers});if(!rounds.value.some(r=>r.id===data.id))rounds.value.push(data);selected.value=data.id;emit('result',data)}catch(e){error.value=e instanceof Error?e.message:'计算失败，请重试。'}finally{loading.value=false}}
async function submit(){
  const a=props.draft.answers
  if(!a||!a.counts.every(n=>n!==null&&Number.isInteger(n)&&n>=0)||Number(a.counts[0])+Number(a.counts[1])!==5||!a.centers.every(n=>n!==null&&Number.isFinite(n))){error.value='请填写两组数量（合计5本）和两个中心。';return}
  loading.value=true;error.value='';try{const saved=await calculationRequest<CalculationSubmission>(props.sessionId,'submissions',{result_id:result.value!.id,...a});emit('submitted',saved)}catch(e){error.value=e instanceof Error?e.message:'提交失败，请重试。'}finally{loading.value=false}
}
</script>
<template>
 <section class="calculation-card" aria-label="分组计算">
  <p>五本书的借阅次数：2、6、9、16、18。</p>
  <svg viewBox="0 0 500 110" role="img" aria-label="借阅次数数轴，圆点是书，菱形是中心">
   <line x1="30" y1="62" x2="470" y2="62" stroke="#b7a6c9"/>
   <g v-for="n in [0,5,10,15,20]" :key="n"><line :x1="x(n)" y1="58" :x2="x(n)" y2="66" stroke="#b7a6c9"/><text :x="x(n)" y="84" text-anchor="middle">{{n}}</text></g>
   <g v-for="(n,i) in [2,6,9,16,18]" :key="n"><circle :cx="x(n)" cy="42" r="7" :fill="result?(result.records[i]?.group===0?'#9972c5':'#38a69a'):'#a99ab9'"/><text :x="x(n)" y="24" text-anchor="middle">{{n}}</text></g>
   <g v-for="(n,i) in (result?.centers_before||draft.centers)" :key="i"><template v-if="n!==null"><path :d="`M${x(n)} 87 l6 6 -6 6 -6 -6z`" :fill="i===0?'#9972c5':'#38a69a'"/><text :x="x(n)" y="110" text-anchor="middle">中心{{i+1}}：{{fmt(n)}}</text></template></g>
  </svg>
  <div v-if="!result" class="center-inputs"><label v-for="(_,i) in draft.centers" :key="i">开始的中心{{i+1}}<input v-model.number="draft.centers[i]" type="number" min="0" max="20" step="any" :disabled="loading"></label></div>

  <template v-if="result">
   <div class="table-scroll"><table><thead><tr><th>书名（次数）</th><th>到中心1</th><th>到中心2</th><th>分到</th></tr></thead><tbody><tr v-for="book in result.records" :key="book.id"><td>{{book.name}}（{{book.value}}）</td><td>{{fmt(book.distances[0]!)}}</td><td>{{fmt(book.distances[1]!)}}</td><td>第{{book.group+1}}组</td></tr></tbody></table></div>
   <div v-for="g in result.groups" :key="g.group" class="group-result"><p>第{{g.group+1}}组：{{g.values.join('、')||'没有书'}}，共{{g.count}}本。</p><p v-if="g.count" class="center-equation">新中心：({{g.values.join(' + ')}}) ÷ {{g.count}} {{Number.isInteger(g.center)?'=':''}} {{fmt(g.center)}}</p><p v-else>这一组没有书，保留原中心。</p></div>
   <p v-for="warning in result.warnings" :key="warning">{{warning}}</p>
   <details><summary>查看前面的计算</summary><button v-for="r in chain" :key="r.id" class="round-link" :disabled="loading" @click="selected=r.id">第{{r.round}}轮</button></details><button v-if="selected!==rounds.at(-1)?.id" class="round-link" @click="selected=rounds.at(-1)!.id">回到最新一轮</button>
  </template>
  <p v-if="result?.converged" role="status">分组和中心都没有变化，计算完成了。请自己填写结果。</p>
  <div class="actions"><button v-if="!result?.converged" :disabled="loading" @click="calculate">{{loading?'正在计算…':result?'用新中心计算下一轮':'计算这一轮'}}</button><button v-else :disabled="loading" @click="formOpen=true">填写结果</button><button v-if="error" class="secondary" :disabled="loading" @click="load">重新连接</button></div>
  <form v-if="formOpen&&result?.converged&&draft.answers" @submit.prevent="submit">
   <h3>写下你的结果</h3><p>可以看着上面的计算过程填写。</p>
   <div v-for="i in [0,1]" :key="i" class="center-inputs"><label>第{{i+1}}组有几本书？<input v-model.number="draft.answers.counts[i]" type="number" min="0" max="5" required></label><label>最后的中心是多少？<input v-model.number="draft.answers.centers[i]" type="number" step="any" required></label></div>
   <button :disabled="loading">{{loading?'正在保存…':'提交结果，进入活动2'}}</button>
  </form>
  <p v-if="error" role="alert">{{error}}</p>
 </section>
</template>
<style scoped>
.group-result{margin:18px 0}.group-result p{margin-bottom:6px}.center-equation{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.center-equation input{width:100px;border-width:0 0 1px;border-radius:0;text-align:center}.round-link{background:transparent;color:#8764a8;padding:6px 10px;font-size:14px}
.calculation-card{padding:22px;background:#fff;border:1px solid #e9e0f2;border-radius:18px;color:#665174;font-size:16px;line-height:1.8}.calculation-card p{margin:10px 0 18px}.center-inputs{display:flex;gap:14px;margin:14px 0}.center-inputs label{flex:1;min-width:0}label{display:block}input,select{display:block;width:100%;box-sizing:border-box;border:1px solid #d8c9e6;border-radius:8px;padding:9px;color:#665174;background:white;font-size:16px}svg{width:100%;margin:20px 0;font-size:12px;fill:#705983;overflow:visible}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:8px 4px;border-bottom:1px solid #eee7f5;text-align:left}.table-scroll{overflow:auto}small{display:block;color:#8e7f9d;margin-top:14px}button{background:#9070c1;color:white;border:0;border-radius:10px;padding:11px 16px;font-size:16px;cursor:pointer}button:disabled{opacity:.5}.secondary{background:#f1ebf7;color:#7c6293}.actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}form{margin-top:24px;padding-top:16px;border-top:1px solid #e9e0f2}h3{font-size:18px}details{margin:16px 0}summary{cursor:pointer}[role=alert]{color:#b05050}
</style>
