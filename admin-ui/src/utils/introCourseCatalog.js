/**
 * دروس ترم اول دوره آشنایی — هم‌نام با دمو و تست‌ها (theory_1 … theory_5).
 */
export const INTRODUCTORY_TERM1_COURSES = [
  { value: 'theory_1', label_fa: 'تئوری روانکاوی ۱' },
  { value: 'theory_2', label_fa: 'تئوری روانکاوی ۲' },
  { value: 'theory_3', label_fa: 'تئوری روانکاوی ۳' },
  { value: 'theory_4', label_fa: 'تئوری روانکاوی ۴' },
  { value: 'theory_5', label_fa: 'تئوری روانکاوی ۵' },
]

const LABEL_BY_VALUE = Object.fromEntries(
  INTRODUCTORY_TERM1_COURSES.map((c) => [c.value, c.label_fa]),
)

/** نمایش فارسی آرایهٔ کد درس */
export function formatCourseCodesDisplay(codes) {
  const list = Array.isArray(codes) ? codes : []
  if (!list.length) return ''
  return list.map((c) => LABEL_BY_VALUE[c] || c).join('، ')
}
