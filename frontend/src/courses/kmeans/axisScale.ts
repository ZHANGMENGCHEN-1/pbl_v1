/** Whole-number grid; positive data starts at zero. Negative values remain visible. */
export function axisScale(values:number[]){
  const lower=Math.min(0,...values),upper=Math.max(0,...values)
  const target=Math.max(1,(upper-lower)*1.05/5)
  const magnitude=10**Math.floor(Math.log10(target))
  const step=[1,2,5,10].map(n=>n*magnitude).find(n=>n>=target)!
  const min=Math.floor(lower/step)*step,max=Math.max(min+step,Math.ceil(upper*1.05/step)*step)
  const ticks=Array.from({length:Math.round((max-min)/step)+1},(_,i)=>min+i*step)
  return {min,max,ticks}
}
