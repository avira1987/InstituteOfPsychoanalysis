/** نمایش مشترک زنجیره تکمیل ۵۰ ساعت سوپرویژن فردی (فرایند ۲۰). */

import React from 'react'
import { computeSlaRemaining, SlaBanner, ReadonlyRow } from './earlyTerminationChainDisplay'

export { computeSlaRemaining, SlaBanner, ReadonlyRow }

export const EVALUATION_WARNING_FA =
  'سوپروایزر گرامی، از آنجایی که سوپروایزی شما به ۵۰مین حضور خود در این دوره سوپرویژن رسیده است، لازم است ظرف حداکثر ۳ روز آینده فرم «ارزیابی دانشجو بعد از ۵۰ ساعت سوپرویژن فردی» را تکمیل کنید.'

export const REMINDER_45_48_SMS_EXCERPT_FA =
  '…با نزدیک شدن به خاتمه ۵۰ ساعت سوپرویژن خود با سوپروایزر فعلی‌تان، الزامی است که از الان به شناسایی نام سوپروایزر بعدی…'

export const SUPERVISION_50H_STATES = {
  session_scheduled: {
    title: 'جلسه برنامه‌ریزی شده',
    hint: 'پس از رسیدن زمان جلسه، در صورت پرداخت (یا جلسه اول دوره اول) ثبت حضور/غیاب برای سوپروایزر باز می‌شود. بدون پرداخت، غیبت خودکار ثبت می‌شود.',
    color: '#64748b',
    bg: '#f8fafc',
  },
  supervisor_recording: {
    title: 'ثبت حضور/غیاب توسط سوپروایزر',
    hint: 'تا پایان همان روز (۲۴:۰۰) وضعیت حاضر یا غایب را ثبت کنید. فقط «حاضر» یک ساعت به بلوک فعلی اضافه می‌کند. اگر پرداخت نشده باشد، فقط «غایب» قابل ثبت است.',
    color: '#2563eb',
    bg: '#eff6ff',
  },
  site_manager_pending: {
    title: 'پیگیری مسئول سایت',
    hint: 'سوپروایزر حضور/غیاب را ثبت نکرده است. پس از تماس، «مسئول سایت پیگیری کرد» را بزنید. مهلت: ۲ روز؛ سپس پرونده به معاون آموزش اسکیت می‌شود.',
    color: '#dc2626',
    bg: '#fef2f2',
  },
  deputy_escalated: {
    title: 'اسکیلیشن به معاون مدیر آموزش',
    hint: 'مسئول سایت در مهلت ۲ روزه پیگیری نکرده است. معاون آموزش باید پرونده را بررسی کند.',
    color: '#d97706',
    bg: '#fffbeb',
  },
  evaluation_pending: {
    title: 'تکمیل فرم ارزیابی ۵۰ ساعت',
    hint: EVALUATION_WARNING_FA,
    color: '#7c3aed',
    bg: '#f5f3ff',
  },
  evaluation_completed: {
    title: 'ارزیابی تکمیل شد',
    hint: 'فرم ارزیابی پایان دوره ثبت شده است. این سیکل جلسه به پایان رسید.',
    color: '#16a34a',
    bg: '#f0fdf4',
  },
  evaluation_sla_breach: {
    title: 'عدم تکمیل فرم در ۳ روز',
    hint: 'مهلت ۳ روزه برای تکمیل فرم ارزیابی گذشته است. گزارش تخلف به کمیته نظارت ارسال می‌شود.',
    color: '#dc2626',
    bg: '#fef2f2',
  },
  session_completed: {
    title: 'جلسه تکمیل شد',
    hint: 'حضور ثبت شد و یک ساعت به بلوک فعلی اضافه شد.',
    color: '#16a34a',
    bg: '#f0fdf4',
  },
  absence_recorded: {
    title: 'غیبت ثبت شد',
    hint: 'غیبت ثبت شده است. فرایند تعیین تکلیف هزینه (فرایند ۷) آغاز می‌شود.',
    color: '#7c3aed',
    bg: '#f5f3ff',
  },
  auto_absence_unpaid: {
    title: 'غیبت خودکار (پرداخت نشده)',
    hint: 'دانشجو هزینه جلسه را پرداخت نکرده بود. غیبت خودکار ثبت و تعیین تکلیف هزینه آغاز می‌شود.',
    color: '#dc2626',
    bg: '#fef2f2',
  },
  recording_closed: {
    title: 'ثبت بسته شد',
    hint: 'جلسه کنسل شده یا دانشجو در وقفه سوپرویژن است — ثبت حضور/غیاب بسته شد.',
    color: '#64748b',
    bg: '#f1f5f9',
  },
}

