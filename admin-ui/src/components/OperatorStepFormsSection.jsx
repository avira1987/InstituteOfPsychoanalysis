import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { processExecApi } from '../services/api'
import UnifiedFormRenderer from './UnifiedFormRenderer'
import FallSemesterPrepReadonlySummary from './FallSemesterPrepReadonlySummary'
import InterviewSlotsAdmin from './InterviewSlotsAdmin'

const SUPPORTED_PROCESSES = new Set([
  'fall_semester_preparation',
  'winter_semester_preparation',
])

/** گام‌های فرایند ۲۹ — هشت مرحلهٔ عملیاتی قبل از انتشار */
const FALL_SEMESTER_STEPS = [
  { code: 'calendar_entry', label: 'تقویم آموزشی دو ترم' },
  { code: 'tuition_entry', label: 'شهریه و هزینه مصاحبه' },
  { code: 'license_check', label: 'بررسی پروانه' },
  { code: 'course_list_creation', label: 'لیست دروس، مدرسین، کمک‌مدرسین' },
  { code: 'course_finalization', label: 'مکان‌ها و هماهنگی با مدرسین' },
  { code: 'marketing_campaign', label: 'کمپین بازاریابی پذیرش' },
  { code: 'interviewer_assignment', label: 'تعیین مصاحبه‌کنندگان و بازه زمانی' },
  { code: 'interview_scheduling', label: 'زمان‌بندی دقیق اسلات‌های مصاحبه' },
]

function collectFieldNames(forms) {
  const names = []
  for (const form of forms || []) {
    for (const field of form?.fields || []) {
      if (field?.name) names.push(field.name)
    }
  }
  return names
}

function buildCoursesFinalizedFromDraft(courses) {
  if (!Array.isArray(courses) || !courses.length) return []
  return courses.map((row) => ({
    course_name: row.course_name || '',
    track: row.track || '',
    day: row.proposed_day || row.day || '',
    time: row.proposed_time || row.time || '',
    instructor: row.instructor || '',
    teaching_assistant: row.teaching_assistant || '',
    classroom_location: row.classroom_location || '',
    instructor_coordinated: Boolean(row.instructor_coordinated),
  }))
}

function buildInitialValues(forms, contextData, processCode, currentState, suggestedContext) {
  const names = collectFieldNames(forms)
  const ctx = { ...(suggestedContext || {}), ...(contextData || {}) }
  const init = {}
  names.forEach((n) => {
    if (ctx[n] !== undefined) init[n] = ctx[n]
  })

  if (
    processCode === 'fall_semester_preparation' &&
    currentState === 'course_finalization' &&
    (!init.courses_finalized || !init.courses_finalized.length) &&
    Array.isArray(ctx.courses) &&
    ctx.courses.length
  ) {
    init.courses_finalized = buildCoursesFinalizedFromDraft(ctx.courses)
  }

  return init
}

/** گام‌های فرایند ۳۰ — قبل از انتشار */
const WINTER_SEMESTER_STEPS = [
  { code: 'license_check', label: 'بررسی پروانه' },
  { code: 'course_list_review', label: 'بازبینی لیست دروس زمستان' },
  { code: 'course_finalization', label: 'نهایی‌سازی مکان و مدرسین' },
  { code: 'marketing_campaign', label: 'کمپین بازاریابی زمستان' },
  { code: 'interviewer_assignment', label: 'تعیین مصاحبه‌کنندگان' },
  { code: 'interview_scheduling', label: 'زمان‌بندی مصاحبه‌ها' },
]

