import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import {
  SupervisionIncreaseFlowStepper,
  ScheduleChip,
  parseWeeklyCount,
  resolveStudentRequestedSchedule,
  resolveSupervisorAlternativeSchedule,
  resolveStudentCounterSchedule,
} from '../utils/supervisionSessionIncreaseDisplay'

const PROCESS_TITLE_FA =
  'درخواست افزایش جلسات هفتگی سوپرویژن (فرایند ۲۱)'

const STATE_HINTS = {
  request_submitted: {
    student: 'تاریخ نزدیک‌ترین جلسه و ساعت شروع را در فرم زیر وارد کنید؛ پس از «ثبت فرم»، «ادامه و ثبت مرحله» را بزنید تا درخواست به سوپروایزر برود.',
    supervisor: 'دانشجو در حال ثبت زمان پیشنهادی است.',
  },
  supervisor_review: {
    student: 'سوپروایزر در حال بررسی زمان پیشنهادی شماست. پس از اعلام نتیجه همین صفحه را تازه کنید.',
    supervisor: 'زمان پیشنهادی دانشجو را بررسی کنید؛ تأیید، پیشنهاد جایگزین، یا رد کامل.',
  },
  student_response: {
    student: 'سوپروایزر زمان دیگری پیشنهاد داده است. اگر موافقید «تأیید» را بزنید؛ در غیر این صورت تاریخ و ساعت جدید را در فرم بنویسید و «ورود زمان جدید» را انتخاب کنید.',
    supervisor: 'منتظر پاسخ دانشجو به پیشنهاد جایگزین.',
  },
  session_added: {
    student: 'جلسهٔ هفتگی سوپرویژن جدید به برنامهٔ شما اضافه شد و مشمول فرایند تکمیل دوره‌های ۵۰ ساعته است.',
    supervisor: 'جلسهٔ هفتگی جدید ثبت شد و به فرایند ۵۰ ساعته متصل شد.',
  },
  request_rejected: {
    student: 'سوپروایزر در حال حاضر امکان افزایش جلسات هفتگی را اعلام نکرده است؛ در صورت نیاز بعداً می‌توانید دوباره درخواست دهید.',
    supervisor: 'درخواست رد شد — دانشجو می‌تواند بعداً دوباره درخواست دهد.',
  },
}

function StatTile({ label, value, sub, tone = '#7c3aed', bg = '#f5f3ff' }) {
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
      <div style={{ fontSize: '1.15rem', fontWeight: 800, color: tone }}>{value}</div>
      {sub && <div style={{ fontSize: '0.76rem', color: '#78716c', marginTop: '0.2rem' }}>{sub}</div>}
    </div>
  )
}

/**
 * داشبورد راهنمای «افزایش جلسات هفتگی سوپرویژن» — فرایند ۲۱.
 * نمای دانشجو (پیش‌فرض) یا سوپروایزر با prop `portalRole`.
 */
