import portalRoleMap from '../../../metadata/portal_role_assigned_role_map.json' with { type: 'json' }
import {
  canonicalPortalRole,
  operatorPortalRoles,
  orderedActorRoles,
  primaryRole,
} from './userRoles.js'

const TYPO_MAP = portalRoleMap.normalize_assigned_role_typo || {}

export function normalizeAssignedRole(code) {
  if (!code || !String(code).trim()) return ''
  const c = String(code).trim()
  return TYPO_MAP[c] || c
}

/**
 * نقش‌های assigned_role که این portal role می‌تواند روی آن‌ها اقدام کند.
 * admin → null (همهٔ مراحل اپراتوری).
 */
export function resolveAssignedRolesForPortalRole(portalRole) {
  if (!portalRole) return []
  const lookup = canonicalPortalRole(portalRole) || portalRole
  const cfg = portalRoleMap.portal_roles?.[lookup] || portalRoleMap.portal_roles?.[portalRole]
  if (!cfg) return []
  if (cfg.include_all_operator_assigned_roles) return null
  return (cfg.assigned_roles || []).map(normalizeAssignedRole)
}

export function portalRoleCanActOnState(portalRole, stateAssignedRole) {
  if (!portalRole || !stateAssignedRole) return false
  const allowed = resolveAssignedRolesForPortalRole(portalRole)
  if (allowed === null) return true
  const normalized = normalizeAssignedRole(stateAssignedRole)
  return allowed.includes(normalized)
}

export function anyPortalRoleCanActOnState(roles, stateAssignedRole) {
  if (!stateAssignedRole) return false
  const list = (Array.isArray(roles) ? roles : []).filter(Boolean)
  if (list.includes('admin')) return true
  return list.some((r) => portalRoleCanActOnState(r, stateAssignedRole))
}

export function effectivePortalRole(user, stateAssignedRole) {
  const ordered = orderedActorRoles(user)
  if (stateAssignedRole) {
    const hit = ordered.find((r) => portalRoleCanActOnState(r, stateAssignedRole))
    if (hit) return hit
  }
  return primaryRole(user)
}

export function formRolesForUser(user, fallbackRole) {
  const fromUser = operatorPortalRoles(user)
  if (fromUser.length) return fromUser
  const r = String(fallbackRole || primaryRole(user) || '').trim()
  return r ? [r] : []
}
