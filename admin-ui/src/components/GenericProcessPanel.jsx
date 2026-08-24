import React, { useState } from 'react'
import ProcessStepForms from './ProcessStepForms'
import UnifiedFormRenderer from './UnifiedFormRenderer'
import InstanceContextSummary from './InstanceContextSummary'
import DecisionNotesBlock from './DecisionNotesBlock'
import { usesGenericProcessPanel } from '../utils/processPanelRegistry'
import { labelProcess, labelState } from '../utils/processDisplay'
import {
  STUDENT_TRANSITION_CTA_INTRO,
  getStudentTransitionButtonMain,
  getStudentTransitionButtonSub,
  getStudentTransitionTooltip,
} from '../utils/studentTransitionCta'

function operatorTransitionTone(triggerEvent) {
  const ev = triggerEvent || ''
  if (ev.includes('approved') || ev.includes('confirm') || ev.includes('verified') || ev.includes('submitted') || ev.includes('done')) {
    return 'var(--success, #16a34a)'
  }
  if (ev.includes('reject') || ev.includes('decline') || ev.includes('escalate')) {
    return 'var(--danger, #dc2626)'
  }
  return 'var(--primary, #2563eb)'
}

/**
 * پوستهٔ عمومی فرایند: راهنما + فرم متادیتا + انتقال‌های مجاز + تاریخچه.
 * پنل سفارشی اختیاری است (children)؛ بدون آن هم مرحله از UI قابل تکمیل است.
 */
