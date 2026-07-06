import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { processExecApi } from '../services/api'
import UnifiedFormRenderer from './UnifiedFormRenderer'
import FallSemesterPrepReadonlySummary from './FallSemesterPrepReadonlySummary'
import MarketingCampaignHandoffPanel, { isMarketingHandoffField } from './MarketingCampaignHandoffPanel'
import SemesterPrepStepDeadlineBanner from './SemesterPrepStepDeadlineBanner'
import InterviewSlotsAdmin from './InterviewSlotsAdmin'
import DecisionNotesBlock from './DecisionNotesBlock'
import { validateUnifiedAnswers } from '../utils/unifiedFormValidation'
import {
  denormalizeCourseRosterTableRows,
  normalizeCourseTableInitialRows,
  resolveFormOptionsSource,
} from '../utils/resolveFormOptionsSource'
import { SEMESTER_PREP_PROCESSES } from '../utils/instituteProcesses'
import { buildWaitingForRoleTaskFa } from '../utils/operatorProcessGuidance'
import { portalRoleCanActOnState } from '../utils/portalRoleAccess'
import { resolveCheckboxListOptions } from '../utils/resolveCourseFieldOptions'
import {
  defaultShamsiDate,
  defaultShamsiTehranNow,
  shamsiDateToIsoDate,
  shamsiDateTimeToUtcIso,
} from '../utils/shamsiDateTime'

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

  const isCourseFinalization =
    currentState === 'course_finalization' &&
    (processCode === 'fall_semester_preparation' || processCode === 'winter_semester_preparation')
  if (isCourseFinalization && processCode === 'fall_semester_preparation') {
    const draftPairs = [
      ['courses_finalized_fall', 'courses_fall'],
      ['courses_finalized_winter', 'courses_winter'],
    ]
    for (const [finalName, draftName] of draftPairs) {
      if ((!init[finalName] || !init[finalName].length) && Array.isArray(ctx[draftName]) && ctx[draftName].length) {
        init[finalName] = buildCoursesFinalizedFromDraft(ctx[draftName])
      }
    }
  }
  if (
    isCourseFinalization &&
    processCode === 'winter_semester_preparation' &&
    (!init.courses_finalized || !init.courses_finalized.length) &&
    Array.isArray(ctx.courses) &&
    ctx.courses.length
  ) {
    init.courses_finalized = buildCoursesFinalizedFromDraft(ctx.courses)
  }
  if (
    isCourseFinalization &&
    processCode === 'fall_semester_preparation' &&
    (!init.courses_finalized_fall || !init.courses_finalized_fall.length) &&
    Array.isArray(ctx.courses) &&
    ctx.courses.length
  ) {
    init.courses_finalized_fall = buildCoursesFinalizedFromDraft(ctx.courses)
  }

  for (const form of forms || []) {
    for (const field of form?.fields || []) {
      if ((field.type || '').toLowerCase() !== 'table' || !field.required) continue
      const name = field.name
      let rows = init[name]
      if (Array.isArray(rows) && rows.length) {
        init[name] = normalizeCourseTableInitialRows(field, rows)
      } else if (!Array.isArray(rows) || rows.length === 0) {
        const blank = {}
        for (const col of field.columns || []) {
          const ct = (col.type || 'text').toLowerCase()
          blank[col.name] = ct === 'checkbox' ? false : ''
        }
        init[name] = [blank]
      }
    }
  }

  for (const form of forms || []) {
    for (const field of form?.fields || []) {
      const ft = (field.type || '').toLowerCase()
      const name = field.name
      if (!name) continue
      const current = init[name]
      if (current !== undefined && current !== null && current !== '') continue
      if (ft === 'date') {
        const d = defaultShamsiDate()
        try {
          init[name] = shamsiDateToIsoDate(d.jy, d.jm, d.jd)
        } catch {
          /* ignore */
        }
      } else if (ft === 'datetime') {
        const d = defaultShamsiTehranNow()
        try {
          init[name] = shamsiDateTimeToUtcIso(d.jy, d.jm, d.jd, d.hour, d.minute)
        } catch {
          /* ignore */
        }
      }
    }
  }

  return init
}

