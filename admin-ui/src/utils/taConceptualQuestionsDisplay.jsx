/** نمایش مشترک زنجیره «ثبت ۳ سوال تستی‌مفهومی» — فرایند ۴۳. */

import React from 'react'
import { computeSlaRemaining, SlaBanner } from './earlyTerminationChainDisplay'
import { formatShamsiTehran } from './shamsiDateTime'
import { parseStepFileUploadValue, resolveUploadPublicUrl } from './uploadPublicUrl'

export const TA_CONCEPTUAL_FLOW_STEPS = [
  { key: 'ta_upload', state: 'ta_upload', label: 'آپلود TA' },
  { key: 'instructor_review', state: 'instructor_review', label: 'بررسی مدرس' },
  { key: 'question_rejected', state: 'question_rejected', label: 'اصلاح' },
  { key: 'questions_approved', state: 'questions_approved', label: 'تأیید نهایی' },
]

export const TA_CONCEPTUAL_SAMPLE_PATH = '/templates/ta-conceptual-question/sample.pdf'
export const TA_CONCEPTUAL_TEMPLATE_PATH = '/templates/ta-conceptual-question/template.pdf'

export const MAX_TERM_SCORE = 34
export const MAX_SESSIONS_WITH_QUESTIONS = 17
export const SESSION_SCORE_AWARD = 2

const QUESTION_STATUS_LABELS = {
  accepted: 'قابل قبول',
  rejected: 'غیر قابل قبول',
}

const STATE_SLA_CONFIG = {
  ta_upload: { hours: 24, key: 'ta_upload_entered_at', title: 'مهلت آپلود کمک‌مدرس (۲۴ ساعت)' },
  upload_late: { hours: 24, key: 'ta_upload_entered_at', title: 'مهلت آپلود (گذشته — تخلف ثبت شده)' },
  question_rejected: { hours: 24, key: 'question_rejected_entered_at', title: 'مهلت اصلاح پس از رد (۲۴ ساعت)' },
  instructor_review: { days: 4, key: 'instructor_review_entered_at', title: 'مهلت بررسی مدرس (۴ روز)' },
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
  const sessionNum = ctx.session_number ?? ctx.class_session_number ?? null
  return {
    courseName: ctx.course_name || ctx.lesson_name || '—',
    sessionNumber: sessionNum != null ? Number(sessionNum) : null,
    sessionDate: ctx.session_date || ctx.class_session_date || null,
    instructorName: ctx.instructor_name || '—',
    taName: ctx.teaching_assistant_name || ctx.teaching_assistant || '—',
    courseTrack: ctx.course_track || ctx.track || '—',
  }
}

export function resolveUploadedQuestions(ctx = {}) {
  return [1, 2, 3].map((n) => {
    const key = `question_${n}`
    const raw = ctx[key]
    const parsed = parseStepFileUploadValue(raw)
    return {
      number: n,
      key,
      raw,
      url: parsed.url ? resolveUploadPublicUrl(parsed.url) : '',
      mime: parsed.mime,
      fileName: typeof raw === 'object' && raw?.file_name ? raw.file_name : null,
      hasFile: !!parsed.url,
    }
  })
}

export function resolveInstructorReview(ctx = {}) {
  return [1, 2, 3].map((n) => {
    const status = ctx[`question_${n}_status`] || null
    const note = (ctx[`question_${n}_rejection_note`] || '').trim() || null
    return {
      number: n,
      status,
      statusLabel: status ? (QUESTION_STATUS_LABELS[status] || status) : null,
      rejectionNote: note,
      rejected: status === 'rejected',
    }
  })
}

export function hasAnyRejected(reviews) {
  return Array.isArray(reviews) && reviews.some((r) => r.rejected)
}

export function allAccepted(reviews) {
  return Array.isArray(reviews)
    && reviews.length === 3
    && reviews.every((r) => r.status === 'accepted')
}

export function resolveScoreSummary(ctx = {}) {
  const total = ctx.conceptual_questions_score_total ?? ctx.ta_conceptual_score_total ?? null
  const sessionAward = ctx.session_score_awarded ?? (ctx.current_state === 'questions_approved' ? SESSION_SCORE_AWARD : null)
  const totalNum = total != null ? Number(total) : null
  return {
    termTotal: Number.isFinite(totalNum) ? totalNum : null,
    sessionAward: sessionAward != null ? Number(sessionAward) : null,
    maxTerm: MAX_TERM_SCORE,
    maxSessions: MAX_SESSIONS_WITH_QUESTIONS,
  }
}

