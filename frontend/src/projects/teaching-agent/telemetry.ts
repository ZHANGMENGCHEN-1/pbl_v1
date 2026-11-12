// Retain the same request ID after a network failure; edits create a new attempt.
const pending=new Map<string,string>()
export function submissionBody(session:string,path:string,body:unknown){
  const key=JSON.stringify([session,path,body])
  if(!pending.has(key))pending.set(key,crypto.randomUUID())
  return {key,body:{...(body as Record<string,unknown>),request_id:pending.get(key)!}}
}
export function submissionSaved(key:string){pending.delete(key)}
export async function saveSorting(session:string,order:string[]){
  const request=submissionBody(session,'sorting',{order})
  const response=await fetch('/api/projects/teaching-agent/activities/explain_algorithm/submissions',{method:'POST',headers:{'Content-Type':'application/json','X-Session-ID':session},body:JSON.stringify(request.body)})
  const data=await response.json().catch(()=>null)
  if(!response.ok)throw new Error(typeof data?.detail==='string'?data.detail:'排序保存失败，请重试。')
  submissionSaved(request.key)
  return data as {id:string;created:string;payload:{correct:boolean;feedback:string}}
}
export async function recordActivityEntry(session:string,activity:string){
  const body={id:crypto.randomUUID(),activity_id:activity,type:'activity_entered'}
  for(let attempt=0;attempt<2;attempt++){
    try{const response=await fetch('/api/projects/teaching-agent/events',{method:'POST',headers:{'Content-Type':'application/json','X-Session-ID':session},body:JSON.stringify(body),keepalive:true});if(response.ok)return}catch{}
  }
}
