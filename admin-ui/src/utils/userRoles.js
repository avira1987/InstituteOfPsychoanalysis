/** نقش‌های چندگانهٔ کاربر پورتال — primary در user.role */

function normalizeRoleCode(code) {
  if (code == null || code === '') return ''
  return String(code).trim().toLowerCase()
}

export function getUserRoles(user) {
  if (!user) return []
  const raw = Array.isArray(user.roles) ? user.roles : []
  const out = []
  const seen = new Set()
  for (const item of raw) {
    const code = normalizeRoleCode(item)
    if (!code || seen.has(code)) continue
    seen.add(code)
    out.push(code)
  }
  const primary = normalizeRoleCode(user.role)
  if (primary && !seen.has(primary)) {
    out.unshift(primary)
  }
  if (!out.length && primary) return [primary]
  return out
}

export function userHasRole(user, code, { adminBypass = true } = {}) {
  const needed = normalizeRoleCode(code)
  if (!needed) return false
  const have = getUserRoles(user)
  if (adminBypass && have.includes('admin')) return true
  return have.includes(needed)
}

export function userHasAnyRole(user, codes, { adminBypass = true } = {}) {
  if (!codes || !codes.length) return false
  const have = new Set(getUserRoles(user))
  if (adminBypass && have.has('admin')) return true
  return codes.some((c) => have.has(normalizeRoleCode(c)))
}

export function primaryRole(user) {
  const p = normalizeRoleCode(user?.role)
  if (p) return p
  const roles = getUserRoles(user)
  return roles[0] || 'student'
}
