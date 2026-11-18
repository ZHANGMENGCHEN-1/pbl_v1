import {activities} from '../../courses/kmeans/activities'
import {useTeachingLearning as useSharedLearning} from '../../shared/composables/teaching/useTeachingLearning'
export const learningStorageKey='orbit-meaning-making-learning-v1'
export function useTeachingLearning(){return useSharedLearning(activities,learningStorageKey,'orbit-meaning-making-demo-v1')}
