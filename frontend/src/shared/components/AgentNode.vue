<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import { Cpu, Sunny, Moon, ArrowRight, Check, Document, Refresh, DataAnalysis } from '@element-plus/icons-vue'
defineProps<{ id: string; data: { label: string; enabled: boolean; status: string; selected: boolean; model?: string; locked?: boolean } }>()
</script>
<template>
  <div class="agent-node" :class="[id, { disabled: !data.enabled, selected: data.selected, active: data.status === 'running', complete: data.status === 'success', failed: data.status === 'error' }]">
    <Handle v-if="id !== 'brain'" type="target" :position="Position.Left" :connectable="false" />
    <div class="node-head"><span class="node-icon"><el-icon><Cpu v-if="id === 'brain'"/><Sunny v-else-if="id === 'weather'"/><Document v-else-if="id === 'inspect_dataset'"/><Refresh v-else-if="id === 'run_kmeans_step'"/><DataAnalysis v-else-if="id === 'run_kmeans_analysis'"/><Moon v-else/></el-icon></span><div><strong>{{ data.label }}</strong></div><span class="status-dot"/></div>
    <div class="node-foot"><span :title="id === 'brain' ? data.model : undefined">{{ id === 'brain' ? data.model : data.locked ? '未解锁' : data.enabled ? '已启用' : '已禁用' }}</span><span v-if="data.status === 'running'" class="pulsing">运行中</span><el-icon v-else-if="data.status === 'success'"><Check/></el-icon><el-icon v-else><ArrowRight/></el-icon></div>
    <Handle v-if="id === 'brain'" type="source" :position="Position.Right" :connectable="false" />
  </div>
</template>
