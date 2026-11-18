import {computed,ref,watch} from 'vue'
import type {ActivityId} from '../../teaching/activityTypes'
import type {Calculation,CalculationSubmission} from '../../../courses/kmeans/calculation'
import type {Analysis,ExplorationSubmission} from '../../../courses/kmeans/exploration'
import {saveSorting,recordActivityEntry} from '../../teaching/telemetry'
import type {useTeachingLearning} from './useTeachingLearning'

// Each fixed route chooses its condition; students cannot select a condition.
export const teachingConditions={
  A:{sourceRoute:'learning-activities',withRobot:false,reflectionDiscussion:false},
  B:{sourceRoute:'teaching-agent',withRobot:true,reflectionDiscussion:false},
  C:{sourceRoute:'meaning-making',withRobot:true,reflectionDiscussion:true},
} as const
type Condition=typeof teachingConditions[keyof typeof teachingConditions]
interface Reflection {activityId:ActivityId;submissionId:string;measured:boolean;measurementId?:string}
interface Options {
  learning:ReturnType<typeof useTeachingLearning>
  condition:Condition
  chatBusy?:()=>boolean
  stopChat?:()=>void
  openReflectionDiscussion?:()=>void
  focusChat?:()=>void
}

export function useTeachingFlow(options:Options){
  const {learning,condition}=options
  const {state,current,persist,model}=learning
  const entry=ref<'hello'|'story'|'learning'>('hello'),operationOpen=ref(false)
  const className=ref(''),studentNumber=ref(''),identitySaving=ref(false),identityError=ref('')
  const selfReportOpen=ref(false),taskBusy=ref(false),recordsOpen=ref(false)
  const sortingSaving=ref(false),sortingError=ref(''),sortingCorrect=ref<boolean|null>(null)
  const reflection=ref<Reflection|null>(null)
  const calculationHint=ref(''),explorationHint=ref('')
  const boundary=ref(state.value.messages.at(-1)?.id||0)
  const registered=computed(()=>!!state.value.student)
  const saving=computed(()=>identitySaving.value||sortingSaving.value)
  const error=computed(()=>identityError.value||sortingError.value)
  const navigationBlocked=computed(()=>saving.value||taskBusy.value||selfReportOpen.value||!!options.chatBusy?.()||!!(reflection.value&&!reflection.value.measured))
  function clearBoundary(){boundary.value=state.value.messages.at(-1)?.id||0}
  function scrollTop(){window.scrollTo({top:0,behavior:'smooth'})}
  function canEnter(id:ActivityId){return model.canEnter(state.value,id)}
  async function identify(){
    if(identitySaving.value)return
    identityError.value=''
    if(!className.value.trim()||!studentNumber.value.trim()){identityError.value='请填写班级和学号。';return}
    identitySaving.value=true
    try{
      const response=await fetch('/api/projects/teaching-agent/student',{method:'POST',headers:{'Content-Type':'application/json','X-Session-ID':state.value.sessionId},body:JSON.stringify({class_name:className.value.trim(),student_number:studentNumber.value.trim(),source_route:condition.sourceRoute})})
      const data=await response.json()
      if(!response.ok)throw new Error(typeof data?.detail==='string'?data.detail:'保存失败，请重试。')
      state.value.student={className:data.class_name,studentNumber:data.student_number}
      persist();selfReportOpen.value=true
    }catch(e){identityError.value=e instanceof Error?e.message:'连接失败，请重试。'}finally{identitySaving.value=false}
  }
  function selfReportSaved(){
    selfReportOpen.value=false
    entry.value=condition.withRobot?'story':'learning'
    operationOpen.value=!condition.withRobot
  }
  function start(){entry.value='learning';operationOpen.value=true;clearBoundary()}
  function openTask(){if(navigationBlocked.value)return;clearBoundary();operationOpen.value=true}
  function beginReflection(activityId:ActivityId,submissionId:string){
    options.stopChat?.();operationOpen.value=false;clearBoundary()
    reflection.value={activityId,submissionId,measured:false};scrollTop()
  }
  function measurementSaved(saved:{id:string}){
    if(!reflection.value||reflection.value.measured)return
    reflection.value.measured=true
    if(condition.reflectionDiscussion){
      reflection.value.measurementId=saved.id
      options.openReflectionDiscussion?.()
    }
    options.focusChat?.()
  }
  function switchActivity(id:ActivityId,direct=true){
    if(navigationBlocked.value||!canEnter(id))return false
    options.stopChat?.()
    if(!learning.enter(id))return false
    reflection.value=null;recordsOpen.value=false;identityError.value='';sortingError.value=''
    sortingCorrect.value=null;calculationHint.value='';explorationHint.value=''
    entry.value='learning';operationOpen.value=direct||!condition.withRobot||id==='explore_2d'
    clearBoundary();scrollTop();return true
  }
  function review(id:ActivityId){return switchActivity(id)}
  function continueReflection(){
    if(navigationBlocked.value||!reflection.value?.measured)return
    const id=reflection.value.activityId
    if(id==='explore_2d'){recordsOpen.value=true;return}
    switchActivity(id==='group_books'?'explain_algorithm':'explore_2d',false)
  }
  function continueToThree(){return switchActivity('explore_2d')}
  function calculated(result:Calculation){
    current.value.operation={status:result.converged?'completed':'pending',source:'backend',result:result as unknown as Record<string,unknown>,updatedAt:new Date().toISOString()}
    calculationHint.value=result.converged?'两组的书和中心都不再变化了。你可以看着计算过程，自己写下两组的数量和最后的中心。':'这一轮分好了！把这一组中每本书的借阅次数加起来，再除以这一组有几本书，就得到新的中心。'
    clearBoundary();persist()
  }
  function restoredCalculation(saved:CalculationSubmission){model.recordCalculation(state.value,saved,false);persist()}
  function calculationSubmitted(saved:CalculationSubmission){
    restoredCalculation(saved);calculationHint.value='';beginReflection('group_books',saved.id)
  }
  async function submitOrder(order:string[]){
    if(sortingSaving.value||taskBusy.value||options.chatBusy?.())return
    options.stopChat?.();sortingSaving.value=true;sortingError.value='';sortingCorrect.value=null
    try{
      const saved=await saveSorting(state.value.sessionId,order)
      clearBoundary();model.recordStepOrder(state.value,order,saved);sortingCorrect.value=saved.payload.correct;persist()
      if(saved.payload.correct)beginReflection('explain_algorithm',saved.id)
    }catch(e){sortingError.value=e instanceof Error?e.message:'排序保存失败，请重试。'}finally{sortingSaving.value=false}
  }
  function explorationChanged(){
    explorationHint.value='';clearBoundary()
    state.value.activities.explore_2d.operation={status:'pending',source:'backend',result:null,updatedAt:null};persist()
  }
  function explorationCalculated(result:Analysis){
    state.value.activities.explore_2d.operation={status:'completed',source:'backend',result:result as unknown as Record<string,unknown>,updatedAt:new Date().toISOString()}
    explorationHint.value='先看看两种颜色的点各在哪里：哪一组更靠右，哪一组更靠上？试着用自己的话说说两组有什么不同。'
    clearBoundary();persist()
  }
  function explorationSubmitted(saved:ExplorationSubmission){
    model.recordExploration(state.value,saved,state.value.activities.explore_2d.operation.result as unknown as Analysis)
    persist();beginReflection('explore_2d',saved.id)
  }
  function resetFlow(){
    if(navigationBlocked.value)return false
    options.stopChat?.();learning.reset();reflection.value=null;entry.value='hello';operationOpen.value=false
    recordsOpen.value=false;selfReportOpen.value=false;sortingCorrect.value=null
    sortingError.value='';identityError.value='';calculationHint.value='';explorationHint.value='';clearBoundary();return true
  }
  watch(()=>state.value.activeActivityId,clearBoundary)
  watch(()=>[entry.value,selfReportOpen.value,state.value.activeActivityId,state.value.sessionId],()=>{
    if(entry.value==='learning'&&!selfReportOpen.value&&state.value.student)void recordActivityEntry(state.value.sessionId,state.value.activeActivityId)
  })
  return {...learning,entry,operationOpen,className,studentNumber,identitySaving,identityError,selfReportOpen,
    taskBusy,recordsOpen,sortingSaving,sortingError,sortingCorrect,reflection,calculationHint,explorationHint,
    boundary,registered,saving,error,navigationBlocked,canEnter,identify,selfReportSaved,start,openTask,
    measurementSaved,continueReflection,review,go:review,continueToThree,calculated,restoredCalculation,
    calculationSubmitted,submitOrder,explorationChanged,explorationCalculated,explorationSubmitted,resetFlow}
}
