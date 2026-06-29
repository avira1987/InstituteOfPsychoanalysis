import React, { useMemo } from 'react'
import {
  IntroTermEndFlowStepper,
  labelIntroTermEndState,
  resolveTermEndContext,
  hasTranscriptsReady,
  showRegistrationReminder,
  THERAPY_BLOCK_MESSAGE_FA,
  fmtIsoDate,
} from '../utils/introductoryTermEndDisplay'

const PROCESS_TITLE_FA = 'پایان ترم دوره آشنایی (فرایند ۳۲)'

const SYSTEM_STATES = new Set([
  'grades_submitted',
  'transcript_generated',
  'therapy_check',
  'decline_list_generated',
])

/** راهنمای هر وضعیت برای دانشجو. */
const STATE_HINTS = {
  grades_submitted: 'تمام نمرات ترم توسط اساتید ثبت شده است. سامانه در حال تولید کارنامه ترمی و کارنامه تجمیعی شماست — این مرحله خودکار است؛ چند دقیقه بعد صفحه را تازه کنید.',
  transcript_generated: 'کارنامه ترمی و تجمیعی شما آماده است. از بخش «کارنامه‌ها» در تب پروفایل می‌توانید آن را مشاهده یا دانلود کنید. مراحل بعد (بررسی شرط درمان و اطلاع‌رسانی) به‌صورت خودکار ادامه می‌یابد.',
  therapy_check: 'سامانه در حال بررسی شرط درمان (برای پذیرش مشروط) است. اگر اقدامی از سمت شما لازم باشد، در همین صفحه اعلام می‌شود.',
  therapy_blocked: THERAPY_BLOCK_MESSAGE_FA,
  registration_notification_sent: 'پیامک مهلت ثبت‌نام ترم بعد برای شما ارسال شده است. در مهلت اعلام‌شده دروس ترم بعد را انتخاب و شهریه را پرداخت کنید.',
  decline_list_generated: 'فرایند پایان ترم در حال تکمیل است. در صورت افت تحصیلی، مسئول پذیرش ممکن است با شما تماس بگیرد.',
  followup_in_progress: 'مسئول پذیرش در حال پیگیری دانشجویان افت تحصیلی است. اگر برای شما تماس یا پیام ثبت شد، همان را دنبال کنید؛ در غیر این صورت نیازی به اقدام فوری در پنل نیست.',
  followup_complete: 'فرایند پایان ترم تکمیل شد. کارنامه‌ها در تب پروفایل در دسترس است؛ برای ترم بعد طبق پیامک و راهنمای پنل اقدام کنید.',
}

function InfoTile({ label, value, tone = '#2563eb', bg = '#eff6ff' }) {
  if (value == null || value === '') return null
  return (
    <div
      style={{
        padding: '0.75rem 0.85rem',
        borderRadius: '10px',
        background: bg,
        borderRight: `4px solid ${tone}`,
        minWidth: 0,
      }}
    >
      <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.2rem' }}>{label}</div>
      <div style={{ fontSize: '1.05rem', fontWeight: 800, color: tone }}>{value}</div>
    </div>
  )
}

/**
 * داشبورد راهنمای «پایان ترم دوره آشنایی» — فرایند ۳۲.
 */
