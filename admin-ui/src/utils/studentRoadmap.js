/** ترتیب نمایش مراحل از روی گراف انتقال‌ها (DFS از initial_state). */
export function buildRoadmapStates(def) {
  if (!def?.states?.length) return []
  const initial = def.process?.initial_state
  const states = def.states
  const trans = def.transitions || []
  const codeSet = new Set(states.map(s => s.code))
  const adj = new Map()
  for (const t of trans) {
    if (!t.from || !t.to || !codeSet.has(t.from) || !codeSet.has(t.to)) continue
    if (!adj.has(t.from)) adj.set(t.from, [])
    adj.get(t.from).push(t.to)
  }
  const visited = []
  const seen = new Set()
  function walk(code) {
    if (seen.has(code)) return
    seen.add(code)
    visited.push(code)
    for (const n of adj.get(code) || []) walk(n)
  }
  if (initial) walk(initial)
  for (const s of states) {
    if (!seen.has(s.code)) visited.push(s.code)
  }
  return visited.map(code => states.find(s => s.code === code)).filter(Boolean)
}
