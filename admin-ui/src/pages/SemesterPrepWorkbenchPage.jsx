import React, { useCallback, useMemo, useState } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import OperatorStepFormsSection from '../components/OperatorStepFormsSection'
import OperatorInstanceGuidanceBlock from '../components/OperatorInstanceGuidanceBlock'
import ProcessRollbackSection from '../components/ProcessRollbackSection'
import ProcessRestartSection from '../components/ProcessRestartSection'
import ProcessDataManager from '../components/ProcessDataManager'
import { useToast } from '../contexts/ToastContext'
import { formatShamsiTehran } from '../utils/shamsiDateTime'
import { notesPayload } from '../utils/decisionPayload'
import { labelState } from '../utils/processDisplay'
import { processExecApi } from '../services/api'
import {
  SEMESTER_PREP_CODES,
  useSemesterPrepWorkbench,
} from '../hooks/useSemesterPrepWorkbench'
import { anyPortalRoleCanActOnState, formRolesForUser } from '../utils/portalRoleAccess'
import { effectiveSemesterPrepAssignedRole } from '../utils/semesterPrepRoles'
import { userHasAnyRole, userHasRole } from '../utils/userRoles'
import { OVERRIDE_ROLES } from '../utils/processRollbackUtils'
import { contextHasOutlierCalendarDates } from '../utils/semesterPrepCalendarValidation'
import { semesterPrepStepReadinessHint } from '../utils/semesterPrepReadinessHints'
import SemesterPrepReadinessPanel from '../components/SemesterPrepReadinessPanel'

const PROCESS_LABELS = {
  fall_semester_preparation: 'آماده‌سازی ترم پاییز',
  winter_semester_preparation: 'آماده‌سازی ترم زمستان',
}

/** گام‌های ۷ و ۸ در یک مرحلهٔ واحد ادغام شده‌اند */
const MERGED_INTERVIEW_HINT =
  'مصاحبه‌گرها را فقط از استخر پیش‌آماده‌سازی انتخاب کنید و روز و ساعت مصاحبه را تعیین کنید؛ نوبت‌ها خودکار ساخته و تقویم منتشر می‌شود.'

const STATE_HINTS = {
  fall_semester_preparation: {
    calendar_entry:
      'ثبت تاریخ‌های ترم پاییز و زمستان، پنجرهٔ ثبت‌نام، مهلت مصاحبه‌ها و تعطیلات نوروز.',
    tuition_entry:
      'تعیین شهریه، هزینه مصاحبه و پیش‌فرض‌های درمان. فاکتور پشتیبان ثبت‌نام و پیش‌فرض جلسهٔ کلاس/دوره در پنل مالی تنظیم می‌شوند.',
    license_check: 'بررسی و به‌روزرسانی شماره پروانه فعالیت انستیتو.',
    course_list_creation:
      'ردیف‌های درس، مدرس و کمک‌مدرس را اضافه یا حذف کنید؛ در صورت نیاز مورد جدید بسازید و روز و ساعت را تکمیل کنید.',
    course_finalization: 'نهایی‌سازی مکان کلاس‌ها و هماهنگی با مدرسین.',
    marketing_campaign:
      'خروجی فعالیت‌های ۱، ۲ و ۵ را به‌صورت PDF برای مدیر مارکتینگ ارسال کنید و تأیید ارسال را ثبت کنید.',
    interviewer_assignment: MERGED_INTERVIEW_HINT,
    interview_scheduling: MERGED_INTERVIEW_HINT,
  },
  winter_semester_preparation: {
    license_check: 'بررسی پروانه فعالیت برای ترم زمستان.',
    course_list_review:
      'لیست دروس زمستان را بازبینی کنید؛ ردیف درس، مدرس و کمک‌مدرس را می‌توانید اضافه یا حذف کنید.',
    course_finalization: 'نهایی‌سازی مکان کلاس‌ها و تأییدیه مدرسین.',
    marketing_campaign:
      'خروجی فعالیت‌های ۲ و ۳ را به‌صورت PDF برای مدیر مارکتینگ ارسال کنید و تأیید ارسال را ثبت کنید.',
    interviewer_assignment: MERGED_INTERVIEW_HINT,
    interview_scheduling: MERGED_INTERVIEW_HINT,
  },
}

export default function SemesterPrepWorkbenchPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const processParam = searchParams.get('process_code')
  const { showToast } = useToast()
  const [decisionNotes, setDecisionNotes] = useState('')
  const [rollbackBusy, setRollbackBusy] = useState(false)
  const [restartBusy, setRestartBusy] = useState(false)

  const {
    status,
    readiness,
    entry,
    resolvedCode,
    instanceId,
    currentState,
    isActive,
    isCompletedEditable,
    instanceDetail,
    actionTransitions,
    loading,
    busy,
    load,
    loadInstance,
    applyInstanceContext,
    reloadReadiness,
    startProcess,
    triggerTransition,
  } = useSemesterPrepWorkbench(processParam)

  const fallPublished = Boolean(status?.processes?.fall_semester_preparation?.last_completed_at)
  const canStart =
    userHasRole(user, 'admin', { adminBypass: false }) ||
    userHasRole(user, 'deputy_education', { adminBypass: false }) ||
    userHasRole(user, 'course_committee', { adminBypass: false })

  const winterBlocked =
    resolvedCode === 'winter_semester_preparation' &&
    !status?.processes?.fall_semester_preparation?.last_completed_at

  const stateTitle = entry.state_name_fa || labelState(currentState)
  const stateHint =
    STATE_HINTS[resolvedCode]?.[currentState] ||
    'فرم این مرحله را تکمیل و سپس دکمهٔ اقدام را بزنید.'

  const stepReadinessHint = useMemo(
    () => semesterPrepStepReadinessHint(currentState, readiness),
    [currentState, readiness],
  )

  const showReadinessBanner = Boolean(readiness && readiness.incomplete_count > 0)

  const deadlineLabel = entry.calendar_sla_deadline_at
    ? formatShamsiTehran(entry.calendar_sla_deadline_at, { dateOnly: true })
    : null

  const stepSla = useMemo(() => {
    const deadlineAt =
      entry.sla_deadline_at ||
      (currentState === 'calendar_entry' ? entry.calendar_sla_deadline_at : null)
    if (!deadlineAt) return null
    return {
      deadlineAt,
      overdue: !!entry.sla_overdue,
      warningRecipientsFa: entry.sla_warning_recipients_fa || [],
    }
  }, [entry, currentState])

  const lockAssignedRole = effectiveSemesterPrepAssignedRole(
    resolvedCode,
    currentState,
    entry?.assigned_role,
  )
  const formRoles = formRolesForUser(user, user?.role)
  const stepFormLocked = !!(
    formRoles.length
    && lockAssignedRole
    && !anyPortalRoleCanActOnState(formRoles, lockAssignedRole)
  )

  const isPublished = currentState === 'published'

  // ویرایش تقویم فقط در مرحلهٔ calendar_entry (فرم مرحله) یا پس از انتشار (ProcessDataManager)
  const showCalendarCorrection =
    resolvedCode === 'fall_semester_preparation'
    && instanceId
    && isCompletedEditable

  const calendarOutlier = useMemo(
    () => showCalendarCorrection && contextHasOutlierCalendarDates(instanceDetail?.context_data),
    [showCalendarCorrection, instanceDetail?.context_data],
  )

  const goToAcademicCalendar = useCallback(() => {
    navigate('/panel/academic-calendar')
  }, [navigate])

  const handleStart = async () => {
    const result = await startProcess(resolvedCode)
    if (result.ok) {
      showToast(`${PROCESS_LABELS[resolvedCode]} شروع شد.`)
    } else {
      showToast(result.error, 'error')
    }
  }

  const handleTrigger = async (transition) => {
    const result = await triggerTransition(transition, (text) => notesPayload(text || decisionNotes))
    if (result.ok) {
      setDecisionNotes('')
      if (result.toState === 'published') {
        showToast('تقویم آموزشی منتشر شد — در حال انتقال به صفحهٔ تقویم…')
        goToAcademicCalendar()
        return
      }
      showToast(`مرحله ثبت شد — بعدی: ${labelState(result.toState)}`)
    } else {
      showToast(result.error, 'error')
    }
  }

  const primaryTransition = actionTransitions[0] ?? null

  const handleAdvanceAfterSave = useCallback(
    async (transition) => {
      const result = await triggerTransition(transition, (text) => notesPayload(text || decisionNotes))
      if (result.ok) {
        setDecisionNotes('')
        if (result.toState === 'published') {
          goToAcademicCalendar()
        }
      }
      return result
    },
    [triggerTransition, decisionNotes, goToAcademicCalendar],
  )

  const handleFormsUpdated = useCallback(
    (ctx) => {
      if (ctx && typeof ctx === 'object') {
        applyInstanceContext(ctx)
        return
      }
      if (instanceId) loadInstance(instanceId)
    },
    [applyInstanceContext, instanceId, loadInstance],
  )

  const handleRollback = async (reason) => {
    if (!instanceId) return
    setRollbackBusy(true)
    try {
      const res = await processExecApi.rollback(instanceId, { reason: reason || undefined })
      if (res.data?.success) {
        setDecisionNotes('')
        showToast(`بازگشت به مرحلهٔ ${labelState(res.data.to_state)}`)
        await load()
      } else {
        showToast(res.data?.error || 'بازگشت انجام نشد', 'error')
      }
    } catch (e) {
      const d = e?.response?.data?.detail
      showToast(typeof d === 'string' ? d : 'خطا در بازگشت فرایند', 'error')
    } finally {
      setRollbackBusy(false)
    }
  }

  const handleProcessRestart = async (reason) => {
    if (!instanceId) return false
    setRestartBusy(true)
    try {
      const res = await processExecApi.restart(instanceId, {
        reason: reason || undefined,
        confirm: true,
      })
      if (res.data?.success) {
        showToast('فرایند از ابتدا با پروندهٔ جدید باز شد')
        await load()
        return true
      }
      showToast(res.data?.error || 'شروع دوباره انجام نشد', 'error')
      return false
    } catch (e) {
      const d = e?.response?.data?.detail
      showToast(typeof d === 'string' ? d : 'خطا در شروع دوباره', 'error')
      return false
    } finally {
      setRestartBusy(false)
    }
  }

  return (
    <div
      className="page-container semester-prep-workbench"
      style={{ width: '100%', maxWidth: 'min(920px, 100%)', margin: '0 auto', padding: '1.25rem' }}
    >
      <div style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
        <Link to="/panel/semester-prep" className="muted" style={{ fontSize: '0.82rem' }}>
          ← بازگشت به آماده‌سازی ترم
        </Link>
        {SEMESTER_PREP_CODES.length > 1 && (
          <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
            {SEMESTER_PREP_CODES.map((code) => {
              const activeProc = status?.processes?.[code]?.active
              return (
                <Link
                  key={code}
                  to={`/panel/semester-prep/workbench?process_code=${code}`}
                  className={code === resolvedCode ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm'}
                  style={{ fontSize: '0.78rem' }}
                >
                  {PROCESS_LABELS[code]}
                  {activeProc ? ' ●' : ''}
                </Link>
              )
            })}
          </div>
        )}
      </div>

      <h1 style={{ fontSize: '1.35rem', marginBottom: '0.35rem' }}>
        {PROCESS_LABELS[resolvedCode] || 'مرحلهٔ آماده‌سازی'}
      </h1>
      {isActive && (
        <p style={{ margin: '0 0 0.25rem', fontSize: '1rem', fontWeight: 600 }}>{stateTitle}</p>
      )}
      <p className="muted" style={{ marginBottom: '1.25rem', lineHeight: 1.7 }}>
        {stateHint}
        {deadlineLabel && currentState === 'calendar_entry' ? (
          <span style={{ display: 'block', marginTop: '0.35rem' }}>مهلت هدف تقویم: تا {deadlineLabel}</span>
        ) : null}
        {entry.sla_hours ? (
          <span style={{ display: 'block', marginTop: '0.35rem', fontSize: '0.88rem' }}>
            مهلت این مرحله: {entry.sla_hours} ساعت
            {entry.sla_overdue ? ' (گذشته)' : ''}
          </span>
        ) : null}
        {entry.sla_overdue ? (
          <span style={{ color: '#b91c1c', display: 'block', marginTop: '0.35rem' }}>
            مهلت این مرحله گذشته — لطفاً هرچه زودتر تکمیل کنید (فقط هشدار مدیریتی).
          </span>
        ) : null}
        {stepReadinessHint ? (
          <span
            style={{ display: 'block', marginTop: '0.5rem', color: '#92400e', fontSize: '0.88rem' }}
            data-testid="semester-prep-step-readiness-hint"
          >
            {stepReadinessHint}
          </span>
        ) : null}
      </p>

      {!loading && showReadinessBanner ? (
        <div style={{ marginBottom: '1rem' }} data-testid="semester-prep-readiness-banner">
          <SemesterPrepReadinessPanel
            readiness={readiness}
            compact
            showTitle
            onReload={() => reloadReadiness()}
          />
          <p style={{ margin: '0.5rem 0 0', fontSize: '0.82rem' }}>
            <Link to="/panel/semester-prep/readiness">رفتن به صفحهٔ تکمیل پیش‌نیازها</Link>
          </p>
        </div>
      ) : null}

      {loading ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : isCompletedEditable ? (
        <>
          <div
            style={{
              border: '1px solid #bae6fd',
              background: '#f0f9ff',
              borderRadius: '10px',
              padding: '1rem 1.15rem',
              marginBottom: '1rem',
              lineHeight: 1.7,
            }}
          >
            <p style={{ margin: 0, fontWeight: 600 }}>این فرایند برای ترم فعلی منتشر شده است.</p>
            <p style={{ margin: '0.35rem 0 0', fontSize: '0.9rem', color: '#475569' }}>
              فرم‌های مراحل به‌صورت فقط‌خواندنی نمایش داده می‌شوند. برای اصلاح تقویم از بخش «ویرایش
              تقویم آموزشی» استفاده کنید.
              {userHasAnyRole(user, OVERRIDE_ROLES) ? (
                <>
                  {' '}
                  برای سایر مراحل، مدیر سامانه یا معاون آموزش می‌توانند از «بازگشت به مرحلهٔ قبلی» در
                  انتهای صفحه استفاده کنند.
                </>
              ) : (
                <>
                  {' '}
                  اصلاح مراحل قبلی (بازگشت یا شروع دوباره) فقط توسط مدیر سامانه یا معاون آموزش انجام
                  می‌شود؛ هر نقش فقط مرحلهٔ خودش را طبق SOP تکمیل و پاس می‌دهد.
                </>
              )}
            </p>
            {isPublished ? (
              <div style={{ marginTop: '0.85rem' }}>
                <Link to="/panel/academic-calendar" className="btn btn-primary btn-sm">
                  مشاهده تقویم آموزشی منتشرشده
                </Link>
              </div>
            ) : null}
          </div>

          <OperatorInstanceGuidanceBlock
            instanceDetail={instanceDetail}
            user={user}
            portalRole={user?.role}
            availableTransitions={actionTransitions}
            stepFormLocked={stepFormLocked}
          />

          {showCalendarCorrection ? (
            <>
              {calendarOutlier ? (
                <div
                  style={{
                    marginBottom: '1rem',
                    padding: '0.75rem 1rem',
                    background: '#fef2f2',
                    border: '1px solid #fecaca',
                    borderRadius: '10px',
                    fontSize: '0.88rem',
                    color: '#991b1b',
                    lineHeight: 1.65,
                  }}
                  data-testid="calendar-outlier-warning"
                >
                  برخی تاریخ‌های تقویم آموزشی خارج از بازهٔ مجاز سال جاری هستند — از بخش زیر اصلاح کنید.
                </div>
              ) : null}
              <ProcessDataManager
                instanceId={instanceId}
                user={user}
                role={user?.role}
                stateCode="calendar_entry"
                title="ویرایش تقویم آموزشی (پاییز و زمستان)"
                showToast={showToast}
                onUpdated={handleFormsUpdated}
              />
            </>
          ) : null}

          <OperatorStepFormsSection
            instanceId={instanceId}
            processCode={resolvedCode}
            currentState={currentState}
            contextData={instanceDetail?.context_data}
            isCompleted={instanceDetail?.is_completed}
            isCancelled={instanceDetail?.is_cancelled}
            role={user?.role}
            user={user}
            stateAssignedRole={entry?.assigned_role}
            showToast={showToast}
            onUpdated={handleFormsUpdated}
            primaryTransition={primaryTransition}
            onAdvanceAfterSave={handleAdvanceAfterSave}
            advanceBusy={busy}
            actionTransitions={actionTransitions}
            decisionNotes={decisionNotes}
            onDecisionNotesChange={setDecisionNotes}
            onActionTrigger={handleTrigger}
            onSemesterPrepPublished={goToAcademicCalendar}
            actionBusy={busy}
          />

          <ProcessRestartSection
            user={user}
            instanceDetail={instanceDetail}
            onRestart={handleProcessRestart}
            busy={restartBusy}
          />

          <ProcessRollbackSection
            user={user}
            instanceDetail={instanceDetail}
            onRollback={handleRollback}
            busy={rollbackBusy}
          />
        </>
      ) : !isActive ? (
        <div
          style={{
            border: '1px solid #e2e8f0',
            borderRadius: '10px',
            padding: '1.15rem',
            background: '#fff',
          }}
        >
          <p style={{ margin: '0 0 0.75rem', lineHeight: 1.65 }}>
            {winterBlocked
              ? 'ابتدا آماده‌سازی پاییز باید به «انتشار» برسد.'
              : 'فرایند فعال نیست یا به پایان رسیده است.'}
          </p>
          {canStart && !winterBlocked && !entry.active ? (
            <button type="button" className="btn btn-primary" disabled={busy} onClick={handleStart}>
              {busy ? '…' : `شروع ${PROCESS_LABELS[resolvedCode]}`}
            </button>
          ) : (
            <p className="muted" style={{ margin: 0, fontSize: '0.88rem' }}>
              برای شروع یا پیگیری از{' '}
              <Link to="/panel/semester-prep">صفحهٔ آماده‌سازی ترم</Link> اقدام کنید.
            </p>
          )}
        </div>
      ) : (
        <>
          <OperatorInstanceGuidanceBlock
            instanceDetail={instanceDetail}
            user={user}
            portalRole={user?.role}
            availableTransitions={actionTransitions}
            stepFormLocked={stepFormLocked}
          />

          <OperatorStepFormsSection
            instanceId={instanceId}
            processCode={resolvedCode}
            currentState={currentState}
            contextData={instanceDetail?.context_data}
            isCompleted={instanceDetail?.is_completed}
            isCancelled={instanceDetail?.is_cancelled}
            role={user?.role}
            user={user}
            stateAssignedRole={entry?.assigned_role}
            showToast={showToast}
            onUpdated={handleFormsUpdated}
            stepSla={stepSla}
            actionTransitions={actionTransitions}
            decisionNotes={decisionNotes}
            onDecisionNotesChange={setDecisionNotes}
            onActionTrigger={handleTrigger}
            onSemesterPrepPublished={goToAcademicCalendar}
            actionBusy={busy}
          />

          <ProcessRestartSection
            user={user}
            instanceDetail={instanceDetail}
            onRestart={handleProcessRestart}
            busy={restartBusy}
          />

          <ProcessRollbackSection
            user={user}
            instanceDetail={instanceDetail}
            onRollback={handleRollback}
            busy={rollbackBusy}
          />
        </>
      )}

    </div>
  )
}
