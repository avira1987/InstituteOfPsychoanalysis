/** نمایش مشترک فرایند ۵۱ — تغییر یا اضافه کردن رسته کمک‌مدرس. */

import React from 'react'
import { formatShamsiTehran } from './shamsiDateTime'

export const PROCESS_CODE = 'ta_track_change'
export const PROCESS_TITLE_FA = 'تغییر یا اضافه کردن رسته کمک‌مدرس (فرایند ۵۱)'

export const TA_TRACK_FLOW_STEPS = [
  { key: 'path', label: 'انتخاب مسیر', states: ['ta_click'] },
  { key: 'sent', label: 'ارسال به کمیته', states: ['path_selected'] },
  { key: 'meeting', label: 'هماهنگی جلسه', states: ['course_committee_review', 'meeting_scheduled'] },
  { key: 'done', label: 'نتیجه', states: ['track_applied', 'rejected'] },
]

export const PATH_LABELS = {
  add: 'اضافه کردن رسته (حفظ رسته فعلی + رسته جدید)',
  change: 'تغییر رسته (جایگزینی رسته فعلی)',
}

export const TRACK_OPTIONS = [
  { value: 'psychoanalysis_theory_1_5', label_fa: 'تئوری روانکاوی ۱ تا ۵' },
  { value: 'film_observation_1_3_continuous', label_fa: 'مشاهده فیلم‌های درمانی ۱ تا ۳ و مشاهده مستمر یک درمان تحلیلی' },
  { value: 'technique_theory_1_3', label_fa: 'تئوری تکنیک‌ها ۱ تا ۳' },
  { value: 'technique_skills_1_4', label_fa: 'تکنیک: تمرین مهارت‌ها ۱ تا ۴' },
  { value: 'group_supervision_1_3', label_fa: 'دروس پیشرفته: سوپرویژن گروهی ۱ تا ۳' },
  { value: 'clinical_case_conference', label_fa: 'دروس پیشرفته: کنفرانس کیس بالینی' },
  { value: 'early_termination', label_fa: 'دروس پیشرفته: خاتمه زودرس' },
  { value: 'counter_transference', label_fa: 'دروس پیشرفته: انتقال متقابل' },
  { value: 'article_writing', label_fa: 'دروس پیشرفته: مقاله‌نویسی' },
  { value: 'live_therapy_observation', label_fa: 'دروس پیشرفته: مشاهده زنده درمان' },
  { value: 'live_supervision', label_fa: 'دروس پیشرفته: سوپرویژن زنده' },
  { value: 'ethics_professional_law_hill', label_fa: 'دروس پیشرفته: کلاس اخلاق و قوانین حرفه‌ای و هیل' },
]

const TRACK_LABEL_BY_VALUE = Object.fromEntries(
  TRACK_OPTIONS.map((o) => [o.value, o.label_fa]),
)

export const MEETING_TYPE_LABELS = {
  in_person: 'حضوری (مکان انستیتو)',
  online: 'آنلاین',
}

export const STOP_STATES = new Set(['rejected'])

export const STOP_MESSAGES = {
  rejected: 'درخواست شما در جلسه کمیته دروس مورد موافقت قرار نگرفت. توضیحات در جلسه حضوری ارائه شده است.',
}

export const STATE_HINTS = {
  ta_click: 'ابتدا با مدرس هماهنگ کنید؛ سپس یکی از دو مسیر را در فرم انتخاب و «ثبت مسیر» را بزنید.',
  path_selected: 'درخواست شما به کمیته دروس ارسال شد. منتظر تماس و تعیین وقت جلسه باشید.',
  course_committee_review: 'کمیته دروس در حال هماهنگی و ثبت زمان جلسه است.',
  meeting_scheduled: 'جلسه برنامه‌ریزی شده است. پس از برگزاری، کمیته نتیجه را ثبت می‌کند.',
  track_applied: 'رسته(های) جدید با موفقیت در پرونده کمک‌مدرسی شما اعمال شد.',
}

export function labelTrackCode(code) {
  if (!code) return '—'
  return TRACK_LABEL_BY_VALUE[String(code)] || String(code)
}

export function labelTracks(codes) {
  const list = normalizeTrackList(codes)
  if (!list.length) return '—'
  return list.map(labelTrackCode).join('، ')
}

export function normalizeTrackList(raw) {
  if (Array.isArray(raw)) {
    return raw.map((x) => String(x).trim()).filter(Boolean)
  }
  if (raw != null && String(raw).trim() !== '') return [String(raw).trim()]
  return []
}

