import React, { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import OperatorStepFormsSection from '../components/OperatorStepFormsSection'
import OperatorInstanceGuidanceBlock from '../components/OperatorInstanceGuidanceBlock'
import ProcessRollbackSection from '../components/ProcessRollbackSection'
import { useToast } from '../contexts/ToastContext'
import { formatShamsiTehran } from '../utils/shamsiDateTime'
import { notesPayload } from '../utils/decisionPayload'
import { labelState } from '../utils/processDisplay'
import { processExecApi } from '../services/api'
import {
  SEMESTER_PREP_CODES,
  useSemesterPrepWorkbench,
} from '../hooks/useSemesterPrepWorkbench'
import { portalRoleCanActOnState } from '../utils/portalRoleAccess'

const PROCESS_LABELS = {
  fall_semester_preparation: 'آماده‌سازی ترم پاییز',
  winter_semester_preparation: 'آماده‌سازی ترم زمستان',
}

const STATE_HINTS = {
  fall_semester_preparation: {
    calendar_entry:
      'ثبت تاریخ‌های ترم پاییز و زمستان، پنجرهٔ ثبت‌نام، مهلت مصاحبه‌ها و تعطیلات نوروز.',
    tuition_entry: 'تعیین شهریه هر واحد و هزینه مصاحبه برای دوره آشنایی و جامع.',
    license_check: 'بررسی و به‌روزرسانی شماره پروانه فعالیت انستیتو.',
    course_list_creation: 'تدوین لیست دروس، روز و ساعت، مدرسین و کمک‌مدرسین برای دو ترم.',
    course_finalization: 'نهایی‌سازی مکان کلاس‌ها و هماهنگی با مدرسین.',
    marketing_campaign:
      'خروجی فعالیت‌های ۱، ۲ و ۵ را به‌صورت PDF برای مدیر مارکتینگ ارسال کنید و تأیید ارسال را ثبت کنید.',
    interviewer_assignment: 'تعیین مصاحبه‌کنندگان و بازهٔ زمانی مصاحبه‌های ورودی.',
    interview_scheduling:
      'زمان‌بندی دقیق اسلات‌های مصاحبه (ساعت شروع/پایان، مدت نوبت، حضوری یا آنلاین).',
  },
  winter_semester_preparation: {
    license_check: 'بررسی پروانه فعالیت برای ترم زمستان.',
    course_list_review: 'بازبینی و ویرایش لیست دروس زمستان (پیش‌پر از پاییز).',
    course_finalization: 'نهایی‌سازی مکان کلاس‌ها و تأییدیه مدرسین.',
    marketing_campaign:
      'خروجی فعالیت‌های ۲ و ۳ را به‌صورت PDF برای مدیر مارکتینگ ارسال کنید و تأیید ارسال را ثبت کنید.',
    interviewer_assignment: 'تعیین مصاحبه‌کنندگان و بازهٔ زمانی مصاحبه‌های زمستان.',
    interview_scheduling: 'ثبت اسلات‌های دقیق مصاحبه برای متقاضیان.',
  },
}

export default function SemesterPrepWorkbenchPage() {
  const { user } = useAuth()
  const [searchParams] = useSearchParams()
  const processParam = searchParams.get('process_code')
  const { showToast } = useToast()
  const [decisionNotes, setDecisionNotes] = useState('')
  const [rollbackBusy, setRollbackBusy] = useState(false)

  const {
    status,
    entry,
    resolvedCode,
    instanceId,
    currentState,
    isActive,
    instanceDetail,
    actionTransitions,
    loading,
    busy,
    loadInstance,
    startProcess,
    triggerTransition,
  } = useSemesterPrepWorkbench(processParam)

  const canStart =
    user?.role === 'admin' ||
    user?.role === 'deputy_education' ||
    user?.role === 'course_committee' ||
    (user?.role === 'staff' && resolvedCode === 'fall_semester_preparation')

  const winterBlocked =
    resolvedCode === 'winter_semester_preparation' &&
    !status?.processes?.fall_semester_preparation?.last_completed_at

  const stateTitle = entry.state_name_fa || labelState(currentState)
  const stateHint =
    STATE_HINTS[resolvedCode]?.[currentState] ||
    'فرم این مرحله را تکمیل و سپس دکمهٔ اقدام را بزنید.'

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
      showToast(`مرحله ثبت شد — بعدی: ${labelState(result.toState)}`)
    } else {
      showToast(result.error, 'error')
    }
  }

  const handleRollback = async (reason) => {
    if (!instanceId) return
    setRollbackBusy(true)
    try {
      const res = await processExecApi.rollback(instanceId, { reason: reason || undefined })
      if (res.data?.success) {
        showToast(`بازگشت به مرحلهٔ ${labelState(res.data.to_state)}`)
        await loadInstance(instanceId)
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
      </p>

      {loading ? (
        <p className="muted">در حال بارگذاری…</p>
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
            portalRole={user?.role}
            availableTransitions={actionTransitions}
            stepFormLocked={
              !!(user?.role && entry?.assigned_role && !portalRoleCanActOnState(user.role, entry.assigned_role))
            }
          />

          <OperatorStepFormsSection
            instanceId={instanceId}
            processCode={resolvedCode}
            currentState={currentState}
            contextData={instanceDetail?.context_data}
            isCompleted={instanceDetail?.is_completed}
            isCancelled={instanceDetail?.is_cancelled}
            role={user?.role}
            stateAssignedRole={entry?.assigned_role}
            showToast={showToast}
            onUpdated={() => loadInstance(instanceId)}
            stepSla={stepSla}
            actionTransitions={actionTransitions}
            decisionNotes={decisionNotes}
            onDecisionNotesChange={setDecisionNotes}
            onActionTrigger={handleTrigger}
            actionBusy={busy}
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
