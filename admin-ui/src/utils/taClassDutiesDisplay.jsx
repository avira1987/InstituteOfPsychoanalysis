/** نمایش مشترک وظایف کمک‌مدرس پس از جلسه کلاس — فرایندهای SOP 43–46. */

import React from 'react'
import { resolveStateDisplayLabel } from './processDisplay'
import { formatShamsiTehran } from './shamsiDateTime'
import { computeSlaRemaining, SlaBanner } from './earlyTerminationChainDisplay'

export const TA_CLASS_DUTY_PROCESS_CODES = [
  'ta_conceptual_questions',
  'ta_student_consultation',
  'ta_essay_upload',
  'ta_blog_content',
]

const TA_ROLE_STATES = new Set([
  'ta_upload',
  'ta_write',
  'ta_form_fill',
  'upload_late',
  'question_rejected',
  'rejected_revision',
])

const INSTRUCTOR_ROLE_STATES = new Set(['instructor_review'])

const TERMINAL_STATES = new Set([
  'questions_approved',
  'form_submitted',
  'form_locked',
  'content_published',
  'approved_marketing_draft',
])

/** @type {Record<string, { sop: number, accent: string, accentBg: string, accentText: string, titleFa: string, flowSteps: { key: string, states: string[], label: string }[], slaByState: Record<string, { hours?: number, days?: number }>, hintsTa: Record<string, string>, hintsInstructor: Record<string, string>, specialNotes?: Record<string, string> }>} */
export const TA_DUTY_CONFIG = {
  ta_conceptual_questions: {
    sop: 43,
    accent: '#2563eb',
    accentBg: '#eff6ff',
    accentText: '#1e40af',
    titleFa: 'ثبت ۳ سوال تستی‌مفهومی (فرایند ۴۳)',
    flowSteps: [
      { key: 'upload', states: ['session_ended', 'ta_upload', 'upload_late'], label: 'آپلود سوالات' },
      { key: 'review', states: ['instructor_review'], label: 'بررسی مدرس' },
      { key: 'revision', states: ['question_rejected'], label: 'اصلاح' },
      { key: 'done', states: ['questions_approved'], label: 'تأیید نهایی' },
    ],
    slaByState: {
      ta_upload: { hours: 24 },
      upload_late: { hours: 24 },
      instructor_review: { days: 4 },
      question_rejected: { hours: 24 },
    },
    hintsTa: {
      ta_upload: 'قالب خام را دانلود کنید؛ سه فایل PDF سوال را آپلود و ارسال کنید. مهلت ۲۴ ساعت پس از پایان جلسه.',
      upload_late: 'مهلت ۲۴ ساعت گذشته و تخلف ثبت شده است؛ همچنان می‌توانید آپلود کنید.',
      question_rejected: 'بازخورد مدرس را ببینید؛ سوال(های) ردشده را اصلاح و PDF جدید آپلود کنید (مهلت ۲۴ ساعت).',
      questions_approved: 'هر سه سوال تأیید شد؛ ۲ نمره به پروندهٔ کمک‌مدرس اضافه می‌شود.',
    },
    hintsInstructor: {
      instructor_review: 'هر سه سوال را در فرم پایین بررسی کنید؛ برای هر سوال «قابل قبول» یا «غیر قابل قبول» (با توضیح در صورت رد) ثبت کنید.',
    },
    specialNotes: {
      template: 'قالب خام سوال و نمونه نگارش از بخش منابع آموزشی در دسترس است.',
    },
  },
  ta_student_consultation: {
    sop: 44,
    accent: '#7c3aed',
    accentBg: '#f5f3ff',
    accentText: '#5b21b6',
    titleFa: 'شناسایی، تشویق و مشورت آموزشی (فرایند ۴۴)',
    flowSteps: [
      { key: 'trigger', states: ['session_5_10_15'], label: 'جلسه milestone' },
      { key: 'fill', states: ['ta_form_fill'], label: 'تکمیل فرم' },
      { key: 'done', states: ['form_submitted', 'form_locked'], label: 'نتیجه' },
    ],
    slaByState: {
      ta_form_fill: { days: 4 },
    },
    hintsTa: {
      ta_form_fill: 'دانشجویان نیازمند تشویق یا مشورت را با «افزودن دانشجو» ثبت کنید؛ علت انتخاب و محتوای مداخله را بنویسید. مهلت ۴ روز.',
      form_submitted: 'فرم ثبت شد؛ ۲ نمره اضافه و گزارش به کمیته پیشرفت ارسال می‌شود.',
      form_locked: 'مهلت ۴ روز گذشته؛ فرم قفل و نمره صفر ثبت شده است.',
    },
    hintsInstructor: {},
    specialNotes: {
      milestone: 'این فرایند پس از جلسات ۵، ۱۰ و ۱۵ هر درس اجرا می‌شود.',
    },
  },
  ta_essay_upload: {
    sop: 45,
    accent: '#d97706',
    accentBg: '#fffbeb',
    accentText: '#92400e',
    titleFa: 'آپلود جستار و دقایق فیلم (فرایند ۴۵)',
    flowSteps: [
      { key: 'upload', states: ['session_ended', 'ta_upload'], label: 'آپلود' },
      { key: 'review', states: ['instructor_review'], label: 'بررسی مدرس' },
      { key: 'revision', states: ['rejected_revision'], label: 'اصلاح' },
      { key: 'pipeline', states: ['reference_center_editing', 'marketing_publication'], label: 'تدوین و انتشار' },
      { key: 'done', states: ['content_published'], label: 'منتشر شد' },
    ],
    slaByState: {
      ta_upload: { hours: 24 },
      instructor_review: { days: 4 },
      rejected_revision: { hours: 24 },
      marketing_publication: { days: 7 },
    },
    hintsTa: {
      ta_upload: 'قالب خام را دانلود کنید؛ جستار و دقایق منتخب را در Word بنویسید و هر دو فرمت Word و PDF را آپلود کنید.',
      rejected_revision: 'بازخورد مدرس را ببینید؛ فایل‌ها را اصلاح و مجدداً آپلود کنید.',
      content_published: 'محتوا تأیید و در مسیر انتشار قرار گرفت.',
    },
    hintsInstructor: {
      instructor_review: 'فایل‌های آپلودشده را بررسی کنید؛ «قابل قبول» یا «غیر قابل قبول» (با توضیح اجباری در صورت رد).',
      reference_center_editing: 'ویرایش ادبی و تدوین نهایی — مرکز مرجع.',
      marketing_publication: 'ثبت پلتفرم‌ها و تاریخ انتشار.',
    },
    specialNotes: {
      formats: 'هر دو فرمت Word و PDF الزامی است.',
      template: 'قالب خام: /templates/ta_essay_minutes_template.docx',
    },
  },
  ta_blog_content: {
    sop: 46,
    accent: '#059669',
    accentBg: '#ecfdf5',
    accentText: '#047857',
    titleFa: 'ثبت محتوای وبلاگ (فرایند ۴۶)',
    flowSteps: [
      { key: 'write', states: ['session_ended', 'ta_write'], label: 'نگارش' },
      { key: 'review', states: ['instructor_review'], label: 'بررسی مدرس' },
      { key: 'revision', states: ['rejected_revision'], label: 'اصلاح' },
      { key: 'done', states: ['approved_marketing_draft'], label: 'پیش‌نویس مارکتینگ' },
    ],
    slaByState: {
      ta_write: { hours: 24 },
      instructor_review: { days: 4 },
      rejected_revision: { hours: 24 },
    },
    hintsTa: {
      ta_write: 'خلاصهٔ کاربردی مباحث را مستقیماً در فیلد متنی بنویسید (حدود نیم صفحه A4). آپلود فایل مجاز نیست.',
      rejected_revision: 'بازخورد مدرس را ببینید؛ متن را اصلاح و مجدداً ارسال کنید.',
      approved_marketing_draft: 'متن تأیید شد و به‌عنوان پیش‌نویس مارکتینگ ثبت می‌شود.',
    },
    hintsInstructor: {
      instructor_review: 'متن وبلاگ را فقط‌خواندنی ببینید؛ «قابل قبول» یا «غیر قابل قبول» (با توضیح در صورت رد).',
    },
    specialNotes: {
      textOnly: 'فقط متن — آپلود فایل مجاز نیست.',
    },
  },
}

