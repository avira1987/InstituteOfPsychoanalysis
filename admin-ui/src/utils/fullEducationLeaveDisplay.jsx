/** نمایش مشترک فرایند ۵۹ — مرخصی موقت از کل آموزش. */

import React from 'react'
import { formatShamsiTehran } from './shamsiDateTime'

export const FULL_LEAVE_SOP_WARNING_FA =
  'دانشجوی گرامی با اجرای این فرایند تمامی فعالیت‌های شما به غیر از درمان آموزشی در انستیتو متوقف خواهد شد.'

export const FULL_LEAVE_FLOW_STEPS = [
  { key: 'request', label: 'درخواست', states: ['leave_request'] },
  {
    key: 'committee',
    label: 'جلسه کمیته',
    states: ['committee_review', 'deputy_alerted', 'session_scheduled', 'committee_decision'],
  },
  { key: 'therapist', label: 'تعیین درمانگر', states: ['therapist_assignment'] },
  {
    key: 'on_leave',
    label: 'در مرخصی',
    states: ['on_leave', 'return_reminder_sent'],
  },
  {
    key: 'done',
    label: 'پایان',
    states: ['leave_rejected', 'leave_complete', 'violation_registered'],
  },
]

export const FULL_LEAVE_STATE_HINTS = {
  leave_request:
    'مدت مرخصی (۱ یا ۲ ترم) را انتخاب کنید. پس از ارسال، پرونده به کمیته پیشرفت ارجاع می‌شود.',
  committee_review: 'کمیته پیشرفت در حال بررسی درخواست شماست. پس از تعیین جلسه، جزئیات در همین صفحه نمایش داده می‌شود.',
  deputy_alerted: 'درخواست شما در صف بررسی کمیته است. به‌زودی زمان جلسه اعلام می‌شود.',
  session_scheduled:
    'زمان و نحوهٔ برگزاری جلسه در باکس زیر نمایش داده شده است؛ در روز مقرر طبق اعلام کمیته حاضر شوید.',
  committee_decision: 'جلسه کمیته برگزار شده یا در حال برگزاری است. نتیجهٔ نهایی از طریق کمیته اعلام می‌شود.',
  therapist_assignment:
    'در صورت تمایل به ادامه درمان، ظرف ۳ روز با مسئول هماهنگی‌ها تماس بگیرید. جزئیات تماس در باکس زیر است.',
  on_leave:
    'شما در مرخصی از کل آموزش هستید. برای بازگشت، فرایند «بازگشت به کل آموزش» (فرایند ۶۰) را آغاز کنید.',
  return_reminder_sent:
    'مهلت بازگشت فرا رسیده است. فرایند «بازگشت به کل آموزش پس از مرخصی» (فرایند ۶۰) را آغاز و تکمیل کنید.',
  leave_rejected: 'درخواست مرخصی رد شد. شرح توافقات در باکس زیر نمایش داده می‌شود.',
  leave_complete: 'بازگشت به کل آموزش با موفقیت انجام شد.',
  violation_registered: 'به‌دلیل عدم بازگشت در مهلت مقرر، گزارش تخلف ثبت شده است.',
}

export {
  HintBlock,
  InfoTile,
  ScheduleChip,
  fmtIsoDate,
} from './returnToFullEducationDisplay'

export function fmtMeetingDateTime(iso) {
  if (!iso) return '—'
  try {
    return formatShamsiTehran(iso, { dateStyle: 'medium', timeStyle: 'short' })
  } catch {
    return String(iso)
  }
}

export function meetingModeLabel(mode) {
  if (mode === 'online') return 'آنلاین'
  if (mode === 'in_person') return 'حضوری'
  return ''
}

export function resolveFullLeaveContext(ctx = {}) {
  const leaveTerms = ctx.leave_terms
  let leaveTermsLabel = ctx.leave_terms_display || '—'
  if (!ctx.leave_terms_display && leaveTerms != null) {
    const n = Number(leaveTerms)
    leaveTermsLabel = n === 1 ? 'یک ترم' : n === 2 ? 'دو ترم' : String(leaveTerms)
  }
  return {
    leaveTerms,
    leaveTermsLabel,
    isIntern: ctx.is_intern === true,
    isInternLabel: ctx.is_intern_display_fa || (ctx.is_intern ? 'انترن' : 'غیر انترن'),
    hasActiveTherapist: ctx.has_active_therapist === true,
    therapistName: ctx.current_therapist_display || ctx.therapist_name || null,
    meetingAt: ctx.committee_meeting_at || null,
    meetingMode: ctx.committee_meeting_mode || null,
    meetingLink: ctx.committee_meeting_link || null,
    meetingLocation: ctx.committee_meeting_location_fa || null,
    rejectionReason: (ctx.rejection_reason_fa || '').trim(),
    returnReminderAt: ctx.return_reminder_at || null,
    returnDeadlineAt: ctx.return_deadline_at || null,
    therapyCoordPhone: ctx.therapy_coord_phone_fa || '02122728000 داخلی 1',
    therapyCoordSms: ctx.therapy_coord_sms_fa || ctx.student_portal_alert_fa || null,
    internWarning: ctx.leave_intern_2term_warning_applies === true,
  }
}

export function isFullLeaveTerminal(state) {
  return ['leave_rejected', 'leave_complete', 'violation_registered'].includes(state)
}

export function isFullLeaveActiveLeave(state) {
  return ['on_leave', 'return_reminder_sent'].includes(state)
}

export function FullLeaveFlowStepper({ currentState, compact = false }) {
  const activeIdx = FULL_LEAVE_FLOW_STEPS.findIndex((step) => step.states.includes(currentState))
  return (
    <div
      data-testid="full-leave-flow-stepper"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: compact ? '0.35rem' : '0.5rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {FULL_LEAVE_FLOW_STEPS.map((step, idx) => {
        const done = activeIdx > idx
        const active = activeIdx === idx
        return (
          <div
            key={step.key}
            style={{
              flex: compact ? '1 1 45%' : '1 1 100px',
              padding: compact ? '0.45rem 0.55rem' : '0.55rem 0.7rem',
              borderRadius: '8px',
              fontSize: compact ? '0.72rem' : '0.78rem',
              fontWeight: active ? 800 : 600,
              textAlign: 'center',
              background: done ? '#f0fdf4' : active ? '#eff6ff' : '#f8fafc',
              color: done ? '#16a34a' : active ? '#2563eb' : '#64748b',
              border: `1px solid ${done ? '#bbf7d0' : active ? '#bfdbfe' : '#e2e8f0'}`,
            }}
          >
            {step.label}
          </div>
        )
      })}
    </div>
  )
}
