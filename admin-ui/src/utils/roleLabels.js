import roleLabelsJson from '../../../metadata/role_labels_fa.json' with { type: 'json' }

const LABELS = roleLabelsJson.labels || {}
const TYPO_ALIASES = roleLabelsJson.typo_aliases || {}

/** نرمال‌سازی کد نقش (trim + aliasهای رایج). */
export function normalizeRoleCode(code) {
  if (code == null || code === '') return ''
  const raw = String(code).trim().toLowerCase()
  if (!raw) return ''
  return TYPO_ALIASES[raw] || raw
}

/** برچسب فارسی خام بدون کد انگلیسی. */
export function roleLabelFaOnly(code) {
  const normalized = normalizeRoleCode(code)
  if (!normalized) return '—'
  return LABELS[normalized] || 'نقش نامشخص'
}

/**
 * برچسب نمایشی نقش: «نام فارسی (کد)».
 * @param {string|null|undefined} code
 * @param {{ includeCode?: boolean }} [opts]
 */
export function labelRoleFa(code, { includeCode = true } = {}) {
  const normalized = normalizeRoleCode(code)
  if (!normalized) return '—'
  const fa = LABELS[normalized] || 'نقش نامشخص'
  if (!includeCode) return fa
  return `${fa} (${normalized})`
}

/** alias — assigned_role در متادیتای فرایند */
export const labelAssignedRoleFa = labelRoleFa

/** alias — User.role در پورتال */
export const labelPortalRoleFa = labelRoleFa

/** alias — actor_role در تاریخچه */
export const formatActorRole = labelRoleFa

export { LABELS as ROLE_LABELS_FA_MAP }
