<script setup lang="ts">
import { useId } from 'vue'
withDefaults(defineProps<{compact?:boolean;mood?:'ready'|'thinking'|'talking'}>(),{compact:false,mood:'ready'})
const id=useId().replace(/:/g,'')
</script>
<template>
  <div class="teaching-robot" :class="[mood,{compact}]" role="img" aria-label="小知，一只微笑的卡通学习机器人">
    <svg :viewBox="compact?'65 42 230 170':'0 0 360 370'" fill="none" aria-hidden="true">
      <defs>
        <linearGradient :id="id+'shell'" x1="100" y1="80" x2="270" y2="300" gradientUnits="userSpaceOnUse"><stop stop-color="#fff"/><stop offset="1" stop-color="#e0d9fb"/></linearGradient>
        <linearGradient :id="id+'screen'" x1="125" y1="106" x2="250" y2="185" gradientUnits="userSpaceOnUse"><stop stop-color="#383c65"/><stop offset="1" stop-color="#23263f"/></linearGradient>
        <linearGradient :id="id+'badge'" x1="150" y1="220" x2="210" y2="270" gradientUnits="userSpaceOnUse"><stop stop-color="#9d86eb"/><stop offset="1" stop-color="#7355c6"/></linearGradient>
      </defs>
      <g v-if="!compact" class="robot-surroundings">
        <circle cx="181" cy="183" r="126" fill="#eeebfc"/>
        <circle cx="181" cy="183" r="143" stroke="#dcd5f3" stroke-dasharray="3 10"/>
        <path d="M56 106v16m-8-8h16M295 215v12m-6-6h12" stroke="#b09bdc" stroke-width="3" stroke-linecap="round"/>
        <circle cx="296" cy="91" r="8" fill="#b9e5da"/><circle cx="78" cy="268" r="5" fill="#c4b4eb"/>
        <path d="m280 45 3 8 8 3-8 3-3 8-3-8-8-3 8-3z" fill="#e5c387"/>
        <ellipse cx="180" cy="337" rx="80" ry="12" fill="#ded6f0" opacity=".65"/>
      </g>
      <g class="robot-body">
        <path d="M180 69V51" stroke="#8d77bc" stroke-width="7" stroke-linecap="round"/>
        <circle class="robot-antenna" cx="180" cy="43" r="11" fill="#83d5c2" stroke="#effcf8" stroke-width="5"/>
        <rect x="77" y="119" width="21" height="49" rx="10" fill="#c8b6eb"/>
        <rect x="262" y="119" width="21" height="49" rx="10" fill="#c8b6eb"/>
        <rect x="91" y="75" width="178" height="131" rx="47" :fill="'url(#'+id+'shell)'" stroke="#c7b8e9" stroke-width="3"/>
        <rect x="111" y="99" width="138" height="85" rx="29" :fill="'url(#'+id+'screen)'"/>
        <g class="robot-eyes" fill="#a3f1dc"><rect x="139" y="122" width="17" height="25" rx="8.5"/><rect x="204" y="122" width="17" height="25" rx="8.5"/></g>
        <path d="M167 155q13 12 26 0" stroke="#a3f1dc" stroke-width="4.5" stroke-linecap="round"/>
        <ellipse cx="128" cy="156" rx="7" ry="3" fill="#bda5ed" opacity=".7"/><ellipse cx="232" cy="156" rx="7" ry="3" fill="#bda5ed" opacity=".7"/>
        <path d="M160 208v10h40v-10" fill="#b2a0d5"/>
        <rect x="127" y="215" width="106" height="92" rx="34" :fill="'url(#'+id+'shell)'" stroke="#c7b8e9" stroke-width="3"/>
        <rect x="158" y="235" width="44" height="38" rx="14" :fill="'url(#'+id+'badge)'"/>
        <path d="m180 242 3.6 8.4 9.4 1-7 6.1 2 9-8-4.8-8 4.8 2-9-7-6.1 9.4-1z" fill="#fff"/>
        <g class="robot-hand"><path d="M233 235q29 6 42-25" stroke="#c7b8e9" stroke-width="24" stroke-linecap="round"/><path d="M233 234q29 6 42-25" stroke="#ede6fc" stroke-width="18" stroke-linecap="round"/><circle cx="279" cy="198" r="17" fill="#f3effe" stroke="#c7b8e9" stroke-width="3"/><path d="m279 188 1 12m-7-8 5 10m8-8-4 9" stroke="#b6a0d6" stroke-width="2" stroke-linecap="round"/></g>
        <path d="M126 236q-17 13-15 32" stroke="#c7b8e9" stroke-width="22" stroke-linecap="round"/><path d="M126 236q-17 13-15 32" stroke="#ede6fc" stroke-width="16" stroke-linecap="round"/>
        <rect x="142" y="298" width="29" height="24" rx="11" fill="#bca9df"/><rect x="189" y="298" width="29" height="24" rx="11" fill="#bca9df"/>
        <path d="M139 317h34m14 0h34" stroke="#ede6fc" stroke-width="13" stroke-linecap="round"/>
      </g>
    </svg>
  </div>
</template>
<style scoped>
.teaching-robot{width:100%;line-height:0}.teaching-robot svg{width:100%;height:auto;overflow:visible}.robot-body{transform-origin:180px 185px;animation:robot-float 5s ease-in-out infinite}.compact .robot-body{animation:none}.robot-eyes{transform-origin:180px 136px;animation:robot-blink 6s infinite}.robot-hand{transform-origin:233px 234px}.teaching-robot:hover .robot-hand,.talking .robot-hand{animation:robot-wave 1.5s ease-in-out infinite}.thinking .robot-antenna{animation:robot-glow 1s ease-in-out infinite}.talking .robot-antenna{fill:#b29be9}.compact svg{overflow:hidden}@keyframes robot-float{50%{transform:translateY(-7px)}}@keyframes robot-blink{0%,43%,47%,100%{transform:scaleY(1)}45%{transform:scaleY(.12)}}@keyframes robot-wave{50%{transform:rotate(-12deg)}}@keyframes robot-glow{50%{opacity:.35}}@media(prefers-reduced-motion:reduce){.robot-body,.robot-eyes,.robot-hand,.robot-antenna{animation:none!important}}
</style>