function SemesterPrepStepper({ steps, currentState, testId = 'semester-prep-stepper' }) {
  const idx = steps.findIndex((s) => s.code === currentState)
  if (idx < 0) return null

  return (
    <div
      data-testid={testId}
      style={{
        marginBottom: '1rem',
        padding: '0.75rem 0',
        overflowX: 'auto',
      }}
    >
      <div style={{ display: 'flex', gap: '0.35rem', minWidth: 'max-content', alignItems: 'flex-start' }}>
        {steps.map((step, i) => {
          const done = i < idx
          const active = i === idx
          const bg = active ? '#2563eb' : done ? '#dbeafe' : '#f1f5f9'
          const color = active ? '#fff' : done ? '#1e40af' : '#64748b'
          const border = active ? '2px solid #1d4ed8' : '1px solid #e2e8f0'
          return (
            <div
              key={step.code}
              style={{
                flex: '0 0 auto',
                maxWidth: '9.5rem',
                padding: '0.45rem 0.55rem',
                borderRadius: '8px',
                background: bg,
                color,
                border,
                fontSize: '0.72rem',
                lineHeight: 1.45,
                fontWeight: active ? 700 : 500,
                textAlign: 'center',
              }}
              title={step.label}
            >
              <span style={{ display: 'block', opacity: 0.85, marginBottom: '0.15rem' }}>{i + 1}</span>
              {step.label}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function FallSemesterStepper({ currentState }) {
  return (
    <SemesterPrepStepper
      steps={FALL_SEMESTER_STEPS}
      currentState={currentState}
      testId="fall-semester-stepper"
    />
  )
}

function WinterSemesterStepper({ currentState }) {
  return (
    <SemesterPrepStepper
      steps={WINTER_SEMESTER_STEPS}
      currentState={currentState}
      testId="winter-semester-stepper"
    />
  )
}

export default function OperatorStepFormsSection({
  instanceId,
  processCode,
  currentState,
  contextData,
  isCompleted,
  isCancelled,
  role,
  showToast,
  onUpdated,
}) {
  const supported = SUPPORTED_PROCESSES.has(processCode)
  const isFall = processCode === 'fall_semester_preparation'
  const isWinter = processCode === 'winter_semester_preparation'
  const [forms, setForms] = useState([])
  const [values, setValues] = useState({})
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)

  const visible = useMemo(
    () => !!(supported && instanceId && currentState && !isCompleted && !isCancelled),
    [supported, instanceId, currentState, isCompleted, isCancelled],
  )

  useEffect(() => {
    if (!visible) {
      setForms([])
      return
    }
    let active = true
    setLoading(true)
    processExecApi
      .getProcessFormsForState(processCode, currentState, instanceId)
      .then((res) => {
        if (!active) return
        const list = Array.isArray(res.data?.forms)
          ? res.data.forms
          : Array.isArray(res.data)
            ? res.data
            : []
        const suggested = res.data?.suggested_context || {}
        setForms(list)
        setValues(buildInitialValues(list, contextData, processCode, currentState, suggested))
      })
      .catch(() => active && setForms([]))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [visible, processCode, currentState, instanceId])

  const onChange = useCallback((next) => setValues(next), [])

  const save = async () => {
    setBusy(true)
    try {
      const res = await processExecApi.registerOperatorStepForms(instanceId, {
        form_values: values,
        state_code: currentState,
      })
      showToast?.('فرم این مرحله ثبت شد. اکنون می‌توانید دکمهٔ اقدام را بزنید.')
      onUpdated?.(res.data?.context_data)
    } catch (e) {
      const d = e?.response?.data?.detail
      if (d && typeof d === 'object' && Array.isArray(d.missing)) {
        showToast?.(`فیلدهای الزامی: ${d.missing.join('، ')}`, 'error')
      } else {
        showToast?.(typeof d === 'string' ? d : 'خطا در ثبت فرم مرحله', 'error')
      }
    } finally {
      setBusy(false)
    }
  }

  if (!visible) return null
  if (loading) {
    return (
      <div style={{ marginBottom: '1.25rem', padding: '1rem', background: '#eff6ff', borderRadius: '10px' }}>
        <p className="muted" style={{ margin: 0 }}>در حال بارگذاری فرم مرحله…</p>
      </div>
    )
  }
  if (!forms.length && currentState !== 'interview_scheduling') return null

  const showSlotsAdmin =
    (isFall || isWinter) && currentState === 'interview_scheduling'

  return (
    <div
      style={{
        marginBottom: '1.25rem',
        padding: '1rem 1.25rem',
        background: '#eff6ff',
        borderRadius: '10px',
        borderRight: '4px solid #2563eb',
      }}
      data-testid="operator-step-forms-section"
    >
      {isFall && <FallSemesterStepper currentState={currentState} />}
      {isWinter && <WinterSemesterStepper currentState={currentState} />}

      <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.5rem', color: '#1e40af' }}>
        فرم این مرحله
      </h4>
      <p style={{ fontSize: '0.82rem', color: '#334155', margin: '0 0 0.85rem', lineHeight: 1.65 }}>
        اطلاعات این مرحله را پر و ثبت کنید؛ سپس دکمهٔ اقدام (پایین) را برای پیشروی فرایند بزنید.
      </p>

      {(isFall || isWinter) && (
        <FallSemesterPrepReadonlySummary currentState={currentState} contextData={contextData} />
      )}

      {isFall && currentState === 'tuition_entry' && (
        <div
          style={{
            marginBottom: '0.85rem',
            padding: '0.65rem 0.85rem',
            background: '#fef3c7',
            borderRadius: '6px',
            border: '1px solid #fcd34d',
            fontSize: '0.82rem',
            fontWeight: 600,
            color: '#92400e',
          }}
        >
          هزینه مصاحبه ورود باید همخوان با شأن علمی انستیتو باشد.
        </div>
      )}

      {forms.map((form) => (
        <div key={form.code || form.name_fa} style={{ marginBottom: '1rem' }}>
          {form.name_fa && (
            <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.5rem' }}>{form.name_fa}</div>
          )}
          <UnifiedFormRenderer
            schemaJson={{ fields: form.fields || [] }}
            values={values}
            onChange={onChange}
            role={role}
            showToast={showToast}
          />
        </div>
      ))}

      {showSlotsAdmin && (
        <div
          style={{ marginTop: '1rem', marginBottom: '1rem' }}
          data-testid="fall-interview-slots-admin"
        >
          <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.35rem', color: '#1e293b' }}>
            ثبت اسلات‌های دقیق مصاحبه
          </div>
          <p style={{ fontSize: '0.8rem', color: '#475569', margin: '0 0 0.75rem', lineHeight: 1.6 }}>
            با مصاحبه‌گران تماس بگیرید و برای هر بازه، اسلات‌های قابل رزرو را در جدول زیر ایجاد کنید.
            پس از ثبت اسلات‌ها، تنظیمات کلی بالا را ذخیره کرده و دکمهٔ اقدام را بزنید.
          </p>
          <InterviewSlotsAdmin showToast={showToast} />
        </div>
      )}

      {(forms.length > 0 || showSlotsAdmin) && (
        <button
          type="button"
          className="btn btn-primary btn-sm"
          data-testid="operator-step-forms-save"
          disabled={busy}
          onClick={save}
        >
          {busy ? 'در حال ثبت…' : 'ثبت فرم این مرحله'}
        </button>
      )}
    </div>
  )
}
