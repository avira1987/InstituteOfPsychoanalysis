import React, { useEffect, useMemo, useState } from 'react'
import { panelApi } from '../services/api'
import { labelState } from '../utils/processDisplay'
import {
  CancellationStatTile,
  ClassCancellationFlowStepper,
  ClassCancellationHintBlock,
  MakeupPreviewBlock,
  PROCESS_TITLE_FA,
  SessionPickList,
  STATE_HINTS,
  labelClassCancellationState,
  resolveClassCancellationContext,
} from '../utils/classSessionCancellationDisplay'
import { fmtIsoDate } from '../utils/lessonStartPerTermDisplay'

/**
 * پنل کنسل جلسات کلاس — فرایند ۵۶ (class_session_cancellation).
 */
export default function InstructorClassSessionCancellationPanel({
  detail = null,
  stepFormValues = {},
  active = true,
  compact = false,
  allowAllCourses = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const lessonCtx = useMemo(
    () => resolveClassCancellationContext(ctx, stepFormValues),
    [ctx, stepFormValues],
  )

  const [preview, setPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  const lessonId = lessonCtx.lessonId
    || stepFormValues?.lesson_id
    || ctx.lesson_id
  const sessionKey = lessonCtx.sessionKey
    || stepFormValues?.session_to_cancel
    || ctx.session_to_cancel

  useEffect(() => {
    if (!active || detail?.process_code !== 'class_session_cancellation') return
    if (currentState !== 'cancellation_request') return
    if (!lessonId) {
      setPreview(null)
      return
    }

    let cancelled = false
    setPreviewLoading(true)
    panelApi.classCancellationPreview(lessonId, sessionKey || undefined)
      .then((res) => {
        if (!cancelled) setPreview(res.data || null)
      })
      .catch(() => {
        if (!cancelled) setPreview(null)
      })
      .finally(() => {
        if (!cancelled) setPreviewLoading(false)
      })

    return () => { cancelled = true }
  }, [active, detail?.process_code, currentState, lessonId, sessionKey])

  const displayCtx = useMemo(() => {
    if (!preview) return lessonCtx
    return resolveClassCancellationContext(ctx, { ...stepFormValues, ...preview })
  }, [lessonCtx, preview, ctx, stepFormValues])

  if (!active || !detail || detail.process_code !== 'class_session_cancellation') {
    return null
  }

  const isTerminal = currentState === 'makeup_scheduled'
  const hint = STATE_HINTS[currentState] || 'ثبت کنسلی و جبرانی جلسه کلاس.'

  return (
    <div
      className="card"
      data-testid="instructor-class-session-cancellation-panel"
      style={{ marginBottom: compact ? 0 : '1.25rem' }}
    >
      {!compact && (
        <div className="card-header">
          <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
          {currentState && (
            <span
              className={`badge ${isTerminal ? 'badge-success' : 'badge-warning'}`}
              style={{ fontSize: '0.78rem' }}
            >
              {labelClassCancellationState(currentState) || labelState(currentState)}
            </span>
          )}
        </div>
      )}

      <div style={{ padding: compact ? '0' : '0 1rem 1rem' }}>
        {!compact && <ClassCancellationFlowStepper currentState={currentState} />}

        {displayCtx.violationPending && (
          <ClassCancellationHintBlock tone="warn">
            {displayCtx.violationHint
              || 'تخلف نظارت ۲ ساعته ثبت شده است. در اسرع وقت کنسلی و جبرانی را تأیید کنید.'}
          </ClassCancellationHintBlock>
        )}

        {!isTerminal && (
          <ClassCancellationHintBlock tone="info">
            {hint}
            {allowAllCourses && (
              <span>
                {' '}
                (دسترسی کمیته دروس — همهٔ کلاس‌های ترم)
              </span>
            )}
          </ClassCancellationHintBlock>
        )}

        {isTerminal ? (
          <ClassCancellationHintBlock tone="success">
            کنسلی ثبت شد.
            {displayCtx.cancelledSession && (
              <span>
                {' '}
                جلسهٔ
                {' '}
                {displayCtx.cancelledSession.session_number || '—'}
                {' '}
                مورخ
                {' '}
                {fmtIsoDate(displayCtx.cancelledSession.session_date)}
                {' '}
                کنسل شد.
              </span>
            )}
            {displayCtx.makeupSession && (
              <span>
                {' '}
                کلاس جبرانی:
                {' '}
                {fmtIsoDate(displayCtx.makeupSession.session_date)}
                {' '}
                ساعت
                {' '}
                {displayCtx.makeupSession.session_time || '—'}
                .
              </span>
            )}
            {displayCtx.studentsUpdated != null && (
              <span>
                {' '}
                (
                {displayCtx.studentsUpdated.toLocaleString('fa-IR')}
                {' '}
                پروندهٔ دانشجو به‌روز شد)
              </span>
            )}
            {' '}
            حضور جبرانی را پس از برگزاری در ستون جلسهٔ جبرانی ثبت کنید.
          </ClassCancellationHintBlock>
        ) : (
          <>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(9rem, 1fr))',
                gap: '0.65rem',
                marginBottom: '0.85rem',
              }}
            >
              <CancellationStatTile
                label="درس انتخابی"
                value={displayCtx.lessonLabel}
                accent={{ color: '#2563eb', bg: '#eff6ff' }}
              />
              <CancellationStatTile
                label="کنسلی ترم (این درس)"
                value={displayCtx.ordinalFa ? `${displayCtx.ordinalFa}` : '—'}
                sub={displayCtx.termWeekLabel || undefined}
                accent={{ color: '#0d9488', bg: '#f0fdfa' }}
              />
              <CancellationStatTile
                label="تاریخ جبرانی"
                value={displayCtx.makeupDate ? fmtIsoDate(displayCtx.makeupDate) : (previewLoading ? '…' : '—')}
                accent={{ color: '#7c3aed', bg: '#f5f3ff' }}
              />
              <CancellationStatTile
                label="ساعت جبرانی"
                value={displayCtx.makeupTime || (previewLoading ? '…' : '—')}
                sub={displayCtx.usualTime ? `ساعت معمول: ${displayCtx.usualTime}` : undefined}
                accent={{ color: '#7c3aed', bg: '#f5f3ff' }}
              />
            </div>

            <MakeupPreviewBlock
              makeupDate={displayCtx.makeupDate}
              makeupTime={displayCtx.makeupTime}
              summary={displayCtx.makeupSummary}
              termWeekLabel={displayCtx.termWeekLabel}
              ordinalFa={displayCtx.ordinalFa}
            />

            <SessionPickList
              sessions={displayCtx.sessions}
              selectedKey={displayCtx.sessionKey}
              compact={compact}
            />
          </>
        )}
      </div>
    </div>
  )
}