async function enrichColumnOptions(col, contextData = null) {
  const next = { ...col }
  if (!next.options_source || (Array.isArray(next.options) && next.options.length)) {
    return next
  }
  const { options, optionsByTrack, optionsByCourse } = await resolveFormOptionsSource(next.options_source, contextData)
  if (optionsByCourse) {
    next._optionsByCourse = optionsByCourse
    next.filter_by_column = next.options_source.filter_by_column || next.filter_by_column
  } else if (optionsByTrack) {
    next._optionsByTrack = optionsByTrack
    next.filter_by_column = next.options_source.filter_by_column || next.filter_by_column
  } else if (options.length) {
    next.options = options
  }
  return next
}

async function enrichFormsWithDynamicOptions(forms, contextData) {
  const out = []
  for (const form of forms || []) {
    const fields = []
    for (const field of form?.fields || []) {
      const next = { ...field }
      const ft = (next.type || '').toLowerCase()
      if (ft === 'table' && Array.isArray(next.columns)) {
        const columns = []
        for (const col of next.columns) {
          columns.push(await enrichColumnOptions(col, contextData))
        }
        next.columns = columns
      } else if (ft === 'dynamic_list' && Array.isArray(next.fields)) {
        const nested = []
        for (const col of next.fields) {
          if (typeof col === 'object' && col?.options_source) {
            nested.push(await enrichColumnOptions(col, contextData))
          } else {
            nested.push(col)
          }
        }
        next.fields = nested
      } else if (next.source && !(Array.isArray(next.options) && next.options.length)) {
        const resolved = resolveCheckboxListOptions(next, contextData)
        if (resolved.options?.length) next.options = resolved.options
        if (resolved.maxSelect != null) next.maxSelect = resolved.maxSelect
        if (resolved.minSelect != null) next.minSelect = resolved.minSelect
        if (resolved.hint) next._optionsHint = resolved.hint
      } else if (next.options_source && !(Array.isArray(next.options) && next.options.length)) {
        const { options, optionsByTrack, optionsByCourse } = await resolveFormOptionsSource(next.options_source, contextData)
        if (optionsByCourse) next._optionsByCourse = optionsByCourse
        else if (optionsByTrack) next._optionsByTrack = optionsByTrack
        else if (options.length) next.options = options
      } else if (ft === 'user_select' && !(Array.isArray(next.options) && next.options.length)) {
        const { options } = await resolveFormOptionsSource({ type: 'users' }, contextData)
        if (options.length) next.options = options
      }
      fields.push(next)
    }
    out.push({ ...form, fields })
  }
  return out
}