export function getTaDutyConfig(processCode) {
  return TA_DUTY_CONFIG[processCode] || null
}

export function isTaClassDutyProcess(processCode) {
  return TA_CLASS_DUTY_PROCESS_CODES.includes(processCode)
}

export function isTaDutyTerminalState(state) {
  return TERMINAL_STATES.has(state)
}

export function resolveActorKind(currentState, userRole) {
  if (INSTRUCTOR_ROLE_STATES.has(currentState)) return 'instructor'
  if (TA_ROLE_STATES.has(currentState)) return 'teaching_assistant'
  const role = (userRole || '').trim()
  if (role === 'instructor') return 'instructor'
  if (role === 'teaching_assistant') return 'teaching_assistant'
  return 'operator'
}

export function fmtIsoDate(iso) {
  if (!iso) return '—'
  try {
    return formatShamsiTehran(iso)
  } catch {
    return String(iso)
  }
}

/** استخراج زمینهٔ جلسه از context_data */
export function resolveTaDutyContext(ctx = {}, extraData = {}) {
  const merged = { ...ctx }
  const courseName =
    merged.course_name
    || merged.lesson_name
    || merged.course_id
    || extraData?.course_name
    || null
  const sessionIndex =
    merged.session_index
    ?? merged.session_number
    ?? merged.milestone_session
    ?? null
  const sessionDate =
    merged.session_date
    || merged.class_session_date
    || merged.lesson_date
    || null
  const milestoneSession =
    merged.milestone_session
    ?? merged.session_index
    ?? merged.session_number
    ?? null
  const taScore = merged.ta_score_points ?? merged.points_awarded ?? null

  return {
    courseName: courseName ? String(courseName) : null,
    sessionIndex: sessionIndex != null ? Number(sessionIndex) : null,
    sessionDate: sessionDate ? String(sessionDate) : null,
    milestoneSession: milestoneSession != null ? Number(milestoneSession) : null,
    taScore: taScore != null ? Number(taScore) : null,
    uploadLate: Boolean(merged.upload_late || merged.violation_registered),
  }
}

