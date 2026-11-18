import {activities} from '../../courses/kmeans/pureActivities'
import {useTeachingLearning as useSharedLearning} from '../../shared/composables/teaching/useTeachingLearning'
export const learningStorageKey='orbit-learning-activities-learning-v1'
export function useTeachingLearning(){return useSharedLearning(activities,learningStorageKey,'orbit-learning-activities-demo-v1')}
