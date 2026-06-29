import React, { useMemo, useState } from 'react'
import { processExecApi } from '../services/api'
import { labelState } from '../utils/processDisplay'
import {
  TaAssistantFlowStepper,
  TA_ASSISTANT_STATE_HINTS,
  TA_ASSISTANT_STOP_MESSAGES,
  resolveTaUpgradeContext,
  isTaAssistantStopState,
  HintBlock,
  InfoTile,
} from '../utils/taToAssistantFacultyDisplay'

const PROCESS_TITLE_FA = 'ارتقا به دستیار هیئت علمی (فرایند ۴۹)'

/**
 * داشبورد کمک‌مدرس — فرایند ۴۹.
 */
export default function TaToAssistantFacultyTaPanel({
  detail = null,
  studentId = null,
  active = true,
  compact = false,
  showToast = null,
  onAfterStart = null,
}) {
  const [busy, setBusy] = useState(false)
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const upgrade = useMemo(() => resolveTaUpgradeContext(ctx), [ctx])

  if (!active || !detail || detail.process_code !== 'ta_to_assistant_faculty') {
    return null
  }

  const isStop = isTaAssistantStopState(currentState)
  const isComplete = currentState === 'upgrade_applied'
  const hint = TA_ASSISTANT_STOP_MESSAGES[currentState]
    || TA_ASSISTANT_STATE_HINTS[currentState]
    || 'مراحل ارتقا به دستیار هیئت علمی را طبق راهنمای پنل پیش ببرید.'

  const startManualRetry = async () => {
    if (!studentId || busy) return
    const courseCode = ctx.course_code
    if (!courseCode) {
      showToast?.('کد درس برای درخواست مجدد مشخص نیست.', 'error')
      return
    }
    setBusy(true)
    try {
      const res = await processExecApi.start({
        process_code: 'ta_to_assistant_faculty',
        student_id: studentId,
        initial_context: {
          course_code: courseCode,
          manual_retry: true,
          source: 'ta_manual_retry',
        },
      })
      showToast?.(`درخواست ارزیابی مجدد ثبت شد: ${labelState(res.data?.current_state)}`)
      onAfterStart?.(res.data)
    } catch (err) {
      showToast?.(err.response?.data?.detail || 'خطا در ثبت درخواست', 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="card"
      data-testid="ta-assistant-faculty-ta-panel"
      style={{ marginBottom: compact ? '0.75rem' : '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isStop && currentState !== 'upgrade_applied' ? 'badge-danger' : isComplete ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <TaAssistantFlowStepper currentState={currentState} />

        {isStop && currentState !== 'upgrade_applied' && (
          <HintBlock tone="#dc2626" bg="#fef2f2">
            <strong>وضعیت:</strong>
            {' '}
            {hint}
          </HintBlock>
        )}

        {!isStop && (
          <HintBlock tone="#d97706" bg="#fffbeb">
            {hint}
          </HintBlock>
        )}

        {isComplete && (
          <HintBlock tone="#16a34a" bg="#f0fdf4">
            {hint}
          </HintBlock>
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '0.65rem',
            marginBottom: '0.75rem',
          }}
        >
          <InfoTile label="درس" value={upgrade.courseName} />
          <InfoTile label="سابقه TA" value={upgrade.passSummary} />
          <InfoTile label="رتبه فعلی" value={upgrade.currentRankFa} />
        </div>

        {currentState === 'supervision_rejected' && (
          <div style={{ marginTop: '0.5rem' }}>
            {upgrade.portalMessageFa && (
              <p style={{ fontSize: '0.84rem', lineHeight: 1.7, color: '#334155', marginBottom: '0.75rem' }}>
                {upgrade.portalMessageFa}
              </p>
            )}
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={busy}
              onClick={startManualRetry}
              data-testid="ta-assistant-manual-retry-btn"
            >
              {busy ? 'در حال ثبت…' : 'درخواست ارزیابی مجدد برای ارتقا'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
