import React, { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { usePortalInstanceDeepLink } from '../hooks/usePortalInstanceDeepLink'
import { useProcessCodeUrlFilter } from '../hooks/useProcessCodeUrlFilter'
import { processExecApi, studentApi, panelApi } from '../services/api'
import { labelProcess, labelState, formatStudentCodeDisplay } from '../utils/processDisplay'
import { notesPayload } from '../utils/decisionPayload'
import { mergeInterviewBranchPayload } from '../utils/transitionInterviewPayload'
import { isDocumentReviewState } from '../utils/documentReviewStates'
import {
  isComprehensiveEvalTrigger,
  validateInterviewEvaluationForm,
  mergeInterviewEvaluationPayload,
} from '../utils/interviewEvaluationPayload'
import {
  canSubmitInterviewResult,
  filterInterviewResultTransitions,
} from '../utils/interviewResultAccess'
import InstanceContextSummary from '../components/InstanceContextSummary'
import DecisionNotesBlock from '../components/DecisionNotesBlock'
import { useToast } from '../contexts/ToastContext'
import ProcessRollbackSection from '../components/ProcessRollbackSection'
import ProcessRestartSection from '../components/ProcessRestartSection'
import OperatorPortalReminderBanner from '../components/OperatorPortalReminderBanner'
import OperatorFollowupSection from '../components/OperatorFollowupSection'
import ResolvedProcessHistoryBanner from '../components/ResolvedProcessHistoryBanner'
import OperatorStepFormsSection from '../components/OperatorStepFormsSection'
import OperatorInstanceGuidanceBlock from '../components/OperatorInstanceGuidanceBlock'
import { mergeEducationalLeaveTriggerPayload } from '../utils/educationalLeaveTriggerPayload'
import { mergeFullEducationLeaveTriggerPayload } from '../utils/fullEducationLeaveTriggerPayload'
import { mergeCommitteesReviewTriggerPayload } from '../utils/committeesReviewTriggerPayload'
import { mergeCommissionReviewTriggerPayload } from '../utils/commissionReviewTriggerPayload'
import CommitteesReviewPanel from '../components/CommitteesReviewPanel'
import UnannouncedAbsenceReactionPanel from '../components/UnannouncedAbsenceReactionPanel'
import UnannouncedSupervisionAbsenceReactionPanel from '../components/UnannouncedSupervisionAbsenceReactionPanel'
import SpecializedCommissionReviewPanel from '../components/SpecializedCommissionReviewPanel'
import IntroductoryCourseCompletionReviewPanel from '../components/IntroductoryCourseCompletionReviewPanel'
import TaToInstructorAutoReportPanel from '../components/TaToInstructorAutoReportPanel'
import InternHoursIncreasePanel from '../components/InternHoursIncreasePanel'
import StudentNonRegistrationReviewPanel from '../components/StudentNonRegistrationReviewPanel'
import FullEducationLeaveCommitteeReviewPanel from '../components/FullEducationLeaveCommitteeReviewPanel'
import ViolationRegistrationReviewPanel from '../components/ViolationRegistrationReviewPanel'
import InstructorClassSessionCancellationPanel from '../components/InstructorClassSessionCancellationPanel'
import ThesisDefenseProgressReviewPanel from '../components/ThesisDefenseProgressReviewPanel'
import ThesisDefenseSupervisionReviewPanel from '../components/ThesisDefenseSupervisionReviewPanel'
import ThesisDefenseEducationSchedulePanel from '../components/ThesisDefenseEducationSchedulePanel'
import EducationalTherapistMonitoringReviewPanel from '../components/EducationalTherapistMonitoringReviewPanel'
import EducationalTherapistInterviewPanel from '../components/EducationalTherapistInterviewPanel'
import EducationalTherapistTherapistReviewPanel from '../components/EducationalTherapistTherapistReviewPanel'
import TaToAssistantFacultyReviewPanel from '../components/TaToAssistantFacultyReviewPanel'
import TaUpgradeSupervisionReviewPanel from '../components/TaUpgradeSupervisionReviewPanel'
import { mergeEducationalTherapistUpgradeTriggerPayload } from '../utils/educationalTherapistUpgradeTriggerPayload'
import { mergeTaToAssistantFacultyTriggerPayload } from '../utils/taToAssistantFacultyTriggerPayload'
import { mergeUpgradeToTaTriggerPayload } from '../utils/upgradeToTaTriggerPayload'
import { mergeTaTrackChangeTriggerPayload } from '../utils/taTrackChangeTriggerPayload'
import TaTrackChangeCommitteePanel from '../components/TaTrackChangeCommitteePanel'
import TaTrackCompletionInstancePanel from '../components/TaTrackCompletionInstancePanel'
import InternBulkPatientReferralSupervisionPanel from '../components/InternBulkPatientReferralSupervisionPanel'
import InternBulkPatientReferralTherapyCommitteePanel from '../components/InternBulkPatientReferralTherapyCommitteePanel'
import { mergeNonRegistrationTriggerPayload } from '../utils/nonRegistrationTriggerPayload'
import { mergeReferralTriggerPayload } from '../utils/internBulkPatientReferralTriggerPayload'
import {
  COMMITTEE_DEEP_LINK_TABS,
  COMMITTEE_DEFAULT_CONFIG,
  getCommitteeKindConfig,
  getCommitteeKindPath,
  getCommitteeRoleConfig,
} from '../utils/portalCommitteeKinds'
import { SEMESTER_PREP_PROCESSES } from '../utils/instituteProcesses'
import { mergeProcessInboxIntoPending } from '../utils/mergeProcessInboxPending'
import {
  getPendingTaskDestination,
  isSemesterPrepWorkbenchDestination,
  resolvePendingInstanceId,
} from '../utils/operatorFollowupDeepLinks'

const DEPUTY_SEMESTER_PREP_STATES = new Set([
  'tuition_entry',
  'license_check',
  'interviewer_assignment',
])

export default function CommitteePortal() {
  const { kind: kindParam } = useParams()
  const navigate = useNavigate()
  const kind = kindParam || 'progress'
  const kindMeta = getCommitteeKindConfig(kind)
  const portalPath = getCommitteeKindPath(kind)
  const { user } = useAuth()
  const config = getCommitteeRoleConfig(user?.role) || COMMITTEE_DEFAULT_CONFIG
  const [activeTab, setActiveTab] = useState('reviews')
  const [allStudents, setAllStudents] = useState([])
  const [pendingReviews, setPendingReviews] = useState([])
  const [allActiveInstances, setAllActiveInstances] = useState([])
  const [selectedInstance, setSelectedInstance] = useState(null)
  const [instanceDetail, setInstanceDetail] = useState(null)
  const [availableTransitions, setAvailableTransitions] = useState([])
  const [decisionNotes, setDecisionNotes] = useState('')
  const [loading, setLoading] = useState(true)
  const [rollbackBusy, setRollbackBusy] = useState(false)
  const [restartBusy, setRestartBusy] = useState(false)
  const [operatorFollowupItems, setOperatorFollowupItems] = useState([])
  const [operatorReadinessAlerts, setOperatorReadinessAlerts] = useState([])
  /** فرم ارزیابی مصاحبهٔ ورود به دوره جامع (محرمانه) — همراه تریگر نتیجه ارسال می‌شود */
  const [interviewEval, setInterviewEval] = useState({
    evaluation_notes: '',
    rejection_reason: '',
    suggestion_text: '',
  })
  const { showToast } = useToast()

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    try {
      const [studentsRes, followupRes] = await Promise.all([
        studentApi.list().catch(() => ({ data: [] })),
        panelApi.myOperatorFollowup().catch(() => ({ data: {} })),
      ])
      const students = studentsRes.data || []
      setAllStudents(students)
      setOperatorFollowupItems(followupRes.data?.items || [])
      setOperatorReadinessAlerts(followupRes.data?.readiness_alerts || [])

      const pending = []
      const allActive = []
      for (const s of students) {
        try {
          const instRes = await processExecApi.studentInstances(s.id)
          const instances = instRes.data?.instances || []
          for (const inst of instances) {
            if (!inst.is_completed && !inst.is_cancelled) {
              // مراحل بررسی/تکمیل مدارک مخصوص پنل کارمند است و در پنل‌های کمیته نمایش داده نمی‌شود.
              if (isDocumentReviewState(inst.current_state)) continue
              const enriched = { ...inst, student_code: s.student_code, student_id: s.id }
              allActive.push(enriched)
              if (isWaitingForReview(inst.current_state, inst.process_code)) {
                pending.push(enriched)
              }
            }
          }
        } catch { /* skip */ }
      }
      const followupItems = followupRes.data?.items || []
      setPendingReviews(mergeProcessInboxIntoPending(followupItems, pending))
      setAllActiveInstances(allActive)
    } catch (err) {
      console.error('Load error:', err)
    } finally {
      setLoading(false)
    }
  }

  const openPendingReview = (task) => {
    const dest = getPendingTaskDestination(task)
    if (isSemesterPrepWorkbenchDestination(dest.href)) {
      navigate(dest.href)
      return
    }
    const instanceId = resolvePendingInstanceId(task)
    if (instanceId) {
      viewInstance(instanceId)
      setActiveTab('reviews')
    }
  }

  const isWaitingForReview = (state, processCode) => {
    if (!state) return false
    if (
      SEMESTER_PREP_PROCESSES.has(processCode)
      && user?.role === 'deputy_education'
      && DEPUTY_SEMESTER_PREP_STATES.has(state)
    ) {
      return true
    }
    if (
      processCode === 'committees_review'
      && (state === 'supervision_review' || state === 'education_review')
    ) {
      const kindRoles = kindMeta?.portalRoles || []
      if (user?.role === 'admin' || kindRoles.includes(user?.role)) return true
      if (user?.role === 'supervision_committee' && state === 'supervision_review') return true
      if (user?.role === 'education_committee' && state === 'education_review') return true
      if (user?.role === 'deputy_education' && state === 'education_review') return true
      return false
    }
    if (processCode === 'specialized_commission_review' && state === 'commission_review') {
      if (user?.role === 'specialized_commission' || user?.role === 'admin') return true
      return false
    }
    if (
      processCode === 'unannounced_absence_reaction'
      && state === 'committee_pending'
    ) {
      if (user?.role === 'therapy_committee_chair' || user?.role === 'admin') return true
      return false
    }
    if (
      processCode === 'introductory_course_completion'
      && state === 'certificate_review'
    ) {
      const kindRoles = kindMeta?.portalRoles || []
      return user?.role === 'admin' || kindRoles.includes(user?.role)
    }
    if (
      processCode === 'student_non_registration'
      && ['list_generated', 'meeting_scheduled', 'meeting_held'].includes(state)
    ) {
      return user?.role === 'supervision_committee' || user?.role === 'admin'
    }
    if (processCode === 'upgrade_to_educational_therapist') {
      if (state === 'monitoring_review') {
        return user?.role === 'supervision_committee' || user?.role === 'admin'
      }
      if (
        ['interview_scheduling', 'interview_held', 'therapist_committee_review', 'therapy_frequency_escalation'].includes(state)
      ) {
        return user?.role === 'education_committee' || user?.role === 'admin'
      }
      return false
    }
    if (processCode === 'upgrade_to_ta') {
      if (state === 'supervision_review') {
        return user?.role === 'supervision_committee' || user?.role === 'admin'
      }
      return false
    }
    if (processCode === 'ta_to_assistant_faculty' && state === 'supervision_review') {
      return user?.role === 'supervision_committee' || user?.role === 'admin'
    }
    if (processCode === 'intern_bulk_patient_referral') {
      if (state === 'supervision_start' && (user?.role === 'supervision_committee' || user?.role === 'admin')) {
        return true
      }
      if (
        state === 'general_therapy_committee_review'
        && (user?.role === 'therapy_committee_executor' || user?.role === 'admin')
      ) {
        return true
      }
      return false
    }
    if (processCode === 'internship_12month_conditional_review') {
      if (user?.role === 'admin') return true
      if (
        state === 'interview_scheduling'
        && (user?.role === 'progress_committee' || user?.role === 'progress_committee_project')
      ) {
        return true
      }
      if (
        state === 'interview_held'
        && (user?.role === 'progress_committee' || user?.role === 'progress_committee_scientific')
      ) {
        return true
      }
      return false
    }
    const keywordMatch = config.reviewKeywords.some((kw) => {
      if (!state.includes(kw)) return false
      if (kw === 'interview_completed' && processCode !== 'comprehensive_course_registration') {
        return false
      }
      return true
    })
    if (!keywordMatch) return false
    const kindRoles = kindMeta?.portalRoles || []
    if (user?.role === 'admin' || kindRoles.includes(user?.role)) return true
    return false
  }

  const viewInstance = async (instanceId) => {
    setSelectedInstance(instanceId)
    try {
      const [statusRes, transRes] = await Promise.all([
        processExecApi.status(instanceId),
        processExecApi.transitions(instanceId),
      ])
      setInstanceDetail(statusRes.data)
      setAvailableTransitions(transRes.data?.transitions || [])
      const ctx = statusRes.data?.context_data || {}
      setInterviewEval({
        evaluation_notes: ctx.interview_evaluation_notes || '',
        rejection_reason: ctx.interview_rejection_reason || '',
        suggestion_text: ctx.interview_suggestion_text || '',
      })
    } catch (err) {
      console.error('View error:', err)
    }
  }

  usePortalInstanceDeepLink({
    loading,
    setActiveTab,
    viewInstance,
    allowedTabs: COMMITTEE_DEEP_LINK_TABS,
  })

  const { processCodeFilter, filteredItems: pendingReviewsFiltered } = useProcessCodeUrlFilter({
    loading,
    items: pendingReviews,
    getProcessCode: (p) => p.process_code,
    getInstanceId: (p) => p.instance_id || p.id,
    viewInstance,
    setActiveTab,
    tabWhenFiltered: 'reviews',
  })

  const displayPendingReviews = processCodeFilter ? pendingReviewsFiltered : pendingReviews

  const handleProcessRollback = async (reason) => {
    if (!selectedInstance) return
    setRollbackBusy(true)
    try {
      const res = await processExecApi.rollback(selectedInstance, { reason: reason || undefined })
      if (res.data?.success) {
        showToast(`فرایند به «${labelState(res.data.to_state)}» برگردانده شد`)
        await viewInstance(selectedInstance)
        loadData()
      } else {
        showToast(res.data?.error || 'بازگشت انجام نشد', 'error')
      }
    } catch (e) {
      const d = e.response?.data?.detail
      showToast(typeof d === 'string' ? d : (e.message || 'خطا در بازگشت'), 'error')
    } finally {
      setRollbackBusy(false)
    }
  }

  const handleProcessRestart = async (reason) => {
    if (!selectedInstance) return false
    setRestartBusy(true)
    try {
      const res = await processExecApi.restart(selectedInstance, {
        reason: reason || undefined,
        confirm: true,
      })
      if (res.data?.success) {
        const newId = res.data.new_instance_id
        showToast('فرایند از ابتدا با پروندهٔ جدید باز شد')
        setSelectedInstance(newId)
        await viewInstance(newId)
        loadData()
        return true
      }
      showToast(res.data?.error || 'شروع دوباره انجام نشد', 'error')
      return false
    } catch (e) {
      const d = e.response?.data?.detail
      showToast(typeof d === 'string' ? d : (e.message || 'خطا در شروع دوباره'), 'error')
      return false
    } finally {
      setRestartBusy(false)
    }
  }

  const triggerTransition = async (transition) => {
    if (!selectedInstance) return
    const triggerEvent = typeof transition === 'string' ? transition : transition.trigger_event
    const toState = typeof transition === 'object' ? transition.to_state : undefined
    try {
      let payload = notesPayload(decisionNotes)
      const leaveMerge = mergeEducationalLeaveTriggerPayload(
        instanceDetail,
        triggerEvent,
        payload,
      )
      if (leaveMerge.error) {
        showToast(leaveMerge.error, 'error')
        return
      }
      payload = leaveMerge.payload
      const fullLeaveMerge = mergeFullEducationLeaveTriggerPayload(
        instanceDetail,
        triggerEvent,
        payload,
      )
      if (fullLeaveMerge.error) {
        showToast(fullLeaveMerge.error, 'error')
        return
      }
      payload = fullLeaveMerge.payload
      const committeesMerge = mergeCommitteesReviewTriggerPayload(
        instanceDetail,
        triggerEvent,
        payload,
      )
      if (committeesMerge.error) {
        showToast(committeesMerge.error, 'error')
        return
      }
      payload = committeesMerge.payload
      const commissionMerge = mergeCommissionReviewTriggerPayload(
        instanceDetail,
        triggerEvent,
        payload,
      )
      if (commissionMerge.error) {
        showToast(commissionMerge.error, 'error')
        return
      }
      payload = commissionMerge.payload
      const nonRegMerge = mergeNonRegistrationTriggerPayload(
        instanceDetail,
        triggerEvent,
        payload,
      )
      if (nonRegMerge.error) {
        showToast(nonRegMerge.error, 'error')
        return
      }
      payload = nonRegMerge.payload
      const referralMerge = mergeReferralTriggerPayload(
        instanceDetail,
        triggerEvent,
        payload,
      )
      if (referralMerge.error) {
        showToast(referralMerge.error, 'error')
        return
      }
      payload = referralMerge.payload
      const etUpgradeMerge = mergeEducationalTherapistUpgradeTriggerPayload(
        instanceDetail,
        triggerEvent,
        payload,
      )
      if (etUpgradeMerge.error) {
        showToast(etUpgradeMerge.error, 'error')
        return
      }
      payload = etUpgradeMerge.payload
      const taAssistantMerge = mergeTaToAssistantFacultyTriggerPayload(
        instanceDetail,
        triggerEvent,
        payload,
      )
      if (taAssistantMerge.error) {
        showToast(taAssistantMerge.error, 'error')
        return
      }
      payload = taAssistantMerge.payload
      const taUpgradeMerge = mergeUpgradeToTaTriggerPayload(
        instanceDetail,
        triggerEvent,
        payload,
      )
      if (taUpgradeMerge.error) {
        showToast(taUpgradeMerge.error, 'error')
        return
      }
      payload = taUpgradeMerge.payload
      const taTrackMerge = mergeTaTrackChangeTriggerPayload(
        instanceDetail,
        triggerEvent,
        payload,
      )
      if (taTrackMerge.error) {
        showToast(taTrackMerge.error, 'error')
        return
      }
      payload = taTrackMerge.payload
      payload = mergeInterviewBranchPayload(payload, toState, triggerEvent)
      if (
        instanceDetail?.process_code === 'comprehensive_course_registration'
        && isComprehensiveEvalTrigger(triggerEvent)
      ) {
        const evalError = validateInterviewEvaluationForm(interviewEval, triggerEvent)
        if (evalError) {
          showToast(evalError, 'error')
          return
        }
        payload = mergeInterviewEvaluationPayload(payload, interviewEval, triggerEvent)
      }
      if (toState) payload.to_state = toState
      const res = await processExecApi.trigger(selectedInstance, {
        trigger_event: triggerEvent,
        payload,
        ...(toState ? { to_state: toState } : {}),
      })
      if (res.data.success) {
        showToast(`تصمیم ثبت شد: ${labelState(res.data.to_state)}`)
        viewInstance(selectedInstance)
        loadData()
      } else {
        showToast(res.data.error || 'خطا', 'error')
      }
    } catch (err) {
      showToast(err.response?.data?.detail || 'خطا', 'error')
    }
  }

  const tabs = useMemo(() => {
    const base = [
      { id: 'reviews', label: `کارهای من (${displayPendingReviews.length})`, icon: '📥' },
      { id: 'dashboard', label: 'داشبورد', icon: '📊' },
    ]
    if (kindMeta?.showAllTab || user?.role === 'admin') {
      base.push({ id: 'all', label: 'همه فرایندها', icon: '🔄' })
    }
    base.push({ id: 'students', label: 'دانشجویان', icon: '👨‍🎓' })
    return base
  }, [displayPendingReviews.length, kindMeta, user?.role])

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '4rem' }}>
        <div className="loading-spinner" />
      </div>
    )
  }

  const instanceContext = instanceDetail?.context_data || {}
  const transitionsForActions = filterInterviewResultTransitions(
    availableTransitions,
    user,
    instanceContext,
  )
  const canSubmitInterview = canSubmitInterviewResult(user, instanceContext)

  return (
    <div>

      <ResolvedProcessHistoryBanner
        instanceDetail={instanceDetail}
        availableTransitions={availableTransitions}
      />

      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{
            width: '48px', height: '48px', borderRadius: '12px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '1.5rem', background: 'var(--primary-light)',
          }}>
            {config.icon}
          </div>
          <div>
            <h1 className="page-title">{config.title}</h1>
            <p className="page-subtitle">
              {user?.full_name_fa || user?.username} | {config.subtitle}
            </p>
          </div>
        </div>
      </div>

      <OperatorPortalReminderBanner
        portalPath={portalPath}
        pendingTab="reviews"
        actionLabel="رفتن به بررسی‌ها"
      />

      <OperatorFollowupSection
        items={operatorFollowupItems}
        readinessAlerts={operatorReadinessAlerts}
        inboxTitle="پرونده‌های باز مرتبط با نقش شما"
      />

      <div className="tab-bar">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`tab-item ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <span style={{ marginLeft: '0.35rem' }}>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Dashboard */}
      {activeTab === 'dashboard' && (
        <>
          <div className="stats-grid">
            <div
              className="stat-card stat-card-clickable"
              role="button"
              tabIndex={0}
              onClick={() => setActiveTab('reviews')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('reviews') } }}
              title="مشاهده درخواست‌های منتظر بررسی"
            >
              <div className="stat-icon warning">📥</div>
              <div>
                <div className="stat-value">{displayPendingReviews.length}</div>
                <div className="stat-label">منتظر بررسی</div>
              </div>
            </div>
            <div
              className="stat-card stat-card-clickable"
              role="button"
              tabIndex={0}
              onClick={() => setActiveTab('all')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('all') } }}
              title="مشاهده همه فرایندها"
            >
              <div className="stat-icon primary">🔄</div>
              <div>
                <div className="stat-value">{allActiveInstances.length}</div>
                <div className="stat-label">فرایند فعال</div>
              </div>
            </div>
            <div
              className="stat-card stat-card-clickable"
              role="button"
              tabIndex={0}
              onClick={() => setActiveTab('students')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('students') } }}
              title="مشاهده لیست دانشجویان"
            >
              <div className="stat-icon info">👨‍🎓</div>
              <div>
                <div className="stat-value">{allStudents.length}</div>
                <div className="stat-label">دانشجویان</div>
              </div>
            </div>
            <div
              className="stat-card stat-card-clickable"
              role="button"
              tabIndex={0}
              onClick={() => setActiveTab('all')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('all') } }}
              title="مشاهده فرایندهای بررسی‌شده"
            >
              <div className="stat-icon success">✅</div>
              <div>
                <div className="stat-value">{allActiveInstances.length - displayPendingReviews.length}</div>
                <div className="stat-label">بررسی‌شده</div>
              </div>
            </div>
          </div>

          <div className="dashboard-grid">
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">درخواست‌های منتظر بررسی</h3>
                {displayPendingReviews.length > 0 && (
                  <button className="btn btn-outline btn-sm" onClick={() => setActiveTab('reviews')}>
                    بررسی
                  </button>
                )}
              </div>
              {displayPendingReviews.length === 0 ? (
                <div className="empty-state" style={{ padding: '2rem' }}>
                  <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>✅</div>
                  <p>درخواست منتظری وجود ندارد</p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {displayPendingReviews.slice(0, 6).map(p => (
                    <button
                      key={p.instance_id}
                      onClick={() => openPendingReview(p)}
                      style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '0.75rem 1rem', borderRadius: '8px', cursor: 'pointer',
                        textAlign: 'right', border: '1px solid #fde68a', background: '#fffbeb',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 500 }}>
                          {labelProcess(p.process_code)}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                          دانشجو: {formatStudentCodeDisplay(p.student_code)} | {labelState(p.current_state)}
                        </div>
                      </div>
                      <span className="badge badge-warning" style={{ fontSize: '0.7rem' }}>منتظر</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="card">
              <div className="card-header">
                <h3 className="card-title">آمار دانشجویان</h3>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--primary)' }}>
                    {allStudents.filter(s => s.course_type === 'comprehensive').length}
                  </div>
                  <div style={{ fontSize: '0.82rem', color: '#6b7280' }}>دوره جامع</div>
                </div>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--info)' }}>
                    {allStudents.filter(s => s.course_type === 'introductory').length}
                  </div>
                  <div style={{ fontSize: '0.82rem', color: '#6b7280' }}>دوره آشنایی</div>
                </div>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--success)' }}>
                    {allStudents.filter(s => s.therapy_started).length}
                  </div>
                  <div style={{ fontSize: '0.82rem', color: '#6b7280' }}>درمان فعال</div>
                </div>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--warning)' }}>
                    {allStudents.filter(s => s.is_intern).length}
                  </div>
                  <div style={{ fontSize: '0.82rem', color: '#6b7280' }}>کارآموز</div>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Reviews Tab */}
      {activeTab === 'reviews' && (
        <div style={{ display: 'grid', gridTemplateColumns: instanceDetail ? '1fr 1.5fr' : '1fr', gap: '1.5rem' }}>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">بررسی‌ها ({displayPendingReviews.length})</h3>
            </div>
            {pendingReviews.length === 0 ? (
              <div className="empty-state" style={{ padding: '3rem' }}>
                <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>✅</div>
                <p>همه موارد بررسی شده‌اند</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {displayPendingReviews.map(p => (
                  <button
                    key={p.instance_id}
                    onClick={() => openPendingReview(p)}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '0.75rem 1rem', borderRadius: '8px', cursor: 'pointer',
                      textAlign: 'right',
                      border: selectedInstance === p.instance_id ? `2px solid ${config.accentColor}` : '1px solid var(--border)',
                      background: selectedInstance === p.instance_id ? 'var(--primary-light)' : '#fff',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 500 }}>{labelProcess(p.process_code)}</div>
                      <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                        دانشجو: {formatStudentCodeDisplay(p.student_code)} | {labelState(p.current_state)}
                      </div>
                    </div>
                    <span className="badge badge-warning" style={{ fontSize: '0.7rem' }}>منتظر</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {instanceDetail && (
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">
                  {labelProcess(instanceDetail.process_code)}
                </h3>
                <button onClick={() => { setSelectedInstance(null); setInstanceDetail(null) }}
                  className="btn btn-outline btn-sm">بستن</button>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
                  <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>وضعیت</label>
                  <div style={{ fontWeight: 700, color: config.accentColor }}>{labelState(instanceDetail.current_state)}</div>
                </div>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
                  <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>تاریخ شروع</label>
                  <div>{instanceDetail.started_at ? new Date(instanceDetail.started_at).toLocaleDateString('fa-IR') : '-'}</div>
                </div>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
                  <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>وضعیت کلی</label>
                  {instanceDetail.is_completed
                    ? <span className="badge badge-success">تکمیل</span>
                    : <span className="badge badge-warning">در جریان</span>
                  }
                </div>
              </div>

              <OperatorInstanceGuidanceBlock
                instanceDetail={instanceDetail}
                portalRole={user?.role}
                availableTransitions={availableTransitions}
              />

              <CommitteesReviewPanel detail={instanceDetail} />
              <IntroductoryCourseCompletionReviewPanel detail={instanceDetail} user={user} />
              <TaToInstructorAutoReportPanel
                detail={instanceDetail}
                active={instanceDetail?.process_code === 'ta_to_instructor_auto'}
                audience="committee"
              />
              <SpecializedCommissionReviewPanel detail={instanceDetail} />
              <UnannouncedAbsenceReactionPanel detail={instanceDetail} />
              <UnannouncedSupervisionAbsenceReactionPanel detail={instanceDetail} />
              <InternHoursIncreasePanel detail={instanceDetail} />
              <StudentNonRegistrationReviewPanel detail={instanceDetail} />
              <FullEducationLeaveCommitteeReviewPanel detail={instanceDetail} />
              <ViolationRegistrationReviewPanel
                detail={instanceDetail}
                studentExtraData={instanceDetail?.student_extra_data}
              />
              <InstructorClassSessionCancellationPanel
                detail={instanceDetail}
                active={instanceDetail?.process_code === 'class_session_cancellation'}
                allowAllCourses
              />
              <ThesisDefenseProgressReviewPanel detail={instanceDetail} />
              <ThesisDefenseSupervisionReviewPanel detail={instanceDetail} />
              <ThesisDefenseEducationSchedulePanel detail={instanceDetail} />
              <EducationalTherapistMonitoringReviewPanel detail={instanceDetail} user={user} />
              <EducationalTherapistInterviewPanel detail={instanceDetail} user={user} />
              <TaTrackChangeCommitteePanel detail={instanceDetail} user={user} />
              <EducationalTherapistTherapistReviewPanel detail={instanceDetail} user={user} />
              <TaUpgradeSupervisionReviewPanel detail={instanceDetail} user={user} />
              <TaToAssistantFacultyReviewPanel detail={instanceDetail} user={user} />
              <InternBulkPatientReferralSupervisionPanel detail={instanceDetail} />
              <InternBulkPatientReferralTherapyCommitteePanel detail={instanceDetail} />

              <TaTrackCompletionInstancePanel
                detail={instanceDetail}
                studentId={instanceDetail?.student_id}
                studentName={instanceDetail?.student_code}
                portalRole={user?.role}
                active={instanceDetail?.process_code === 'ta_track_completion'}
              />

              <InstanceContextSummary
                contextData={instanceDetail.context_data}
                history={instanceDetail.history}
                title="پرونده و سابقه (قبل از تصمیم)"
              />

              <OperatorStepFormsSection
                instanceId={selectedInstance}
                processCode={instanceDetail.process_code}
                currentState={instanceDetail.current_state}
                contextData={instanceDetail.context_data}
                isCompleted={instanceDetail.is_completed}
                isCancelled={instanceDetail.is_cancelled}
                role={user?.role}
                showToast={showToast}
                onUpdated={() => viewInstance(selectedInstance)}
              />

              {instanceDetail.process_code === 'comprehensive_course_registration'
                && instanceDetail.current_state === 'interview_completed'
                && canSubmitInterview
                && transitionsForActions.some(t => isComprehensiveEvalTrigger(t.trigger_event)) && (
                <div style={{
                  padding: '1rem 1.25rem', marginBottom: '1.25rem', borderRadius: '10px',
                  background: '#fef2f2', borderRight: '4px solid #dc2626',
                }}>
                  <h4 style={{ fontSize: '0.92rem', fontWeight: 700, marginBottom: '0.5rem', color: '#b91c1c' }}>
                    فرم ارزیابی مصاحبهٔ ورود به دوره جامع (محرمانه)
                  </h4>
                  <p style={{ fontSize: '0.8rem', color: '#7f1d1d', marginBottom: '0.75rem', lineHeight: 1.65 }}>
                    این فرم را پیش از ثبت نتیجه پر کنید. توضیحات ارزیابی و دلیل رد محرمانه است و فقط در پورتال پذیرش
                    ذخیره می‌شود و هرگز به دانشجو نمایش داده نمی‌شود. سپس روی دکمهٔ نتیجهٔ موردنظر (پذیرش / رد قطعی /
                    رد با پیشنهاد) کلیک کنید.
                  </p>
                  <label style={{ display: 'block', marginBottom: '0.6rem', fontSize: '0.85rem' }}>
                    توضیحات ارزیابی (الزامی)
                    <textarea
                      className="psf-input psf-textarea"
                      rows={3}
                      style={{ width: '100%', marginTop: '0.35rem' }}
                      value={interviewEval.evaluation_notes}
                      onChange={e => setInterviewEval(prev => ({ ...prev, evaluation_notes: e.target.value }))}
                    />
                  </label>
                  <label style={{ display: 'block', marginBottom: '0.6rem', fontSize: '0.85rem' }}>
                    دلیل رد (محرمانه — الزامی در صورت رد)
                    <textarea
                      className="psf-input psf-textarea"
                      rows={2}
                      style={{ width: '100%', marginTop: '0.35rem' }}
                      placeholder="فقط در صورت رد قطعی یا رد با پیشنهاد لازم است"
                      value={interviewEval.rejection_reason}
                      onChange={e => setInterviewEval(prev => ({ ...prev, rejection_reason: e.target.value }))}
                    />
                  </label>
                  <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.85rem' }}>
                    متن پیشنهاد (الزامی برای «رد همراه با پیشنهاد»)
                    <textarea
                      className="psf-input psf-textarea"
                      rows={2}
                      style={{ width: '100%', marginTop: '0.35rem' }}
                      value={interviewEval.suggestion_text}
                      onChange={e => setInterviewEval(prev => ({ ...prev, suggestion_text: e.target.value }))}
                    />
                  </label>
                </div>
              )}

              <ProcessRollbackSection
                user={user}
                instanceDetail={instanceDetail}
                onRollback={handleProcessRollback}
                busy={rollbackBusy}
              />

              <ProcessRestartSection
                user={user}
                instanceDetail={instanceDetail}
                onRestart={handleProcessRestart}
                busy={restartBusy}
              />

              {transitionsForActions.length > 0 && (
                <div style={{
                  padding: '1.25rem', background: 'var(--success-light)',
                  borderRadius: '10px', marginBottom: '1.5rem', borderRight: '4px solid var(--success)',
                }}>
                  <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--success)' }}>
                    {instanceDetail.process_code === 'specialized_commission_review'
                      ? 'تصمیم کمیسیون تخصصی'
                      : 'تصمیم کمیته'}
                  </h4>
                  <DecisionNotesBlock
                    value={decisionNotes}
                    onChange={setDecisionNotes}
                    title="توضیح یا مستندات تصمیم (اختیاری)"
                    hint="متن همراه همان دکمه‌ای که می‌زنید در پرونده ثبت می‌شود."
                  />
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    {transitionsForActions.map((t, idx) => {
                      const isApproval = t.trigger_event?.includes('approved') || t.trigger_event?.includes('confirm') || t.trigger_event?.includes('accept') || t.trigger_event?.includes('eligible') || t.trigger_event?.includes('continue')
                      const isReject = t.trigger_event?.includes('reject') || t.trigger_event?.includes('decline') || t.trigger_event?.includes('ineligible') || t.trigger_event?.includes('terminate')
                      return (
                        <button
                          key={idx}
                          onClick={() => triggerTransition(t)}
                          style={{
                            padding: '0.6rem 1.2rem', borderRadius: '8px', border: 'none',
                            cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem',
                            background: isApproval ? 'var(--success)' : isReject ? 'var(--danger)' : 'var(--primary)',
                            color: '#fff',
                          }}
                        >
                          {t.description || t.trigger_event}
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* All Processes Tab */}
      {activeTab === 'all' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">همه فرایندهای فعال ({allActiveInstances.length})</h3>
          </div>
          {allActiveInstances.length === 0 ? (
            <div className="empty-state" style={{ padding: '2rem' }}>
              <p>فرایند فعالی وجود ندارد</p>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>فرایند</th>
                    <th>دانشجو</th>
                    <th>وضعیت</th>
                    <th>تاریخ شروع</th>
                    <th>عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  {allActiveInstances.map(p => (
                    <tr key={p.instance_id}>
                      <td style={{ fontWeight: 500 }}>{labelProcess(p.process_code)}</td>
                      <td>{formatStudentCodeDisplay(p.student_code)}</td>
                      <td>
                        <span className={`badge ${isWaitingForReview(p.current_state, p.process_code) ? 'badge-warning' : 'badge-info'}`}>
                          {labelState(p.current_state)}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.82rem', color: '#6b7280' }}>
                        {p.started_at ? new Date(p.started_at).toLocaleDateString('fa-IR') : '-'}
                      </td>
                      <td>
                        <button className="btn btn-outline btn-sm" onClick={() => { viewInstance(p.instance_id); setActiveTab('reviews') }}>
                          بررسی
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Students Tab */}
      {activeTab === 'students' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">دانشجویان ({allStudents.length})</h3>
          </div>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>کد دانشجویی</th>
                  <th>نوع دوره</th>
                  <th>ترم</th>
                  <th>جلسات هفتگی</th>
                  <th>وضعیت درمان</th>
                  <th>کارآموز</th>
                </tr>
              </thead>
              <tbody>
                {allStudents.map(s => (
                  <tr key={s.id}>
                    <td style={{ fontWeight: 600 }}>{formatStudentCodeDisplay(s.student_code)}</td>
                    <td>
                      <span className={`badge ${s.course_type === 'comprehensive' ? 'badge-primary' : 'badge-info'}`}>
                        {s.course_type === 'comprehensive' ? 'جامع' : 'آشنایی'}
                      </span>
                    </td>
                    <td>{s.current_term}/{s.term_count}</td>
                    <td>{s.weekly_sessions}</td>
                    <td>
                      <span className={`badge ${s.therapy_started ? 'badge-success' : 'badge-warning'}`}>
                        {s.therapy_started ? 'فعال' : 'آغاز نشده'}
                      </span>
                    </td>
                    <td>{s.is_intern ? 'بله' : 'خیر'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
