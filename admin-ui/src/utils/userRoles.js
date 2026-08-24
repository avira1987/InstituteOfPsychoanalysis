/** نقش‌های چندگانهٔ کاربر پورتال — primary در user.role */

function normalizeRoleCode(code) {
  if (code == null || code === '') return ''
  return String(code).trim().toLowerCase()
}

/** نقش سازمانی که قابلیت نقش‌های پورتال را هم دارد */
const ROLE_IMPLIES = {
  faculty_1: ['supervisor', 'interviewer'],
  educational_instructor: ['instructor'],
  internal_manager: ['staff'],
}

/** نقش ورود که برای خانه/منو/دسترسی معادل نقش دیگری است */
const PORTAL_ROLE_CANONICAL = {
  internal_manager: 'staff',
}

export function canonicalPortalRole(code) {
  const normalized = normalizeRoleCode(code)
  if (!normalized) return ''
  return PORTAL_ROLE_CANONICAL[normalized] || normalized
}

function expandedRoles(have) {
  const out = new Set(have)
  for (const code of have) {
    for (const implied of ROLE_IMPLIES[code] || []) out.add(implied)
  }
  return out
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
  const have = expandedRoles(getUserRoles(user))
  if (adminBypass && have.has('admin')) return true
  return have.has(needed)
}

export function userHasAnyRole(user, codes, { adminBypass = true } = {}) {
  if (!codes || !codes.length) return false
  const have = expandedRoles(getUserRoles(user))
  if (adminBypass && have.has('admin')) return true
  return codes.some((c) => have.has(normalizeRoleCode(c)))
}

/** آیا یک کد نقش (با impliedهایی مثل faculty_1 → interviewer) در فهرست مجاز است؟ */
export function roleMatchesAllowedList(role, allowed) {
  const allowedNorm = (Array.isArray(allowed) ? allowed : [])
    .map(normalizeRoleCode)
    .filter(Boolean)
  if (!allowedNorm.length) return true
  const r = normalizeRoleCode(role)
  if (!r) return false
  if (allowedNorm.includes(r)) return true
  const canon = canonicalPortalRole(r)
  if (canon && allowedNorm.includes(canon)) return true
  const have = expandedRoles([r, canon].filter(Boolean))
  return allowedNorm.some((code) => have.has(code))
}

export function primaryRole(user) {
  const p = normalizeRoleCode(user?.role)
  if (p) return p
  const roles = getUserRoles(user)
  return roles[0] || 'student'
}

export function orderedActorRoles(user) {
  const stored = getUserRoles(user)
  const prim = primaryRole(user)
  const ordered = []
  const seen = new Set()
  const add = (code) => {
    const n = normalizeRoleCode(code)
    if (!n || seen.has(n)) return
    seen.add(n)
    ordered.push(n)
  }
  add(prim)
  for (const code of stored) add(code)
  for (const code of [...ordered]) {
    for (const implied of [...(ROLE_IMPLIES[code] || [])].sort()) add(implied)
  }
  return ordered
}

const STUDENT_PORTAL_ROLES = new Set(['student', 'applicant'])

export function operatorPortalRoles(user) {
  if (primaryRole(user) === 'student') return []
  return orderedActorRoles(user).filter((c) => !STUDENT_PORTAL_ROLES.has(c))
}
