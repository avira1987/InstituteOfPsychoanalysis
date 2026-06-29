/** نمایش مشترک فرایند ۵۷ — ارزیابی دانشجو از مدرسین */

import React from 'react'

export const PROCESS_TITLE_FA = 'ارزیابی دانشجو از مدرسین (فرایند ۵۷)'

export const ANONYMITY_NOTICE_FA =
  'بازخورد شما در رابطه با مدرسین و نحوه آموزش برای ما بسیار ارزشمند است. '
  + 'نام شما به‌عنوان پاسخ‌دهنده در سیستم ارزیابی قابل شناسایی نخواهد بود. '
  + 'پر کردن فرم کاملاً اختیاری است و عدم تکمیل هیچ محدودیتی در دسترسی‌های آموزشی ایجاد نمی‌کند.'

export const EVAL_FLOW_STEPS = [
  { key: 'open', label: 'مهلت ارزیابی', states: ['evaluation_open'] },
  { key: 'closed', label: 'پایان مهلت', states: ['evaluation_closed'] },
]

export const EVAL_STATE_LABELS = {
  evaluation_open: 'مهلت ارزیابی — تکمیل فرم',
  evaluation_closed: 'پایان مهلت — محاسبات و توزیع نتایج',
}

export const SCORE_FIELDS = [
  { name: 'overall_score', label_fa: 'نمره کلی کیفیت تدریس' },
  { name: 'teaching_clarity', label_fa: 'شفافیت و انتقال مطلب' },
  { name: 'interaction_quality', label_fa: 'کیفیت تعامل با دانشجویان' },
]

export function labelEvaluationState(state) {
  if (!state) return '—'
  return EVAL_STATE_LABELS[state] || state
}

export function activeEvalStepIndex(currentState) {
  if (!currentState) return 0
  if (currentState === 'evaluation_closed') return EVAL_FLOW_STEPS.length - 1
  const idx = EVAL_FLOW_STEPS.findIndex((s) => s.states.includes(currentState))
  return idx >= 0 ? idx : 0
}

function courseCode(entry) {
  if (typeof entry === 'string') return entry
  if (!entry || typeof entry !== 'object') return ''
  return String(entry.course_code || entry.code || entry.course_name || entry.name_fa || '').trim()
}

function courseName(entry, code) {
  if (typeof entry === 'object' && entry) {
    return String(
      entry.course_name || entry.name_fa || entry.title_fa || code,
    ).trim()
  }
  return code
}

function instructorFromEntry(entry) {
  if (!entry || typeof entry !== 'object') return { instructor_id: null, instructor_name: 'مدرس' }
  return {
    instructor_id: entry.instructor_id || entry.instructor_user_id || null,
    instructor_name: String(
      entry.instructor_name || entry.instructor || entry.teacher_name || 'مدرس',
    ).trim(),
  }
}

/** فهرست دروس قابل ارزیابی از extra_data دانشجو. */
export function resolveEvaluationCourses(extraData = {}, contextData = {}) {
  const lms = extraData?.lms || {}
  const enrolled = lms.enrolled_courses || lms.course_links || []
  const instructorsBy = lms.instructors_by_course || {}
  const termCode = contextData.term_code || null
  const submitted = new Set(
    (contextData.submitted_course_codes || []).map((c) => String(c)),
  )
  const seen = new Set()
  const rows = []
  if (!Array.isArray(enrolled)) return rows
  enrolled.forEach((entry) => {
    const code = courseCode(entry)
    if (!code || seen.has(code)) return
    seen.add(code)
    let { instructor_id: iid, instructor_name: iname } = instructorFromEntry(entry)
    if (!iid && !iname) {
      const ibc = instructorsBy[code]
      if (ibc && typeof ibc === 'object') {
        ({ instructor_id: iid, instructor_name: iname } = instructorFromEntry(ibc))
      } else if (typeof ibc === 'string' && ibc.trim()) {
        iname = ibc.trim()
      }
    }
    rows.push({
      course_code: code,
      course_name: courseName(entry, code),
      instructor_id: iid,
      instructor_name: iname || 'مدرس',
      term_code: termCode,
      submitted: submitted.has(code),
    })
  })
  return rows
}

export function buildCourseSubmissionPayload(formState) {
  return {
    overall_score: Number(formState.overall_score),
    teaching_clarity: Number(formState.teaching_clarity),
    interaction_quality: Number(formState.interaction_quality),
    comments: formState.comments?.trim() || null,
  }
}

export function validateCourseForm(formState) {
  const missing = []
  SCORE_FIELDS.forEach(({ name, label_fa }) => {
    const v = formState[name]
    const n = Number(v)
    if (!Number.isFinite(n) || n < 1 || n > 5) missing.push(label_fa)
  })
  return { ok: missing.length === 0, missing }
}

export function EvaluationFlowStepper({ currentState, compact = false }) {
  const activeIdx = activeEvalStepIndex(currentState)
  return (
    <div
      data-testid="eval-flow-stepper"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: compact ? '0.35rem' : '0.5rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {EVAL_FLOW_STEPS.map((step, idx) => {
        const done = idx < activeIdx
        const active = idx === activeIdx
        return (
          <div
            key={step.key}
            style={{
              flex: '1 1 120px',
              padding: compact ? '0.45rem 0.55rem' : '0.55rem 0.7rem',
              borderRadius: '8px',
              fontSize: compact ? '0.75rem' : '0.8rem',
              fontWeight: active ? 700 : 500,
              textAlign: 'center',
              background: done ? '#dcfce7' : active ? '#eff6ff' : '#f8fafc',
              color: done ? '#166534' : active ? '#1d4ed8' : '#64748b',
              border: `1px solid ${done ? '#86efac' : active ? '#93c5fd' : '#e2e8f0'}`,
            }}
          >
            {step.label}
          </div>
        )
      })}
    </div>
  )
}

export function ScorePicker({ label, value, onChange, disabled = false, name }) {
  const selected = value != null && value !== '' ? Number(value) : null
  return (
    <div className="psf-field" style={{ marginBottom: '0.65rem' }}>
      <span className="psf-label" style={{ display: 'block', marginBottom: '0.35rem' }}>
        {label}
        {' '}
        *
      </span>
      <div
        role="radiogroup"
        aria-label={label}
        data-testid={name ? `score-picker-${name}` : undefined}
        style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}
      >
        {[1, 2, 3, 4, 5].map((n) => {
          const on = selected === n
          return (
            <button
              key={n}
              type="button"
              role="radio"
              aria-checked={on}
              disabled={disabled}
              onClick={() => onChange(String(n))}
              style={{
                minWidth: '2.25rem',
                height: '2.25rem',
                borderRadius: '8px',
                border: `2px solid ${on ? '#2563eb' : '#cbd5e1'}`,
                background: on ? '#2563eb' : '#fff',
                color: on ? '#fff' : '#334155',
                fontWeight: 700,
                cursor: disabled ? 'not-allowed' : 'pointer',
                opacity: disabled ? 0.6 : 1,
              }}
            >
              {n.toLocaleString('fa-IR')}
            </button>
          )
        })}
      </div>
    </div>
  )
}

export function fmtDeadline(iso) {
  if (!iso) return null
  try {
    return new Date(iso).toLocaleString('fa-IR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}
