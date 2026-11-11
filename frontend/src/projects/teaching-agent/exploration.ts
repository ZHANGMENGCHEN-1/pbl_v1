export interface ExcelColumn {id:string;name:string;numeric_count:number}
export interface ExcelRow {row:number;values:(string|number|boolean|null)[]}
export interface Dataset {id:string;filename:string;version:string;sheet:string;sheet_count:number;columns:ExcelColumn[];row_count:number;default_features:string[];preview:ExcelRow[]}
export interface Excluded {row:number;reasons:string[]}
export interface DataPreview {dataset_id:string;dataset_version:string;features:string[];total_count:number;sample_count:number;excluded:Excluded[]}
export interface Analysis {
 id:string;dataset_id:string;dataset_version:string;filename:string;sheet:string;features:ExcelColumn[];
 total_count:number;sample_count:number;excluded_count:number;excluded:Excluded[];columns:ExcelColumn[];
 groups:{group:number;count:number;center:number[]}[];points:(ExcelRow&{coordinates:number[];group:number})[];
 converged:boolean;iterations:number;warnings:string[];teaching_context:Record<string,unknown>;
}
export interface ExplorationSubmission {id:string;result_id:string;created:string;payload:{student_result:{counts:number[];description:string};tool_result:{counts:number[];centers:number[][]};dataset_id:string;dataset_version:string;features:ExcelColumn[];teaching_context:Record<string,unknown>}}
export async function explorationRequest<T>(session:string,path:string,body?:unknown,file?:File):Promise<T>{
 let response:Response
 try{response=await fetch(`/api/projects/teaching-agent/activities/explore_2d/${path}`,{method:body||file?'POST':'GET',headers:{'X-Session-ID':session,'Content-Type':file?'application/octet-stream':'application/json',...(file?{'X-File-Name':encodeURIComponent(file.name)}:{})},body:file??(body?JSON.stringify(body):undefined)})}catch{throw new Error('连接不上计算服务，请检查后端是否已启动，再试一次。')}
 const data=await response.json().catch(()=>null)
 if(!response.ok)throw new Error(typeof data?.detail==='string'?data.detail:response.status===413?'文件太大，请使用5MB以内的.xlsx文件。':'这次操作没有完成，请检查数据和后端服务后重试。')
 return data
}
