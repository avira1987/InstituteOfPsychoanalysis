import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'

const THRESHOLD_DAYS = 42

function parseDateLoose(raw) {
  if (raw == null || raw === '') return null
  if (raw instanceof Date) return Number.isNaN(raw.getTime()) ? null : raw
  const s = String(raw).trim()
  if (!s) return null
  const d = new Date(s)
  return Number.isNaN(d.getTime()) ? null : d
}

function diffInDays(start, end) {
  const a = parseDateLoose(start)
  const b = parseDateLoose(end)
  if (!a || !b) return null
  const ms = b.getTime() - a.getTime()
  if (ms < 0) return null
  return Math.round(ms / (1000 * 60 * 60 * 24))
}

function readDays(stepFormValues, ctx) {
  const raw = stepFormValues?.interruption_days ?? ctx.interruption_days
  if (raw != null && raw !== '') {
    const n = Number(raw)
    if (Number.isFinite(n)) return n
  }
  const start = stepFormValues?.interruption_start_date ?? ctx.interruption_start_date
  const end = stepFormValues?.interruption_end_date ?? ctx.interruption_end_date
  return diffInDays(start, end)
}

function BranchCard({ activeKey }) {
  const branches = [
    {
      key: 'short',
      title: 'وقفهٔ کوتاه (کمتر از ۴۲ روز)',
      color: '#16a34a',
      bg: '#f0fdf4',
      items: [
        'درمانگر و سوپروایزر شما حفظ می‌شوند.',
        'تاریخ‌های وقفه در پرونده ثبت می‌شود.',
        'در تاریخ پایان وقفه، بازگشت شما بررسی می‌شود.',
        'در صورت عدم بازگشت: آزادسازی منابع و ارجاع بیمار (برای انترن).',
      ],
    },
    {
      key: 'long',
      title: 'وقفهٔ بلند (۴۲ روز یا بیشتر)',
      color: '#d97706',
      bg: '#fffbeb',
      items: [
        'آزادسازی فوری وقت سوپروایزر و درمانگر.',
        'انتقال به فهرست‌های گذشته.',
        'ارجاع بیمار به فرایند patient_referral (برای انترن).',
        'ثبت تاریخ‌های وقفه در پرونده.',
      ],
    },
  ]
  return (
    <div style={{ display: 'grid', gap: '0.65rem', marginBottom: '0.85rem' }}>
      {branches.map((b) => {
        const isActive = activeKey === b.key
        return (
          <div
            key={b.key}
            data-testid={`therapy-interruption-branch-${b.key}`}
            style={{
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: isActive ? b.bg : '#f8fafc',
              borderRight: `4px solid ${b.color}`,
              fontSize: '0.84rem',
              lineHeight: 1.7,
              opacity: activeKey && !isActive ? 0.6 : 1,
            }}
          >
            <strong style={{ display: 'block', marginBottom: '0.35rem', color: b.color }}>
              {b.title}
              {isActive && (
                <span style={{ marginInlineStart: '0.4rem', fontSize: '0.75rem' }}>← مسیر فعلی</span>
              )}
            </strong>
            <ul style={{ margin: 0, paddingInlineStart: '1.1rem' }}>
              {b.items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        )
      })}
    </div>
  )
}

/**
 * داشبورد راهنمای «وقفه در درمان آموزشی توسط دانشجو» — فرایند ۱۶ (therapy_interruption).
 * نمایشی/راهنما؛ ورود داده از ProcessStepForms انجام می‌شود.
 */
export default function StudentTherapyInterruptionPanel({
  detail = null,
  stepFormValues = {},
  active = true,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null

  const days = useMemo(() => readDays(stepFormValues, ctx), [stepFormValues, ctx])
  const branchKey = days == null ? null : (days >= THRESHOLD_DAYS ? 'long' : 'short')

  const meetingDate = ctx.meeting_date || ctx.committee_meeting_date || null
  const meetingTime = ctx.meeting_time || ctx.committee_meeting_time || null
  const meetingMode = ctx.meeting_mode || ctx.committee_meeting_mode || null
  const rejectionNote = ctx.rejection_reason || ctx.committee_note || ctx.decision_note || null
  const returnDate = ctx.interruption_end_date || ctx.end_date || ctx.return_date || null

  if (!active || !detail || detail.process_code !== 'therapy_interruption') {
    return null
  }

  return (
    <div className="card" data-testid="student-therapy-interruption-panel">
      <div className="card-header">
        <h3 className="card-title">وقفه در درمان آموزشی (فرایند ۱۶)</h3>
        {currentState && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: '0 1rem 1rem' }}>
        {currentState === 'request_submitted' && (
          <div
            data-testid="therapy-interruption-init-hint"
            style={{
              marginBottom: '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: '#eff6ff',
              borderRight: '4px solid #2563eb',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#1e3a8a',
            }}
          >
            تاریخ شروع و پایان وقفه را در فرم زیر وارد کنید و سپس «ادامه و ثبت مرحله» را بزنید.
            درخواست شما برای تعیین جلسه به کمیتهٔ پیشرفت ارجاع می‌شود.
          </div>
        )}

        <div
          data-testid="therapy-interruption-financial-note"
          style={{
            marginBottom: '0.85rem',
            padding: '0.7rem 0.9rem',
            borderRadius: '8px',
            background: '#f0fdf4',
            borderRight: '4px solid #16a34a',
            fontSize: '0.84rem',
            lineHeight: 1.7,
            color: '#14532d',
          }}
        >
          <strong>قانون مالی:</strong> بابت جلسات بازهٔ وقفه بدهکار نمی‌شوید.
        </div>

        {days != null && (
          <div
            data-testid="therapy-interruption-duration-preview"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem',
              borderRadius: '10px',
              background: branchKey === 'long' ? '#fffbeb' : '#f0fdf4',
              borderRight: `4px solid ${branchKey === 'long' ? '#d97706' : '#16a34a'}`,
            }}
          >
            <div style={{ fontSize: '0.78rem', color: '#64748b' }}>طول وقفه (پیش‌نمایش)</div>
            <div style={{
              fontSize: '1.25rem',
              fontWeight: 800,
              color: branchKey === 'long' ? '#92400e' : '#14532d',
            }}
            >
              {days.toLocaleString('fa-IR')}
              <span style={{ fontSize: '0.85rem', fontWeight: 500 }}> روز</span>
            </div>
            <div style={{ fontSize: '0.8rem', color: '#78716c', marginTop: '0.25rem' }}>
              {branchKey === 'long'
                ? 'این بازه ۴۲ روز یا بیشتر است؛ منابع بلافاصله آزاد می‌شوند.'
                : 'این بازه کمتر از ۴۲ روز است؛ درمانگر و سوپروایزر حفظ می‌شوند.'}
            </div>
          </div>
        )}

        {(currentState === 'request_submitted'
          || currentState === 'committee_scheduling'
          || currentState === 'meeting_held') && (
          <BranchCard activeKey={branchKey} />
        )}

        {currentState === 'committee_scheduling' && (
          <div
            data-testid="therapy-interruption-scheduling"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#eff6ff',
              borderRight: '4px solid #2563eb',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#1e3a8a',
            }}
          >
            درخواست شما ثبت شد. کمیتهٔ پیشرفت در حال تعیین تاریخ و ساعت جلسه است؛
            جزئیات جلسه از طریق پورتال، پیامک و ایمیل به شما اطلاع‌رسانی می‌شود.
          </div>
        )}

        {(meetingDate || meetingTime || meetingMode) && (
          <div
            data-testid="therapy-interruption-meeting-details"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f5f3ff',
              borderRight: '4px solid #7c3aed',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#4c1d95',
            }}
          >
            <strong style={{ display: 'block', marginBottom: '0.35rem' }}>جزئیات جلسهٔ کمیته</strong>
            {meetingDate && <div>تاریخ: {meetingDate}</div>}
            {meetingTime && <div>ساعت: {meetingTime}</div>}
            {meetingMode && <div>نحوهٔ برگزاری: {meetingMode}</div>}
          </div>
        )}

        {currentState === 'awaiting_return' && (
          <div
            data-testid="therapy-interruption-awaiting-return"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#fffbeb',
              borderRight: '4px solid #d97706',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#92400e',
            }}
          >
            <strong style={{ display: 'block', marginBottom: '0.35rem' }}>در انتظار بازگشت</strong>
            وقفهٔ شما تأیید شد و درمانگر و سوپروایزر حفظ شده‌اند.
            {returnDate && (
              <>
                {' '}
                لطفاً در تاریخ پایان وقفه ({returnDate}) درمان را از سر بگیرید.
              </>
            )}
            {' '}
            در صورت عدم بازگشت، منابع آزاد و بیمار ارجاع داده می‌شود.
          </div>
        )}

        {currentState === 'rejected' && (
          <div
            role="alert"
            data-testid="therapy-interruption-rejected"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#fef2f2',
              borderRight: '4px solid #dc2626',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#7f1d1d',
            }}
          >
            <strong style={{ display: 'block', marginBottom: '0.35rem' }}>درخواست وقفه رد شد</strong>
            {rejectionNote
              ? <span>توضیحات کمیته: {rejectionNote}</span>
              : <span>کمیتهٔ پیشرفت با درخواست وقفه موافقت نکرد. گزارش به کمیتهٔ نظارت ارسال شد.</span>}
          </div>
        )}

        {currentState === 'returned_successfully' && (
          <div
            data-testid="therapy-interruption-returned"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#f0fdf4',
              borderRight: '4px solid #16a34a',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#14532d',
            }}
          >
            بازگشت شما با موفقیت ثبت شد و درمان از سر گرفته شد.
          </div>
        )}

        {(currentState === 'no_return_resources_freed'
          || currentState === 'long_interruption_applied') && (
          <div
            data-testid="therapy-interruption-resources-freed"
            style={{
              marginBottom: '0.85rem',
              padding: '0.85rem 1rem',
              borderRadius: '10px',
              background: '#fff7ed',
              borderRight: '4px solid #ea580c',
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: '#9a3412',
            }}
          >
            <strong style={{ display: 'block', marginBottom: '0.35rem' }}>آزادسازی منابع</strong>
            {currentState === 'long_interruption_applied'
              ? 'به دلیل وقفهٔ ۴۲ روز یا بیشتر، وقت درمانگر و سوپروایزر آزاد شد و بیمار (در صورت انترن بودن) ارجاع داده شد.'
              : 'به دلیل عدم بازگشت در تاریخ پایان وقفه، منابع آزاد و بیمار ارجاع داده شد.'}
          </div>
        )}
      </div>
    </div>
  )
}
