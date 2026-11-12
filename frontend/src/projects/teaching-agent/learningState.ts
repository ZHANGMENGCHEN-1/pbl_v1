import type {ExplorationSubmission,Analysis} from './exploration'
import {checkStepOrder} from './sorting'
import type {CalculationSubmission} from './calculation'
import { activities,activityIds,type ActivityId } from './activities'
export type OperationStatus='pending'|'previewed'|'completed'|'error'
export interface ActivityDraft {centers:[number|null,number|null];stepOrder:string[];datasetId:string|null;features:string[];note:string;question:string;exploration?:{counts:[number|null,number|null];description:string};roundCenters?:Record<string,(number|null)[]>;answers:{counts:[number|null,number|null];centers:[number|null,number|null]}}
export interface OperationState {status:OperationStatus;source:'preview'|'backend'|'local';result:Record<string,unknown>|null;updatedAt:string|null}
export interface Submission {id:string;activityId:ActivityId;kind:'framework_preview'|'learning_result';createdAt:string;payload:{note:string;draft:ActivityDraft;operation:OperationState;exploration?:ExplorationSubmission;calculation?:CalculationSubmission;sorting?:{order:string[];correct:boolean;feedback:string}}}
export interface ActivityState {draft:ActivityDraft;operation:OperationState;submissions:Submission[]}
export interface TeachingMessage {id:number;role:'assistant'|'student';activityId:ActivityId;kind:'introduction'|'chat'|'submission';text:string;paused?:boolean;status?:'streaming'|'completed'|'paused'|'error';error?:string}
export interface TeachingSession {version:1;mode:'guided_learning';sessionId:string;student?:{className:string;studentNumber:string};activeActivityId:ActivityId;activities:Record<ActivityId,ActivityState>;messages:TeachingMessage[]}

const copy=<T>(value:T):T=>JSON.parse(JSON.stringify(value))
const newId=()=>Array.from(crypto.getRandomValues(new Uint8Array(16)),n=>n.toString(16).padStart(2,'0')).join('')
function blankActivity():ActivityState{return {draft:{centers:[2,11],stepOrder:[],datasetId:null,features:[],note:'',question:'',answers:{counts:[null,null],centers:[null,null]}},operation:{status:'pending',source:'preview',result:null,updatedAt:null},submissions:[]}}
export function appendMessage(state:TeachingSession,message:Omit<TeachingMessage,'id'>){
  state.messages.push({id:Math.max(0,...state.messages.map(m=>m.id))+1,...message})
  if(state.messages.length>120)state.messages.splice(0,state.messages.length-120)
}
export function createSession():TeachingSession{
  const state:TeachingSession={version:1,mode:'guided_learning',sessionId:newId(),activeActivityId:activityIds[0],activities:Object.fromEntries(activityIds.map(id=>[id,blankActivity()])) as Record<ActivityId,ActivityState>,messages:[]}
  appendMessage(state,{role:'assistant',activityId:activityIds[0],kind:'introduction',text:activities[0]!.introduction})
  return state
}
export function submittedCount(state:TeachingSession){return activityIds.filter(id=>state.activities[id].submissions.some(s=>s.kind==='learning_result'&&(id!=='explain_algorithm'||s.payload.sorting?.correct===true))).length}
export function canEnter(state:TeachingSession,id:ActivityId){
  const index=activityIds.indexOf(id)
  return index>=0&&activityIds.slice(0,index).every(previous=>state.activities[previous].submissions.some(s=>s.kind==='learning_result'&&(previous!=='explain_algorithm'||s.payload.sorting?.correct===true)))
}
export function enterActivity(state:TeachingSession,id:ActivityId){
  if(!canEnter(state,id))return false
  if(state.activeActivityId===id)return true
  state.activeActivityId=id
  appendMessage(state,{role:'assistant',activityId:id,kind:'introduction',text:activities.find(a=>a.id===id)!.introduction})
  return true
}
export function submitPreview(state:TeachingSession){
  const id=state.activeActivityId,activity=state.activities[id]
  if(id!=='explore_2d')throw new Error('请先完成真实计算并提交结果。')
  // A preview acknowledgement must never be confused with actual calculation evidence.
  activity.operation={status:'previewed',source:'preview',result:null,updatedAt:new Date().toISOString()}
  const submission:Submission={id:newId(),activityId:id,kind:'framework_preview',createdAt:new Date().toISOString(),payload:copy({note:activity.draft.note,draft:activity.draft,operation:activity.operation})}
  activity.submissions.push(submission)
  appendMessage(state,{role:'assistant',activityId:id,kind:'submission',text:'这一步的流程体验已记录。这不是计算结果，也不表示已经完成真实实验。'})
  const next=activityIds[activityIds.indexOf(id)+1]
  if(next)enterActivity(state,next)
  return submission
}
export function restoreSession(raw:unknown):TeachingSession|null{
  if(!raw||typeof raw!=='object')return null
  const state=raw as TeachingSession
  if(state.version!==1||state.mode!=='guided_learning'||!activityIds.includes(state.activeActivityId)||typeof state.sessionId!=='string'||!Array.isArray(state.messages)||!state.activities)return null
  for(const id of activityIds){
    const value=state.activities[id]
    if(!value||!value.draft||!value.operation||!Array.isArray(value.submissions))return null
    const draft=value.draft
    if(!Array.isArray(draft.centers)||draft.centers.length!==2||!draft.centers.every(n=>n===null||(typeof n==='number'&&Number.isFinite(n)))||!Array.isArray(draft.stepOrder)||!draft.stepOrder.every(s=>typeof s==='string')||!Array.isArray(draft.features)||!draft.features.every(s=>typeof s==='string')||(draft.datasetId!==null&&typeof draft.datasetId!=='string')||typeof draft.note!=='string'||draft.note.length>2000||typeof draft.question!=='string'||draft.question.length>2000)return null
    if(!['pending','previewed','completed','error'].includes(value.operation.status)||!['preview','backend','local'].includes(value.operation.source))return null
    if(value.operation.source==='preview'&&value.operation.result!==null)return null
    if(value.operation.source==='backend'&&(!value.operation.result||typeof value.operation.result.id!=='string'))return null
    if(!draft.answers||!Array.isArray(draft.answers.counts)||!Array.isArray(draft.answers.centers))return null
    if(value.submissions.some(s=>!s||s.activityId!==id||!['framework_preview','learning_result'].includes(s.kind)||typeof s.id!=='string'||typeof s.createdAt!=='string'||typeof s.payload?.note!=='string'||(s.kind==='learning_result'&&(id==='group_books'?!s.payload.calculation:id==='explain_algorithm'?!s.payload.sorting:!s.payload.exploration))))return null
  }
  if(!canEnter(state,state.activeActivityId))return null
  if(state.messages.some(m=>!m||!Number.isSafeInteger(m.id)||!['assistant','student'].includes(m.role)||!activityIds.includes(m.activityId)||!['introduction','chat','submission'].includes(m.kind)||typeof m.text!=='string'||m.text.length>10000))return null
  return copy(state)
}

