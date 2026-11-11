// Run with the project's Node.js: node scripts/teaching_learning_state_smoke.mjs
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import ts from '../frontend/node_modules/typescript/lib/typescript.js'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../frontend/src/projects/teaching-agent')
const cache=new Map()
function load(name){
  const file=path.resolve(root,name.endsWith('.ts')?name:name+'.ts')
  if(cache.has(file))return cache.get(file)
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
  const module={exports:{}};cache.set(file,module.exports)
  new Function('module','exports','require',code)(module,module.exports,dependency=>load(dependency))
  return module.exports
}

const {createSession,canEnter,enterActivity,submitPreview,submittedCount,restoreSession,recordCalculation,recordStepOrder,recordExploration}=load('learningState')
const state=createSession()
assert.equal(canEnter(state,'explain_algorithm'),false)
assert.throws(()=>submitPreview(state))
assert.ok(restoreSession(JSON.parse(JSON.stringify(state))))
const result={id:'real-round',converged:true,centers_after:[17/3,17]}
const saved={id:'saved-result',created:new Date().toISOString(),result_id:'real-round',payload:{calculation_result:result,student_result:{counts:[4,1],centers:[1,18]},tool_result:{counts:[3,2],centers:[17/3,17]}}}
recordCalculation(state,saved)
assert.equal(state.activeActivityId,'explain_algorithm')
assert.equal(submittedCount(state),1)
assert.equal(canEnter(state,'explore_2d'),false)
state.activities.group_books.draft.note='changed draft'
assert.equal(state.activities.group_books.submissions[0].payload.note,'')
recordCalculation(state,saved,false)
assert.equal(state.activities.group_books.submissions.length,1)
const wrong=recordStepOrder(state,['calculate','data','count','centers'])
assert.equal(wrong.correct,false)
assert.ok(wrong.feedback.includes('整理'))
assert.equal(canEnter(state,'explore_2d'),false)
assert.throws(()=>submitPreview(state))
recordStepOrder(state,['data','count','centers','calculate'])
assert.equal(canEnter(state,'explore_2d'),true)
assert.equal(state.activities.explain_algorithm.submissions.length,2)
assert.equal(state.activities.explain_algorithm.submissions[0].payload.sorting.correct,false)
enterActivity(state,'explore_2d')
assert.equal(state.activeActivityId,'explore_2d')
assert.deepEqual(restoreSession(JSON.parse(JSON.stringify(state))),state)
const invalid=createSession();invalid.activeActivityId='explore_2d'
assert.equal(restoreSession(invalid),null)
console.log('Passed: real calculation evidence required, immutable submissions, idempotent restore, stage unlock and persistence.')

const {shuffledSteps,checkStepOrder}=load('sorting')
const canonical=['data','count','centers','calculate']
for(let i=0;i<100;i++){
  const shuffled=shuffledSteps()
  assert.notDeepEqual(shuffled,canonical)
  assert.deepEqual([...shuffled].sort(),[...canonical].sort())
}
function permutations(list){return list.length?list.flatMap((x,i)=>permutations(list.filter((_,j)=>i!==j)).map(rest=>[x,...rest])):[[]]}
for(const order of permutations(canonical)){
  const result=checkStepOrder(order)
  assert.equal(result.correct,order.join()===canonical.join())
  assert.ok(result.feedback.length>10)
}
assert.equal(checkStepOrder(['data','data','centers','calculate']).correct,false)
console.log('Passed: randomized initial order, all 24 orderings, concrete feedback and immutable retry records.')
const analysis={id:'real-analysis',dataset_id:'uploaded-data',dataset_version:'immutable-version',sample_count:150,groups:[{count:75},{count:75}]}
const submission={id:'excel-submission',result_id:analysis.id,created:new Date().toISOString(),payload:{student_result:{counts:[149,1],description:'两组的位置不同'},tool_result:{counts:[75,75]},features:[],teaching_context:{filename:'uploaded.xlsx'}}}
recordExploration(state,submission,analysis)
assert.equal(submittedCount(state),3)
assert.ok(restoreSession(state))
analysis.groups[0].count=1
assert.equal(state.activities.explore_2d.submissions[0].payload.operation.result.groups[0].count,75)
recordExploration(state,submission,analysis)
assert.equal(state.activities.explore_2d.submissions.length,1)
console.log('Passed: actual Excel submission completes third activity, retains distinct student answers and freezes evidence.')
const {axisScale}=load('axisScale')
for(const values of [[0,174],[2,18],[.1,.3],[0,0],[-5,20],[-8,-2]]){
  const axis=axisScale(values)
  assert.ok(axis.max>axis.min)
  assert.ok(axis.min<=Math.min(...values)&&axis.max>=Math.max(...values))
  assert.ok(axis.ticks.includes(0)&&axis.ticks.every(Number.isInteger))
  if(values.every(v=>v>=0))assert.equal(axis.min,0)
}
console.log('Passed: integer chart ticks, zero origin, visible extrema, small and negative data ranges.')