export function HintBlock({ testId, title, children, color = '#2563eb', bg = '#eff6ff' }) {
  return (
    <div
      data-testid={testId}
      style={{
        marginBottom: '0.85rem',
        padding: '0.75rem 1rem',
        borderRadius: '10px',
        background: bg,
        borderRight: `4px solid ${color}`,
        fontSize: '0.86rem',
        lineHeight: 1.75,
      }}
    >
      {title && (
        <strong style={{ display: 'block', marginBottom: '0.35rem', color }}>{title}</strong>
      )}
      {children}
    </div>
  )
}

export function BlockProgressBar({ hours = 0, max = 50, blockNumber = null }) {
  const h = Number(hours)
  const safe = Number.isFinite(h) ? Math.max(0, Math.min(max, h)) : 0
  const pct = max > 0 ? Math.round((safe / max) * 100) : 0
  const nearEnd = safe >= 45 && safe < 50
  const at49 = safe === 49 || safe >= 49
  const tone = at49 ? '#7c3aed' : nearEnd ? '#d97706' : '#0d9488'

  return (
    <div
      data-testid="supervision-50h-block-progress"
      style={{ marginBottom: '0.85rem' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '0.35rem' }}>
        <span style={{ color: '#475569' }}>
          پیشرفت بلوک
          {blockNumber != null ? ` ${Number(blockNumber).toLocaleString('fa-IR')}` : ''}
          {' '}
          (هدف: ۵۰ ساعت)
        </span>
        <span style={{ fontWeight: 700, color: tone }}>
          {safe.toLocaleString('fa-IR')}
          /
          {max.toLocaleString('fa-IR')}
        </span>
      </div>
      <div style={{ height: '10px', borderRadius: '999px', background: '#e2e8f0', overflow: 'hidden' }}>
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: tone,
            borderRadius: '999px',
            transition: 'width 0.3s ease',
          }}
        />
      </div>
      {nearEnd && !at49 && (
        <p style={{ fontSize: '0.75rem', color: '#92400e', margin: '0.35rem 0 0' }}>
          نزدیک پایان دوره — SMS یادآوری ۴۵/۴۸ ساعت (به‌جز دوره پنجم) ارسال می‌شود.
        </p>
      )}
      {at49 && (
        <p style={{ fontSize: '0.75rem', color: '#6d28d9', margin: '0.35rem 0 0' }}>
          جلسه ۴۹ — پس از ثبت حضور، پرداخت جلسه ۵۰ام و انتخاب سوپروایزر بعدی باز می‌شود.
        </p>
      )}
    </div>
  )
}

export function resolveBlockHours(ctx = {}) {
  const raw =
    ctx.current_supervision_block_hours
    ?? ctx.supervision_block_hours
    ?? ctx.block_hours
    ?? ctx.current_supervision_block_attendance
    ?? null
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
}

export function resolveBlockNumber(ctx = {}) {
  const raw = ctx.current_supervision_block_number ?? ctx.supervision_block_number ?? ctx.block_number ?? null
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
}

export function formatSupervisionSessionContext(ctx = {}) {
  const parts = []
  const sessionDate = ctx.supervision_session_date || ctx.session_date
  if (sessionDate) parts.push(`تاریخ جلسه: ${sessionDate}`)
  const sessionId = ctx.supervision_session_id || ctx.session_id
  if (sessionId) parts.push(`شناسه جلسه: ${sessionId}`)
  const blockNum = resolveBlockNumber(ctx)
  if (blockNum != null) parts.push(`بلوک سوپرویژن: ${blockNum.toLocaleString('fa-IR')}`)
  const blockHours = resolveBlockHours(ctx)
  if (blockHours != null) parts.push(`ساعات ثبت‌شده در بلوک: ${blockHours.toLocaleString('fa-IR')}`)
  if (ctx.reminder_45_48_sent_at) parts.push('SMS یادآوری ۴۵/۴۸ ساعت ارسال شده است.')
  if (ctx.payment_unlocked_for_50th_session) parts.push('قفل پرداخت جلسه ۵۰ام باز شده است.')
  if (ctx.block_counter_locked) parts.push('شمارنده بلوک قفل شده — دوره بعدی فعال است.')
  return parts
}

export function formatPaymentStatus(ctx = {}) {
  const paid = ctx.supervision_session_paid ?? ctx.session_paid
  if (paid === true) return 'پرداخت شده'
  if (paid === false) return 'پرداخت نشده'
  return null
}
