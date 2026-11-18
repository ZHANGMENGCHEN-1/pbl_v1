// Run: node scripts/teaching_flow_smoke.mjs
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import {createRequire} from 'node:module'
import {fileURLToPath} from 'node:url'
import ts from '../frontend/node_modules/typescript/lib/typescript.js'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../frontend/src')
const require=createRequire(new URL('../frontend/package.json',import.meta.url))
const {effectScope,nextTick,ref}=require('vue')
const cache=new Map()
function load(name,from=root){
  if(!name.startsWith('.')&&from!==root)return require(name)
  const file=path.resolve(from,name.endsWith('.ts')?name:name+'.ts')
  if(cache.has(file))return cache.get(file).exports
  const module={exports:{}};cache.set(file,module)
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
  new Function('module','exports','require',code)(module,module.exports,dependency=>load(dependency,path.dirname(file)))
  return module.exports
}
globalThis.window={scrollTo(){}}
globalThis.localStorage={removeItem(){}}
const {useTeachingFlow,teachingConditions}=load('shared/composables/teaching/useTeachingFlow')
const requests=[]
let failSorting=false
globalThis.fetch=async(url,options)=>{
  const body=JSON.parse(options.body);requests.push({url,body})
  if(url.endsWith('/student'))return Response.json(body)
  if(url.endsWith('/submissions')){
    if(failSorting)return Response.json({detail:'retry sorting'},{status:503})
    return Response.json({id:crypto.randomUUID(),created:new Date().toISOString(),payload:{correct:body.order.join(',')==='data,count,centers,calculate',feedback:'test feedback'}})
  }
  return Response.json({})
}

for(const [condition,route] of [['A','learning-activities'],['B','teaching-agent'],['C','meaning-making']]){
  const scope=effectScope(),chatBusy=ref(false)
  let openings=0
  const flow=scope.run(()=>useTeachingFlow({
    learning:load('projects/'+route+'/useTeachingLearning').useTeachingLearning(),condition:teachingConditions[condition],
    chatBusy:()=>chatBusy.value,openReflectionDiscussion:()=>{openings++},stopChat(){},
  }))
  assert.equal(flow.canEnter('explain_algorithm'),false)
  const session=flow.state.value.sessionId
  flow.className.value='test';flow.studentNumber.value='001'
  await flow.identify()
  assert.equal(requests.findLast(r=>r.url.endsWith('/student')).body.source_route,teachingConditions[condition].sourceRoute)
  assert.equal(flow.navigationBlocked.value,true)
  assert.equal(flow.review('group_books'),false)
  flow.selfReportSaved();flow.start()
  assert.equal(flow.state.value.sessionId,session)
  const result={id:'round',converged:true,centers_after:[5,17]}
  const saved={id:'submission-1',created:new Date().toISOString(),result_id:'round',payload:{calculation_result:result,student_result:{counts:[3,2],centers:[5,17]},tool_result:{counts:[3,2],centers:[5,17]}}}
  flow.calculationSubmitted(saved)
  assert.equal(flow.canEnter('explain_algorithm'),true)
  assert.equal(flow.review('explain_algorithm'),false,'cannot skip measurement')
  flow.measurementSaved({id:'measurement-1'})
  flow.measurementSaved({id:'measurement-1'})
  assert.equal(openings,condition==='C'?1:0,'only C auto-opens discussion, once')
  assert.equal(flow.reflection.value.measurementId,condition==='C'?'measurement-1':undefined)
  chatBusy.value=true
  flow.continueReflection()
  assert.equal(flow.activity.value.id,'group_books','wait for model reply')
  chatBusy.value=false;flow.continueReflection()
  assert.equal(flow.activity.value.id,'explain_algorithm')
  assert.equal(flow.reflection.value,null)
  assert.equal(flow.operationOpen.value,condition==='A')
  flow.openTask()
  failSorting=true
  await flow.submitOrder(['data','count','centers','calculate'])
  assert.match(flow.sortingError.value,/retry/)
  assert.equal(flow.navigationBlocked.value,false)
  assert.equal(flow.canEnter('explore_2d'),false)
  failSorting=false
  await flow.submitOrder(['calculate','centers','count','data'])
  assert.equal(flow.reflection.value,null)
  assert.equal(flow.canEnter('explore_2d'),false)
  await flow.submitOrder(['data','count','centers','calculate'])
  assert.equal(flow.review('explore_2d'),false)
  flow.measurementSaved({id:'measurement-2'});flow.continueReflection()
  assert.equal(flow.activity.value.id,'explore_2d')
  assert.equal(flow.operationOpen.value,true)
  flow.taskBusy.value=true
  assert.equal(flow.review('group_books'),false)
  assert.equal(flow.resetFlow(),false)
  flow.taskBusy.value=false
  assert.equal(flow.review('group_books'),true)
  assert.equal(flow.canEnter('explore_2d'),true,'returning must preserve unlocks')
  assert.equal(flow.sortingCorrect.value,null)
  assert.equal(flow.explorationHint.value,'')
  flow.review('explore_2d')
  const analysis={id:'analysis',sample_count:4,groups:[],features:[]}
  flow.explorationCalculated(analysis)
  flow.explorationSubmitted({id:'submission-3',created:new Date().toISOString(),result_id:'analysis',payload:{student_result:{counts:[2,2],description:'test'}}})
  flow.measurementSaved({id:'measurement-3'});flow.continueReflection()
  assert.equal(flow.recordsOpen.value,true)
  assert.equal(flow.complete.value,true)
  assert.equal(openings,condition==='C'?3:0)
  assert.equal(flow.resetFlow(),true)
  assert.notEqual(flow.state.value.sessionId,session)
  assert.equal(flow.complete.value,false)
  assert.equal(flow.reflection.value,null)
  await nextTick();scope.stop()
  console.log(`Passed ${condition}: fixed source, submission/measurement gates, failures, discussion policy, busy guards, review and reset.`)
}
