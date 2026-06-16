import React, { useState, useEffect } from 'react'
import { buildRoadmapStates } from '../utils/studentRoadmap'
import { buildStudentGuidance, findStateDefinition } from '../utils/studentProcessGuidance'
import ProcessStepForms from './ProcessStepForms'
import InterviewSlotPicker, { InterviewPaidBookingSummary } from './InterviewSlotPicker'
import StudentProcessGuidancePanel from './StudentProcessGuidancePanel'
import {
  filterFormsForStudent,
  stepFormsBlockTransition,
  CTX_DOCUMENTS_RESUBMIT_FIELDS,
} from '../utils/processFormsStudent'
import { labelProcess, labelState, resolveStateDisplayLabel } from '../utils/processDisplay'
import {
  STUDENT_TRANSITION_CTA_INTRO,
  getStudentTransitionButtonMain,
  getStudentTransitionButtonSub,
  getStudentTransitionTooltip,
} from '../utils/studentTransitionCta'
import { showStudentTransitionCta } from '../utils/studentTransitionCtaVisibility'
import SepPaymentPanel from './SepPaymentPanel'
import StudentProcessStepReview from './StudentProcessStepReview'
import StudentSmsHistorySection from './StudentSmsHistorySection'

const REGISTRATION_PROCESS_CODES = ['introductory_course_registration', 'comprehensive_course_registration']

function hasRegistrationInterviewBooking(detail) {
  const ctx = detail?.context_data || {}
  return !!(ctx.selected_timeslot || ctx.interview_date)
}

/** نقش‌هایی که «منتظر اقدام همکار» برایشان بلوک جدا می‌گذاریم — نه system */
const STAFF_HUMAN_ROLES = ['interviewer', 'admissions_officer', 'progress_committee', 'supervision_committee']

const ASSIGNED_ROLE_LABELS_FA = {
  interviewer: 'مصاحبه‌کننده',
  admissions_officer: 'مسئول پذیرش',
  system: 'سامانه / واحد آموزش',
  progress_committee: 'کمیته پیشرفت',
  supervision_committee: 'کمیته نظارت',
  applicant: 'متقاضی',
  student: 'دانشجو',
}

function resolveSepPaymentDescription(detail) {
  const pc = detail?.process_code
  const cs = detail?.current_state
  if (pc === 'start_therapy' && cs === 'payment_pending') {
    return 'پرداخت هزینه جلسه اول آغاز درمان آموزشی'
  }
  if (pc === 'extra_session' && cs === 'payment_required') {
    return 'پرداخت جلسه اضافی درمان آموزشی'
  }
  if (cs === 'interview_payment') {
    if (pc === 'comprehensive_course_registration') return 'پرداخت هزینه مصاحبهٔ دوره جامع'
    if (pc === 'introductory_course_registration') return 'پرداخت هزینه مصاحبهٔ دوره آشنایی'
  }
  if (cs === 'payment' && REGISTRATION_PROCESS_CODES.includes(pc)) {
    return pc === 'comprehensive_course_registration'
      ? 'پرداخت شهریه دوره جامع'
      : 'پرداخت شهریه دوره آشنایی'
  }
  return 'پرداخت جلسات درمان آموزشی'
}

/**
 * کارت «قدم بعد» — فرم‌های مرحله + فقط اقدامات مجاز از API انتقال + مسیر بازی‌گونه
 */