export default function StudentSupervisionSessionIncreasePanel({
  detail = null,
  stepFormValues = {},
  active = true,
  compact = false,
  portalRole = 'student',
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const isSupervisor = portalRole === 'supervisor' || portalRole === 'admin'

  const weeklyBefore = useMemo(() => {
    const fromCtx = parseWeeklyCount(
      ctx.supervision_weekly_sessions
      ?? ctx.weekly_supervision_sessions
      ?? ctx.supervision_weekly_sessions_before
      ?? ctx.weekly_sessions_at_start,
    )
    return fromCtx
  }, [ctx])

  const weeklyAfter = parseWeeklyCount(ctx.weekly_supervision_sessions_after ?? ctx.supervision_weekly_sessions_after)

  const requested = useMemo(
    () => resolveStudentRequestedSchedule(ctx, stepFormValues),
    [ctx, stepFormValues],
  )
  const alternative = useMemo(() => resolveSupervisorAlternativeSchedule(ctx), [ctx])
  const counter = useMemo(
    () => resolveStudentCounterSchedule(ctx, stepFormValues),
    [ctx, stepFormValues],
  )

  const hasAlternative = !!(alternative.date || alternative.time)
  const showCounterPreview = currentState === 'student_response'
    && (counter.date || counter.time)

  if (!active || !detail || detail.process_code !== 'supervision_session_increase') {
    return null
  }

  const hint = STATE_HINTS[currentState]?.[isSupervisor ? 'supervisor' : 'student']
    ?? (isSupervisor
      ? 'پروندهٔ افزایش جلسات هفتگی سوپرویژن.'
      : 'پس از تأیید سوپروایزر، یک جلسهٔ هفتگی دیگر به برنامهٔ سوپرویژن شما اضافه می‌شود.')

  const isTerminal = currentState === 'session_added' || currentState === 'request_rejected'

  return (
    <div className="card" data-testid="student-supervision-session-increase-panel">
      <div className="card-header">
        <h3 className="card-title">{PROCESS_TITLE_FA}</h3>
        {currentState && !compact && (
          <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>

      <div style={{ padding: compact ? '0 0.75rem 0.75rem' : '0 1rem 1rem' }}>
        <SupervisionIncreaseFlowStepper currentState={currentState} compact={compact} />

        {!isTerminal && hint && (
          <div
            data-testid="supervision-increase-state-hint"
            style={{
              marginBottom: compact ? '0.65rem' : '0.85rem',
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: isSupervisor ? '#f0fdfa' : '#eff6ff',
              borderRight: `4px solid ${isSupervisor ? '#0d9488' : '#2563eb'}`,
              fontSize: '0.86rem',
              lineHeight: 1.75,
              color: isSupervisor ? '#134e4a' : '#1e3a8a',
            }}
          >
            {hint}
          </div>
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: '0.65rem',
            marginBottom: compact ? '0.65rem' : '0.85rem',
          }}
        >
          {weeklyBefore != null && (
            <StatTile
              label="جلسات هفتگی فعلی"
              value={`${weeklyBefore.toLocaleString('fa-IR')} جلسه`}
              sub={weeklyAfter != null && currentState === 'session_added'
                ? `پس از افزایش: ${weeklyAfter.toLocaleString('fa-IR')} جلسه`
                : 'قبل از افزایش'}
              tone="#7c3aed"
              bg="#f5f3ff"
            />
          )}
          {currentState === 'session_added' && weeklyAfter == null && weeklyBefore != null && (
            <StatTile
              label="پس از افزایش (تخمینی)"
              value={`${(weeklyBefore + 1).toLocaleString('fa-IR')} جلسه`}
              sub="یک جلسهٔ هفتگی اضافه شد"
              tone="#16a34a"
              bg="#f0fdf4"
            />
          )}
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '0.65rem',
            marginBottom: compact ? '0.5rem' : '0.75rem',
          }}
        >
          <ScheduleChip
            testId="supervision-increase-requested-schedule"
            label={isSupervisor ? 'زمان درخواستی دانشجو' : 'زمان درخواستی شما'}
            date={requested.date}
            time={requested.time}
            weekday={requested.weekday}
            tone="#2563eb"
            bg="#eff6ff"
          />

          {hasAlternative && (
            <ScheduleChip
              testId="supervision-increase-alternative-schedule"
              label="پیشنهاد جایگزین سوپروایزر"
              date={alternative.date}
              time={alternative.time}
              tone="#d97706"
              bg="#fffbeb"
            />
          )}

          {showCounterPreview && (
            <ScheduleChip
              testId="supervision-increase-counter-schedule"
              label="زمان جدید (پیش‌نمایش)"
              date={counter.date}
              time={counter.time}
              tone="#ea580c"
              bg="#fff7ed"
            />
          )}
        </div>

        {currentState === 'student_response' && hasAlternative && !isSupervisor && (
          <div
            role="status"
            data-testid="supervision-increase-negotiation-note"
            style={{
              marginBottom: '0.65rem',
              padding: '0.7rem 0.9rem',
              borderRadius: '8px',
              background: '#fefce8',
              borderRight: '4px solid #ca8a04',
              fontSize: '0.84rem',
              lineHeight: 1.7,
              color: '#713f12',
            }}
          >
            مذاکرهٔ زمانی: اگر با پیشنهاد سوپروایزر موافقید دکمهٔ تأیید را بزنید؛
            در غیر این صورت تاریخ و ساعت جدید را در فرم پایین وارد کنید.
          </div>
        )}

        {currentState === 'supervisor_review' && isSupervisor && (
          <div
            role="status"
            data-testid="supervision-increase-supervisor-review-note"
            style={{
              fontSize: '0.8rem',
              color: '#64748b',
              lineHeight: 1.65,
              margin: 0,
            }}
          >
            پس از تأیید، جلسهٔ هفتگی جدید ثبت و به فرایند تکمیل ۵۰ ساعتهٔ سوپرویژن متصل می‌شود.
            برای «پیشنهاد جایگزین»، تاریخ و ساعت را در بخش تصمیم پایین وارد کنید.
          </div>
        )}

        {currentState === 'session_added' && (
          <p
            data-testid="supervision-increase-success-note"
            style={{ margin: 0, fontSize: '0.82rem', color: '#166534', lineHeight: 1.7 }}
          >
            جلسهٔ جدید در برنامهٔ سوپرویژن شما ثبت شد. پیگیری ساعات از طریق فرایند تکمیل دوره‌های ۵۰ ساعته انجام می‌شود.
          </p>
        )}

        {(counter.note || '').trim() && showCounterPreview && (
          <p style={{ margin: '0.65rem 0 0', fontSize: '0.82rem', color: '#57534e', lineHeight: 1.65 }}>
            <strong>توضیح دانشجو:</strong>
            {' '}
            {counter.note.trim()}
          </p>
        )}
      </div>
    </div>
  )
}
