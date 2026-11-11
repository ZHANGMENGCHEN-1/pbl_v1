import { computed,ref } from 'vue'
import { activities,activityIds,type ActivityId } from './activities'
import { createSession,submitPreview,enterActivity,submittedCount } from './learningState'

export const learningStorageKey='orbit-teaching-agent-learning-v1'
export function useTeachingLearning(){
  const saveError=ref('')
  // Testing mode: every page entry gets a new backend session as well as fresh UI state.
  // Do not restore or write old browser records on pagehide/beforeunload.
  try{localStorage.removeItem(learningStorageKey);localStorage.removeItem('orbit-teaching-agent-demo-v1')}catch{}
  const state=ref(createSession())
  const activity=computed(()=>activities.find(a=>a.id===state.value.activeActivityId)!)
  const current=computed(()=>state.value.activities[state.value.activeActivityId])
  const count=computed(()=>submittedCount(state.value))
  const complete=computed(()=>count.value===activityIds.length)
  const records=computed(()=>activities.map(a=>({...a,state:state.value.activities[a.id]})))
  function persist(){/* Current-page state stays in memory; backend calculations are still saved. */}
  function submit(){const saved=submitPreview(state.value);persist();return saved}
  function enter(id:ActivityId){const entered=enterActivity(state.value,id);if(entered)persist();return entered}
  function reset(){state.value=createSession();persist()}
  return {state,activity,current,count,complete,records,saveError,persist,submit,enter,reset}
}