export default function StudentIntroductoryTermEndPanel({
  detail = null,
  extraData = null,
  active = true,
  compact = false,
  onGoToProfile = null,
  onGoToProcesses = null,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const termEnd = useMemo(() => resolveTermEndContext(ctx, extraData || {}), [ctx, extraData])

  if (!active || !detail || detail.process_code !== 'introductory_term_end') {
    return null
  }

  const hint = STATE_HINTS[currentState]
    ?? 'پایان ترم دوره آشنایی — مراحل عمدتاً خودکار است؛ این صفحه را بعداً تازه کنید.'
  const isComplete = currentState === 'followup_complete'
  const showTranscripts = hasTranscriptsReady(currentState)
  const showTherapyBlock = currentState === 'therapy_blocked' || termEnd.therapyBlocked
  const showRegDeadline = showRegistrationReminder(currentState) && termEnd.nextTermDeadline

  const fmtGpa = (v) => {
    const n = Number(v)
    if (!Number.isFinite(n)) return null
    return n.toLocaleString('fa-IR', { maximumFractionDigits: 2 })
  }

  return (
    <div className="card" data-testid="student-introductory-term-end-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span
            className={`badge ${isComplete ? 'badge-success' : 'badge-warning'}`}
            style={{ fontSize: '0.78rem' }}
          >
            {labelIntroTermEndState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <IntroTermEndFlowStepper currentState={currentState} compact={compact} />

        {hint && (
          <div
            data-testid="intro-term-end-state-hint"
            style={{
              marginBottom: compact ? '0.65rem' : '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#eff6ff',
              borderRight: '4px solid #2563eb',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#1e3a8a',
            }}
          >
            {hint}
          </div>
        )}

        {SYSTEM_STATES.has(currentState) && currentState !== 'therapy_blocked' && (
          <p
            className="muted"
            style={{ margin: '0 0 0.75rem', fontSize: '0.82rem', lineHeight: 1.65 }}
          >
            این مرحله توسط سامانه انجام می‌شود؛ در صورت تأخیر، صفحه را یک‌بار تازه کنید.
          </p>
        )}

        {(termEnd.termCode || termEnd.termGpa != null || termEnd.cumulativeGpa != null) && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(160px, 1fr))',
              gap: '0.65rem',
              marginBottom: compact ? '0.65rem' : '0.85rem',
            }}
          >
            {termEnd.termCode && (
              <InfoTile label="ترم" value={String(termEnd.termCode)} tone="#0d9488" bg="#f0fdfa" />
            )}
            {fmtGpa(termEnd.termGpa) && (
              <InfoTile label="معدل ترم" value={fmtGpa(termEnd.termGpa)} tone="#2563eb" bg="#eff6ff" />
            )}
            {fmtGpa(termEnd.cumulativeGpa) && (
              <InfoTile label="معدل کل" value={fmtGpa(termEnd.cumulativeGpa)} tone="#7c3aed" bg="#f5f3ff" />
            )}
          </div>
        )}

        {showTranscripts && (
          <div
            data-testid="intro-term-end-transcripts-ready"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
            }}
          >
            <p style={{ margin: '0 0 0.5rem', fontSize: '0.86rem', color: '#166534', lineHeight: 1.7 }}>
              کارنامه ترمی و تجمیعی شما آماده است.
            </p>
            {typeof onGoToProfile === 'function' && (
              <button
                type="button"
                className="btn btn-sm btn-outline"
                data-testid="intro-term-end-go-transcripts"
                onClick={onGoToProfile}
              >
                مشاهده کارنامه‌ها در پروفایل
              </button>
            )}
          </div>
        )}

        {showTherapyBlock && (
          <div
            role="alert"
            data-testid="intro-term-end-therapy-blocked"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.84rem',
              lineHeight: 1.75,
              color: '#991b1b',
            }}
          >
            <strong style={{ display: 'block', marginBottom: '0.35rem' }}>مسدودیت ثبت‌نام ترم دوم</strong>
            {THERAPY_BLOCK_MESSAGE_FA}
            {typeof onGoToProcesses === 'function' && (
              <div style={{ marginTop: '0.65rem' }}>
                <button
                  type="button"
                  className="btn btn-sm btn-primary"
                  data-testid="intro-term-end-go-start-therapy"
                  onClick={onGoToProcesses}
                >
                  رفتن به فرایندها — آغاز درمان آموزشی
                </button>
              </div>
            )}
          </div>
        )}

        {showRegDeadline && (
          <div
            data-testid="intro-term-end-registration-deadline"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#fffbeb',
              borderRight: '4px solid #d97706',
              fontSize: '0.84rem',
              lineHeight: 1.7,
              color: '#92400e',
            }}
          >
            <strong>مهلت ثبت‌نام ترم بعد:</strong>
            {' '}
            {fmtIsoDate(termEnd.nextTermDeadline)}
          </div>
        )}

        {isComplete && (
          <div
            data-testid="intro-term-end-complete-block"
            style={{
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
            }}
          >
            <p style={{ margin: 0, fontSize: '0.84rem', color: '#166534', lineHeight: 1.7 }}>
              فرایند پایان ترم تکمیل شد. کارنامه‌ها در تب پروفایل در دسترس است.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