export function resolveSlaForState(processCode, currentState, ctx = {}) {
  const cfg = getTaDutyConfig(processCode)
  if (!cfg) return null
  const sla = cfg.slaByState[currentState]
  if (!sla) return null

  const enteredKeys = [
    `${currentState}_entered_at`,
    'state_entered_at',
    'entered_at',
    'started_at',
    'reminder_sent_at',
  ]
  let enteredAt = null
  for (const k of enteredKeys) {
    if (ctx[k]) {
      enteredAt = ctx[k]
      break
    }
  }

  if (sla.hours) {
    if (!enteredAt) {
      return { expired: false, hoursLeft: sla.hours, fallbackText: `مهلت: ${sla.hours.toLocaleString('fa-IR')} ساعت پس از پایان جلسه` }
    }
    const start = new Date(enteredAt)
    if (Number.isNaN(start.getTime())) return null
    const deadline = new Date(start.getTime() + sla.hours * 60 * 60 * 1000)
    const msLeft = deadline.getTime() - Date.now()
    const hoursLeft = Math.ceil(msLeft / (1000 * 60 * 60))
    return { hoursLeft, deadline, expired: hoursLeft <= 0 }
  }

  if (sla.days) {
    return computeSlaRemaining(ctx, sla.days)
  }
  return null
}

export function resolveStateHint(processCode, currentState, actorKind) {
  const cfg = getTaDutyConfig(processCode)
  if (!cfg) return null
  if (actorKind === 'instructor' && cfg.hintsInstructor[currentState]) {
    return cfg.hintsInstructor[currentState]
  }
  if (cfg.hintsTa[currentState]) return cfg.hintsTa[currentState]
  if (actorKind === 'instructor' && INSTRUCTOR_ROLE_STATES.has(currentState)) {
    return cfg.hintsInstructor.instructor_review || null
  }
  if (TA_ROLE_STATES.has(currentState)) {
    const uploadStates = ['ta_upload', 'ta_write', 'ta_form_fill']
    const hit = uploadStates.find((s) => cfg.hintsTa[s])
    return hit ? cfg.hintsTa[hit] : null
  }
  return null
}

