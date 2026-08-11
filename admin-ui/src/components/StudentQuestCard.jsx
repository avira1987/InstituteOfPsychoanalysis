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
import { labelRoleFa } from '../utils/roleLabels'
import {
  STUDENT_TRANSITION_CTA_INTRO,
  getStudentTransitionButtonMain,
  getStudentTransitionButtonSub,
  getStudentTransitionTooltip,
} from '../utils/studentTransitionCta'
import { showStudentTransitionCta } from '../utils/studentTransitionCtaVisibility'
import SepPaymentPanel from './SepPaymentPanel'
import StudentSessionPaymentPanel from './StudentSessionPaymentPanel'
import StudentTherapyCompletionPanel from './StudentTherapyCompletionPanel'
import StudentSupervisionBlockTransitionPanel from './StudentSupervisionBlockTransitionPanel'
import StudentEducationalTherapistUpgradePanel from './StudentEducationalTherapistUpgradePanel'
import StudentInternshipReadinessConsultationPanel from './StudentInternshipReadinessConsultationPanel'
import StudentReturnToFullEducationPanel from './StudentReturnToFullEducationPanel'
import StudentFullEducationLeavePanel from './StudentFullEducationLeavePanel'
import StudentUpgradeToTaPanel from './StudentUpgradeToTaPanel'
import StudentTaTrackChangePanel from './StudentTaTrackChangePanel'
import StudentTaToInstructorAutoPanel from './StudentTaToInstructorAutoPanel'
import StudentSupervisionSessionIncreasePanel from './StudentSupervisionSessionIncreasePanel'
import StudentSupervisionSessionReductionPanel from './StudentSupervisionSessionReductionPanel'
import StudentSupervisionInterruptionPanel from './StudentSupervisionInterruptionPanel'
import StudentSupervisionCancellationPanel from './StudentSupervisionCancellationPanel'
import StudentExtraSupervisionSessionPanel from './StudentExtraSupervisionSessionPanel'
import SupervisorSessionCancellationPanel from './SupervisorSessionCancellationPanel'
import StudentComprehensiveTermStartPanel from './StudentComprehensiveTermStartPanel'
import { labelIntroTermEndState } from '../utils/introductoryTermEndDisplay'
import { labelComprehensiveTermEndState } from '../utils/comprehensiveTermEndDisplay'
import StudentClassAttendancePanel from './StudentClassAttendancePanel'
import StudentInstructorEvaluationPanel from './StudentInstructorEvaluationPanel'
import StudentProcessStepReview from './StudentProcessStepReview'
import StudentSmsHistorySection from './StudentSmsHistorySection'

const REGISTRATION_PROCESS_CODES = ['introductory_course_registration', 'comprehensive_course_registration']
const TERM2_REG_CODE = 'intro_second_semester_registration'

function hasRegistrationInterviewBooking(detail) {
  const ctx = detail?.context_data || {}
  return !!(ctx.selected_timeslot || ctx.interview_date)
}

/** نقش‌هایی که «منتظر اقدام همکار» برایشان بلوک جدا می‌گذاریم — نه system */
const STAFF_HUMAN_ROLES = ['interviewer', 'admissions_officer', 'progress_committee', 'supervision_committee']

