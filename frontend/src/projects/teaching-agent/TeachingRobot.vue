<script setup lang="ts">
import { defineAsyncComponent, onBeforeUnmount, onMounted, ref } from 'vue'
import TeachingRobotSvg from './TeachingRobotSvg.vue'

withDefaults(defineProps<{compact?:boolean;mood?:'ready'|'thinking'|'talking';interactive?:boolean;showControls?:boolean}>(),{compact:false,mood:'ready',interactive:true,showControls:true})
const root=ref<HTMLElement>(),ready=ref(false),failed=ref(false),visible=ref(false)
const scene=ref<{reset:()=>void}>()
defineExpose({reset:()=>scene.value?.reset()})
const RobotScene=defineAsyncComponent(()=>import('./RobotScene.vue'))
let observer:IntersectionObserver|undefined
onMounted(()=>{
  if(!root.value)return
  observer=new IntersectionObserver(entries=>{if(entries[0]?.isIntersecting){visible.value=true;observer?.disconnect()}},{rootMargin:'100px'})
  observer.observe(root.value)
})
onBeforeUnmount(()=>observer?.disconnect())
</script>
<template>
  <div ref="root" class="teaching-robot-view" :class="{compact,interactive:interactive&&!compact,'is-3d':ready&&!failed}" :data-mood="mood" :data-renderer="compact?'svg':ready&&!failed?'three':'svg'" role="group" aria-label="小知，卡通学习机器人">
    <TeachingRobotSvg v-if="compact" compact :mood="mood"/>
    <template v-else>
      <div class="robot-halo" aria-hidden="true"/>
      <div v-if="!ready||failed" class="robot-fallback"><TeachingRobotSvg :mood="mood"/></div>
      <RobotScene v-if="visible&&!failed" ref="scene" :mood="mood" :interactive="interactive" @ready="ready=true" @unsupported="failed=true;ready=false"/>
      <div v-if="showControls&&interactive&&ready&&!failed" class="robot-3d-controls"><span>拖动转一转</span><button type="button" aria-label="让小知转回正面" @click="scene?.reset()">复位 ↺</button></div>
    </template>
  </div>
</template>
<style scoped>
.teaching-robot-view{position:relative;width:100%;aspect-ratio:360/370;isolation:isolate}.teaching-robot-view.compact{aspect-ratio:auto;line-height:0}.robot-halo{position:absolute;width:88%;aspect-ratio:1;left:6%;top:5%;border:1px dashed #ddd0ee;border-radius:50%;background:radial-gradient(circle at 45% 38%,#f4efff 0,#ebe4f8 70%,#f5f1fb 100%);z-index:-1}.robot-fallback{position:absolute;inset:0}.robot-3d-controls{position:absolute;left:0;right:0;bottom:-10px;display:flex;align-items:center;justify-content:center;gap:12px;color:#9d8bab;font-size:11px;line-height:1.8}.robot-3d-controls button{border:1px solid #e0d5ef;background:#ffffffc9;border-radius:6px;padding:2px 7px;color:#8a72a6;font-size:11px}.robot-3d-controls button:hover{background:#f5f0fb}.robot-3d-controls button:focus-visible{outline:2px solid #b69ad8;outline-offset:2px}.interactive.is-3d :deep(canvas){cursor:grab}.interactive.is-3d :deep(canvas:active){cursor:grabbing}.teaching-robot-view:not(.interactive) :deep(canvas){pointer-events:none}.compact .robot-halo{display:none}@media(max-width:900px){.robot-3d-controls{display:none}}
</style>