export default function GenericProcessPanel({
  audience = 'student',
  instanceDetail = null,
  children = null,
  guidance = null,
  hideGuidance = false,
  formsNode = null,
  hideForms = false,
  forms,
  values,
  onFieldChange,
  disabled = false,
  onRegisterSubmit,
  hasAvailableTransitions = true,
  instanceId = null,
  resubmitFieldNames = null,
  contextData = null,
  studentProfile = null,
  extraData = null,
  currentState = null,
  operatorSchemaJson = null,
  operatorFormProps = null,
  transitions = [],
  hideTransitions = false,
  onTriggerTransition,
  decisionNotes = '',
  onDecisionNotesChange,
  triggerBusy = false,
  extraBeforeActions = null,
  historyNode = null,
  hideHistory = false,
  historyTitle = 'پرونده و سابقه (قبل از اقدام)',
  user = null,
  formsForHistory = null,
  extraLabelForms = null,
  transitionBlockedHint = null,
  testId = 'generic-process-panel',
}) {
  const [selectedIdx, setSelectedIdx] = useState(0)
  const processCode = instanceDetail?.process_code
  const audienceKey = audience === 'staff' ? 'operator' : audience
  const genericFallback = usesGenericProcessPanel(processCode, audienceKey)

  const studentFormsNode = !hideForms && !formsNode && audience === 'student' ? (
    <ProcessStepForms
      forms={forms}
      values={values}
      onFieldChange={onFieldChange}
      disabled={disabled}
      onRegisterSubmit={onRegisterSubmit}
      hasAvailableTransitions={hasAvailableTransitions}
      instanceId={instanceId || instanceDetail?.instance_id}
      resubmitFieldNames={resubmitFieldNames}
      contextData={contextData ?? instanceDetail?.context_data}
      studentProfile={studentProfile}
      extraData={extraData}
      currentState={currentState ?? instanceDetail?.current_state}
    />
  ) : null

  const operatorFormsNode = !hideForms && !formsNode && audience === 'operator' && operatorSchemaJson ? (
    <UnifiedFormRenderer
      schemaJson={operatorSchemaJson}
      values={values || {}}
      onChange={(next) => {
        const prev = values || {}
        Object.keys({ ...prev, ...next }).forEach((k) => {
          if (next[k] !== prev[k]) onFieldChange?.(k, next[k])
        })
      }}
      disabled={disabled}
      {...(operatorFormProps || {})}
    />
  ) : null

  const renderedForms = hideForms ? null : (formsNode || studentFormsNode || operatorFormsNode)

  const list = Array.isArray(transitions) ? transitions : []
  const selected = list[Math.min(selectedIdx, Math.max(0, list.length - 1))] || list[0]
  const showTransitions = !hideTransitions && list.length > 0 && typeof onTriggerTransition === 'function'

  const defaultHistory = !hideHistory && !historyNode && instanceDetail ? (
    <InstanceContextSummary
      contextData={instanceDetail.context_data}
      history={instanceDetail.history}
      forms={formsForHistory || forms}
      extraLabelForms={extraLabelForms}
      portalRole={user?.role}
      instanceDetail={instanceDetail}
      showTechnicalContext={user?.role === 'admin'}
      showOperatorCaseFacts={audience !== 'student'}
      title={historyTitle}
    />
  ) : null

  return (
    <div
      className="generic-process-panel"
      data-testid={testId}
      data-audience={audience}
      data-generic-fallback={genericFallback ? 'true' : 'false'}
      data-process-code={processCode || ''}
    >
      {!hideGuidance && (guidance || instanceDetail) && (
        <div className="generic-process-panel__guidance" style={{ marginBottom: '1rem' }}>
          {guidance || (
            <div style={{ padding: '0.75rem 1rem', background: '#f8fafc', borderRadius: '8px' }}>
              <div style={{ fontWeight: 700 }}>{labelProcess(processCode)}</div>
              <div className="muted" style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}>
                وضعیت: {labelState(instanceDetail?.current_state)}
              </div>
            </div>
          )}
        </div>
      )}

      {children}

      {renderedForms}

      {transitionBlockedHint}

      {typeof extraBeforeActions === 'function'
        ? extraBeforeActions({
          transitions: list,
          transitionsForActions: list,
          triggerTransition: onTriggerTransition,
          triggerBusy,
        })
        : extraBeforeActions}

      {showTransitions && audience === 'student' && selected && (
        <div
          style={{
            padding: '1.25rem',
            background: 'linear-gradient(135deg, var(--primary-light) 0%, #f0f4ff 100%)',
            borderRadius: '10px',
            marginBottom: '1.5rem',
            borderRight: '4px solid var(--primary)',
          }}
          data-testid="process-detail-transition-block"
        >
          <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.5rem', color: 'var(--primary)' }}>
            قدم بعد در مسیر
          </h4>
          <p style={{ fontSize: '0.8rem', color: '#475569', marginBottom: '0.85rem', lineHeight: 1.75 }}>
            {STUDENT_TRANSITION_CTA_INTRO}
          </p>
          {list.length > 1 && (
            <div style={{ marginBottom: '0.85rem' }}>
              <label
                htmlFor="generic-process-transition-select"
                style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, marginBottom: '0.35rem' }}
              >
                انتخاب مسیر بعدی
              </label>
              <select
                id="generic-process-transition-select"
                data-testid="process-detail-transition-select"
                value={Math.min(selectedIdx, list.length - 1)}
                onChange={(e) => setSelectedIdx(Number(e.target.value))}
                style={{
                  width: '100%',
                  padding: '0.5rem 0.75rem',
                  borderRadius: '8px',
                  border: '1px solid var(--border)',
                  fontSize: '0.9rem',
                  background: 'var(--bg)',
                }}
              >
                {list.map((t, idx) => (
                  <option key={`${t.trigger_event}-${t.to_state}-${idx}`} value={idx}>
                    {labelState(t.to_state) !== '—' ? labelState(t.to_state) : (t.trigger_event || `مسیر ${idx + 1}`)}
                  </option>
                ))}
              </select>
            </div>
          )}
          {typeof onDecisionNotesChange === 'function' && (
            <DecisionNotesBlock
              value={decisionNotes}
              onChange={onDecisionNotesChange}
              title="توضیح همراه اقدام (اختیاری)"
              hint="با زدن دکمه، این متن به‌عنوان یادداشت همراه انتقال ثبت می‌شود (با مقادیر فرم ادغام می‌شود)."
            />
          )}
          <button
            type="button"
            data-testid={`process-detail-transition-${selected.to_state || selected.trigger_event || selectedIdx}`}
            onClick={() => onTriggerTransition(selected)}
            className="btn btn-primary"
            disabled={triggerBusy}
            title={getStudentTransitionTooltip(selected)}
            style={{ fontSize: '0.85rem', display: 'inline-flex', flexDirection: 'column', gap: '0.2rem' }}
          >
            <span>{getStudentTransitionButtonMain(selected, list.length)}</span>
            {selected.to_state && (
              <span style={{ fontSize: '0.7rem', opacity: 0.88 }}>
                {getStudentTransitionButtonSub(selected)}
              </span>
            )}
          </button>
        </div>
      )}

      {showTransitions && audience === 'operator' && (
        <div
          style={{
            padding: '1.25rem',
            background: 'var(--info-light, #eff6ff)',
            borderRadius: '10px',
            marginBottom: '1.5rem',
            borderRight: '4px solid var(--info, #2563eb)',
          }}
        >
          <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--info, #1e40af)' }}>اقدامات</h4>
          {typeof onDecisionNotesChange === 'function' && (
            <DecisionNotesBlock
              value={decisionNotes}
              onChange={onDecisionNotesChange}
              title="توضیح یا نظر (اختیاری)"
              hint="متن همراه همان دکمه‌ای که می‌زنید در پرونده ثبت می‌شود."
            />
          )}
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {list.map((t, idx) => (
              <button
                key={`${t.trigger_event}-${t.to_state || idx}`}
                type="button"
                data-testid={`operator-transition-${t.trigger_event}`}
                disabled={triggerBusy}
                onClick={() => onTriggerTransition(t)}
                style={{
                  padding: '0.6rem 1.2rem',
                  borderRadius: '8px',
                  border: 'none',
                  cursor: triggerBusy ? 'wait' : 'pointer',
                  fontWeight: 500,
                  fontSize: '0.85rem',
                  background: operatorTransitionTone(t.trigger_event),
                  color: '#fff',
                  opacity: triggerBusy ? 0.7 : 1,
                }}
              >
                {t.description || t.trigger_event}
              </button>
            ))}
          </div>
        </div>
      )}

      {!hideHistory && (historyNode || defaultHistory)}
    </div>
  )
}
