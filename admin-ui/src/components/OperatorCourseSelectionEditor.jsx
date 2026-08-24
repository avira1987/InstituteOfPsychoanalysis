import React, { useMemo, useState } from 'react'
import { processExecApi } from '../services/api'
import { formatCourseCodesDisplay, formatCourseOptionSpecs, NO_OFFERINGS_HINT_FA } from '../utils/introCourseCatalog'
import {
  resolveCheckboxListOptions,
  normalizeSelectedCoursesValue,
} from '../utils/resolveCourseFieldOptions'

const EDITABLE_BY_PROCESS = {
  introductory_course_registration: new Set(['course_selection', 'payment']),
  intro_second_semester_registration: new Set([
    'course_selection',
    'payment_method',
    'payment_processing',
  ]),
}

const FIELD_BY_PROCESS = {
  introductory_course_registration: 'selected_courses',
  intro_second_semester_registration: 'available_courses',
}

function courseFieldForProcess(processCode) {
  return FIELD_BY_PROCESS[processCode] || 'selected_courses'
}

function isEditableState(processCode, currentState) {
  const allowed = EDITABLE_BY_PROCESS[processCode]
  return !!(allowed && currentState && allowed.has(currentState))
}

/**
 * ویرایش مستقیم دروس انتخاب‌شده توسط ادمین / مسئول پذیرش.
 */
