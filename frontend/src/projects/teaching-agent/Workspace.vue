<script setup lang="ts">
import CompanionLayout from '../../shared/components/teaching/CompanionLayout.vue'
import TeachingRobot from '../../shared/components/teaching/robot/TeachingRobot.vue'
import {useTeachingLearning} from './useTeachingLearning'
</script>

<template>
  <CompanionLayout condition="B" :create-learning="useTeachingLearning" :robot-component="TeachingRobot"/>
</template>
