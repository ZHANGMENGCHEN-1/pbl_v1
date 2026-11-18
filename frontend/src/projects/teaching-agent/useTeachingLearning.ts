import {activities} from '../../courses/kmeans/activities'
import {useTeachingLearning as useSharedLearning} from '../../shared/composables/teaching/useTeachingLearning'
export const learningStorageKey='orbit-teaching-agent-learning-v1'
export function useTeachingLearning(){return useSharedLearning(activities,learningStorageKey,'orbit-teaching-agent-demo-v1')}