export function resolveSlaInfo(ctx = {}, currentState, startedAt) {
  const cfg = STATE_SLA_CONFIG[currentState]
  if (!cfg) return null

  const deadlineKey = {
    ta_upload: 'upload_deadline_at',
    upload_late: 'upload_deadline_at',
    instructor_review: 'review_deadline_at',
    question_rejected: 'revision_deadline_at',
  }[currentState]

  if (deadlineKey && ctx[deadlineKey]) {
    const deadline = new Date(ctx[deadlineKey])
    if (!Number.isNaN(deadline.getTime())) {
      const now = new Date()
      const msLeft = deadline.getTime() - now.getTime()
      if (cfg.hours) {
        const hoursLeft = Math.ceil(msLeft / (1000 * 60 * 60))
        return {
          title: cfg.title,
          expired: hoursLeft <= 0,
          hoursLeft,
          deadline,
          isHours: true,
        }
      }
      const daysLeft = Math.ceil(msLeft / (1000 * 60 * 60 * 24))
      return {
        title: cfg.title,
        expired: daysLeft <= 0,
        daysLeft,
        deadline,
        isHours: false,
      }
    }
  }

  const merged = { ...ctx, started_at: startedAt }
  if (cfg.hours) {
    let enteredAt = merged[cfg.key] || merged.started_at
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

export function activeTaConceptualStepIndex(currentState) {
  if (!currentState) return 0
  if (currentState === 'session_ended') return 0
  if (currentState === 'upload_late') return 0
  if (currentState === 'question_rejected') return 2
  const idx = TA_CONCEPTUAL_FLOW_STEPS.findIndex((s) => s.state === currentState)
  if (idx >= 0) return idx
  return 0
}

export function TaConceptualFlowStepper({ currentState, testId = 'ta-conceptual-flow-stepper' }) {
  const activeIdx = activeTaConceptualStepIndex(currentState)
  const onLate = currentState === 'upload_late'
  const onRevision = currentState === 'question_rejected'
  const done = currentState === 'questions_approved'

  return (
    <div
      data-testid={testId}
      style={{ display: 'flex', gap: '0.35rem', marginBottom: '0.85rem', flexWrap: 'wrap' }}
    >
      {TA_CONCEPTUAL_FLOW_STEPS.map((step, i) => {
        const stepDone = done || i < activeIdx
        const stepActive = !done && i === activeIdx
        const lateHint = onLate && i === 0
        const revisionHint = onRevision && i === 2
        return (
          <div
            key={step.key}
            style={{
              flex: '1 1 5.5rem',
              padding: '0.45rem 0.55rem',
              borderRadius: '8px',
              background: lateHint || revisionHint
                ? '#fef2f2'
                : stepActive
                  ? '#7c3aed'
                  : stepDone
                    ? '#ede9fe'
                    : '#f1f5f9',
              color: lateHint || revisionHint
                ? '#991b1b'
                : stepActive
                  ? '#fff'
                  : stepDone
                    ? '#5b21b6'
                    : '#64748b',
              border: lateHint || revisionHint
                ? '2px solid #dc2626'
                : stepActive
                  ? '2px solid #6d28d9'
                  : '1px solid #e2e8f0',
              fontSize: '0.72rem',
              textAlign: 'center',
              fontWeight: stepActive || lateHint || revisionHint ? 700 : 500,
            }}
          >
            {lateHint ? 'تأخیر آپلود' : revisionHint ? 'اصلاح TA' : step.label}
          </div>
        )
      })}
    </div>
  )
}

export function SessionInfoTiles({ session }) {
  const sessionLabel = session.sessionNumber != null
    ? `جلسه ${session.sessionNumber.toLocaleString('fa-IR')} از ${MAX_SESSIONS_WITH_QUESTIONS.toLocaleString('fa-IR')}`
    : '—'
  const tiles = [
    { label: 'درس', value: session.courseName },
    { label: 'جلسه', value: sessionLabel },
    { label: 'تاریخ جلسه', value: session.sessionDate ? fmtIsoDate(session.sessionDate) : '—' },
    { label: 'مدرس', value: session.instructorName },
    { label: 'کمک‌مدرس', value: session.taName },
  ]
  return (
    <div
      data-testid="ta-conceptual-session-tiles"
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

export function TaConceptualSlaBanner({ ctx, currentState, startedAt }) {
  const sla = resolveSlaInfo(ctx, currentState, startedAt)
  if (!sla) return null
  if (sla.isHours) {
    const expired = sla.expired
    return (
      <div
        data-testid="ta-conceptual-sla-banner"
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
        {expired ? (
          <span style={{ color: '#b91c1c', marginRight: '0.35rem' }}>
            {' '}
            — مهلت گذشته
            {currentState === 'upload_late' ? ' (تخلف ثبت شده؛ آپلود همچنان ممکن است)' : ''}
          </span>
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
    <div data-testid="ta-conceptual-sla-banner">
      <SlaBanner slaInfo={sla} title={sla.title} fallbackText={sla.title} />
    </div>
  )
}

export function ScoreProgressBar({ scoreSummary }) {
  const total = scoreSummary.termTotal
  if (total == null) return null
  const pct = Math.min(100, Math.round((total / scoreSummary.maxTerm) * 100))
  return (
    <div
      data-testid="ta-conceptual-score-progress"
      style={{
        marginBottom: '0.85rem',
        padding: '0.75rem 1rem',
        borderRadius: '10px',
        background: '#f5f3ff',
        borderRight: '4px solid #7c3aed',
      }}
    >
      <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.35rem' }}>
        نمرهٔ تجمیعی «طراحی سوال تستی‌مفهومی» در این ترم
      </div>
      <div style={{ fontSize: '1.05rem', fontWeight: 800, color: '#5b21b6', marginBottom: '0.45rem' }}>
        {total.toLocaleString('fa-IR')}
        {' '}
        از
        {' '}
        {scoreSummary.maxTerm.toLocaleString('fa-IR')}
      </div>
      <div style={{ height: '8px', borderRadius: '4px', background: '#e9d5ff', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: '#7c3aed', borderRadius: '4px' }} />
      </div>
    </div>
  )
}

export function QuestionPdfPreview({ questions }) {
  if (!Array.isArray(questions) || !questions.some((q) => q.hasFile)) return null
  return (
    <div data-testid="ta-conceptual-pdf-preview" style={{ marginBottom: '0.85rem' }}>
      <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.4rem', color: '#334155' }}>
        فایل‌های سوال آپلودشده
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
        {questions.filter((q) => q.hasFile).map((q) => (
          <div
            key={q.key}
            style={{
              padding: '0.65rem 0.85rem',
              borderRadius: '8px',
              border: '1px solid #e2e8f0',
              background: '#fff',
            }}
          >
            <div style={{ fontWeight: 600, fontSize: '0.82rem', marginBottom: '0.35rem' }}>
              سوال
              {' '}
              {q.number.toLocaleString('fa-IR')}
              {q.fileName ? ` — ${q.fileName}` : ''}
            </div>
            {q.mime === 'application/pdf' && q.url ? (
              <iframe
                title={`سوال ${q.number}`}
                src={q.url}
                style={{ width: '100%', height: '220px', border: '1px solid #e5e7eb', borderRadius: '6px' }}
              />
            ) : (
              <a href={q.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.82rem' }}>
                مشاهده / دانلود فایل
              </a>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export function InstructorReviewSummary({ reviews }) {
  if (!Array.isArray(reviews) || !reviews.some((r) => r.status)) return null
  return (
    <div
      data-testid="ta-conceptual-review-summary"
      style={{
        marginBottom: '0.85rem',
        padding: '0.75rem 1rem',
        borderRadius: '8px',
        background: '#faf5ff',
        border: '1px solid #e9d5ff',
        fontSize: '0.84rem',
        lineHeight: 1.75,
      }}
    >
      <strong style={{ color: '#5b21b6' }}>نتیجهٔ بررسی مدرس:</strong>
      <ul style={{ margin: '0.5rem 0 0', paddingRight: '1.2rem' }}>
        {reviews.map((r) => (
          <li key={r.number}>
            سوال
            {' '}
            {r.number.toLocaleString('fa-IR')}
            :
            {' '}
            {r.statusLabel || '—'}
            {r.rejectionNote && (
              <span style={{ color: '#991b1b' }}>
                {' '}
                —
                {' '}
                {r.rejectionNote}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function HintBlock({ children, tone = 'info' }) {
  const styles = {
    info: { bg: '#eff6ff', border: '#2563eb', color: '#1e40af' },
    warn: { bg: '#fffbeb', border: '#d97706', color: '#92400e' },
    success: { bg: '#f0fdf4', border: '#16a34a', color: '#166534' },
    purple: { bg: '#f5f3ff', border: '#7c3aed', color: '#5b21b6' },
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

export function TemplateDownloadLinks() {
  return (
    <div
      data-testid="ta-conceptual-template-links"
      style={{
        marginBottom: '0.85rem',
        padding: '0.65rem 0.85rem',
        borderRadius: '8px',
        background: '#f8fafc',
        border: '1px dashed #cbd5e1',
        fontSize: '0.84rem',
        lineHeight: 1.8,
      }}
    >
      <strong>دانلود قالب:</strong>
      {' '}
      <a href={TA_CONCEPTUAL_SAMPLE_PATH} download title="فایل نمونه — در صورت نبود، از کمیته دروس دریافت کنید">
        نمونه سوال
      </a>
      {' '}
      |
      {' '}
      <a href={TA_CONCEPTUAL_TEMPLATE_PATH} download title="قالب خام — در صورت نبود، از کمیته دروس دریافت کنید">
        قالب خام (Template)
      </a>
    </div>
  )
}
