/**
 * آیا بلوک «قدم بعد / ثبت مرحله» برای دانشجو نمایش داده شود؟
 * تا وقتی فرم مرحله اجباری ناقص است، نباید دکمهٔ انتقال دیده شود (به‌جای disabled).
 */
export function showStudentTransitionCta({ transitions, transitionBlocked, detailDone }) {
  const n = transitions?.length || 0
  if (!n || detailDone) return false
  if (transitionBlocked) return false
  return true
}
