/** نمایش مشترک زنجیره قطع زودرس درمان (فرایندهای ۱۱–۱۳). */

import React from 'react'

export const TERMINATION_REASONS = {
  1: {
    label: 'دانشجو ترجیح می‌دهد درمانگر را تغییر دهد',
    path: 'standard',
    pathLabel: 'مسیر استاندارد',
    color: '#2563eb',
    bg: '#eff6ff',
  },
  2: {
    label: 'درمانگر ترجیح می‌دهد دانشجو با درمانگر دیگر ادامه دهد',
    path: 'standard',
    pathLabel: 'مسیر استاندارد',
    color: '#2563eb',
    bg: '#eff6ff',
  },
  3: {
    label: 'درمان تحلیلی نامناسب (پس از مشورت با کمیسیون تخصصی)',
    path: 'scientific',
    pathLabel: 'مسیر علمی',
    color: '#7c3aed',
    bg: '#f5f3ff',
  },
  4: {
    label: 'دانشجو مناسب درمان تحلیلی نیست (درمانگر دوم/سوم/...)',
    path: 'disciplinary',
    pathLabel: 'مسیر انضباطی',
    color: '#dc2626',
    bg: '#fef2f2',
  },
}

export const RESTART_SMS_TEXT_FA =
  'با توجه به قطع زودرس درمان آموزشی توسط درمانگر آموزشی‌تان، لازم است تا ۵ روز از تاریخ دریافت این پیام از فرایند «آغاز دوباره درمان آموزشی یا تغییر زمان یا تغییر درمانگر آموزشی در دوره آشنایی یا جامع» درمانگر آموزشی جدیدی را برای خود انتخاب فرمایید.'

export function parseReasonCode(raw) {
  if (raw == null || raw === '') return null
  const n = Number(raw)
  return Number.isFinite(n) && n >= 1 && n <= 4 ? n : null
}

export function terminationReasonLabel(ctx = {}) {
  const code = parseReasonCode(ctx.termination_reason_code ?? ctx.reason_code)
  if (code != null && TERMINATION_REASONS[code]) return TERMINATION_REASONS[code].label
  return ctx.termination_reason_display || '—'
}

export function resolveEntrySource(ctx = {}) {
  if (ctx.label) return String(ctx.label)
  const entry = ctx.entry_reason || ctx.reason
  if (entry === 'ineligibility_specialized_commission') {
    return 'ارجاع از کمیسیون تخصصی — عدم صلاحیت تخصصی'
  }
  if (entry === 'termination_reason_4' || parseReasonCode(ctx.termination_reason_code) === 4) {
    return 'مسیر انضباطی — علت ۴ (گزارش درمانگر)'
  }
  if (ctx.parent_process_code === 'specialized_commission_review') {
    return 'ارجاع از کمیسیون تخصصی — عدم صلاحیت تخصصی'
  }
  if (ctx.parent_process_code === 'therapy_early_termination') {
    return 'ارجاع مستقیم از فرایند قطع زودرس درمان'
  }
  return entry ? String(entry) : '—'
}

export function formatNezaratRecommendation(ctx = {}, stepFormValues = {}) {
  const code = stepFormValues.nezarat_recommendation_code ?? ctx.nezarat_recommendation_code
  const text = (stepFormValues.nezarat_recommendation_fa ?? ctx.nezarat_recommendation_fa ?? '').trim()
  if (text) return text
  if (code === 'continue') return 'پیشنهاد الف — مشکل قابل اغماض است (ادامه آموزش)'
  if (code === 'terminate') return 'پیشنهاد ب — تخلف محرز است (قطع آموزش)'
  return '—'
}

export function formatCommissionOpinion(ctx = {}) {
  const text = (ctx.commission_opinion_fa || ctx.commission_opinion_display || '').trim()
  if (text) return text
  if (ctx.entry_reason === 'ineligibility_specialized_commission') {
    return 'رد صلاحیت — ارجاع به کمیته‌ها'
  }
  return '—'
}

export function computeSlaRemaining(ctx, slaDays = 5, enteredAtKey = null) {
  const keys = enteredAtKey
    ? [enteredAtKey]
    : [
      'awaiting_restart_entered_at',
      'reason_submitted_at',
      'supervision_review_entered_at',
      'education_review_entered_at',
      'started_at',
    ]
  let enteredAt = null
  for (const k of keys) {
    if (ctx?.[k]) {
      enteredAt = ctx[k]
      break
    }
  }
  if (!enteredAt) return null
  const start = new Date(enteredAt)
  if (Number.isNaN(start.getTime())) return null
  const deadline = new Date(start)
  deadline.setDate(deadline.getDate() + slaDays)
  const now = new Date()
  const msLeft = deadline.getTime() - now.getTime()
  const daysLeft = Math.ceil(msLeft / (1000 * 60 * 60 * 24))
  return { daysLeft, deadline, expired: daysLeft <= 0 }
}

export function SlaBanner({ slaInfo, title, fallbackText }) {
  if (!slaInfo && !fallbackText) return null
  const expired = slaInfo?.expired
  return (
    <div
      style={{
        marginBottom: '0.85rem',
        padding: '0.75rem 1rem',
        borderRadius: '10px',
        background: expired ? '#fef2f2' : '#fffbeb',
        borderRight: `4px solid ${expired ? '#dc2626' : '#d97706'}`,
        fontSize: '0.86rem',
        lineHeight: 1.75,
      }}
    >
      {title && (
        <strong style={{ display: 'block', marginBottom: '0.35rem' }}>{title}</strong>
      )}
      {slaInfo ? (
        expired ? (
          <span style={{ color: '#991b1b' }}>مهلت به پایان رسیده است.</span>
        ) : (
          <span style={{ color: '#92400e' }}>
            {slaInfo.daysLeft.toLocaleString('fa-IR')}
            {' '}
            روز باقی‌مانده
            {slaInfo.deadline && (
              <>
                {' '}
                (مهلت:
                {' '}
                {slaInfo.deadline.toLocaleDateString('fa-IR')}
                )
              </>
            )}
          </span>
        )
      ) : (
        <span style={{ color: '#92400e' }}>{fallbackText}</span>
      )}
    </div>
  )
}

export function ReadonlyRow({ label, value, testId }) {
  if (!value || value === '—') return null
  return (
    <p
      data-testid={testId}
      style={{ margin: '0 0 0.5rem', fontSize: '0.84rem', lineHeight: 1.7 }}
    >
      <strong>{label}:</strong>
      {' '}
      {value}
    </p>
  )
}
