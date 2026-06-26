/** نمایش مشترک زنجیره حضور و غیاب درمان (فرایند ۶) و غیبت بدون اطلاع (فرایند ۱۵). */

import React from 'react'
import { computeSlaRemaining, SlaBanner, ReadonlyRow } from './earlyTerminationChainDisplay'

export { computeSlaRemaining, SlaBanner, ReadonlyRow }

export const ATTENDANCE_STATES = {
  therapist_recording: {
    title: 'ثبت حضور و غیاب توسط درمانگر',
    hint: 'درمانگر باید تا پایان همان روز (۲۴:۰۰) وضعیت حاضر یا غایب را ثبت کند. در صورت عدم ثبت، پرونده به مسئول سایت ارجاع می‌شود.',
    color: '#2563eb',
    bg: '#eff6ff',
  },
  site_manager_pending: {
    title: 'پیگیری مسئول سایت',
    hint: 'درمانگر حضور/غیاب را ثبت نکرده است. پس از تماس یا پیگیری، «مسئول سایت پیگیری کرد» را بزنید. مهلت: ۲ روز؛ پس از آن پرونده به معاون آموزش اسکیت می‌شود.',
    color: '#dc2626',
    bg: '#fef2f2',
  },
  deputy_escalated: {
    title: 'اسکیلیشن به معاون مدیر آموزش',
    hint: 'مسئول سایت در مهلت ۲ روزه پیگیری نکرده است. معاون آموزش باید پرونده را بررسی کند.',
    color: '#d97706',
    bg: '#fffbeb',
  },
}

export const UNANNOUNCED_SITE_MANAGER_OPTIONS = [
  {
    key: 'option_1',
    trigger: 'site_manager_option_1',
    title: 'گزینه ۱ — قصد غیبت معین',
    items: [
      'ارسال SMS به دانشجو',
      'ثبت تخلف آموزشی (دو جلسه پیوسته No-Show)',
    ],
    color: '#dc2626',
  },
  {
    key: 'option_2',
    trigger: 'site_manager_option_2',
    title: 'گزینه ۲ — قطع قطعی درمان',
    items: [
      'آزادسازی وقت درمانگر و انتقال به گذشته',
      'ارسال SMS قطع درمان',
      'ارجاع به رئیس کمیته درمان آموزشی',
    ],
    color: '#7c3aed',
  },
  {
    key: 'option_3',
    trigger: 'site_manager_option_3',
    title: 'گزینه ۳ — وضعیت مبهم',
    items: [
      'آزادسازی وقت درمانگر',
      'ارسال SMS به دانشجو',
      'تایمر ۳ هفته برای بازگشت یا ارجاع به کمیته',
    ],
    color: '#d97706',
  },
]

export const UNANNOUNCED_EXECUTOR_OPTIONS = [
  {
    key: 'option_a',
    trigger: 'executor_option_a',
    title: 'گزینه الف — قطع درمان قطعی',
    items: [
      'ثبت نتیجه در پرونده دانشجو',
      'اطمینان از آزادسازی وقت درمانگر',
      'ثبت تخلف آموزشی',
    ],
    color: '#dc2626',
  },
  {
    key: 'option_b',
    trigger: 'executor_option_b',
    title: 'گزینه ب — پذیرفته بازگشت',
    items: [
      'ثبت توافق بازگشت در پرونده دانشجو',
      'ثبت تخلف آموزشی (غیبت پیوسته)',
    ],
    color: '#16a34a',
  },
]

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

export function OptionCard({ option, testIdPrefix }) {
  return (
    <div
      data-testid={`${testIdPrefix}-${option.key}`}
      style={{
        padding: '0.75rem 1rem',
        borderRadius: '10px',
        background: '#f8fafc',
        borderRight: `4px solid ${option.color}`,
        fontSize: '0.84rem',
        lineHeight: 1.7,
      }}
    >
      <strong style={{ display: 'block', marginBottom: '0.35rem', color: option.color }}>
        {option.title}
      </strong>
      <ul style={{ margin: 0, paddingInlineStart: '1.1rem' }}>
        {option.items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

export function formatSessionContext(ctx = {}) {
  const parts = []
  if (ctx.session_date) parts.push(`تاریخ جلسه: ${ctx.session_date}`)
  if (ctx.therapy_session_id || ctx.session_id) {
    parts.push(`شناسه جلسه: ${ctx.therapy_session_id || ctx.session_id}`)
  }
  if (ctx.consecutive_unannounced_count != null) {
    parts.push(`تعداد غیبت پیوسته: ${Number(ctx.consecutive_unannounced_count).toLocaleString('fa-IR')}`)
  }
  return parts
}
