/** New activity attempt: avoid both the canonical and previous saved order. */
export function shuffledSteps(ids: string[], previous: string[] = []): string[] {
  const next = [...ids]
  for (let i = next.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[next[i], next[j]] = [next[j]!, next[i]!]
  }
  const same = (other: string[]) => next.length === other.length && next.every((id, i) => id === other[i])
  if (next.length > 2) {
    while (same(ids) || same(previous)) next.push(next.shift()!)
  }
  return next
}
