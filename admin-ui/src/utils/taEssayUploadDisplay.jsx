/** نمایش مشترک زنجیره «آپلود جستار و دقایق منتخب» — فرایند ۴۵. */

import React from 'react'
import { computeSlaRemaining, SlaBanner } from './earlyTerminationChainDisplay'
import { formatShamsiTehran } from './shamsiDateTime'
import { parseStepFileUploadValue } from './uploadPublicUrl'

export const TA_ESSAY_FLOW_STEPS = [
  { key: 'ta_upload', state: 'ta_upload', label: 'آپلود TA' },
  { key: 'instructor_review', state: 'instructor_review', label: 'بررسی مدرس' },
  { key: 'reference_center_editing', state: 'reference_center_editing', label: 'مرکز مرجع' },
  { key: 'marketing_publication', state: 'marketing_publication', label: 'مارکتینگ' },
  { key: 'content_published', state: 'content_published', label: 'انتشار' },
]

export const TA_ESSAY_TEMPLATE_PATH = '/templates/ta_essay_minutes_template.docx'

export const PUBLISH_PLATFORM_LABELS = {
  instagram: 'اینستاگرام',
  telegram: 'تلگرام',
  site_video: 'دیدنی‌های سایت',
  site_audio: 'شنیدنی‌های سایت',
  site_reading: 'خواندنی‌های سایت',
  youtube: 'یوتیوب',
  aparat: 'آپارات',
  linkedin: 'لینکدین',
}

export const PUBLISH_DATE_FIELD_BY_PLATFORM = {
  instagram: 'publish_date_instagram',
  telegram: 'publish_date_telegram',
  site_video: 'publish_date_site_video',
  site_audio: 'publish_date_site_audio',
  site_reading: 'publish_date_site_reading',
  youtube: 'publish_date_youtube',
  aparat: 'publish_date_aparat',
  linkedin: 'publish_date_linkedin',
}

const STATE_SLA_CONFIG = {
  ta_upload: { hours: 24, key: 'ta_upload_entered_at', title: 'مهلت آپلود کمک‌مدرس (۲۴ ساعت)' },
  rejected_revision: { hours: 24, key: 'rejected_revision_entered_at', title: 'مهلت اصلاح پس از رد (۲۴ ساعت)' },
  instructor_review: { days: 4, key: 'instructor_review_entered_at', title: 'مهلت بررسی مدرس (۴ روز)' },
  marketing_publication: { days: 7, key: 'marketing_publication_entered_at', title: 'مهلت تعیین تکلیف مارکتینگ (۷ روز)' },
}

export function fmtIsoDate(iso) {
  if (!iso) return '—'
  try {
    return formatShamsiTehran(iso)
  } catch {
    return String(iso)
  }
}

export function resolveSessionContext(ctx = {}) {
  return {
    courseName: ctx.course_name || ctx.lesson_name || '—',
    sessionDate: ctx.session_date || ctx.class_session_date || '—',
    instructorName: ctx.instructor_name || '—',
    taName: ctx.teaching_assistant_name || ctx.teaching_assistant || '—',
    courseTrack: ctx.course_track || ctx.track || '—',
  }
}

export function resolveEssayFiles(ctx = {}) {
  return {
    word: ctx.essay_word ?? null,
    pdf: ctx.essay_pdf ?? null,
    editedWord: ctx.edited_essay_word ?? null,
    minutesNote: (ctx.selected_minutes_note || '').trim() || null,
    refinedMinutes: (ctx.refined_minutes_from_to || '').trim() || null,
  }
}

export function resolveInstructorRejection(ctx = {}) {
  const notes = (ctx.notes || ctx.instructor_rejection_notes || ctx.rejection_notes || '').trim()
  const fromHistory = Array.isArray(ctx.history)
    ? ctx.history.find((h) => h?.trigger_event === 'rejected' || h?.to_state === 'rejected_revision')
    : null
  const historyNote = fromHistory?.notes || fromHistory?.payload?.notes
  return (notes || historyNote || '').trim() || null
}

export function resolvePublicationPlatforms(ctx = {}) {
  const raw = ctx.publish_platforms
  const platforms = Array.isArray(raw) ? raw : (raw ? [raw] : [])
  return platforms.map((code) => {
    const dateField = PUBLISH_DATE_FIELD_BY_PLATFORM[code]
    const dateVal = dateField ? ctx[dateField] : null
    return {
      code,
      label: PUBLISH_PLATFORM_LABELS[code] || code,
      publishDate: dateVal,
    }
  })
}

export function computeTaEssaySla(ctx = {}, currentState, startedAt) {
  const cfg = STATE_SLA_CONFIG[currentState]
  if (!cfg) return null
  const merged = { ...ctx, started_at: startedAt }
  if (cfg.hours) {
    const key = cfg.key
    let enteredAt = merged[key] || merged.started_at
    if (!enteredAt) return { title: cfg.title, fallbackText: cfg.title }
    const start = new Date(enteredAt)
    if (Number.isNaN(start.getTime())) return null
    const deadline = new Date(start.getTime() + cfg.hours * 60 * 60 * 1000)
    const now = new Date()
    const msLeft = deadline.getTime() - now.getTime()
    const hoursLeft = Math.ceil(msLeft / (1000 * 60 * 60))
    return {
      title: cfg.title,
      expired: hoursLeft <= 0,
      hoursLeft,
      deadline,
      isHours: true,
    }
  }
  return {
    ...computeSlaRemaining(merged, cfg.days, cfg.key),
    title: cfg.title,
    isHours: false,
  }
}

