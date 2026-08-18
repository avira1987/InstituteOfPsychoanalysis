import React, { useEffect, useState } from 'react'
import { studentApi } from '../services/api'

const COURSE_OPTIONS = [
  { value: 'introductory', label: 'دوره آشنایی' },
  { value: 'comprehensive', label: 'دوره جامع' },
]

export function courseTypeLabelFa(courseType) {
  if (courseType === 'comprehensive') return 'جامع'
  if (courseType === 'introductory') return 'آشنایی'
  return courseType || '—'
}

/**
 * ویرایش نوع دورهٔ انتخاب‌شده در فرم اولیهٔ ثبت‌نام (ادمین / پذیرش).
 * @param {{ studentId: string, initialCourseType?: string, onSaved?: (result: object) => void, showToast?: (msg: string, type?: string) => void, compact?: boolean }} props
 */
export default function RegistrationCourseTypeEditor({
  studentId,
  initialCourseType = 'introductory',
  onSaved,
  showToast,
  compact = false,
}) {
  const [courseType, setCourseType] = useState(initialCourseType || 'introductory')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setCourseType(initialCourseType || 'introductory')
  }, [initialCourseType, studentId])

  const save = async () => {
    if (!studentId) return
    setBusy(true)
    try {
      const res = await studentApi.updateRegistrationCourseType(studentId, {
        course_type: courseType,
        reason: reason.trim() || undefined,
      })
      const data = res.data || {}
      if (data.changed) {
        showToast?.(
          `نوع دوره از «${courseTypeLabelFa(data.previous_course_type)}» به «${courseTypeLabelFa(data.course_type)}» تغییر کرد.`,
        )
      } else {
        showToast?.('نوع دوره تغییری نکرد.')
      }
      onSaved?.(data)
      setReason('')
    } catch (e) {
      const d = e?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در تغییر نوع دوره', 'error')
    } finally {
      setBusy(false)
    }
  }

  if (!studentId) return null

  return (
    <div
      className="registration-course-type-editor"
      data-testid="registration-course-type-editor"
      style={{
        marginBottom: compact ? 0 : '1rem',
        padding: compact ? '0.75rem' : '1rem 1.25rem',
        background: '#f0f9ff',
        borderRadius: '10px',
        borderRight: '4px solid #0284c7',
      }}
    >
      <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.5rem', color: '#0c4a6e' }}>
        نوع دورهٔ ثبت‌نام اولیه
      </h4>
      {!compact && (
        <p style={{ fontSize: '0.8rem', color: '#0369a1', margin: '0 0 0.65rem', lineHeight: 1.6 }}>
          همان انتخابی که دانشجو در فرم اولیهٔ ثبت‌نام (آشنایی یا جامع) انجام داده است.
          با تغییر، فرایند ثبت‌نام نادرستِ در جریان لغو و مسیر دورهٔ جدید فعال می‌شود.
        </p>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'flex-end' }}>
        <label style={{ flex: '1 1 200px', fontSize: '0.88rem' }}>
          <span style={{ fontWeight: 600, display: 'block', marginBottom: '0.35rem' }}>دوره</span>
          <select
            className="form-input"
            value={courseType}
            onChange={(e) => setCourseType(e.target.value)}
            data-testid="registration-course-type-select"
          >
            {COURSE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>
        {!compact && (
          <label style={{ flex: '2 1 260px', fontSize: '0.88rem' }}>
            <span style={{ fontWeight: 600, display: 'block', marginBottom: '0.35rem' }}>دلیل (اختیاری)</span>
            <input
              className="form-input"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="مثلاً: اشتباه در انتخاب هنگام ثبت‌نام"
            />
          </label>
        )}
        <button
          type="button"
          className="btn btn-primary btn-sm"
          data-testid="registration-course-type-save"
          disabled={busy || courseType === initialCourseType}
          onClick={save}
        >
          {busy ? 'در حال ذخیره…' : 'ذخیرهٔ نوع دوره'}
        </button>
      </div>
    </div>
  )
}