function resolveSepPaymentDescription(detail) {
  const pc = detail?.process_code
  const cs = detail?.current_state
  if (pc === 'start_therapy' && cs === 'payment_pending') {
    return 'پرداخت هزینه جلسه اول آغاز درمان آموزشی'
  }
  if (pc === 'session_payment') {
    if (cs === 'awaiting_payment') return 'پرداخت جلسات آتی درمان آموزشی'
    if (cs === 'payment_failed') return 'تلاش مجدد پرداخت جلسات آتی درمان آموزشی'
  }
  if (pc === 'extra_session' && cs === 'payment_required') {
    return 'پرداخت جلسه اضافی درمان آموزشی'
  }
  if (pc === 'extra_supervision_session' && cs === 'payment_required') {
    return 'پرداخت جلسه اضافی سوپرویژن'
  }
  if (pc === 'supervisor_session_cancellation' && cs === 'payment_pending') {
    return 'پرداخت جلسه جبرانی سوپرویژن'
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
  if (cs === 'installment_overdue' && pc === 'introductory_course_registration') {
    return 'پرداخت قسط معوق شهریه دوره آشنایی'
  }
  if (pc === TERM2_REG_CODE) {
    if (cs === 'payment_processing') return 'پرداخت شهریه ترم دوم دوره آشنایی'
    if (cs === 'installment_overdue') return 'پرداخت قسط معوق شهریه ترم دوم'
  }
  if (pc === 'supervision_block_transition') {
    if (cs === 'slot_selected') return 'پرداخت جلسه اول دوره سوپرویژن جدید'
    if (cs === 'new_block_first_paid') return 'پرداخت جلسه ۵۰ام دوره سوپرویژن فعلی'
  }
  if (pc === 'return_to_full_education') {
    if (cs === 'therapy_payment_pending') return 'پرداخت جلسه اول درمان آموزشی (بازگشت به کل آموزش)'
    if (cs === 'supervision_payment_pending') return 'پرداخت جلسه اول سوپرویژن (بازگشت به کل آموزش)'
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
  /** وضعیت قفل ثبت‌نام آشنایی (از API) */
  registrationGate = null,
  /** instance فعال پایان ترم (۳۲/۳۶) — جدا از مسیر اصلی */
  termEndDetail = null,
  /** باز کردن پنل پایان ترم در تب فرایندها */
  onOpenTermEnd = null,
  /** در تب پروفایل خلاصهٔ مصاحبه جداگانه نمایش داده می‌شود */
  hidePaidInterviewSummary = false,
  /** هدایت به تب جلسات آنلاین */
  onGoToOnlineSessions = null,
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

  const processCode = definition?.process?.code

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
  const introRegGateClosed =
    detail?.process_code === 'introductory_course_registration' &&
    registrationGate &&
    registrationGate.allowed === false
  const introRegGateReason =
    registrationGate?.reason_fa ||
    'ثبت‌نام دورهٔ آشنایی پس از انتشار تقویم آموزشی باز می‌شود.'
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
    registrationGate,
  })

  const showLegacySep = detail?.current_state === 'awaiting_payment'
    || detail?.current_state === 'payment_pending'
    || (detail?.process_code === 'session_payment' && detail?.current_state === 'payment_failed')
    || (detail?.process_code === 'extra_session' && detail?.current_state === 'payment_required')
    || (detail?.process_code === 'extra_supervision_session' && detail?.current_state === 'payment_required')

  // قبل از paymentMethodChosen — در غیر این صورت TDZ: Cannot access 'ctx'/'me' before initialization
  const ctx = detail?.context_data || {}
  const hasInterviewBooking = hasRegistrationInterviewBooking(detail)
  const tuitionTotalRial = (() => {
    if (ctx.tuition_total_rial != null) return Number(ctx.tuition_total_rial)
    if (ctx.invoice_amount != null) return Math.round(Number(ctx.invoice_amount) * 10)
    if (ctx.payment_amount_rial != null) return Number(ctx.payment_amount_rial)
    return 0
  })()
  const livePaymentMethod = stepFormValues?.payment_method ?? ctx.payment_method
  const liveInstallmentCount = (() => {
    const raw = stepFormValues?.installment_count ?? ctx.installment_count
    try {
      return raw != null && raw !== '' ? parseInt(raw, 10) : null
    } catch {
      return null
    }
  })()
  const paymentAmountRial = (() => {
    const total = tuitionTotalRial
    if (livePaymentMethod === 'installment' && liveInstallmentCount && liveInstallmentCount > 1 && total > 0) {
      return Math.floor(total / liveInstallmentCount)
    }
    if (livePaymentMethod === 'cash' && total > 0) return total
    if (ctx.payable_amount_rial != null) return Number(ctx.payable_amount_rial)
    if (ctx.payment_amount_rial != null) return Number(ctx.payment_amount_rial)
    return total
  })()
  const isInstallmentPayment = livePaymentMethod === 'installment'
    && liveInstallmentCount > 1
    && tuitionTotalRial > 0
    && paymentAmountRial > 0
  const paymentMethodChosen = Boolean(ctx.payment_method)
  const formMatchesRegistered = (() => {
    if (!ctx.payment_method) return false
    const formPm = stepFormValues?.payment_method
    if (formPm != null && formPm !== '' && formPm !== ctx.payment_method) return false
    if (ctx.payment_method === 'installment') {
      const formIc = stepFormValues?.installment_count
      if (formIc != null && formIc !== '' && String(formIc) !== String(ctx.installment_count)) return false
    }
    return true
  })()
  const gatewayReady = paymentMethodChosen && formMatchesRegistered
  const showRegistrationSep = REGISTRATION_PROCESS_CODES.includes(detail?.process_code)
    && (
      detail?.current_state === 'interview_payment'
      || detail?.current_state === 'installment_overdue'
      || (detail?.current_state === 'payment' && gatewayReady)
      || (detail?.current_state === 'interview_scheduled' && hasInterviewBooking)
    )

  const showIntro2Sep = detail?.process_code === TERM2_REG_CODE
    && (
      detail?.current_state === 'installment_overdue'
      || (detail?.current_state === 'payment_processing' && gatewayReady)
    )

  const showSupervisionBlockSep = detail?.process_code === 'supervision_block_transition'
    && (detail?.current_state === 'slot_selected' || detail?.current_state === 'new_block_first_paid')

  const compTermStartSepInPanel = detail?.process_code === 'comprehensive_term_start'
    && detail?.current_state === 'payment_processing'

  const showSepPanel = !done && studentId && detail?.instance_id
    && !compTermStartSepInPanel
    && (showLegacySep || showRegistrationSep || showIntro2Sep || showSupervisionBlockSep)

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
  }) && !introRegGateClosed

  const selectedTransition = transitionListForCta[selectedTransitionIdx] ?? transitionListForCta[0]

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

  const showInterviewPaidSummary = !hidePaidInterviewSummary
    && !done
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

      {introRegGateClosed && !done && (
        <div
          className="quest-staff-wait"
          role="status"
          data-testid="student-quest-intro-gate-closed"
          style={{
            marginTop: '0.85rem',
            padding: '1rem 1.25rem',
            borderRadius: '10px',
            background: '#fffbeb',
            borderRight: '4px solid #d97706',
            fontSize: '0.9rem',
            lineHeight: 1.75,
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: '0.35rem' }}>ثبت‌نام موقتاً متوقف است</div>
          <p style={{ margin: 0 }}>{introRegGateReason}</p>
        </div>
      )}

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
            color: '#0f172a',
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: '0.35rem', color: '#0f172a' }}>اطلاعات ورود به پرتال دانشجویی (LMS)</div>
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
                {labelRoleFa(assignRole)}
                )
              </span>
            )}
          </div>
          <p>
            {staffDepFa
              || 'این مرحله توسط مرکز در حال پیگیری است؛ پس از به‌روزرسانی وضعیت، همین صفحه را تازه کنید. جزئیات در بخش «اقدام بعدی شما» بالاتر آمده است.'}
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
        <InterviewPaidBookingSummary onGoToOnlineSessions={onGoToOnlineSessions} />
      )}

      {!done && detail?.process_code === 'session_payment'
        && ['payment_due', 'payment_selection', 'awaiting_payment', 'payment_failed'].includes(detail?.current_state) && (
        <StudentSessionPaymentPanel
          detail={detail}
          stepFormValues={stepFormValues}
          compact
        />
      )}

      {!done && detail?.process_code === 'therapy_completion' && (
        <StudentTherapyCompletionPanel detail={detail} compact />
      )}

      {!done && detail?.process_code === 'supervision_block_transition' && (
        <StudentSupervisionBlockTransitionPanel
          detail={detail}
          stepFormValues={stepFormValues}
          extraData={extraData}
          compact
        />
      )}

      {!done && detail?.process_code === 'internship_readiness_consultation' && (
        <StudentInternshipReadinessConsultationPanel
          detail={detail}
          studentProfile={studentId ? { id: studentId, extra_data: extraData } : null}
          compact
        />
      )}

      {!done && detail?.process_code === 'upgrade_to_educational_therapist' && (
        <StudentEducationalTherapistUpgradePanel detail={detail} compact />
      )}

      {!done && detail?.process_code === 'return_to_full_education' && (
        <StudentReturnToFullEducationPanel
          detail={detail}
          studentProfile={studentId ? { id: studentId, extra_data: extraData } : null}
          compact
        />
      )}

      {!done && detail?.process_code === 'full_education_leave' && (
        <StudentFullEducationLeavePanel detail={detail} compact />
      )}

      {detail?.process_code === 'full_education_leave' && (() => {
        const reason = (detail?.context_data?.rejection_reason_fa || '').trim()
        const showRejected = detail?.current_state === 'leave_rejected' || (detail?.is_completed && reason)
        if (!showRejected || !reason) return null
        return (
          <div
            className="quest-leave-rejected"
            style={{
              marginTop: '0.75rem', padding: '0.85rem 1rem', borderRadius: '10px',
              background: 'linear-gradient(135deg, #fef2f2 0%, #fff7ed 100%)',
              borderRight: '4px solid #dc2626', fontSize: '0.86rem', lineHeight: 1.75,
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#991b1b' }}>شرح توافقات / علت رد مرخصی</div>
            <p style={{ margin: 0, color: '#7f1d1d' }}>{reason}</p>
          </div>
        )
      })()}

      {!done && detail?.process_code === 'full_education_leave' && (() => {
        const c = detail?.context_data || {}
        const fmt = (s) => {
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
            <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#1e3a8a' }}>جزئیات مرخصی از کل آموزش</div>
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
                <strong>بازگشت به آموزش:</strong>
                {c.return_reminder_at ? ` یادآوری حدود ${fmt(c.return_reminder_at)}` : ''}
                {c.return_deadline_at ? ` — مهلت بازگشت: ${fmt(c.return_deadline_at)}` : ''}
              </div>
            )}
          </div>
        )
      })()}

      {!done && detail?.process_code === 'upgrade_to_ta' && (
        <StudentUpgradeToTaPanel detail={detail} compact />
      )}

      {!done && detail?.process_code === 'ta_track_change' && (
        <StudentTaTrackChangePanel detail={detail} studentProfile={studentProfile} compact />
      )}

      {detail?.process_code === 'ta_to_instructor_auto' && (
        <StudentTaToInstructorAutoPanel detail={detail} extraData={extraData} compact />
      )}

      {!done && detail?.process_code === 'supervision_session_increase' && (
        <StudentSupervisionSessionIncreasePanel
          detail={detail}
          stepFormValues={stepFormValues}
          compact
        />
      )}

      {!done && detail?.process_code === 'supervision_session_reduction' && (
        <StudentSupervisionSessionReductionPanel
          detail={detail}
          stepFormValues={stepFormValues}
          compact
        />
      )}

      {!done && detail?.process_code === 'supervision_interruption' && (
        <StudentSupervisionInterruptionPanel
          detail={detail}
          stepFormValues={stepFormValues}
          compact
        />
      )}

      {!done && detail?.process_code === 'student_supervision_cancellation' && (
        <StudentSupervisionCancellationPanel
          detail={detail}
          stepFormValues={stepFormValues}
          compact
        />
      )}

      {!done && detail?.process_code === 'supervisor_session_cancellation' && (
        <SupervisorSessionCancellationPanel
          detail={detail}
          stepFormValues={stepFormValues}
          compact
          portalRole="student"
        />
      )}

      {!done && detail?.process_code === 'extra_supervision_session' && (
        <StudentExtraSupervisionSessionPanel
          detail={detail}
          stepFormValues={stepFormValues}
          compact
        />
      )}

      {detail?.process_code === 'comprehensive_term_start' && (
        <StudentComprehensiveTermStartPanel
          detail={detail}
          studentProfile={studentId ? { id: studentId } : null}
          stepFormValues={stepFormValues}
          active
          compact
        />
      )}

      {termEndDetail
        && detail?.process_code !== 'introductory_term_end'
        && detail?.process_code !== 'comprehensive_term_end' && (
        <div
          data-testid="quest-term-end-block"
          style={{
            marginTop: '0.75rem',
            padding: '0.85rem 1rem',
            borderRadius: '10px',
            background: '#f0f9ff',
            borderRight: '4px solid #0284c7',
          }}
        >
          <div style={{ fontWeight: 700, fontSize: '0.88rem', marginBottom: '0.35rem', color: '#0c4a6e' }}>
            {termEndDetail.process_code === 'introductory_term_end'
              ? 'پایان ترم دوره آشنایی'
              : 'پایان ترم دوره جامع'}
          </div>
          <p style={{ margin: '0 0 0.5rem', fontSize: '0.84rem', color: '#0369a1', lineHeight: 1.65 }}>
            {termEndDetail.process_code === 'introductory_term_end'
              ? labelIntroTermEndState(termEndDetail.current_state)
              : labelComprehensiveTermEndState(termEndDetail.current_state)}
          </p>
          {typeof onOpenTermEnd === 'function' && (
            <button
              type="button"
              className="btn btn-sm btn-outline"
              data-testid="quest-term-end-open"
              onClick={() => onOpenTermEnd(termEndDetail.instance_id)}
            >
              مشاهده کارنامه و وضعیت
            </button>
          )}
        </div>
      )}

      {detail?.process_code === 'class_attendance' && (
        <StudentClassAttendancePanel
          detail={detail}
          studentProfile={studentId ? { id: studentId, extra_data: extraData } : null}
          active
          compact
        />
      )}

      {detail?.process_code === 'student_instructor_evaluation' && (
        <StudentInstructorEvaluationPanel
          detail={detail}
          instanceId={instanceId}
          studentProfile={studentId ? { id: studentId, extra_data: extraData } : null}
          active
          compact
        />
      )}

      {detail?.process_code === 'educational_leave' && (() => {
        const reason = (detail?.context_data?.rejection_reason_fa || '').trim()
        const showRejected = detail?.current_state === 'rejected' || (detail?.is_completed && reason)
        if (!showRejected || !reason) return null
        return (
          <div
            className="quest-leave-rejected"
            style={{
              marginTop: '0.75rem', padding: '0.85rem 1rem', borderRadius: '10px',
              background: 'linear-gradient(135deg, #fef2f2 0%, #fff7ed 100%)',
              borderRight: '4px solid #dc2626', fontSize: '0.86rem', lineHeight: 1.75,
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#991b1b' }}>علت رد درخواست مرخصی</div>
            <p style={{ margin: 0, color: '#7f1d1d' }}>{reason}</p>
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

        const rows = [
          { key: 'therapy', label: 'درمان آموزشی', hours: th, threshold: tt, color: '#a21caf' },
          { key: 'clinical', label: 'تجربه بالینی', hours: ch, threshold: ct, color: '#0ea5e9' },
          { key: 'supervision', label: 'سوپرویژن', hours: sh, threshold: st, color: '#f59e0b' },
        ].filter(r => r.hours != null && r.threshold != null)

        const evaluable = rows.filter(r => r.threshold > 0)
        const allMet = evaluable.length > 0 && evaluable.every(r => r.hours >= r.threshold)
        const unmet = evaluable.filter(r => r.hours < r.threshold)

        return (
          <div
            className="quest-therapy-completion-preview"
            data-testid="student-quest-therapy-completion-preview"
            style={{
              marginTop: '0.75rem', padding: '0.85rem 1rem', borderRadius: '10px',
              background: 'linear-gradient(135deg, #fdf4ff 0%, #f8fafc 100%)',
              borderRight: '4px solid #a21caf', fontSize: '0.86rem', lineHeight: 1.75,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', marginBottom: '0.5rem' }}>
              <span style={{ fontWeight: 700, color: '#701a75' }}>ایست بازرسی ساعات (خاتمه درمان)</span>
              {evaluable.length > 0 && (
                <span
                  data-testid="student-quest-therapy-completion-status"
                  style={{
                    fontSize: '0.74rem', fontWeight: 700, padding: '0.15rem 0.6rem', borderRadius: '999px',
                    background: allMet ? '#dcfce7' : '#fef3c7',
                    color: allMet ? '#166534' : '#92400e',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {allMet ? 'همهٔ شرایط احراز شد' : 'شرایط هنوز کامل نیست'}
                </span>
              )}
            </div>

            <div style={{ display: 'grid', gap: '0.6rem' }}>
              {rows.map((r) => {
                const pct = r.threshold > 0
                  ? Math.min(100, Math.round((r.hours / r.threshold) * 100))
                  : 100
                const met = r.threshold <= 0 || r.hours >= r.threshold
                const remaining = Math.max(0, r.threshold - r.hours)
                return (
                  <div key={r.key} data-testid={`student-quest-therapy-row-${r.key}`}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '0.5rem', fontSize: '0.82rem' }}>
                      <span>
                        <strong>{r.label}</strong>
                        {met
                          ? <span style={{ color: '#16a34a', marginInlineStart: '0.4rem' }}>✓ احراز شد</span>
                          : <span style={{ color: '#b45309', marginInlineStart: '0.4rem' }}>{remaining.toLocaleString('fa-IR')} ساعت مانده</span>}
                      </span>
                      <span dir="ltr" style={{ fontVariantNumeric: 'tabular-nums', color: '#475569' }}>
                        {r.hours.toLocaleString('fa-IR')} / {r.threshold.toLocaleString('fa-IR')}
                      </span>
                    </div>
                    <div
                      style={{
                        marginTop: '0.25rem', height: '7px', borderRadius: '999px',
                        background: '#e2e8f0', overflow: 'hidden',
                      }}
                      role="progressbar"
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={pct}
                      aria-label={`${r.label}: ${pct}%`}
                    >
                      <div style={{ width: `${pct}%`, height: '100%', background: met ? '#16a34a' : r.color, transition: 'width 0.4s ease' }} />
                    </div>
                  </div>
                )
              })}
            </div>

            <div
              data-testid="student-quest-therapy-completion-hint"
              style={{
                marginTop: '0.7rem', padding: '0.55rem 0.7rem', borderRadius: '8px', fontSize: '0.8rem',
                background: allMet ? '#f0fdf4' : '#fffbeb',
                color: allMet ? '#166534' : '#92400e',
              }}
            >
              {allMet
                ? 'همهٔ حدنصاب‌ها کامل است. با زدن دکمهٔ «ادامه و ثبت مرحله»، خاتمهٔ رسمی درمان آموزشی ثبت و جلسات آتی لغو می‌شود.'
                : `با زدن دکمهٔ ادامه در وضعیت فعلی، نتیجه «شرایط احراز نشده» ثبت می‌شود. ${unmet.length ? `ابتدا ${unmet.map(r => r.label).join('، ')} را تکمیل کنید.` : ''}`}
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

      {!done && detail?.process_code === 'student_session_cancellation' && (() => {
        const c = detail?.context_data || {}
        const pct = c.cancellation_percent_now != null ? Number(c.cancellation_percent_now) : null
        const upcoming = Array.isArray(c.upcoming_cancellation_sessions)
          ? c.upcoming_cancellation_sessions.length
          : null
        if (pct == null && upcoming == null) return null
        return (
          <div
            className="quest-session-cancellation-preview"
            style={{
              marginTop: '0.75rem', padding: '0.85rem 1rem', borderRadius: '10px',
              background: 'linear-gradient(135deg, #fef2f2 0%, #f8fafc 100%)',
              borderRight: '4px solid #dc2626', fontSize: '0.86rem', lineHeight: 1.75,
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#991b1b' }}>
              کنسل جلسات درمان (فرایند ۱۷)
            </div>
            {pct != null && (
              <div style={{ marginBottom: '0.25rem' }}>
                <strong>درصد کنسلی فعلی:</strong>
                {' '}
                {pct.toLocaleString('fa-IR')}٪
                {pct >= 10 ? ' — نزدیک سقف ۱۲٪' : ''}
              </div>
            )}
            {upcoming != null && (
              <div>
                <strong>جلسات ۳ هفتهٔ آینده:</strong>
                {' '}
                {upcoming.toLocaleString('fa-IR')}
                {' '}
                جلسه
              </div>
            )}
          </div>
        )
      })()}

      {!done && detail?.process_code === 'student_supervision_cancellation' && (() => {
        const c = detail?.context_data || {}
        const pct = c.cancellation_percent_now != null ? Number(c.cancellation_percent_now) : null
        const upcoming = Array.isArray(c.upcoming_cancellation_sessions)
          ? c.upcoming_cancellation_sessions.length
          : null
        if (pct == null && upcoming == null) return null
        return (
          <div
            className="quest-supervision-cancellation-preview"
            style={{
              marginTop: '0.75rem', padding: '0.85rem 1rem', borderRadius: '10px',
              background: 'linear-gradient(135deg, #f0fdfa 0%, #f8fafc 100%)',
              borderRight: '4px solid #0d9488', fontSize: '0.86rem', lineHeight: 1.75,
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#115e59' }}>
              کنسل جلسات سوپرویژن (فرایند ۲۵)
            </div>
            {pct != null && (
              <div style={{ marginBottom: '0.25rem' }}>
                <strong>درصد کنسلی فعلی:</strong>
                {' '}
                {pct.toLocaleString('fa-IR')}٪
                {pct >= 10 ? ' — نزدیک سقف ۱۲٪' : ''}
              </div>
            )}
            {upcoming != null && (
              <div>
                <strong>جلسات ۳ هفتهٔ آینده:</strong>
                {' '}
                {upcoming.toLocaleString('fa-IR')}
                {' '}
                جلسه
              </div>
            )}
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

      {done && detail?.process_code === 'start_therapy' && (
        <div
          data-testid="start-therapy-next-step-card"
          style={{
            marginTop: '0.75rem', padding: '0.85rem 1rem', borderRadius: '10px',
            background: 'linear-gradient(135deg, #ecfdf5 0%, #f8fafc 100%)',
            borderRight: '4px solid #059669', fontSize: '0.86rem', lineHeight: 1.75,
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#065f46' }}>گام بعدی مسیر شما</div>
          <p style={{ margin: 0 }}>
            {(detail?.context_data?.start_therapy_next_step_fa || '').trim()
              || 'درمان آموزشی فعال شد. گام بعدی: پرداخت جلسات آتی — داشبورد را تازه کنید تا مسیر اصلی به‌روز شود.'}
          </p>
          {extraData?.primary_instance_id && String(extraData.primary_instance_id) !== String(detail?.instance_id) && (
            <p style={{ margin: '0.5rem 0 0', fontSize: '0.82rem', color: '#64748b' }}>
              مسیر اصلی پرتال به فرایند بعدی منتقل شده است؛ داشبورد را تازه کنید.
            </p>
          )}
        </div>
      )}

      {done && detail?.process_code === 'session_payment' && (
        <div
          data-testid="session-payment-next-step-card"
          style={{
            marginTop: '0.75rem', padding: '0.85rem 1rem', borderRadius: '10px',
            background: 'linear-gradient(135deg, #ecfdf5 0%, #f8fafc 100%)',
            borderRight: '4px solid #059669', fontSize: '0.86rem', lineHeight: 1.75,
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#065f46' }}>گام بعدی مسیر شما</div>
          <p style={{ margin: 0 }}>
            {(detail?.context_data?.session_payment_next_step_fa || extraData?.dashboard_therapy_hint_fa || '').trim()
              || 'پرداخت جلسات ثبت شد. برای شرکت در جلسات به تب «جلسات آنلاین» بروید.'}
          </p>
          {onGoToOnlineSessions && (
            <button
              type="button"
              className="btn btn-outline btn-sm"
              style={{ marginTop: '0.5rem' }}
              onClick={onGoToOnlineSessions}
            >
              رفتن به جلسات آنلاین
            </button>
          )}
        </div>
      )}

      {done && detail?.process_code === 'introductory_course_registration' && (
        <div
          data-testid="intro-reg-next-step-card"
          style={{
            marginTop: '0.75rem', padding: '0.85rem 1rem', borderRadius: '10px',
            background: 'linear-gradient(135deg, #ecfdf5 0%, #f8fafc 100%)',
            borderRight: '4px solid #059669', fontSize: '0.86rem', lineHeight: 1.75,
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#065f46' }}>گام بعدی مسیر شما</div>
          <p style={{ margin: 0 }}>
            {(detail?.context_data?.intro_registration_next_step_fa || '').trim()
              || 'ثبت‌نام دوره آشنایی تکمیل شد. گام بعدی: آغاز درمان آموزشی — داشبورد را تازه کنید تا مسیر اصلی به‌روز شود.'}
          </p>
          {extraData?.primary_instance_id && String(extraData.primary_instance_id) !== String(detail?.instance_id) && (
            <p style={{ margin: '0.5rem 0 0', fontSize: '0.82rem', color: '#64748b' }}>
              مسیر اصلی پرتال به فرایند بعدی منتقل شده است؛ داشبورد را تازه کنید.
            </p>
          )}
        </div>
      )}

      {done && detail?.process_code === 'comprehensive_course_registration' && (
        <div
          data-testid="comp-reg-next-step-card"
          style={{
            marginTop: '0.75rem', padding: '0.85rem 1rem', borderRadius: '10px',
            background: 'linear-gradient(135deg, #ecfdf5 0%, #f8fafc 100%)',
            borderRight: '4px solid #059669', fontSize: '0.86rem', lineHeight: 1.75,
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#065f46' }}>گام بعدی مسیر شما</div>
          <p style={{ margin: 0 }}>
            ثبت‌نام دوره جامع تکمیل شد. کلاس‌ها و لینک‌های آنلاین در پنل آموزش برای شما فعال می‌شود؛ ادامهٔ مسیر از همان بخش‌هاست.
          </p>
        </div>
      )}

      {detail?.process_code === TERM2_REG_CODE
        && ['registration_complete', 'term2_registration_closed'].includes(detail?.current_state) && (
        <div
          data-testid="intro2-reg-next-step-card"
          style={{
            marginTop: '0.75rem', padding: '0.85rem 1rem', borderRadius: '10px',
            background: 'linear-gradient(135deg, #ecfdf5 0%, #f8fafc 100%)',
            borderRight: '4px solid #059669', fontSize: '0.86rem', lineHeight: 1.75,
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#065f46' }}>گام بعدی مسیر شما</div>
          <p style={{ margin: 0 }}>
            {detail?.current_state === 'term2_registration_closed'
              ? 'ثبت‌نام ترم دوم و تسویهٔ مالی کامل شد؛ دروس و لینک‌های کلاس در پنل آموزش در دسترس است.'
              : 'ثبت‌نام ترم دوم تکمیل شد؛ لینک کلاس فعال است. اگر اقساطی پرداخت کردید، اقساط بعدی را در سررسید از همین پرتال بپردازید.'}
          </p>
        </div>
      )}

      {done && detail?.process_code === 'ta_track_completion' && (
        <div
          style={{
            marginTop: '0.75rem', padding: '0.85rem 1rem', borderRadius: '10px',
            background: 'linear-gradient(135deg, #ecfdf5 0%, #eff6ff 100%)',
            borderRight: '4px solid #2563eb', fontSize: '0.86rem', lineHeight: 1.75,
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: '0.35rem', color: '#1e40af' }}>
            تبریک — خاتمه رسته کمک‌مدرسی
          </div>
          <p style={{ margin: 0 }}>
            تمام دروس رسته
            {detail?.context_data?.track_name_fa ? ` «${detail.context_data.track_name_fa}»` : ''}
            {' '}
            با موفقیت به‌عنوان کمک‌مدرس طی شد. جزئیات در بخش «پرونده کمک‌مدرسی» پروفایل شما به‌روز شده است.
          </p>
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

      <StudentSmsHistorySection refreshKey={smsRefreshKey ?? `${detail?.instance_id || ''}-${detail?.current_state || ''}`} />

      <StudentProcessStepReview detail={detail} definition={definition} />

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
            currentState={detail?.current_state}
          />
          {transitionBlocked && (transitions?.length || 0) > 0 && (
            <p className="quest-block-hint" style={{ marginTop: '0.75rem' }}>
              ابتدا فرم بالا را تکمیل کنید؛ سپس دکمهٔ ثبت مرحله در همین کارت ظاهر می‌شود.
            </p>
          )}
        </div>
      )}

      {(showRegistrationSep || showIntro2Sep || (detail?.current_state === 'payment' && livePaymentMethod)) && (
        <div data-testid="student-quest-sep-payment" style={{ marginTop: '0.85rem' }}>
          {detail?.current_state === 'payment' && !paymentMethodChosen && (
            <p
              style={{
                margin: '0 0 0.5rem',
                padding: '0.75rem 1rem',
                borderRadius: '8px',
                background: '#eff6ff',
                borderRight: '4px solid #2563eb',
                fontSize: '0.86rem',
                lineHeight: 1.7,
                color: '#1e3a8a',
              }}
            >
              ابتدا روش پرداخت (نقدی یا اقساطی) را در فرم بالا انتخاب و ثبت کنید؛ سپس درگاه پرداخت آنلاین فعال می‌شود.
            </p>
          )}
          {detail?.current_state === 'payment' && paymentMethodChosen && !formMatchesRegistered && (
            <p
              style={{
                margin: '0 0 0.5rem',
                padding: '0.75rem 1rem',
                borderRadius: '8px',
                background: '#fffbeb',
                borderRight: '4px solid #d97706',
                fontSize: '0.86rem',
                lineHeight: 1.7,
                color: '#92400e',
              }}
            >
              انتخاب شما تغییر کرد. دوباره دکمهٔ ثبت فرم را بزنید تا مبلغ درگاه به‌روز شود؛ تا آن زمان درگاه غیرفعال است.
            </p>
          )}
          {(isInstallmentPayment || (livePaymentMethod === 'installment' && liveInstallmentCount > 1)) && tuitionTotalRial > 0 && (
            <p style={{ margin: '0 0 0.5rem', fontSize: '0.86rem', color: '#1e3a8a', lineHeight: 1.7 }}>
              شهریه کل: {Math.round(tuitionTotalRial / 10).toLocaleString('fa-IR')} تومان
              {' · '}
              {liveInstallmentCount > 1
                ? `${Number(liveInstallmentCount).toLocaleString('fa-IR')} قسط — مبلغ هر قسط (قسط اول): `
                : 'مبلغ قابل پرداخت: '}
              <strong>{Math.round(paymentAmountRial / 10).toLocaleString('fa-IR')} تومان</strong>
            </p>
          )}
          {livePaymentMethod === 'cash' && tuitionTotalRial > 0 && (
            <p style={{ margin: '0 0 0.5rem', fontSize: '0.86rem', color: '#1e3a8a', lineHeight: 1.7 }}>
              پرداخت نقدی — مبلغ کل:{' '}
              <strong>{Math.round(tuitionTotalRial / 10).toLocaleString('fa-IR')} تومان</strong>
            </p>
          )}
          {(
            detail?.current_state === 'installment_overdue'
            || detail?.current_state === 'interview_payment'
            || (detail?.current_state === 'interview_scheduled' && hasInterviewBooking)
            || gatewayReady
          ) && (
            <SepPaymentPanel
              instanceId={detail.instance_id}
              studentId={studentId}
              amountRial={
                detail?.current_state === 'payment' || detail?.current_state === 'payment_processing'
                  ? (ctx.payable_amount_rial != null ? Number(ctx.payable_amount_rial) : paymentAmountRial)
                  : (ctx.payable_amount_rial != null
                    ? Number(ctx.payable_amount_rial)
                    : (ctx.payment_amount_rial != null
                      ? Number(ctx.payment_amount_rial)
                      : paymentAmountRial))
              }
              description={resolveSepPaymentDescription(detail)}
            />
          )}
        </div>
      )}

      {showSepPanel && !showRegistrationSep && !showIntro2Sep && (
        <div data-testid="student-quest-sep-payment" style={{ marginTop: '0.85rem' }}>
          <SepPaymentPanel
            instanceId={detail.instance_id}
            studentId={studentId}
            amountRial={paymentAmountRial}
            description={resolveSepPaymentDescription(detail)}
          />
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
