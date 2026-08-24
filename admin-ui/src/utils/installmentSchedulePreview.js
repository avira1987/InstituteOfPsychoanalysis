/** هم‌تراز app.services.tuition_installment_service.compute_installment_plan */

export function splitInstallmentAmounts(totalRial, count) {
  const total = Math.trunc(Number(totalRial) || 0)
  const n = Math.trunc(Number(count) || 0)
  if (n <= 0) return [total]
  const base = Math.trunc(total / n)
  const amounts = Array.from({ length: n }, () => base)
  amounts[n - 1] += total % n
  return amounts
}

export function addDaysIso(isoDate, days) {
  const s = String(isoDate || '').slice(0, 10)
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s)
  if (!m) return s
  const y = Number(m[1])
  const mo = Number(m[2])
  const d = Number(m[3])
  const dt = new Date(Date.UTC(y, mo - 1, d))
  dt.setUTCDate(dt.getUTCDate() + Number(days || 0))
  const gy = dt.getUTCFullYear()
  const gm = String(dt.getUTCMonth() + 1).padStart(2, '0')
  const gd = String(dt.getUTCDate()).padStart(2, '0')
  return `${gy}-${gm}-${gd}`
}

export function tehranTodayIso() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tehran',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  const map = {}
  for (const p of parts) {
    if (p.type !== 'literal') map[p.type] = p.value
  }
  return `${map.year}-${map.month}-${map.day}`
}

export function previewInstallmentPlan({
  totalRial,
  paymentMethod = 'installment',
  count,
  gapDays = 25,
  baseDueDate = null,
} = {}) {
  const total = Math.trunc(Number(totalRial) || 0)
  const n = Math.trunc(Number(count) || 0)
  const gap = Math.max(1, Math.min(365, Math.trunc(Number(gapDays) || 25)))
  const base = (baseDueDate && String(baseDueDate).slice(0, 10)) || tehranTodayIso()
  if (paymentMethod !== 'installment' || !n || n <= 1) {
    return [{ index: 1, amount_rial: total, due_at: base, status: 'pending' }]
  }
  const amounts = splitInstallmentAmounts(total, n)
  return amounts.map((amount, i) => ({
    index: i + 1,
    amount_rial: amount,
    due_at: i === 0 ? base : addDaysIso(base, gap * i),
    status: 'pending',
  }))
}

export function normalizeInstallmentPlan(plan) {
  if (!Array.isArray(plan)) return []
  return plan.filter((row) => row && typeof row === 'object')
}