export default function OperatorCourseSelectionEditor({
  instanceId,
  processCode,
  currentState,
  contextData,
  isCompleted,
  isCancelled,
  onUpdated,
  showToast,
}) {
  const fieldName = courseFieldForProcess(processCode)
  const visible = useMemo(() => {
    if (!instanceId || !processCode || isCompleted || isCancelled) return false
    return isEditableState(processCode, currentState)
  }, [instanceId, processCode, currentState, isCompleted, isCancelled])

  const courseFieldDef = useMemo(() => {
    if (processCode === 'introductory_course_registration') {
      return {
        name: 'selected_courses',
        type: 'checkbox_list',
        source: 'available_courses_by_admission_type',
        label_fa: 'انتخاب درس',
      }
    }
    return {
      name: 'available_courses',
      type: 'checkbox_list',
      source: 'filtered_courses_by_admission_type_and_prerequisites',
      label_fa: 'دروس قابل اخذ',
    }
  }, [processCode])

  const resolved = useMemo(
    () => resolveCheckboxListOptions(courseFieldDef, contextData || {}),
    [courseFieldDef, contextData],
  )

  const currentCodes = useMemo(
    () => normalizeSelectedCoursesValue(contextData?.[fieldName]),
    [contextData, fieldName],
  )

  const [selected, setSelected] = useState(() => [...currentCodes])
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  React.useEffect(() => {
    setSelected([...currentCodes])
  }, [currentCodes.join('|'), instanceId])

  if (!visible) return null

  const options =
    resolved.options && resolved.options.length > 0 && !resolved.useFallback
      ? resolved.options
      : []

  const maxSelect = resolved.maxSelect
  const blockedOptions = Array.isArray(resolved.blockedOptions) ? resolved.blockedOptions : []
  const noOfferings = options.length === 0 && blockedOptions.length === 0

  const toggle = (code) => {
    setSelected((prev) => {
      if (prev.includes(code)) return prev.filter((x) => x !== code)
      if (maxSelect != null && prev.length >= maxSelect) return prev
      return [...prev, code]
    })
  }

  const save = async () => {
    const codes = selected
    if (!codes.length) {
      showToast?.('حداقل یک درس انتخاب کنید.', 'error')
      return
    }
    setBusy(true)
    try {
      const res = await processExecApi.operatorUpdateSelectedCourses(instanceId, {
        selected_courses: codes,
        reason: reason.trim() || undefined,
      })
      showToast?.('دروس انتخاب‌شده با موفقیت به‌روزرسانی شد.')
      onUpdated?.(res.data?.context_data)
      setReason('')
    } catch (e) {
      const d = e?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در ذخیرهٔ دروس', 'error')
    } finally {
      setBusy(false)
    }
  }

  const currentLabel = formatCourseCodesDisplay(
    currentCodes,
    contextData?.course_labels || {},
  )

  return (
    <div
      style={{
        marginBottom: '1.25rem',
        padding: '1rem 1.25rem',
        background: '#fffbeb',
        borderRadius: '10px',
        borderRight: '4px solid #d97706',
      }}
      data-testid="operator-course-selection-editor"
    >
      <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.5rem', color: '#92400e' }}>
        تغییر دروس انتخاب‌شده (ادمین / پذیرش)
      </h4>
      <p style={{ fontSize: '0.82rem', color: '#78350f', margin: '0 0 0.75rem', lineHeight: 1.65 }}>
        انتخاب فعلی در پرونده:
        {' '}
        <strong>{currentLabel || '—'}</strong>
        {resolved.hint && (
          <span style={{ display: 'block', marginTop: '0.35rem', color: '#b45309' }}>{resolved.hint}</span>
        )}
      </p>

      {noOfferings ? (
        <p className="muted" style={{ margin: '0 0 0.75rem', fontSize: '0.88rem', lineHeight: 1.65 }}>
          {resolved.hint || NO_OFFERINGS_HINT_FA}
        </p>
      ) : (
        <div style={{ display: 'grid', gap: '0.4rem', marginBottom: '0.75rem' }}>
          {options.map((opt) => {
            const specs = formatCourseOptionSpecs(opt)
            return (
              <label
                key={opt.value}
                style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', fontSize: '0.88rem' }}
              >
                <input
                  type="checkbox"
                  checked={selected.includes(opt.value)}
                  onChange={() => toggle(opt.value)}
                  disabled={
                    !selected.includes(opt.value) &&
                    maxSelect != null &&
                    selected.length >= maxSelect
                  }
                  style={{ marginTop: '0.2rem' }}
                />
                <span>
                  {opt.label_fa || opt.value}
                  {specs ? <span className="psf-course-specs">{specs}</span> : null}
                  {opt.corequisite_note_fa || opt.is_corequisite ? (
                    <span className="psf-course-specs">
                      {opt.corequisite_note_fa || 'هم‌نیاز: مردودی ترم قبل — قابل اخذ همزمان'}
                    </span>
                  ) : null}
                </span>
              </label>
            )
          })}
          {maxSelect != null && (
            <p style={{ fontSize: '0.78rem', color: '#78716c', margin: 0 }}>
              حداکثر {maxSelect} درس — انتخاب‌شده: {selected.length}
            </p>
          )}
          {Array.isArray(resolved.blockedOptions) && resolved.blockedOptions.length > 0
            ? resolved.blockedOptions.map((opt) => (
                <label
                  key={`blocked-${opt.value}`}
                  style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', fontSize: '0.88rem', opacity: 0.7 }}
                >
                  <input type="checkbox" disabled checked={false} style={{ marginTop: '0.2rem' }} />
                  <span>
                    {opt.label_fa || opt.value}
                    {opt.lock_reason_fa ? (
                      <span className="psf-course-specs">{opt.lock_reason_fa}</span>
                    ) : null}
                  </span>
                </label>
              ))
            : null}
        </div>
      )}

      <label style={{ display: 'block', marginBottom: '0.75rem', fontSize: '0.88rem' }}>
        <span style={{ fontWeight: 600 }}>دلیل تغییر (اختیاری)</span>
        <textarea
          className="form-input"
          rows={2}
          style={{ marginTop: '0.35rem' }}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="مثلاً: هماهنگی تلفنی با دانشجو"
        />
      </label>

      <button
        type="button"
        className="btn btn-primary btn-sm"
        data-testid="operator-course-selection-save"
        disabled={busy || noOfferings}
        onClick={save}
      >
        {busy ? 'در حال ذخیره…' : 'ذخیرهٔ دروس انتخاب‌شده'}
      </button>
    </div>
  )
}

export { isEditableState, courseFieldForProcess }