export function fmtIsoDate(iso) {
  if (!iso) return '—'
  try {
    return formatShamsiTehran(iso)
  } catch {
    return String(iso)
  }
}

export function fmtTimeHm(raw) {
  if (!raw) return '—'
  const s = String(raw).trim()
  return s || '—'
}

export function getActiveTracksFromExtra(extra = {}) {
  const lms = extra?.lms && typeof extra.lms === 'object' ? extra.lms : {}
  const fromLms = normalizeTrackList(lms.ta_active_tracks)
  if (fromLms.length) return fromLms
  return normalizeTrackList(extra.ta_active_tracks)
}

export function resolveTaTrackContext(ctx = {}, studentExtra = {}) {
  const path = ctx.path || null
  const currentTracks = normalizeTrackList(
    ctx.current_tracks?.length ? ctx.current_tracks : getActiveTracksFromExtra(studentExtra),
  )
  const newTracks = normalizeTrackList(ctx.new_tracks)
  const appliedTracks = normalizeTrackList(ctx.applied_tracks)

  return {
    path,
    pathLabel: PATH_LABELS[path] || (path ? String(path) : '—'),
    taName: ctx.ta_name_fa || ctx.teaching_assistant_name || '',
    currentTracks,
    currentTracksLabel: labelTracks(currentTracks),
    newTracks,
    newTracksLabel: labelTracks(newTracks),
    appliedTracks,
    appliedTracksLabel: labelTracks(appliedTracks),
    meetingDate: ctx.meeting_date,
    meetingTime: ctx.meeting_time,
    meetingType: ctx.meeting_type,
    meetingLink: ctx.meeting_link,
    meetingLocationFa: ctx.meeting_location_fa || 'مکان انستیتو',
  }
}

export function TaTrackFlowStepper({ currentState, compact = false }) {
  const activeIdx = TA_TRACK_FLOW_STEPS.findIndex((step) =>
    step.states.includes(currentState),
  )
  const idx = activeIdx >= 0 ? activeIdx : 0
  const isDone = currentState === 'track_applied'
  const isStop = currentState === 'rejected'

  return (
    <div
      data-testid="ta-track-flow-stepper"
      style={{
        display: 'grid',
        gridTemplateColumns: compact ? 'repeat(2, 1fr)' : 'repeat(auto-fit, minmax(100px, 1fr))',
        gap: '0.5rem',
        marginBottom: compact ? '0.65rem' : '1rem',
      }}
    >
      {TA_TRACK_FLOW_STEPS.map((step, i) => {
        const done = i < idx || isDone
        const active = i === idx && !isDone && !isStop
        const stop = isStop && i === TA_TRACK_FLOW_STEPS.length - 1
        return (
          <div
            key={step.key}
            style={{
              padding: '0.5rem 0.6rem',
              borderRadius: '8px',
              fontSize: '0.75rem',
              fontWeight: active ? 700 : 500,
              textAlign: 'center',
              background: stop ? '#fef2f2' : done ? '#f0fdf4' : active ? '#eff6ff' : '#f8fafc',
              borderRight: `3px solid ${
                stop ? '#dc2626' : done ? '#16a34a' : active ? '#2563eb' : '#e2e8f0'
              }`,
              color: stop ? '#b91c1c' : done ? '#166534' : active ? '#1d4ed8' : '#64748b',
            }}
          >
            {step.label}
          </div>
        )
      })}
    </div>
  )
}

export function HintBlock({ children, tone = '#2563eb', bg = '#eff6ff', testId = null }) {
  if (!children) return null
  return (
    <div
      data-testid={testId}
      style={{
        marginBottom: '0.85rem',
        padding: '0.75rem 1rem',
        borderRadius: '10px',
        background: bg,
        borderRight: `4px solid ${tone}`,
        fontSize: '0.85rem',
        lineHeight: 1.65,
        color: '#334155',
      }}
    >
      {children}
    </div>
  )
}

export function InfoTile({ label, value, tone = '#2563eb', bg = '#eff6ff' }) {
  return (
    <div
      style={{
        padding: '0.65rem 0.75rem',
        borderRadius: '8px',
        background: bg,
        borderRight: `3px solid ${tone}`,
      }}
    >
      <div style={{ fontSize: '0.72rem', color: '#64748b', marginBottom: '0.2rem' }}>{label}</div>
      <div style={{ fontSize: '0.88rem', fontWeight: 600, color: '#1e293b' }}>{value || '—'}</div>
    </div>
  )
}