function hasVisiblePrefill(forms, suggestedContext) {
  const suggested = suggestedContext || {}
  return (forms || []).some((form) =>
    (form.fields || []).some((field) => {
      if (!field?.pre_filled_from) return false
      const v = suggested[field.name]
      if (v == null || v === '') return false
      if (Array.isArray(v)) return v.length > 0
      return true
    }),
  )
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
      className="semester-prep-stepper-scroll"
      data-testid={testId}
      style={{
        marginBottom: '1rem',
        padding: '0.75rem 0',
        width: '100%',
        maxWidth: '100%',
        minWidth: 0,
        overflowX: 'auto',
        WebkitOverflowScrolling: 'touch',
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
  /** اگر تنظیم شود، پس از ثبت موفق فرم همان ترنزیشن اجرا می‌شود. */
  primaryTransition = null,
  onAdvanceAfterSave = null,
  advanceBusy = false,
  /** مهلت SLA مرحله (از status آماده‌سازی ترم) */
  stepSla = null,
  /** assigned_role متادیتا برای مرحلهٔ فعلی — قفل فرم اگر نقش پورتال مجاز نیست */
  stateAssignedRole = null,
  /** دکمه‌های پیشروی مرحله — در آماده‌سازی ترم زیر همان فرم نمایش داده می‌شوند. */
  actionTransitions = [],
  decisionNotes = '',
  onDecisionNotesChange = null,
  onActionTrigger = null,
  actionBusy = false,
}) {
  const isSemesterPrep = SEMESTER_PREP_PROCESSES.has(processCode)
  const isFall = processCode === 'fall_semester_preparation'
  const isWinter = processCode === 'winter_semester_preparation'
  const [forms, setForms] = useState([])
  const [values, setValues] = useState({})
  const [suggestedContext, setSuggestedContext] = useState({})
  const [canActOnState, setCanActOnState] = useState(true)
  const [fetchedStateAssignedRole, setFetchedStateAssignedRole] = useState(null)
  const [loading, setLoading] = useState(false)
  const effectiveStateAssignedRole = fetchedStateAssignedRole ?? stateAssignedRole
  const [busy, setBusy] = useState(false)

  const showPrefillBanner = useMemo(
    () => isWinter && hasVisiblePrefill(forms, suggestedContext),
    [isWinter, forms, suggestedContext],
  )

  const editableFieldNames = useMemo(() => {
    const names = new Set()
    let hasEditableFlag = false
    for (const form of forms) {
      for (const field of form?.fields || []) {
        if (!field?.name) continue
        if ('__editable' in field) {
          hasEditableFlag = true
          if (field.__editable) names.add(field.name)
        } else {
          names.add(field.name)
        }
      }
    }
    return hasEditableFlag ? names : null
  }, [forms])

  const roleLocked =
    role !== 'admin'
    && (
      canActOnState === false
      || !!(role && effectiveStateAssignedRole && !portalRoleCanActOnState(role, effectiveStateAssignedRole))
    )

  const canEditForms =
    (editableFieldNames == null || editableFieldNames.size > 0) && !roleLocked

  const waitingTaskFa = roleLocked ? buildWaitingForRoleTaskFa(effectiveStateAssignedRole) : ''

  const visible = useMemo(
    () => !!(instanceId && currentState && !isCompleted && !isCancelled),
    [instanceId, currentState, isCompleted, isCancelled],
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
      .then(async (res) => {
        if (!active) return
        const list = Array.isArray(res.data?.forms)
          ? res.data.forms
          : Array.isArray(res.data)
            ? res.data
            : []
        const suggested = res.data?.suggested_context || {}
        const enriched = await enrichFormsWithDynamicOptions(list, contextData)
        if (!active) return
        setSuggestedContext(suggested)
        setForms(enriched)
        setCanActOnState(res.data?.can_act_on_state !== false)
        setFetchedStateAssignedRole(res.data?.state_assigned_role || null)
        setValues(buildInitialValues(enriched, contextData, processCode, currentState, suggested))
      })
      .catch(() => active && setForms([]))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [visible, processCode, currentState, instanceId])

  useEffect(() => {
    if (!forms.length || !visible) return
    setValues((prev) => {
      const next = buildInitialValues(forms, contextData, processCode, currentState, suggestedContext)
      return JSON.stringify(prev) === JSON.stringify(next) ? prev : next
    })
  }, [forms, contextData, suggestedContext, processCode, currentState, visible])

  const onChange = useCallback((next) => setValues(next), [])

  const hasInlineActions = actionTransitions.length > 0 && typeof onActionTrigger === 'function'
  const canAdvanceOnSave = !!(primaryTransition && onAdvanceAfterSave && !hasInlineActions)

  const isMarketingStep = currentState === 'marketing_campaign' && (isFall || isWinter)
  const marketingForm = useMemo(
    () => (isMarketingStep ? forms.find((f) => (f.fields || []).some((field) => isMarketingHandoffField(field.name))) : null),
    [isMarketingStep, forms],
  )

  const filterHandoffFields = useCallback(
    (fields) => (isMarketingStep ? (fields || []).filter((f) => !isMarketingHandoffField(f?.name)) : fields || []),
    [isMarketingStep],
  )

  const save = async () => {
    const allMissing = []
    for (const form of forms) {
      const { ok, missing } = validateUnifiedAnswers({ fields: form.fields || [] }, values, { role })
      if (!ok) allMissing.push(...missing)
    }
    if (allMissing.length) {
      showToast?.(`لطفاً موارد زیر را تکمیل کنید: ${allMissing.join('؛ ')}`, 'error')
      return
    }
    setBusy(true)
    try {
      const payloadValues = { ...values }
      for (const form of forms) {
        for (const field of form?.fields || []) {
          if ((field.type || '').toLowerCase() !== 'table' || !field.name) continue
          const rows = payloadValues[field.name]
          if (Array.isArray(rows)) {
            payloadValues[field.name] = denormalizeCourseRosterTableRows(field, rows)
          }
        }
      }
      const res = await processExecApi.registerOperatorStepForms(instanceId, {
        form_values: payloadValues,
        state_code: currentState,
      })
      if (canAdvanceOnSave) {
        const advanceResult = await onAdvanceAfterSave(primaryTransition)
        if (advanceResult?.ok) {
          const nextLabel = advanceResult.toStateLabel || 'مرحله بعد'
          showToast?.(`مرحله ثبت شد — بعدی: ${nextLabel}`)
          onUpdated?.()
        } else {
          showToast?.(
            advanceResult?.error || 'فرم ثبت شد ولی پیشروی انجام نشد. از دکمهٔ پایین صفحه استفاده کنید.',
            'error',
          )
          onUpdated?.(res.data?.context_data)
        }
      } else {
        showToast?.('فرم این مرحله ثبت شد. اکنون می‌توانید دکمهٔ اقدام را بزنید.')
        onUpdated?.(res.data?.context_data)
      }
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
  const showSlotsAdmin =
    isSemesterPrep && currentState === 'interview_scheduling'

  if (!forms.length && !showSlotsAdmin) return null

  return (
    <div
      className="operator-step-forms-section"
      style={{
        marginBottom: '1.25rem',
        padding: '1rem 1.25rem',
        background: '#eff6ff',
        borderRadius: '10px',
        borderRight: '4px solid #2563eb',
        width: '100%',
        maxWidth: '100%',
        minWidth: 0,
        boxSizing: 'border-box',
      }}
      data-testid="operator-step-forms-section"
    >
      {isFall && <FallSemesterStepper currentState={currentState} />}
      {isWinter && <WinterSemesterStepper currentState={currentState} />}

      {isSemesterPrep && stepSla?.deadlineAt && (
        <SemesterPrepStepDeadlineBanner
          deadlineAt={stepSla.deadlineAt}
          overdue={!!stepSla.overdue}
          warningRecipientsFa={stepSla.warningRecipientsFa}
        />
      )}

      <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.5rem', color: '#1e40af' }}>
        فرم این مرحله
      </h4>
      <p style={{ fontSize: '0.82rem', color: '#334155', margin: '0 0 0.85rem', lineHeight: 1.65 }}>
        {roleLocked
          ? 'این مرحله در انتظار نقش مسئول دیگر است — فقط مشاهده.'
          : isMarketingStep
          ? 'خروجی فعالیت‌های قبلی را بررسی کنید، PDF بگیرید و برای مدیر مارکتینگ ارسال کنید؛ سپس تأیید ارسال را تیک بزنید و فرم را ثبت کنید.'
          : canAdvanceOnSave
          ? 'اطلاعات این مرحله را پر کنید و با دکمهٔ زیر ثبت کنید تا به مرحلهٔ بعد بروید.'
          : hasInlineActions
            ? 'اطلاعات این مرحله را پر کنید، فرم را ذخیره کنید و سپس دکمهٔ پیشروی را بزنید.'
            : 'اطلاعات این مرحله را پر و ثبت کنید؛ سپس دکمهٔ اقدام را برای پیشروی فرایند بزنید.'}
      </p>

      {(isFall || isWinter) && (
        <FallSemesterPrepReadonlySummary
          currentState={currentState}
          contextData={contextData}
          processCode={processCode}
        />
      )}

      {isMarketingStep && (
        <MarketingCampaignHandoffPanel
          instanceId={instanceId}
          processCode={processCode}
          showToast={showToast}
          form={marketingForm}
          values={values}
          onChange={onChange}
          disabled={!canEditForms}
          readOnly={!canEditForms}
        />
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

      {showPrefillBanner && (
        <div
          data-testid="winter-prefill-banner"
          style={{
            marginBottom: '0.85rem',
            padding: '0.65rem 0.85rem',
            background: '#fef3c7',
            borderRadius: '6px',
            border: '1px solid #fcd34d',
            fontSize: '0.82rem',
            color: '#92400e',
            lineHeight: 1.6,
          }}
        >
          این جدول از لیست دروس ترم پاییز پر شده است — می‌توانید ویرایش کنید.
        </div>
      )}

      {forms.map((form) => {
        const visibleFields = filterHandoffFields(form.fields)
        if (!visibleFields.length) return null
        return (
        <div key={form.code || form.name_fa} style={{ marginBottom: '1rem', minWidth: 0, maxWidth: '100%' }}>
          {form.name_fa && !isMarketingStep && (
            <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.5rem' }}>{form.name_fa}</div>
          )}
          {form.note_fa && !isMarketingStep && (
            <p style={{ fontSize: '0.82rem', color: '#475569', margin: '0 0 0.5rem', lineHeight: 1.6 }}>{form.note_fa}</p>
          )}
          <UnifiedFormRenderer
            schemaJson={{ fields: visibleFields, visible_to: form.visible_to, editable_by: form.editable_by }}
            values={values}
            onChange={onChange}
            role={role}
            editableFieldNames={editableFieldNames}
            disabled={!canEditForms}
            showToast={showToast}
          />
        </div>
        )
      })}

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

      {(forms.length > 0 || showSlotsAdmin) && canEditForms && (
        <div
          style={{
            marginTop: hasInlineActions ? '1rem' : 0,
            paddingTop: hasInlineActions ? '1rem' : 0,
            borderTop: hasInlineActions ? '1px solid #bfdbfe' : 'none',
          }}
        >
          {hasInlineActions && typeof onDecisionNotesChange === 'function' && (
            <DecisionNotesBlock
              value={decisionNotes}
              onChange={onDecisionNotesChange}
              title="توضیح یا نظر (اختیاری)"
              hint="متن همراه دکمهٔ اقدام در پرونده ثبت می‌شود."
            />
          )}
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
            <button
              type="button"
              className={hasInlineActions ? 'btn btn-secondary btn-sm' : 'btn btn-primary btn-sm'}
              data-testid="operator-step-forms-save"
              disabled={busy || advanceBusy || actionBusy}
              onClick={save}
            >
              {busy || advanceBusy
                ? 'در حال ثبت…'
                : canAdvanceOnSave
                  ? 'ثبت و رفتن به مرحله بعد'
                  : 'ثبت فرم این مرحله'}
            </button>
            {hasInlineActions &&
              actionTransitions.map((t) => (
                <button
                  key={`${t.trigger_event}-${t.to_state || ''}`}
                  type="button"
                  className="btn btn-primary btn-sm"
                  data-testid="operator-step-forms-action"
                  disabled={busy || actionBusy}
                  onClick={() => onActionTrigger(t)}
                >
                  {t.description || t.description_fa || t.trigger_event}
                </button>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}