export function labelTaDutyState(processCode, state) {
  if (!state) return '—'
  return resolveStateDisplayLabel(state, null, processCode)
}

function stepIndexForState(flowSteps, currentState) {
  if (!currentState || !flowSteps?.length) return 0
  const idx = flowSteps.findIndex((step) => step.states.includes(currentState))
  return idx >= 0 ? idx : 0
}

export function TaDutyFlowStepper({ processCode, currentState, compact = false }) {
  const cfg = getTaDutyConfig(processCode)
  if (!cfg?.flowSteps?.length) return null
  const activeIdx = stepIndexForState(cfg.flowSteps, currentState)
  const isTerminal = isTaDutyTerminalState(currentState)

  return (
    <div
      data-testid="ta-duty-flow-stepper"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: compact ? '0.35rem' : '0.5rem',
        marginBottom: compact ? '0.65rem' : '0.85rem',
      }}
    >
      {cfg.flowSteps.map((step, idx) => {
        const done = isTerminal ? idx <= activeIdx : idx < activeIdx
        const active = idx === activeIdx && !isTerminal
        const bg = done ? cfg.accentBg : active ? '#fff' : '#f8fafc'
        const border = done || active ? cfg.accent : '#e2e8f0'
        const color = done || active ? cfg.accentText : '#64748b'
        return (
          <div
            key={step.key}
            data-testid={`ta-duty-step-${step.key}`}
            style={{
              flex: compact ? '1 1 100%' : '1 1 auto',
              minWidth: compact ? 0 : '5.5rem',
              padding: compact ? '0.45rem 0.6rem' : '0.55rem 0.75rem',
              borderRadius: '8px',
              border: `1px solid ${border}`,
              borderRight: `4px solid ${border}`,
              background: bg,
              fontSize: compact ? '0.78rem' : '0.82rem',
              fontWeight: active ? 700 : 500,
              color,
              textAlign: 'center',
            }}
          >
            {step.label}
          </div>
        )
      })}
    </div>
  )
}

export function TaDutyInfoTile({ label, value, tone = '#334155', bg = '#f8fafc' }) {
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

export function TaDutySlaBanner({ processCode, currentState, ctx }) {
  const slaInfo = resolveSlaForState(processCode, currentState, ctx)
  const cfg = getTaDutyConfig(processCode)
  if (!slaInfo && !cfg?.slaByState[currentState]) return null
  const title = cfg?.slaByState[currentState]?.hours
    ? 'مهلت آپلود / ارسال'
    : 'مهلت بررسی / تکمیل'
  return (
    <div data-testid="ta-duty-sla-banner">
      <SlaBanner
        slaInfo={slaInfo?.hoursLeft != null ? null : slaInfo}
        title={title}
        fallbackText={slaInfo?.fallbackText}
      />
      {slaInfo?.hoursLeft != null && (
        <div
          style={{
            marginBottom: '0.85rem',
            padding: '0.75rem 1rem',
            borderRadius: '10px',
            background: slaInfo.expired ? '#fef2f2' : '#fffbeb',
            borderRight: `4px solid ${slaInfo.expired ? '#dc2626' : '#d97706'}`,
            fontSize: '0.86rem',
          }}
        >
          <strong style={{ display: 'block', marginBottom: '0.35rem' }}>{title}</strong>
          {slaInfo.expired ? (
            <span style={{ color: '#991b1b' }}>مهلت به پایان رسیده است.</span>
          ) : (
            <span style={{ color: '#92400e' }}>
              {slaInfo.hoursLeft.toLocaleString('fa-IR')}
              {' '}
              ساعت باقی‌مانده
            </span>
          )}
        </div>
      )}
    </div>
  )
}