export function activeTaEssayStepIndex(currentState) {
  if (!currentState) return 0
  if (currentState === 'session_ended') return 0
  if (currentState === 'rejected_revision') return 0
  const idx = TA_ESSAY_FLOW_STEPS.findIndex((s) => s.state === currentState)
  if (idx >= 0) return idx
  if (currentState === 'instructor_review') return 1
  return 0
}

export function fileUploadLabel(raw) {
  const { url, mime } = parseStepFileUploadValue(raw)
  if (!url) return 'ثبت نشده'
  if (typeof raw === 'object' && raw?.file_name) return raw.file_name
  return mime.includes('pdf') ? 'فایل PDF' : 'فایل Word'
}

export function TaEssayFlowStepper({ currentState, testId = 'ta-essay-flow-stepper' }) {
  const activeIdx = activeTaEssayStepIndex(currentState)
  const onRevision = currentState === 'rejected_revision'

  return (
    <div
      data-testid={testId}
      style={{ display: 'flex', gap: '0.35rem', marginBottom: '0.85rem', flexWrap: 'wrap' }}
    >
      {TA_ESSAY_FLOW_STEPS.map((step, i) => {
        const done = i < activeIdx || currentState === 'content_published'
        const active = i === activeIdx && currentState !== 'content_published'
        const revisionHint = onRevision && i === 0
        return (
          <div
            key={step.key}
            style={{
              flex: '1 1 5.5rem',
              padding: '0.45rem 0.55rem',
              borderRadius: '8px',
              background: revisionHint ? '#fef2f2' : active ? '#0d9488' : done ? '#ccfbf1' : '#f1f5f9',
              color: revisionHint ? '#991b1b' : active ? '#fff' : done ? '#115e59' : '#64748b',
              border: revisionHint
                ? '2px solid #dc2626'
                : active
                  ? '2px solid #0f766e'
                  : '1px solid #e2e8f0',
              fontSize: '0.72rem',
              textAlign: 'center',
              fontWeight: active || revisionHint ? 700 : 500,
            }}
          >
            {revisionHint ? 'اصلاح TA' : step.label}
          </div>
        )
      })}
    </div>
  )
}

export function SessionInfoTiles({ session }) {
  const tiles = [
    { label: 'درس', value: session.courseName },
    { label: 'تاریخ جلسه', value: session.sessionDate },
    { label: 'مدرس', value: session.instructorName },
    { label: 'کمک‌مدرس', value: session.taName },
    { label: 'رسته', value: session.courseTrack },
  ]
  return (
    <div
      data-testid="ta-essay-session-tiles"
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(9rem, 1fr))',
        gap: '0.5rem',
        marginBottom: '0.85rem',
      }}
    >
      {tiles.map((t) => (
        <div
          key={t.label}
          style={{
            padding: '0.55rem 0.65rem',
            borderRadius: '8px',
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            minWidth: 0,
          }}
        >
          <div style={{ fontSize: '0.72rem', color: '#64748b', marginBottom: '0.15rem' }}>{t.label}</div>
          <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#0f172a' }}>{t.value}</div>
        </div>
      ))}
    </div>
  )
}

export function TaEssaySlaBanner({ ctx, currentState, startedAt }) {
  const sla = computeTaEssaySla(ctx, currentState, startedAt)
  if (!sla) return null
  if (sla.isHours) {
    const expired = sla.expired
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
        <strong>{sla.title}</strong>
        {sla.expired ? (
          <span style={{ color: '#b91c1c', marginRight: '0.35rem' }}> — مهلت گذشته (آپلود همچنان ممکن است؛ گزارش تأخیر ارسال می‌شود)</span>
        ) : (
          <span style={{ color: '#92400e', marginRight: '0.35rem' }}>
            {' '}
            —
            {' '}
            {sla.hoursLeft}
            {' '}
            ساعت مانده
          </span>
        )}
      </div>
    )
  }
  return (
    <SlaBanner
      slaInfo={sla}
      title={sla.title}
      fallbackText={sla.title}
    />
  )
}

export function HintBlock({ children, tone = 'info' }) {
  const styles = {
    info: { bg: '#eff6ff', border: '#2563eb', color: '#1e40af' },
    warn: { bg: '#fffbeb', border: '#d97706', color: '#92400e' },
    success: { bg: '#f0fdf4', border: '#16a34a', color: '#166534' },
  }
  const s = styles[tone] || styles.info
  return (
    <p
      style={{
        fontSize: '0.85rem',
        lineHeight: 1.7,
        margin: '0 0 0.85rem',
        padding: '0.65rem 0.85rem',
        borderRadius: '8px',
        background: s.bg,
        borderRight: `4px solid ${s.border}`,
        color: s.color,
      }}
    >
      {children}
    </p>
  )
}
