/**
 * نمایش برچسب دروس از context منتشرشده (بدون کاتالوگ ثابت).
 */

export function formatCourseCodesDisplay(codes, labels = {}) {
  const list = Array.isArray(codes) ? codes : []
  if (!list.length) return ''
  const map = labels && typeof labels === 'object' ? labels : {}
  return list.map((c) => map[c] || c).join('، ')
}

export function formatCourseOptionLabel(opt) {
  if (!opt || typeof opt !== 'object') return String(opt || '')
  const base = opt.label_fa || opt.value || ''
  const units = opt.units != null && opt.units !== '' ? Number(opt.units) : null
  if (Number.isFinite(units) && units > 0) {
    return `${base} — ${units.toLocaleString('fa-IR')} واحد`
  }
  return base
}

export function formatRialAsToman(rial) {
  try {
    const n = Number(rial)
    if (!Number.isFinite(n) || n <= 0) return ''
    return `${Math.round(n / 10).toLocaleString('fa-IR')} تومان`
  } catch {
    return ''
  }
}

/** گزینه‌های درس از context نمونه فرایند (خروجی آماده‌سازی ترم). */
export function optionsFromContext(contextData) {
  const ctx = contextData && typeof contextData === 'object' ? contextData : {}
  const raw = ctx.available_course_options
  if (Array.isArray(raw) && raw.length) {
    return raw.map((o) => {
      const item = {
        value: String(o.value),
        label_fa: o.label_fa || String(o.value),
        day: o.day,
        time_text: o.time_text,
        classroom_location: o.classroom_location,
        instructor_name: o.instructor_name,
        units: o.units,
        prerequisite_codes: o.prerequisite_codes,
        track: o.track,
        per_unit_cost_rial: o.per_unit_cost_rial,
        line_amount_rial: o.line_amount_rial,
      }
      item.display_label_fa = formatCourseOptionLabel(item)
      return item
    })
  }
  const codes = ctx.available_courses || ctx.lms?.available_courses || []
  const labelMap = ctx.course_labels || {}
  if (Array.isArray(codes) && codes.length) {
    return codes.map((c) => ({
      value: String(c),
      label_fa: labelMap[c] || String(c),
      display_label_fa: labelMap[c] || String(c),
    }))
  }
  return []
}

/** خلاصهٔ شهریه از context (tuition_lines + جمع). */
export function tuitionQuoteFromContext(contextData) {
  const ctx = contextData && typeof contextData === 'object' ? contextData : {}
  const lines = Array.isArray(ctx.tuition_lines) ? ctx.tuition_lines : []
  const totalRial =
    ctx.tuition_total_rial != null
      ? Number(ctx.tuition_total_rial)
      : ctx.tuition_amount_rial != null
        ? Number(ctx.tuition_amount_rial)
        : ctx.payable_amount_rial != null
          ? Number(ctx.payable_amount_rial)
          : null
  const totalUnits = lines.reduce((sum, line) => {
    const u = Number(line?.units)
    return sum + (Number.isFinite(u) && u > 0 ? u : 0)
  }, 0)
  return {
    lines,
    totalRial: Number.isFinite(totalRial) && totalRial > 0 ? totalRial : null,
    totalUnits: totalUnits > 0 ? totalUnits : null,
    totalTomanLabel: formatRialAsToman(totalRial),
  }
}

export const NO_OFFERINGS_HINT_FA =
  'لیست دروس این ترم هنوز از فرایند آماده‌سازی ترم منتشر نشده است؛ پس از انتشار توسط انستیتو این بخش فعال می‌شود.'
