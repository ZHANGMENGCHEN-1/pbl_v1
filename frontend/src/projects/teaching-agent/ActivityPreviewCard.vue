<script setup lang="ts">
import { activities,previewBooks,previewSteps,type ActivityId } from './activities'
import type { ActivityDraft } from './learningState'
const props=defineProps<{activityId:ActivityId;draft:ActivityDraft;minimal?:boolean}>()
const activity=()=>activities.find(a=>a.id===props.activityId)!
function updateCenter(index:number,event:Event){const value=(event.target as HTMLInputElement).value;props.draft.centers[index]=value===''?null:Number(value)}
</script>
<template>
  <section class="activity-preview-card" aria-label="当前活动操作区">
    <div v-if="!minimal" class="preview-card-heading"><span>本步操作</span><strong>{{activity().goal}}</strong></div>
    <template v-if="activityId==='group_books'">
      <div class="preview-book-list"><span v-for="book in previewBooks" :key="book.name"><b>{{book.count}}</b>{{book.name}}</span></div>
      <div class="preview-centers"><label v-for="index in [0,1]" :key="index">开始的中心{{index+1}}<input :value="draft.centers[index]??''" type="number" min="0" max="20" step="0.1" @input="updateCenter(index,$event)"/></label></div>
      <button type="button" class="preview-pending-button" disabled>{{minimal?'计算暂未开放':'逐轮计算 · 待接入'}}</button>
    </template>
    <template v-else-if="activityId==='explain_algorithm'">
      <div class="preview-step-list" aria-label="四个步骤的无序预览"><div v-for="step in previewSteps" :key="step.id"><span>⋮⋮</span>{{step.text}}</div></div>
      <p class="preview-detail">“重复计算”里会展开：算距离 → 分组 → 更新中心。</p>
      <button type="button" class="preview-pending-button" disabled>{{minimal?'排序暂未开放':'拖动排序与程序验证 · 待接入'}}</button>
    </template>
    <template v-else>
      <div class="preview-upload"><span aria-hidden="true">↥</span><strong>准备一张Excel表格</strong><small v-if="!minimal">上传 → 查看数据 → 运行分组 → 解释散点图</small><button type="button" class="preview-pending-button" disabled>{{minimal?'上传暂未开放':'Excel上传 · 待接入'}}</button></div>
    </template>
    <template v-if="!minimal"><p class="preview-pending-note">{{activity().pending}}</p><label class="preview-note-label" :for="'activity-note-'+activityId">这一步想试什么？可以留个备注（选填）</label><textarea :id="'activity-note-'+activityId" v-model="draft.note" rows="2" maxlength="2000" placeholder="也可以先不填，直接提交本段体验。"/></template>
  </section>
</template>
<style scoped>
.activity-preview-card{margin:4px 0 28px 52px;padding:20px;border:1px solid #e3d8f1;border-radius:14px;background:#fdfbff;color:#6c5a7f}.preview-card-heading{display:flex;flex-direction:column;gap:7px;margin-bottom:16px;line-height:1.7}.preview-card-heading>span{font-size:12px;color:#9883af}.preview-card-heading strong{font-size:16px;font-weight:600}.preview-book-list{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:18px}.preview-book-list>span{display:flex;flex-direction:column;gap:5px;align-items:center;flex:1;min-width:70px;padding:10px 5px;background:#f1ecf8;border-radius:9px;font-size:12px;text-align:center}.preview-book-list b{font-size:22px;color:#8060b5}.preview-centers{display:flex;gap:16px;margin-bottom:14px}.preview-centers label{flex:1;font-size:13px;line-height:1.8}.preview-centers input{display:block;width:100%;border:1px solid #e2d7ef;border-radius:7px;margin-top:6px;padding:9px;background:#fff;color:#695379;font-size:16px}.preview-pending-button{border:1px dashed #d8cce8;background:#f5f1fa;color:#a395b2;font-size:13px;padding:10px 15px;border-radius:8px;cursor:not-allowed}.preview-pending-note{font-size:13px;line-height:1.8;color:#917e9e;margin:14px 0 18px}.preview-step-list{display:flex;flex-direction:column;gap:8px}.preview-step-list>div{display:flex;align-items:center;gap:10px;padding:10px 12px;background:#f3eefb;border:1px dashed #e3d8f1;border-radius:8px;font-size:14px;line-height:1.7}.preview-step-list span{font-size:20px;color:#b5a2ca}.preview-detail{font-size:13px;line-height:1.8;color:#8b789d}.preview-upload{padding:20px 12px;border:1px dashed #d6c8e9;border-radius:10px;display:flex;flex-direction:column;align-items:center;gap:12px;text-align:center;background:#f7f3fc}.preview-upload>span{font-size:28px;color:#b09aca}.preview-upload strong{font-size:15px;font-weight:500}.preview-upload small{font-size:12px;line-height:1.8;color:#a18db3}.preview-note-label{display:block;font-size:13px;line-height:1.8;margin-bottom:7px}.activity-preview-card textarea{resize:vertical;width:100%;min-height:64px;max-height:180px;border:1px solid #e4daef;border-radius:8px;padding:10px 12px;color:#6a557b;font-size:15px;line-height:1.7;background:#fff}.activity-preview-card textarea::placeholder{color:#b3a5bf}.activity-preview-card input:focus,.activity-preview-card textarea:focus{outline:2px solid #d3bfe9;outline-offset:1px}@media(max-width:520px){.activity-preview-card{margin-left:0;padding:15px}.preview-centers{gap:10px}.preview-book-list>span{min-width:65px}.preview-card-heading strong{font-size:15px}}
</style>
