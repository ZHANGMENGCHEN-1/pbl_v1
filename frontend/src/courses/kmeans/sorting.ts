export const algorithmSteps=[
  {id:'data',text:'获取原始数据并整理'},
  {id:'count',text:'确定中心点的数量'},
  {id:'centers',text:'随机选择中心点'},
  {id:'calculate',text:'进行计算'},
] as const
export function shuffledSteps(){
  const order=algorithmSteps.map(s=>String(s.id))
  for(let i=order.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[order[i],order[j]]=[order[j]!,order[i]!]}
  if(order.every((id,i)=>id===algorithmSteps[i]!.id))order.push(order.shift()!)
  return order
}
export function checkStepOrder(order:string[]){
  if(order.length!==4||new Set(order).size!==4||order.some(id=>!algorithmSteps.some(s=>s.id===id)))return {correct:false,feedback:'四个步骤都需要用到。请把四张卡片排好，再提交一次。'}
  const reasons=[
    '先要拿到数据，整理好每本书的借阅次数，我们才知道要给哪些书分组。试着把“获取原始数据并整理”放到最前面。',
    '有了数据，要先想好分成几组，也就是需要几个中心点。还没确定数量，就不知道该选几个中心。把“确定中心点的数量”放在整理数据后面试试。',
    '先选好开始的中心，才能算每本书离哪个中心更近。试着把“随机选择中心点”放在“进行计算”前面。',
    '准备好数据、中心点的数量和开始的中心后，才开始计算距离、分组，再更新中心。把“进行计算”放在最后试试。',
  ]
  const index=order.findIndex((id,i)=>id!==algorithmSteps[i]!.id)
  return index<0?{correct:true,feedback:'这个顺序很清楚！先整理数据，再确定需要几个中心，然后随机选出开始的中心，最后进行计算。计算时，我们会反复算距离、分组、更新中心，直到分组和中心稳定。你的排序已经提交了。'}:{correct:false,feedback:reasons[index]!+' 调整后可以再提交。'}
}
