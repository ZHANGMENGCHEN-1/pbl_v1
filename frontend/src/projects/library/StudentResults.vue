<script setup lang="ts">
defineProps<{index:number;payload:Record<string,any>}>()
</script>
<template>
  <section class="student-results">
    <template v-if="index===0&&payload.student_result"><el-table :data="payload.student_result.counts.map((count:number,i:number)=>({group:i+1,count,center:payload.student_result.centers[i]}))" border><el-table-column prop="group" label="分组"/><el-table-column prop="count" label="图书数量"/><el-table-column prop="center" label="最终中心"/></el-table></template>
    <pre v-else-if="index===1" class="prompt-delivery-preview">{{payload.system_prompt}}</pre>
    <template v-else-if="index===2"><el-table :data="payload.group_counts" border><el-table-column label="分组"><template #default="s">第{{s.row.group+1}}组</template></el-table-column><el-table-column prop="count" label="我填写的数量"/></el-table><p>合计 {{payload.total}} 条</p></template>
    <template v-else-if="index===3"><el-table :data="payload.purchases" border><el-table-column prop="type" label="我推荐的采购类型"/><el-table-column prop="quantity" label="采购数量（册）"/></el-table><p>为什么这样买：{{payload.rationale}}</p><div class="student-reflection"><b>我的发现</b><p>{{payload.reflection || '这次提交未填写反思'}}</p></div></template>
    <p v-else>这次历史交付没有保存学生手填的结果。</p>
  </section>
</template>
<style scoped>.student-results{font-size:16px;line-height:1.8;color:#475269}.student-results p{white-space:pre-wrap}.student-reflection{margin-top:16px;padding:16px;background:#f4effb;border-radius:10px}.student-reflection p{margin:8px 0 0}</style>
