import {submissionBody,submissionSaved} from './telemetry'
export interface Calculation {
  id:string; previous_id:string|null; round:number; centers_before:number[]; centers_after:number[];
  converged:boolean; warnings:string[];
  records:{id:string;name:string;value:number;group:number;distances:number[]}[];
  groups:{group:number;count:number;values:number[];center:number}[];
  teaching_context:Record<string,unknown>;
}
export interface CalculationSubmission {id:string;created:string;result_id:string;payload:{student_result:{counts:number[];centers:number[]};tool_result:{counts:number[];centers:number[]};calculation_result:Calculation}}
export async function calculationRequest<T>(session:string,path:string,body?:unknown):Promise<T>{
    const request=body&&(path==='submissions'||path==='round-answers')?submissionBody(session,path,body):null
    if(request)body=request.body
  const response=await fetch(`/api/projects/teaching-agent/activities/group_books/${path}`,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-Session-ID':session},body:body?JSON.stringify(body):undefined})
  const data=await response.json().catch(()=>null)
  if(!response.ok)throw new Error(typeof data?.detail==='string'?data.detail:'计算服务暂时不可用，请检查后端后重试。')
    if(request)submissionSaved(request.key)
  return data
}
