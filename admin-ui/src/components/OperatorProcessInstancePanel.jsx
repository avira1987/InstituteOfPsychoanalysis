import React, { useState } from 'react'
import { processExecApi } from '../services/api'
import { notesPayload } from '../utils/decisionPayload'
import { labelProcess, labelState } from '../utils/processDisplay'
import InstanceContextSummary from './InstanceContextSummary'
import DecisionNotesBlock from './DecisionNotesBlock'
import OperatorInstanceGuidanceBlock from './OperatorInstanceGuidanceBlock'
import OperatorCourseSelectionEditor from './OperatorCourseSelectionEditor'
import OperatorStepFormsSection from './OperatorStepFormsSection'
import ProcessDataManager from './ProcessDataManager'
import ProcessRollbackSection from './ProcessRollbackSection'
import ProcessRestartSection from './ProcessRestartSection'
import { isInstituteLevelProcess } from '../utils/instituteProcesses'

/**
 * پنل یکپارچهٔ جزئیات پروندهٔ فرایند برای اپراتورها — فرم مرحله، راهنما، ترنزیشن.
 */
export default function OperatorProcessInstancePanel({
  user,
  instanceDetail,
  availableTransitions = [],
  onClose,
  showToast,
  onRefreshInstance,
  /** فیلتر ترنزیشن‌ها (مثلاً مصاحبه‌گر) */
  filterTransitions,
  /** محتوای اضافه قبل از بلوک اقدامات */
  renderExtraBeforeActions,
  /** کنترل از بیرون؛ در غیر این صورت state داخلی */
  decisionNotes: decisionNotesProp,
  setDecisionNotes: setDecisionNotesProp,
  onTriggerTransition,
  showUnlockStudentForms = false,
  onUnlockStudentForms,
  unlockFormsBusy = false,
  showRollback = false,
  onRollback,
  rollbackBusy = false,
  showRestart = false,
  onRestart,
  onRestartComplete,
  restartBusy = false,
  showCourseSelection = true,
  contextSummaryTitle = 'پرونده و سابقه (قبل از اقدام)',
  actionsBoxStyle,
  testId = 'operator-process-instance-panel',
}) {
  const [decisionNotesInternal, setDecisionNotesInternal] = useState('')
  const [triggerBusy, setTriggerBusy] = useState(false)

  const decisionNotes = decisionNotesProp !== undefined ? decisionNotesProp : decisionNotesInternal
  const setDecisionNotes = setDecisionNotesProp || setDecisionNotesInternal

  if (!instanceDetail) return null

  const instanceId = instanceDetail.instance_id
  let transitionsForActions = availableTransitions
  if (typeof filterTransitions === 'function') {
    transitionsForActions = filterTransitions(availableTransitions)
  }

  const defaultTrigger = async (transition) => {
    if (!instanceId) return
    const triggerEvent = typeof transition === 'string' ? transition : transition.trigger_event
    const toState = typeof transition === 'object' ? transition.to_state : undefined
    setTriggerBusy(true)
    try {
      const payload = { ...notesPayload(decisionNotes), ...(toState ? { to_state: toState } : {}) }
      await processExecApi.trigger(instanceId, {
        trigger_event: triggerEvent,
        payload,
        ...(toState ? { to_state: toState } : {}),
      })
      showToast?.('اقدام ثبت شد')
      onRefreshInstance?.()
    } catch (e) {
      const d = e?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : (e.message || 'خطا در اجرای اقدام'), 'error')
    } finally {
      setTriggerBusy(false)
    }
  }

  const triggerTransition = onTriggerTransition || defaultTrigger

  const actionBox = actionsBoxStyle || {
    padding: '1.25rem',
    background: 'var(--info-light, #eff6ff)',
    borderRadius: '10px',
    marginBottom: '1.5rem',
    borderRight: '4px solid var(--info, #2563eb)',
  }

  return (
    <div className="card" data-testid={testId}>
      <div className="card-header">
        <h3 className="card-title">{labelProcess(instanceDetail.process_code)}</h3>
        {onClose && (
          <button type="button" onClick={onClose} className="btn btn-outline btn-sm">بستن</button>
        )}
      </div>

      {!instanceDetail.is_completed && !instanceDetail.is_cancelled && showUnlockStudentForms && onUnlockStudentForms && (
        <div style={{ marginBottom: '1.25rem', padding: '1rem', background: '#f0fdf4', borderRadius: '8px', borderRight: '4px solid #16a34a' }}>
          <button
            type="button"
            className="btn btn-outline btn-sm"
            disabled={unlockFormsBusy}
            onClick={onUnlockStudentForms}
            style={{ marginBottom: '0.5rem' }}
          >
            {unlockFormsBusy ? 'در حال انجام…' : 'باز کردن امکان ویرایش فرم مرحله برای دانشجو'}
          </button>
          <p style={{ fontSize: '0.78rem', color: '#166534', margin: 0, lineHeight: 1.6 }}>
            اگر دانشجو فرم این مرحله را ثبت کرده و دیگر نمی‌تواند ویرایش کند، با این دکمه اجازهٔ ویرایش مجدد را می‌دهید.
          </p>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
        <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
          <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>وضعیت</label>
          <div style={{ fontWeight: 700, color: 'var(--primary)' }}>{labelState(instanceDetail.current_state)}</div>
        </div>
        <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
          <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>تاریخ شروع</label>
          <div>{instanceDetail.started_at ? new Date(instanceDetail.started_at).toLocaleDateString('fa-IR') : '-'}</div>
        </div>
      </div>

      <OperatorInstanceGuidanceBlock
        instanceDetail={instanceDetail}
        portalRole={user?.role}
        availableTransitions={availableTransitions}
      />

      {showCourseSelection && (
        <OperatorCourseSelectionEditor
          instanceId={instanceId}
          processCode={instanceDetail.process_code}
          currentState={instanceDetail.current_state}
          contextData={instanceDetail.context_data}
          isCompleted={instanceDetail.is_completed}
          isCancelled={instanceDetail.is_cancelled}
          showToast={showToast}
          onUpdated={() => onRefreshInstance?.()}
        />
      )}

      <OperatorStepFormsSection
        instanceId={instanceId}
        processCode={instanceDetail.process_code}
        currentState={instanceDetail.current_state}
        contextData={instanceDetail.context_data}
        isCompleted={instanceDetail.is_completed}
        isCancelled={instanceDetail.is_cancelled}
        role={user?.role}
        showToast={showToast}
        onUpdated={() => onRefreshInstance?.()}
      />

      {!isInstituteLevelProcess(instanceDetail.process_code) && (
        <ProcessDataManager
          instanceId={instanceId}
          role={user?.role}
          showToast={showToast}
          onUpdated={() => onRefreshInstance?.()}
        />
      )}

      <InstanceContextSummary
        contextData={instanceDetail.context_data}
        history={instanceDetail.history}
        title={contextSummaryTitle}
      />

      {showRollback && onRollback && (
        <ProcessRollbackSection
          user={user}
          instanceDetail={instanceDetail}
          onRollback={onRollback}
          busy={rollbackBusy}
        />
      )}

      {showRestart && onRestart && (
        <ProcessRestartSection
          user={user}
          instanceDetail={instanceDetail}
          onRestart={onRestart}
          onRestartComplete={onRestartComplete}
          busy={restartBusy}
        />
      )}

      {typeof renderExtraBeforeActions === 'function' && renderExtraBeforeActions({
        triggerTransition,
        transitionsForActions,
        triggerBusy,
      })}

      {transitionsForActions.length > 0 && (
        <div style={actionBox}>
          <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--info, #1e40af)' }}>اقدامات</h4>
          <DecisionNotesBlock
            value={decisionNotes}
            onChange={setDecisionNotes}
            title="توضیح یا نظر (اختیاری)"
            hint="متن همراه همان دکمه‌ای که می‌زنید در پرونده ثبت می‌شود."
          />
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {transitionsForActions.map((t, idx) => {
              const isApproval = t.trigger_event?.includes('approved') || t.trigger_event?.includes('confirm') || t.trigger_event?.includes('verified') || t.trigger_event?.includes('submitted') || t.trigger_event?.includes('done')
              const isReject = t.trigger_event?.includes('reject') || t.trigger_event?.includes('decline') || t.trigger_event?.includes('escalate')
              return (
                <button
                  key={`${t.trigger_event}-${t.to_state || idx}`}
                  type="button"
                  data-testid={`operator-transition-${t.trigger_event}`}
                  disabled={triggerBusy}
                  onClick={() => triggerTransition(t)}
                  style={{
                    padding: '0.6rem 1.2rem',
                    borderRadius: '8px',
                    border: 'none',
                    cursor: triggerBusy ? 'wait' : 'pointer',
                    fontWeight: 500,
                    fontSize: '0.85rem',
                    background: isApproval ? 'var(--success, #16a34a)' : isReject ? 'var(--danger, #dc2626)' : 'var(--primary, #2563eb)',
                    color: '#fff',
                    opacity: triggerBusy ? 0.7 : 1,
                  }}
                >
                  {t.description || t.trigger_event}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