export function recordCalculation(state:TeachingSession,saved:CalculationSubmission,advance=true){
  const activity=state.activities.group_books
  const operation:OperationState={status:'completed',source:'backend',result:copy(saved.payload.calculation_result) as unknown as Record<string,unknown>,updatedAt:saved.created}
  if(advance||!activity.operation.result)activity.operation=operation
  if(!activity.submissions.some(s=>s.id===saved.id))activity.submissions.push({id:saved.id,activityId:'group_books',kind:'learning_result',createdAt:saved.created,payload:copy({note:activity.draft.note,draft:activity.draft,operation,calculation:saved})})
  if(advance)enterActivity(state,'explain_algorithm')
}

export function recordStepOrder(state:TeachingSession,order:string[],saved?:{id:string;created:string;payload:{correct:boolean;feedback:string}}){
  const activity=state.activities.explain_algorithm
  const checked=saved?{correct:saved.payload.correct,feedback:saved.payload.feedback}:checkStepOrder(order),createdAt=saved?.created??new Date().toISOString(),id=saved?.id??newId()
  activity.draft.stepOrder=[...order]
  const sorting={order:[...order],...checked}
  activity.operation={status:checked.correct?'completed':'error',source:'local',result:{id,...sorting},updatedAt:createdAt}
  if(!activity.submissions.some(s=>s.id===id))activity.submissions.push({id,activityId:'explain_algorithm',kind:'learning_result',createdAt,payload:copy({note:activity.draft.note,draft:activity.draft,operation:activity.operation,sorting})})
  appendMessage(state,{role:'assistant',activityId:'explain_algorithm',kind:'chat',text:checked.feedback})
  return checked
}

export function recordExploration(state:TeachingSession,saved:ExplorationSubmission,result:Analysis){
  const activity=state.activities.explore_2d
  activity.operation={status:'completed',source:'backend',result:copy(result) as unknown as Record<string,unknown>,updatedAt:saved.created}
  if(!activity.submissions.some(s=>s.id===saved.id))activity.submissions.push({id:saved.id,activityId:'explore_2d',kind:'learning_result',createdAt:saved.created,payload:copy({note:activity.draft.note,draft:activity.draft,operation:activity.operation,exploration:saved})})
}