export default function StudentQuestCard({
  loading,
  detail,
  definition,
  transitions,
  forms,
  stepFormValues,
  onStepFieldChange,
  onFormRegisterSubmit,
  decisionNotes,
  onDecisionNotesChange,
  onTrigger,
  onOpenProcesses,
  extraData,
  /** شناسهٔ رکورد دانشجو (students.id) برای پرداخت درگاه */
  studentId = null,
  /** پس از ثبت موفق فرم در سرور؛ تا باز شدن توسط مسئول فرم مخفی است */
  stepFormLocked = false,
  /** introductory | comprehensive — برای رزرو وقت مصاحبه در مسیر ثبت‌نام */
  courseType = null,
  /** پس از رزرو وقت موفق */
  onInterviewBooked = null,
  /** کلید refetch تاریخچهٔ پیامک (مثلاً instance_id + current_state) */
  smsRefreshKey = null,
}) {
  const [selectedTransitionIdx, setSelectedTransitionIdx] = useState(0)
  const transitionList = transitions || []

  useEffect(() => {
    setSelectedTransitionIdx(0)
  }, [detail?.instance_id, detail?.current_state])

  useEffect(() => {
    const n = transitionList.length
    if (!n) return
    setSelectedTransitionIdx((i) => (i >= n ? 0 : i))
  }, [transitionList.length])

  const roadmapStates = definition ? buildRoadmapStates(definition) : []
  const curIdx = detail && roadmapStates.length
    ? roadmapStates.findIndex(s => s.code === detail.current_state)
    : -1
  const stepIndex = curIdx >= 0 ? curIdx + 1 : 0
  const totalSteps = roadmapStates.length || 1
  const pathPct = roadmapStates.length && curIdx >= 0
    ? Math.min(100, Math.round(((curIdx + 1) / roadmapStates.length) * 100))
    : 0

  const currentStateMeta = roadmapStates.find(s => s.code === detail?.current_state)
  const processCode = definition?.process?.code
  const currentStateLabel = resolveStateDisplayLabel(detail?.current_state, currentStateMeta?.name_fa, processCode) || '—'

  const level = extraData?.gamification?.level

  if (loading) {
    return (
      <div className="quest-card quest-card--loading">
        <div className="quest-card-shimmer" />
        <p className="quest-loading-text">در حال بارگذاری مسیر اصلی شما…</p>
      </div>
    )
  }

  if (!detail) {
    return (
      <div className="quest-card quest-card--empty">
        <div className="quest-card-badge">مسیر</div>
        <h2 className="quest-title">هنوز فرایند اصلی به پروفایل شما وصل نیست</h2>
        <p className="quest-desc">
          معمولاً پس از ثبت‌نام، مسیر ثبت‌نام دوره به‌صورت خودکار باز می‌شود. اگر این پیام را می‌بینید، با پشتیبانی یا بخش پذیرش تماس بگیرید.
        </p>
        {onOpenProcesses && (
          <button
            type="button"
            className="btn btn-primary"
            data-testid="student-quest-nav-processes-empty"
            onClick={onOpenProcesses}
          >
            رفتن به فرایندها
          </button>
        )}
      </div>
    )
  }

  const processTitle = labelProcess(detail.process_code)
  const done = detail.is_completed || detail.is_cancelled
  const studentForms = filterFormsForStudent(forms || [])
  const rawResubmit = detail?.context_data?.[CTX_DOCUMENTS_RESUBMIT_FIELDS]
  const docsResubmit = Array.isArray(rawResubmit) && rawResubmit.length ? rawResubmit : null
  const transitionBlocked = !done && studentForms.length > 0 && !stepFormLocked
    && stepFormsBlockTransition(forms, stepFormValues, {
      resubmitFieldNames: docsResubmit || undefined,
      contextData: detail?.context_data,
    })
  const guidance = buildStudentGuidance({
    definition,
    detail,
    transitions,
    forms,
    stepFormLocked,
  })

  const showLegacySep = detail?.current_state === 'awaiting_payment'
    || detail?.current_state === 'payment_pending'
    || (detail?.process_code === 'extra_session' && detail?.current_state === 'payment_required')

  const hasInterviewBooking = hasRegistrationInterviewBooking(detail)
  const showRegistrationSep = REGISTRATION_PROCESS_CODES.includes(detail?.process_code)
    && (
      detail?.current_state === 'interview_payment'
      || detail?.current_state === 'payment'
      || (detail?.current_state === 'interview_scheduled' && hasInterviewBooking)
    )

  const showSepPanel = !done && studentId && detail?.instance_id && (showLegacySep || showRegistrationSep)

  const transitionListForCta = transitionList.filter((t) => {
    if (
      showSepPanel
      && detail?.current_state === 'interview_scheduled'
      && t.trigger_event === 'proceed_to_payment'
    ) {
      return false
    }
    return true
  })

  const showTransitionCta = showStudentTransitionCta({
    transitions: transitionListForCta,
    transitionBlocked,
    detailDone: done,
  })

  const selectedTransition = transitionListForCta[selectedTransitionIdx] ?? transitionListForCta[0]

  const ctx = detail?.context_data || {}
  const paymentAmountRial =
    ctx.payment_amount_rial != null
      ? Number(ctx.payment_amount_rial)
      : Math.round(Number(ctx.invoice_amount || 0) * 10)

  const stateDefForRole = definition && detail?.current_state
    ? findStateDefinition(definition, detail.current_state)
    : null
  const assignMeta = stateDefForRole?.metadata || {}
  const assignRole = stateDefForRole?.assigned_role
  const studentLikeRole = assignRole === 'student' || assignRole === 'applicant'
  const staffDepFa = (assignMeta.staff_dependency_fa || '').trim()
  const showStaffWaitPanel = !done && stateDefForRole && !studentLikeRole && assignRole && (
    staffDepFa
    || (transitionList.length === 0 && STAFF_HUMAN_ROLES.includes(assignRole))
  )

  const showInterviewSlotInCard = !done && courseType && detail?.instance_id && onInterviewBooked && (
    (detail.process_code === 'introductory_course_registration' && detail.current_state === 'application_submitted')
    || (detail.process_code === 'comprehensive_course_registration' && detail.current_state === 'interview_scheduled')
  )

  const showInterviewPaidSummary = !done
    && REGISTRATION_PROCESS_CODES.includes(detail?.process_code)
    && hasRegistrationInterviewBooking(detail)
    && !['application_submitted', 'interview_scheduled', 'interview_payment'].includes(detail?.current_state)

  return (
    <div className="quest-card" data-testid="student-quest-card">
      <div className="quest-card-top">
        <div className="quest-card-head">
          <span className="quest-pill">مسیر فعلی شما</span>
          {level != null && (
            <span className="quest-pill quest-pill--xp">سطح {level}</span>
          )}
        </div>
        <h2 className="quest-title">{processTitle}</h2>
        <p className="quest-sub">
          {done
            ? (detail.is_completed ? 'این مسیر به پایان رسیده است.' : 'این مسیر لغو شده است.')
            : `مرحلهٔ ${stepIndex} از ${totalSteps} · ${pathPct}% مسیر`}
        </p>
      </div>

      <StudentProcessGuidancePanel guidance={guidance} variant="quest" />

      {!done && detail?.current_state === 'credentials_created' && ctx.portal_username && (
        <div
          className="quest-credentials-banner"
          data-testid="student-quest-portal-credentials"
          style={{
            marginTop: '0.85rem',
            padding: '1rem 1.25rem',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #eff6ff 0%, #f0f9ff 100%)',
            borderRight: '4px solid #2563eb',
            fontSize: '0.9rem',
            lineHeight: 1.75,
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: '0.35rem' }}>اطلاعات ورود به پرتال دانشجویی (LMS)</div>
          <p style={{ margin: 0 }}>
            مدارک شما تأیید شد. تا {ctx.lms_login_deadline || 'مهلت اعلام‌شده'} با مشخصات زیر وارد سامانه شوید و دروس را انتخاب کنید.
          </p>
          <p style={{ margin: '0.5rem 0 0', fontFamily: 'monospace', direction: 'ltr', textAlign: 'left' }}>
            USERNAME: {ctx.portal_username}
            <br />
            PASSWORD: {ctx.portal_password_display || '—'}
          </p>
        </div>
      )}

      {showStaffWaitPanel && (
        <div
          className="quest-staff-wait"
          data-testid="student-quest-staff-wait"
          role="status"
        >
          <div className="quest-staff-wait-title">
            اقدام بعدی در مرکز
            {assignRole && (
              <span>
                {' '}
                (
                {ASSIGNED_ROLE_LABELS_FA[assignRole] || assignRole}
                )
              </span>
            )}
          </div>
          <p>
            {staffDepFa
              || 'این مرحله توسط مرکز در حال پیگیری است؛ پس از به‌روزرسانی وضعیت، همین صفحه را تازه کنید. جزئیات در بخش «وظیفهٔ شما در این مرحله» بالاتر آمده است.'}
          </p>
        </div>
      )}

      {showInterviewSlotInCard && (
        <div className="quest-interview-slot-wrap" data-testid="student-quest-interview-slot-picker" style={{ marginTop: '0.85rem' }}>
          <p className="quest-interview-slot-title">
            رزرو وقت مصاحبه
          </p>
          <InterviewSlotPicker
            courseType={courseType}
            instanceId={detail.instance_id}
            onBooked={onInterviewBooked}
          />
        </div>
      )}

      {showInterviewPaidSummary && (
        <InterviewPaidBookingSummary />
      )}

      {showRegistrationSep && (
        <div data-testid="student-quest-sep-payment" style={{ marginTop: '0.85rem' }}>
          <SepPaymentPanel
            instanceId={detail.instance_id}
            studentId={studentId}
            amountRial={paymentAmountRial}
            description={resolveSepPaymentDescription(detail)}
          />
        </div>
      )}

      {!done && detail?.process_code === 'session_payment' && ['payment_due', 'payment_selection', 'awaiting_payment', 'payment_failed'].includes(detail?.current_state) && (() => {
        const c = detail?.context_data || {}
        const rawDebt = c.debt_sessions_count
        const debt = rawDebt != null ? Number(rawDebt) : 0
        const credit = c.session_credit_balance != null ? Number(c.session_credit_balance) : null
        return (
          <div
            className="quest-session-payment-financial"
            style={{
              marginTop: '0.75rem', padding: '0.85rem 1rem', borderRadius: '10px',
              background: 'linear-gradient(135deg, #f0fdf4 0%, #f8fafc 100%)',
              borderRight: '4px solid #16a34a', fontSize: '0.86rem', lineHeight: 1.75,
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#14532d' }}>وضعیت مالی جلسات درمان</div>
            <div>
              <strong>جلسات بدون پرداخت ثبت‌شده:</strong>{' '}
              {Number.isFinite(debt) ? debt.toLocaleString('fa-IR') : '—'}
            </div>
            {credit != null && Number.isFinite(credit) && credit > 0 && (
              <div style={{ marginTop: '0.35rem' }}>
                <strong>اعتبار پس از پرداخت (تقریبی در پرونده):</strong>{' '}
                {credit.toLocaleString('fa-IR')} تومان
              </div>
            )}
            {Number.isFinite(debt) && debt > 0 && (
              <p style={{ margin: '0.5rem 0 0', fontSize: '0.82rem', color: '#475569' }}>
                در صورت بدهی، در مرحلهٔ «انتخاب جلسات» گزینهٔ تسویهٔ بدهی را فعال کنید؛ در غیر این صورت فقط پرداخت جلسات آتی مجاز نیست.
              </p>
            )}
          </div>
        )
      })()}

      {!done && detail?.process_code === 'educational_leave' && (() => {
        const c = detail?.context_data || {}
        const fmt = s => {
          if (!s || typeof s !== 'string') return null
          const t = Date.parse(s)
          if (Number.isNaN(t)) return s
          try {
            return new Date(t).toLocaleString('fa-IR', { dateStyle: 'medium', timeStyle: 'short' })
          } catch {
            return s
          }
        }
        const hasMeeting = !!(c.committee_meeting_at && String(c.committee_meeting_at).trim())
        const hasSchedule = !!(c.return_reminder_at || c.return_deadline_at)
        if (!hasMeeting && !hasSchedule) return null
        const modeFa = c.committee_meeting_mode === 'online' ? 'آنلاین' : c.committee_meeting_mode === 'in_person' ? 'حضوری' : ''
        return (
          <div
            className="quest-leave-context"
            style={{
              marginTop: '0.75rem', padding: '0.85rem 1rem', borderRadius: '10px',
              background: 'linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%)',
              borderRight: '4px solid #2563eb', fontSize: '0.86rem', lineHeight: 1.75,
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#1e3a8a' }}>جزئیات مرخصی و جلسه</div>
            {hasMeeting && (
              <div style={{ marginBottom: hasSchedule ? '0.5rem' : 0 }}>
                <strong>جلسه کمیته پیشرفت:</strong>{' '}
                {fmt(c.committee_meeting_at)}
                {modeFa ? ` · ${modeFa}` : ''}
                {c.committee_meeting_mode === 'online' && c.committee_meeting_link
                  ? (
                    <span> · <a href={c.committee_meeting_link} target="_blank" rel="noopener noreferrer">لینک جلسه</a></span>
                    )
                  : null}
                {c.committee_meeting_mode === 'in_person' && c.committee_meeting_location_fa
                  ? ` · محل: ${c.committee_meeting_location_fa}`
                  : null}
              </div>
            )}
            {hasSchedule && (
              <div>
                <strong>بازگشت به تحصیل:</strong>
                {c.return_reminder_at ? ` یادآوری حدود ${fmt(c.return_reminder_at)}` : ''}
                {c.return_deadline_at ? ` — مهلت اعلام ثبت‌نام ترم: ${fmt(c.return_deadline_at)}` : ''}
              </div>
            )}
          </div>
        )
      })()}

      {!done && detail?.process_code === 'therapy_completion' && (() => {
        const c = detail?.context_data || {}
        const th = c.therapy_hours_2x != null ? Number(c.therapy_hours_2x) : null
        const tt = c.therapy_threshold != null ? Number(c.therapy_threshold) : null
        const ch = c.clinical_hours != null ? Number(c.clinical_hours) : null
        const ct = c.clinical_threshold != null ? Number(c.clinical_threshold) : null
        const sh = c.supervision_hours != null ? Number(c.supervision_hours) : null
        const st = c.supervision_threshold != null ? Number(c.supervision_threshold) : null
        const preview = (c.therapy_completion_preview_fa || '').trim()
        if (th == null && preview === '') return null
        return (
          <div
            className="quest-therapy-completion-preview"
            style={{
              marginTop: '0.75rem', padding: '0.85rem 1rem', borderRadius: '10px',
              background: 'linear-gradient(135deg, #fdf4ff 0%, #f8fafc 100%)',
              borderRight: '4px solid #a21caf', fontSize: '0.86rem', lineHeight: 1.75,
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#701a75' }}>ایست بازرسی ساعات (خاتمه درمان)</div>
            {preview ? <p style={{ margin: '0 0 0.5rem' }}>{preview}</p> : null}
            <div style={{ display: 'grid', gap: '0.25rem', fontSize: '0.84rem' }}>
              {th != null && tt != null && (
                <div><strong>درمان آموزشی:</strong> {th.toLocaleString('fa-IR')} / {tt.toLocaleString('fa-IR')}</div>
              )}
              {ch != null && ct != null && (
                <div><strong>تجربه بالینی:</strong> {ch.toLocaleString('fa-IR')} / {ct.toLocaleString('fa-IR')}</div>
              )}
              {sh != null && st != null && (
                <div><strong>سوپرویژن:</strong> {sh.toLocaleString('fa-IR')} / {st.toLocaleString('fa-IR')}</div>
              )}
            </div>
          </div>
        )
      })()}

      {!done && detail?.process_code === 'therapy_session_reduction' && (() => {
        const c = detail?.context_data || {}
        const th = c.therapy_hours_2x != null ? Number(c.therapy_hours_2x) : null
        const tt = c.therapy_threshold != null ? Number(c.therapy_threshold) : null
        const ch = c.clinical_hours != null ? Number(c.clinical_hours) : null
        const ct = c.clinical_threshold != null ? Number(c.clinical_threshold) : null
        const sh = c.supervision_hours != null ? Number(c.supervision_hours) : null
        const st = c.supervision_threshold != null ? Number(c.supervision_threshold) : null
        const ws = c.student_weekly_sessions_before != null ? Number(c.student_weekly_sessions_before) : null
        const upcoming = Array.isArray(c.upcoming_therapy_sessions) ? c.upcoming_therapy_sessions.length : null
        if (th == null && ws == null) return null
        return (
          <div
            className="quest-therapy-reduction-preview"
            style={{
              marginTop: '0.75rem', padding: '0.85rem 1rem', borderRadius: '10px',
              background: 'linear-gradient(135deg, #fff7ed 0%, #f8fafc 100%)',
              borderRight: '4px solid #ea580c', fontSize: '0.86rem', lineHeight: 1.75,
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#9a3412' }}>کاهش جلسات هفتگی درمان</div>
            {ws != null && (
              <div style={{ marginBottom: '0.35rem' }}>
                <strong>برنامهٔ فعلی:</strong>{' '}
                {ws.toLocaleString('fa-IR')} جلسه در هفته
                {upcoming != null ? ` — ${upcoming.toLocaleString('fa-IR')} جلسهٔ آتی در تقویم` : ''}
              </div>
            )}
            <div style={{ display: 'grid', gap: '0.25rem', fontSize: '0.84rem' }}>
              {th != null && tt != null && (
                <div><strong>درمان آموزشی:</strong> {th.toLocaleString('fa-IR')} / {tt.toLocaleString('fa-IR')}</div>
              )}
              {ch != null && ct != null && (
                <div><strong>تجربه بالینی:</strong> {ch.toLocaleString('fa-IR')} / {ct.toLocaleString('fa-IR')}</div>
              )}
              {sh != null && st != null && (
                <div><strong>سوپرویژن:</strong> {sh.toLocaleString('fa-IR')} / {st.toLocaleString('fa-IR')}</div>
              )}
            </div>
            {(c.therapy_reduction_next_step_fa || '').trim() ? (
              <p style={{ margin: '0.5rem 0 0', fontSize: '0.82rem', color: '#57534e' }}>{c.therapy_reduction_next_step_fa}</p>
            ) : null}
          </div>
        )
      })()}

      {done && detail?.process_code === 'therapy_session_reduction' && detail?.context_data?.therapy_reduction_next_step_fa && (
        <div
          style={{
            marginTop: '0.75rem', padding: '0.85rem 1rem', borderRadius: '10px',
            background: 'linear-gradient(135deg, #ecfdf5 0%, #f8fafc 100%)',
            borderRight: '4px solid #059669', fontSize: '0.86rem', lineHeight: 1.75,
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#065f46' }}>گام بعد</div>
          <p style={{ margin: 0 }}>{detail.context_data.therapy_reduction_next_step_fa}</p>
          {detail.context_data.violation_registration_instance_id && (
            <p style={{ margin: '0.5rem 0 0', fontSize: '0.8rem', color: '#64748b' }}>
              فرایند ثبت تخلف:{' '}
              <code dir="ltr" style={{ fontSize: '0.78rem' }}>{String(detail.context_data.violation_registration_instance_id)}</code>
            </p>
          )}
        </div>
      )}

      {done && detail?.process_code === 'therapy_changes' && detail?.context_data?.therapy_changes_next_step_fa && (
        <div
          style={{
            marginTop: '0.75rem', padding: '0.85rem 1rem', borderRadius: '10px',
            background: 'linear-gradient(135deg, #ecfdf5 0%, #f8fafc 100%)',
            borderRight: '4px solid #059669', fontSize: '0.86rem', lineHeight: 1.75,
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#065f46' }}>گام بعد پیشنهادی</div>
          <p style={{ margin: 0 }}>{detail.context_data.therapy_changes_next_step_fa}</p>
          {detail.context_data.parent_instance_id && (
            <p style={{ margin: '0.5rem 0 0', fontSize: '0.8rem', color: '#64748b' }}>
              شناسه فرایند مرتبط (در صورت ارجاع):{' '}
              <code dir="ltr" style={{ fontSize: '0.78rem' }}>{String(detail.context_data.parent_instance_id)}</code>
            </p>
          )}
        </div>
      )}

      {done && detail?.process_code === 'therapy_completion' && detail?.context_data?.therapy_completion_next_step_fa && (
        <div
          style={{
            marginTop: '0.75rem', padding: '0.85rem 1rem', borderRadius: '10px',
            background: 'linear-gradient(135deg, #ecfdf5 0%, #f8fafc 100%)',
            borderRight: '4px solid #059669', fontSize: '0.86rem', lineHeight: 1.75,
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#065f46' }}>گام بعد پیشنهادی</div>
          <p style={{ margin: 0 }}>{detail.context_data.therapy_completion_next_step_fa}</p>
        </div>
      )}

      {!done && roadmapStates.length > 0 && (
        <div className="quest-steps" aria-label="مراحل فرایند">
          {roadmapStates.map((st, i) => {
            const isCurrent = st.code === detail.current_state
            const past = curIdx >= 0 && i < curIdx
            return (
              <div
                key={st.code}
                className={`quest-step ${isCurrent ? 'quest-step--current' : ''} ${past ? 'quest-step--past' : ''}`}
                title={resolveStateDisplayLabel(st.code, st.name_fa, processCode)}
              >
                <span className="quest-step-num">{i + 1}</span>
                <span className="quest-step-label">{resolveStateDisplayLabel(st.code, st.name_fa, processCode)}</span>
              </div>
            )
          })}
        </div>
      )}

      <div className="quest-current-box">
        <span className="quest-current-label">وضعیت فعلی</span>
        <strong className="quest-current-value">{currentStateLabel}</strong>
      </div>

      <StudentSmsHistorySection refreshKey={smsRefreshKey ?? `${detail?.instance_id || ''}-${detail?.current_state || ''}`} />

      <StudentProcessStepReview detail={detail} definition={definition} />

      {showSepPanel && !showRegistrationSep && (
        <div data-testid="student-quest-sep-payment">
          <SepPaymentPanel
            instanceId={detail.instance_id}
            studentId={studentId}
            amountRial={paymentAmountRial}
            description={resolveSepPaymentDescription(detail)}
          />
        </div>
      )}

      {!done && studentForms.length > 0 && stepFormLocked && (
        <div className="quest-forms-wrap">
          <div className="psf-locked-banner" role="status" style={{
            padding: '1rem 1.25rem', borderRadius: '10px',
            background: 'linear-gradient(135deg, #ecfdf5 0%, #f0fdf4 100%)',
            borderRight: '4px solid #16a34a', fontSize: '0.9rem', lineHeight: 1.7,
          }}>
            اطلاعات این مرحله قبلاً ثبت شده است. برای ویرایش، مسئول مربوط (اداری) باید از پنل کارمندان، امکان ویرایش را برای شما باز کند؛ سپس همین صفحه را تازه کنید.
          </div>
        </div>
      )}
      {!done && studentForms.length > 0 && !stepFormLocked && (
        <div className="quest-forms-wrap">
          <ProcessStepForms
            forms={forms}
            values={stepFormValues || {}}
            onFieldChange={onStepFieldChange}
            disabled={false}
            hasAvailableTransitions={(transitions?.length || 0) > 0}
            instanceId={detail?.instance_id}
            resubmitFieldNames={docsResubmit}
            onRegisterSubmit={onFormRegisterSubmit}
            contextData={detail?.context_data}
          />
          {transitionBlocked && (transitions?.length || 0) > 0 && (
            <p className="quest-block-hint" style={{ marginTop: '0.75rem' }}>
              ابتدا فرم بالا را تکمیل کنید؛ سپس دکمهٔ ثبت مرحله در همین کارت ظاهر می‌شود.
            </p>
          )}
        </div>
      )}

      {!done && showTransitionCta && selectedTransition && (
        <div className="quest-actions">
          <p className="quest-actions-title">قدم بعد در مسیر</p>
          <p className="quest-cta-intro">{STUDENT_TRANSITION_CTA_INTRO}</p>
          {transitionListForCta.length > 1 && (
            <div style={{ marginBottom: '0.85rem' }}>
              <label
                htmlFor="quest-transition-select"
                style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, marginBottom: '0.35rem', color: 'var(--text-secondary)' }}
              >
                انتخاب مسیر بعدی
              </label>
              <select
                id="quest-transition-select"
                data-testid="quest-transition-select"
                className="quest-transition-select"
                value={Math.min(selectedTransitionIdx, transitionListForCta.length - 1)}
                onChange={(e) => setSelectedTransitionIdx(Number(e.target.value))}
                style={{
                  width: '100%',
                  maxWidth: '100%',
                  padding: '0.5rem 0.75rem',
                  borderRadius: '8px',
                  border: '1px solid var(--border)',
                  fontSize: '0.9rem',
                  background: 'var(--bg)',
                }}
              >
                {transitionListForCta.map((t, idx) => (
                  <option key={`${t.trigger_event}-${t.to_state}-${idx}`} value={idx}>
                    {labelState(t.to_state) !== '—' ? labelState(t.to_state) : (t.trigger_event || `مسیر ${idx + 1}`)}
                  </option>
                ))}
              </select>
              <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.78rem', lineHeight: 1.5 }}>
                در صورت چند گزینه، ابتدا مرحلهٔ بعد را انتخاب کنید، سپس دکمهٔ زیر را بزنید.
              </p>
            </div>
          )}
          <p style={{ fontSize: '0.78rem', opacity: 0.88, marginBottom: '0.45rem', fontWeight: 600 }}>
            توضیح همراه اقدام (اختیاری)
          </p>
          <textarea
            value={decisionNotes}
            onChange={e => onDecisionNotesChange(e.target.value)}
            placeholder="در صورت نیاز توضیح کوتاه بنویسید — با همان دکمه ثبت می‌شود."
            className="quest-payload"
            dir="rtl"
          />
          <div className="quest-btn-row">
            <button
              type="button"
              data-testid={`quest-transition-${selectedTransition.to_state || selectedTransition.trigger_event || selectedTransitionIdx}`}
              className="btn quest-cta"
              onClick={() => onTrigger(selectedTransition)}
              title={getStudentTransitionTooltip(selectedTransition)}
            >
              <span className="quest-cta-main">
                {getStudentTransitionButtonMain(selectedTransition, 1)}
              </span>
              {selectedTransition.to_state && (
                <span className="quest-cta-sub">{getStudentTransitionButtonSub(selectedTransition)}</span>
              )}
            </button>
          </div>
        </div>
      )}

      <div className="quest-footer">
        <button
          type="button"
          className="btn btn-outline btn-sm"
          data-testid="student-quest-footer-processes"
          onClick={onOpenProcesses}
        >
          جزئیات کامل در «فرایندها»
        </button>
      </div>
    </div>
  )
}
