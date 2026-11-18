import {computed,ref} from 'vue'
import {activityIds,type ActivityDefinition,type ActivityId} from '../../teaching/activityTypes'
import {createLearningModel} from '../../teaching/learningState'

export function useTeachingLearning(activities:readonly ActivityDefinition[],storageKey:string,legacyKey:string){
  const model=createLearningModel(activities)
  const saveError=ref('')
  // Preserve current fresh-session behavior; this refactor does not enable resume.
  try{localStorage.removeItem(storageKey);localStorage.removeItem(legacyKey)}catch{}
  const state=ref(model.createSession())
  const activity=computed(()=>activities.find(a=>a.id===state.value.activeActivityId)!)
  const current=computed(()=>state.value.activities[state.value.activeActivityId])
  const count=computed(()=>model.submittedCount(state.value))
  const complete=computed(()=>count.value===activityIds.length)
  const records=computed(()=>activities.map(a=>({...a,state:state.value.activities[a.id]})))
  function persist(){/* Page state is in memory; backend evidence remains persisted. */}
  function submit(){const saved=model.submitPreview(state.value);persist();return saved}
  function enter(id:ActivityId){const entered=model.enterActivity(state.value,id);if(entered)persist();return entered}
  function reset(){state.value=model.createSession();persist()}
  return {state,activity,current,count,complete,records,saveError,persist,submit,enter,reset,model}
}
