import React, { useState, useEffect, useLayoutEffect, useRef, useCallback, useMemo } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { userHasRole } from '../utils/userRoles'
import { usePortalInstanceDeepLink } from '../hooks/usePortalInstanceDeepLink'
import { useProcessCodeUrlFilter } from '../hooks/useProcessCodeUrlFilter'
import { processExecApi, studentApi, panelApi, assignmentApi, interviewSlotsApi } from '../services/api'
import GamificationPanel from '../components/GamificationPanel'
import StudentQuestCard from '../components/StudentQuestCard'
import StudentActionInbox from '../components/StudentActionInbox'
import StudentConditionalTherapyCard from '../components/StudentConditionalTherapyCard'
import StudentSmsHistorySection from '../components/StudentSmsHistorySection'
import StudentProcessStepReview from '../components/StudentProcessStepReview'
import StudentDynamicFormsSection from '../components/StudentDynamicFormsSection'
import InstanceContextSummary from '../components/InstanceContextSummary'
import ProcessRestartSection from '../components/ProcessRestartSection'
import DecisionNotesBlock from '../components/DecisionNotesBlock'
import { buildRoadmapStates } from '../utils/studentRoadmap'
import { buildStudentProcessVisitSequence } from '../utils/studentProcessStepReview'
import { canStartProcess, hasActiveRegistrationProcess, resolvePrimaryInstanceId } from '../utils/studentProcessAccess'
import {
  mergeFormPayload,
  stepFormsBlockTransition,
  isStudentStepFormLocked,
  mergeAdmissionFormDefaultsFromProfile,
  filterFormsForStudent,
  CTX_DOCUMENTS_RESUBMIT_FIELDS,
} from '../utils/processFormsStudent'
import ProcessStepForms from '../components/ProcessStepForms'
import StudentProcessGuidancePanel from '../components/StudentProcessGuidancePanel'
import { useToast } from '../contexts/ToastContext'
import ResolvedProcessHistoryBanner from '../components/ResolvedProcessHistoryBanner'
import { buildStudentGuidance } from '../utils/studentProcessGuidance'
import { mergeInterviewBranchPayload } from '../utils/transitionInterviewPayload'
import { mergeUpgradeToTaTriggerPayload } from '../utils/upgradeToTaTriggerPayload'
import { mergeReturnToFullEducationTriggerPayload } from '../utils/returnToFullEducationTriggerPayload'
import { isInstituteLevelProcess } from '../utils/instituteProcesses'
import { labelProcess, labelState, formatStudentCodeDisplay } from '../utils/processDisplay'
import {
  STUDENT_TRANSITION_CTA_INTRO,
  getStudentTransitionButtonMain,
  getStudentTransitionButtonSub,
  getStudentTransitionTooltip,
  getStudentNextStepHintBox,
} from '../utils/studentTransitionCta'
import { showStudentTransitionCta } from '../utils/studentTransitionCtaVisibility'
import StudentRegistration from './public/StudentRegistration'
import StudentProfileDocumentsSection from '../components/StudentProfileDocumentsSection'
import StudentRegistrationProfileView from '../components/StudentRegistrationProfileView'
import StudentTranscriptsPanel from '../components/StudentTranscriptsPanel'
import StudentAcademicCalendarPanel from '../components/StudentAcademicCalendarPanel'
import StudentCourseStatusPanel from '../components/StudentCourseStatusPanel'
import StudentTaTrackPortfolioSection from '../components/StudentTaTrackPortfolioSection'
import TaTrackCompletionInstancePanel from '../components/TaTrackCompletionInstancePanel'
import StudentSessionPaymentPanel from '../components/StudentSessionPaymentPanel'
import StudentTherapyHoursPanel from '../components/StudentTherapyHoursPanel'
import StudentTherapyJourneyPanel from '../components/StudentTherapyJourneyPanel'
import StudentTherapyCompletionPanel from '../components/StudentTherapyCompletionPanel'
import StudentTherapyReductionPanel from '../components/StudentTherapyReductionPanel'
import StudentTherapyInterruptionPanel from '../components/StudentTherapyInterruptionPanel'
import StudentSessionCancellationPanel from '../components/StudentSessionCancellationPanel'
import StudentSupervisionCancellationPanel from '../components/StudentSupervisionCancellationPanel'
import SupervisorSessionCancellationPanel from '../components/SupervisorSessionCancellationPanel'
import StudentSupervisionBlockTransitionPanel from '../components/StudentSupervisionBlockTransitionPanel'
import StudentSupervisionSessionIncreasePanel from '../components/StudentSupervisionSessionIncreasePanel'
import StudentSupervisionSessionReductionPanel from '../components/StudentSupervisionSessionReductionPanel'
import StudentSupervisionInterruptionPanel from '../components/StudentSupervisionInterruptionPanel'
import StudentExtraSupervisionSessionPanel from '../components/StudentExtraSupervisionSessionPanel'
import StudentIntroductoryCourseRegistrationPanel from '../components/StudentIntroductoryCourseRegistrationPanel'
import StudentComprehensiveCourseRegistrationPanel from '../components/StudentComprehensiveCourseRegistrationPanel'
import StudentIntroductoryTermEndPanel from '../components/StudentIntroductoryTermEndPanel'
import StudentComprehensiveTermEndPanel from '../components/StudentComprehensiveTermEndPanel'
import StudentIntroSecondSemesterRegistrationPanel from '../components/StudentIntroSecondSemesterRegistrationPanel'
import StudentComprehensiveTermStartPanel from '../components/StudentComprehensiveTermStartPanel'
import StudentNonRegistrationPanel from '../components/StudentNonRegistrationPanel'
import StudentInstructorEvaluationPanel from '../components/StudentInstructorEvaluationPanel'
import StudentViolationRegistrationPanel from '../components/StudentViolationRegistrationPanel'
import StudentInternBulkPatientReferralPanel from '../components/StudentInternBulkPatientReferralPanel'
import StudentLessonStartPerTermPanel from '../components/StudentLessonStartPerTermPanel'
import StudentClassAttendancePanel from '../components/StudentClassAttendancePanel'
import StudentIntroductoryCourseCompletionPanel from '../components/StudentIntroductoryCourseCompletionPanel'
import StudentArticleWritingCompletionPanel from '../components/StudentArticleWritingCompletionPanel'
import StudentFilmObservationCourseCompletionPanel from '../components/StudentFilmObservationCourseCompletionPanel'
import StudentLiveTherapyObservationCourseCompletionPanel from '../components/StudentLiveTherapyObservationCourseCompletionPanel'
import StudentSkillsCourseCompletionPanel from '../components/StudentSkillsCourseCompletionPanel'
import StudentTheoryCourseCompletionPanel from '../components/StudentTheoryCourseCompletionPanel'
import StudentGroupSupervisionCourseCompletionPanel from '../components/StudentGroupSupervisionCourseCompletionPanel'
import StudentLiveSupervisionCoursePanel from '../components/StudentLiveSupervisionCoursePanel'
import StudentLiveSupervisionMirrorWritePanel from '../components/StudentLiveSupervisionMirrorWritePanel'
import StudentThesisDefenseRequestPanel from '../components/StudentThesisDefenseRequestPanel'
import StudentCommitteesRestartPanel from '../components/StudentCommitteesRestartPanel'
import StudentFeeDeterminationPanel from '../components/StudentFeeDeterminationPanel'
import StudentFinancialPlanPanel from '../components/StudentFinancialPlanPanel'
import StudentEducationalTherapistUpgradePanel from '../components/StudentEducationalTherapistUpgradePanel'
import StudentInternshipReadinessConsultationPanel from '../components/StudentInternshipReadinessConsultationPanel'
import StudentReturnToFullEducationPanel from '../components/StudentReturnToFullEducationPanel'
import StudentStartTherapyPanel from '../components/StudentStartTherapyPanel'
import StudentFullEducationLeavePanel from '../components/StudentFullEducationLeavePanel'
import StudentUpgradeToTaPanel from '../components/StudentUpgradeToTaPanel'
import StudentTaTrackChangePanel from '../components/StudentTaTrackChangePanel'
import StudentTaToInstructorAutoPanel from '../components/StudentTaToInstructorAutoPanel'
import SepPaymentPanel from '../components/SepPaymentPanel'
import StudentOnlineSessionsPanel from '../components/StudentOnlineSessionsPanel'
import { InterviewPaidBookingSummary } from '../components/InterviewSlotPicker'

const studentProcessCodes = [
  'educational_leave', 'full_education_leave', 'return_to_full_education',
  'start_therapy', 'extra_session', 'session_payment',
  'therapy_changes', 'therapy_session_increase', 'therapy_session_reduction',
  'therapy_interruption', 'student_session_cancellation', 'student_supervision_cancellation', 'supervision_block_transition',
  'extra_supervision_session', 'supervision_session_increase', 'supervision_session_reduction',
  'supervision_interruption', 'supervisor_session_cancellation',
  'introductory_course_registration', 'comprehensive_course_registration',
  'fee_determination', 'therapy_completion', 'upgrade_to_ta', 'ta_track_change', 'upgrade_to_educational_therapist', 'internship_readiness_consultation',
  'thesis_defense_request', 'lesson_start_per_term',
]

/** ناوبری دو سطحی: گروه → زیرتب (testidهای student-portal-tab-* حفظ می‌شوند) */
const STUDENT_TAB_TO_GROUP = {
  dashboard: 'journey',
  processes: 'journey',
  requests: 'journey',
  sessions: 'learning',
  assignments: 'learning',
  gamification: 'learning',
  profile: 'account',
}
const STUDENT_DEFAULT_TAB_BY_GROUP = {
  journey: 'dashboard',
  learning: 'sessions',
  account: 'profile',
}
const STUDENT_NAV_GROUPS = [
  { id: 'journey', label: 'مسیر و فرایند', icon: '📍' },
  { id: 'learning', label: 'کلاس و یادگیری', icon: '📚' },
  { id: 'account', label: 'پروفایل و مدارک', icon: '👤' },
]
const STUDENT_SUB_TABS_BY_GROUP = {
  journey: [
    { id: 'dashboard', label: 'داشبورد', icon: '📊' },
    { id: 'processes', label: 'فرایندها', icon: '🔄' },
    { id: 'requests', label: 'درخواست‌های دیگر', icon: '📝' },
  ],
  learning: [
    { id: 'sessions', label: 'جلسات آنلاین', icon: '🎥' },
    { id: 'assignments', label: 'تکالیف', icon: '📚' },
    { id: 'gamification', label: 'پیشرفت و مدال‌ها', icon: '🏆' },
  ],
  account: [
    { id: 'profile', label: 'پروفایل', icon: '👤' },
  ],
}

const STUDENT_DEEP_LINK_TABS = [
  'dashboard', 'processes', 'requests', 'sessions', 'assignments', 'gamification', 'profile',
]

export default function StudentPortal() {
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [studentProfile, setStudentProfile] = useState(null)
  const [activeProcesses, setActiveProcesses] = useState([])
  const [completedProcesses, setCompletedProcesses] = useState([])
  const [cancelledProcesses, setCancelledProcesses] = useState([])
  const [availableProcesses, setAvailableProcesses] = useState([])
  const [selectedInstance, setSelectedInstance] = useState(null)
  const [instanceDetail, setInstanceDetail] = useState(null)
  const [availableTransitions, setAvailableTransitions] = useState([])
  const [decisionNotes, setDecisionNotes] = useState('')
  const [activeTab, setActiveTab] = useState('dashboard')
  const [loading, setLoading] = useState(true)
  const [restartBusy, setRestartBusy] = useState(false)
  const [processFilter, setProcessFilter] = useState('')
  const [processDefinition, setProcessDefinition] = useState(null)
  const [onlineSessions, setOnlineSessions] = useState([])
  const [interviewBookings, setInterviewBookings] = useState([])
  const [assignments, setAssignments] = useState([])
  const [primaryJourney, setPrimaryJourney] = useState(null)
  const [primaryJourneyLoading, setPrimaryJourneyLoading] = useState(false)
  const [actionInboxItems, setActionInboxItems] = useState([])
  const [actionInboxLoading, setActionInboxLoading] = useState(false)
  /** پروفایل Student هنوز ایجاد نشده (GET /students/me → 404) — فرم پذیرش در همان پنل */
  const [admissionRequired, setAdmissionRequired] = useState(false)
  const [instanceForms, setInstanceForms] = useState([])
  const [stepFormValues, setStepFormValues] = useState({})
  const lastFormCtxRef = useRef('')
  const handleStepFieldChange = useCallback((name, v) => {
    setStepFormValues((prev) => ({ ...prev, [name]: v }))
  }, [])
  const gamificationTabPanelRef = useRef(null)
  const [showNewRequestModal, setShowNewRequestModal] = useState(false)
  const [selectedProcessTransitionIdx, setSelectedProcessTransitionIdx] = useState(0)
  /** کلیک روی chip گذشته در رودمپ فرایند — باز کردن مرور همان مرحله */
  const [reviewRoadmapFocus, setReviewRoadmapFocus] = useState(null)
  /** فرم‌های همهٔ وضعیت‌های طی‌شده برای برچسب‌های InstanceContextSummary */
  const [instanceContextExtraLabelForms, setInstanceContextExtraLabelForms] = useState([])
  const { showToast } = useToast()

  /** بازگشت از درگاه پرداخت (ریدایرکت کال‌بک با ?payment=success|failed) */
  const paymentReturnHandled = useRef(false)
  useEffect(() => {
    const payment = searchParams.get('payment')
    if (!payment) {
      paymentReturnHandled.current = false
      return
    }
    if (paymentReturnHandled.current) return
    paymentReturnHandled.current = true
    if (payment === 'success') {
      showToast('پرداخت با موفقیت ثبت شد. در صورت نیاز صفحه را یک‌بار تازه کنید.', 'success')
    } else if (payment === 'failed') {
      const reason = searchParams.get('reason')
      showToast(
        reason ? `پرداخت ناموفق: ${reason}` : 'پرداخت تکمیل نشد یا توسط بانک رد شد.',
        'error',
      )
    }
    const next = new URLSearchParams(searchParams)
    next.delete('payment')
    next.delete('ref')
    next.delete('reason')
    setSearchParams(next, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- فقط یک‌بار پس از برگشت از بانک
  }, [searchParams, setSearchParams])

  const consumeReviewRoadmapFocus = useCallback(() => {
    setReviewRoadmapFocus(null)
  }, [])

  useEffect(() => {
    if (!instanceDetail?.process_code) {
      setInstanceContextExtraLabelForms([])
      return
    }
    const seq = buildStudentProcessVisitSequence(
      instanceDetail.history,
      processDefinition,
      instanceDetail.current_state,
    )
    const states = [...new Set(seq)]
    if (states.length === 0) {
      setInstanceContextExtraLabelForms([])
      return
    }
    let cancelled = false
    ;(async () => {
      const results = await Promise.all(
        states.map((s) =>
          processExecApi.getProcessFormsForState(instanceDetail.process_code, s)
            .then((r) => r.data?.forms || [])
            .catch(() => []),
        ),
      )
      if (!cancelled) setInstanceContextExtraLabelForms(results)
    })()
    return () => {
      cancelled = true
    }
  }, [
    instanceDetail?.instance_id,
    instanceDetail?.process_code,
    instanceDetail?.current_state,
    instanceDetail?.history,
    processDefinition,
  ])

  const loadLearningData = async () => {
    if (!studentProfile) return
    try {
      const [oRes, aRes, ivRes] = await Promise.all([
        panelApi.myOnlineSessions(false).catch(() => ({ data: { items: [] } })),
        assignmentApi.mine().catch(() => ({ data: [] })),
        interviewSlotsApi.myBookings(false).catch(() => ({ data: { bookings: [] } })),
      ])
      setOnlineSessions(Array.isArray(oRes.data?.items) ? oRes.data.items : [])
      setInterviewBookings(Array.isArray(ivRes.data?.bookings) ? ivRes.data.bookings : [])
      setAssignments(Array.isArray(aRes.data) ? aRes.data : [])
    } catch (e) {
      console.error(e)
    }
  }

  const handleOnlineSessionsLoaded = useCallback((items) => {
    setOnlineSessions(Array.isArray(items) ? items : [])
  }, [])

  useEffect(() => {
    if (studentProfile && (activeTab === 'dashboard' || activeTab === 'sessions' || activeTab === 'assignments' || activeTab === 'profile')) {
      loadLearningData()
    }
  }, [studentProfile, activeTab])

  useEffect(() => {
    const sid = selectedInstance || studentProfile?.extra_data?.primary_instance_id
    const onProcessTab = activeTab === 'processes' && !!(selectedInstance && instanceDetail?.instance_id === selectedInstance)
    const st = onProcessTab
      ? instanceDetail?.current_state
      : primaryJourney?.detail?.current_state
    const ctx = onProcessTab
      ? instanceDetail?.context_data
      : primaryJourney?.detail?.context_data
    const forms = onProcessTab ? instanceForms : primaryJourney?.forms
    if (!sid || !st) return
    const k = `${sid}|${st}|${activeTab === 'processes' ? 'p' : 'd'}`
    if (lastFormCtxRef.current !== k) {
      lastFormCtxRef.current = k
      setStepFormValues(mergeAdmissionFormDefaultsFromProfile(forms, ctx, user, studentProfile))
    }
  }, [
    activeTab,
    selectedInstance,
    instanceDetail?.instance_id,
    instanceDetail?.current_state,
    instanceDetail?.context_data,
    instanceForms,
    primaryJourney?.detail?.current_state,
    primaryJourney?.detail?.context_data,
    primaryJourney?.forms,
    studentProfile?.extra_data?.primary_instance_id,
    user,
    studentProfile,
  ])

  useEffect(() => {
    if (activeTab !== 'gamification') return
    let cancelled = false
    studentApi.me().then(r => {
      if (!cancelled) setStudentProfile(r.data)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [activeTab])

  useEffect(() => {
    if (!studentProfile?.extra_data?.installment_portal_lock?.active) return
    const allowed = new Set(['profile', 'processes', 'dashboard'])
    if (!allowed.has(activeTab)) {
      setActiveTab('processes')
    }
  }, [studentProfile?.extra_data?.installment_portal_lock, activeTab])

  useEffect(() => {
    setSelectedProcessTransitionIdx(0)
  }, [selectedInstance, instanceDetail?.current_state])

  useEffect(() => {
    const n = availableTransitions?.length || 0
    if (!n) return
    setSelectedProcessTransitionIdx((i) => (i >= n ? 0 : i))
  }, [availableTransitions.length])

  /** جلوگیری از پرش ناخواستهٔ viewport به ابتدای صفحه هنگام باز شدن تب گیمیفیکیشن */
  useLayoutEffect(() => {
    if (activeTab !== 'gamification') return
    const el = gamificationTabPanelRef.current
    if (!el) return
    const id = window.requestAnimationFrame(() => {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
    return () => window.cancelAnimationFrame(id)
  }, [activeTab])

  const loadPrimaryJourney = useCallback(async (instanceId) => {
    if (!instanceId) {
      setPrimaryJourney(null)
      return
    }
    setPrimaryJourneyLoading(true)
    try {
      const dashRes = await processExecApi.dashboard(instanceId)
      const status = dashRes.data?.status
      const transitions = dashRes.data?.transitions || []
      const forms = dashRes.data?.forms || []
      const pcode = status?.process_code
      let def = null
      if (pcode) {
        try {
          const defRes = await processExecApi.getDefinition(pcode)
          def = defRes.data
        } catch {
          def = null
        }
      }
      setPrimaryJourney({
        detail: status,
        transitions,
        forms,
        definition: def,
        registrationGate: dashRes.data?.registration_gate || null,
      })
    } catch (e) {
      console.error('Primary journey load failed', e)
      setPrimaryJourney(null)
    } finally {
      setPrimaryJourneyLoading(false)
    }
  }, [])

  const loadActionInbox = useCallback(async () => {
    setActionInboxLoading(true)
    try {
      const res = await studentApi.actionInbox()
      setActionInboxItems(Array.isArray(res.data?.items) ? res.data.items : [])
    } catch (e) {
      console.error('Action inbox load failed', e)
      setActionInboxItems([])
    } finally {
      setActionInboxLoading(false)
    }
  }, [])

  const loadData = useCallback(async () => {
    try {
      // ابتدا پروفایل دانشجو — اگر /process/definitions خطا بدهد، نباید پروفایل خالی بماند
      let myProfile = null
      try {
        const meRes = await studentApi.me()
        myProfile = meRes.data ?? null
        setAdmissionRequired(false)
        if (!myProfile) {
          setAdmissionRequired(true)
        }
      } catch (e) {
        if (e.response?.status === 404) {
          myProfile = null
          setAdmissionRequired(true)
        } else if (userHasRole(user, 'staff')) {
          const listRes = await studentApi.list().catch(() => ({ data: [] }))
          myProfile = listRes.data?.find(s => s.user_id === user?.id)
          setAdmissionRequired(false)
        } else {
          setAdmissionRequired(false)
        }
      }
      setStudentProfile(myProfile)

      if (myProfile) {
        let instances = []
        try {
          const instancesRes = await processExecApi.studentInstances(myProfile.id)
          instances = (instancesRes.data?.instances || []).filter(
            (i) => !isInstituteLevelProcess(i.process_code),
          )
          setActiveProcesses(instances.filter(i => !i.is_completed && !i.is_cancelled))
          setCompletedProcesses(instances.filter(i => i.is_completed))
          setCancelledProcesses(instances.filter(i => i.is_cancelled))
        } catch (e) {
          console.error('Student instances load failed', e)
          setActiveProcesses([])
          setCompletedProcesses([])
          setCancelledProcesses([])
        }

        const primaryId = resolvePrimaryInstanceId({
          studentProfile: myProfile,
          instances,
          activeProcesses: instances.filter(i => !i.is_completed && !i.is_cancelled),
        })
        if (primaryId) {
          await loadPrimaryJourney(primaryId)
        } else {
          setPrimaryJourney(null)
        }
      } else {
        setPrimaryJourney(null)
      }

      let allDefs = []
      try {
        const defsRes = await processExecApi.definitions()
        allDefs = defsRes.data?.processes || []
      } catch (e) {
        console.error('Process definitions load failed', e)
      }
      setAvailableProcesses(allDefs.filter(p =>
        studentProcessCodes.includes(p.code) || p.code?.includes('student')
      ))
      await loadActionInbox()
    } catch (err) {
      console.error('Load error:', err)
    } finally {
      setLoading(false)
    }
  }, [user?.id, user?.role, loadPrimaryJourney, loadActionInbox])

  const handleInterviewBooked = useCallback(async () => {
    const pid =
      primaryJourney?.detail?.instance_id
      || studentProfile?.extra_data?.primary_instance_id
    await loadData()
    if (pid) {
      await loadPrimaryJourney(pid)
    }
    window.requestAnimationFrame(() => {
      document
        .querySelector('[data-testid="student-quest-sep-payment"]')
        ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }, [
    loadData,
    loadPrimaryJourney,
    primaryJourney?.detail?.instance_id,
    studentProfile?.extra_data?.primary_instance_id,
  ])

  useEffect(() => {
    loadData()
  }, [loadData])

  const startProcess = async (processCode) => {
    if (!studentProfile) return showToast('پروفایل دانشجو یافت نشد', 'error')
    try {
      const res = await processExecApi.start({
        process_code: processCode,
        student_id: studentProfile.id,
      })
      showToast(`فرایند ${labelProcess(processCode)} آغاز شد`)
      loadData()
      viewInstance(res.data.instance_id)
      setActiveTab('processes')
    } catch (err) {
      showToast(err.response?.data?.detail || 'خطا در آغاز فرایند', 'error')
    }
  }

  const viewInstance = async (instanceId) => {
    setSelectedInstance(instanceId)
    try {
      const dashRes = await processExecApi.dashboard(instanceId)
      const status = dashRes.data?.status
      const transitions = dashRes.data?.transitions || []
      const forms = dashRes.data?.forms || []
      setInstanceDetail(status)
      setAvailableTransitions(transitions)
      setInstanceForms(forms)
      const pcode = status?.process_code
      if (pcode) {
        try {
          const defRes = await processExecApi.getDefinition(pcode)
          setProcessDefinition(defRes.data)
        } catch {
          setProcessDefinition(null)
        }
      } else {
        setProcessDefinition(null)
      }
    } catch (err) {
      console.error('View error:', err)
    }
  }

  usePortalInstanceDeepLink({
    loading,
    setActiveTab,
    viewInstance,
    allowedTabs: STUDENT_DEEP_LINK_TABS,
  })

  const { processCodeFilter, filteredItems: activeProcessesFiltered } = useProcessCodeUrlFilter({
    loading,
    items: activeProcesses,
    getProcessCode: (p) => p.process_code,
    getInstanceId: (p) => p.instance_id,
    viewInstance,
    setActiveTab,
    tabWhenFiltered: 'processes',
  })

  const displayActiveProcesses = processCodeFilter ? activeProcessesFiltered : activeProcesses

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
    const lockedProc = isStudentStepFormLocked(instanceDetail?.context_data, instanceDetail?.current_state)
    const rawResubmit = instanceDetail?.context_data?.[CTX_DOCUMENTS_RESUBMIT_FIELDS]
    const resubmitNames = Array.isArray(rawResubmit) && rawResubmit.length ? rawResubmit : undefined
    if (!lockedProc && stepFormsBlockTransition(instanceForms, stepFormValues, {
      resubmitFieldNames: resubmitNames,
      contextData: instanceDetail?.context_data,
    })) {
      showToast('ابتدا همهٔ موارد الزام فرم این مرحله را تکمیل کنید.', 'error')
      return
    }
    try {
      let payload = mergeFormPayload(decisionNotes, stepFormValues)
      payload = mergeInterviewBranchPayload(payload, toState, triggerEvent)
      const taMerge = mergeUpgradeToTaTriggerPayload(instanceDetail, triggerEvent, payload)
      if (taMerge.error) {
        showToast(taMerge.error, 'error')
        return
      }
      payload = taMerge.payload
      const returnMerge = mergeReturnToFullEducationTriggerPayload(instanceDetail, triggerEvent, payload)
      if (returnMerge.error) {
        showToast(returnMerge.error, 'error')
        return
      }
      payload = returnMerge.payload
      if (toState) payload.to_state = toState
      const res = await processExecApi.trigger(selectedInstance, {
        trigger_event: triggerEvent,
        payload,
        ...(toState ? { to_state: toState } : {}),
      })
      if (res.data.success) {
        showToast(`انتقال انجام شد: ${labelState(res.data.to_state)}`)
        viewInstance(selectedInstance)
        loadData()
      } else {
        showToast(res.data.error || 'خطا در انتقال', 'error')
      }
    } catch (err) {
      showToast(err.response?.data?.detail || 'خطا', 'error')
    }
  }

  const triggerPrimaryTransition = async (transition) => {
    const triggerEvent = typeof transition === 'string' ? transition : transition.trigger_event
    const toState = typeof transition === 'object' ? transition.to_state : undefined
    const pid = studentProfile?.extra_data?.primary_instance_id || primaryJourney?.detail?.instance_id
    if (!pid) {
      showToast('مسیر اصلی یافت نشد', 'error')
      return
    }
    const lockedP = isStudentStepFormLocked(primaryJourney?.detail?.context_data, primaryJourney?.detail?.current_state)
    const rawPrimary = primaryJourney?.detail?.context_data?.[CTX_DOCUMENTS_RESUBMIT_FIELDS]
    const resubmitPrimary = Array.isArray(rawPrimary) && rawPrimary.length ? rawPrimary : undefined
    if (!lockedP && stepFormsBlockTransition(primaryJourney?.forms, stepFormValues, {
      resubmitFieldNames: resubmitPrimary,
      contextData: primaryJourney?.detail?.context_data,
    })) {
      showToast('ابتدا همهٔ موارد الزام فرم این مرحله را تکمیل کنید.', 'error')
      return
    }
    try {
      let payload = mergeFormPayload(decisionNotes, stepFormValues)
      payload = mergeInterviewBranchPayload(payload, toState, triggerEvent)
      const taMergePrimary = mergeUpgradeToTaTriggerPayload(primaryJourney?.detail, triggerEvent, payload)
      if (taMergePrimary.error) {
        showToast(taMergePrimary.error, 'error')
        return
      }
      payload = taMergePrimary.payload
      if (toState) payload.to_state = toState
      const res = await processExecApi.trigger(pid, {
        trigger_event: triggerEvent,
        payload,
        ...(toState ? { to_state: toState } : {}),
      })
      if (res.data.success) {
        showToast(`انتقال انجام شد: ${labelState(res.data.to_state)}`)
        setSelectedInstance(pid)
        await Promise.all([loadPrimaryJourney(pid), viewInstance(pid)])
        loadData()
      } else {
        showToast(res.data.error || 'خطا در انتقال', 'error')
      }
    } catch (err) {
      showToast(err.response?.data?.detail || 'خطا', 'error')
    }
  }

  const registerPrimaryStepForms = useCallback(async ({ ok, missing }) => {
    if (!ok) {
      showToast(`موارد ناقص: ${missing.join('، ')}`, 'error')
      return
    }
    const pid = studentProfile?.extra_data?.primary_instance_id || primaryJourney?.detail?.instance_id
    if (!pid) {
      showToast('شناسه فرایند یافت نشد', 'error')
      return
    }
    try {
      const regRes = await processExecApi.registerStudentStepForms(pid, { form_values: stepFormValues })
      await loadPrimaryJourney(pid)
      if (regRes.data?.auto_advanced_to_documents_review) {
        showToast(
          'مدارک در پرونده ثبت شد و به‌صورت خودکار برای بررسی پذیرش ارسال شد. در پنل کارمند در «بررسی مدارک» دیده می‌شود.',
          'success',
        )
      } else {
        showToast(
          'اطلاعات این مرحله ثبت شد. اگر دکمهٔ «ادامه و ثبت مرحله» را می‌بینید همان را بزنید تا پرونده برای پذیرش برود؛ در غیر این صورت منتظر اقدام اداری بمانید.',
          'success',
        )
      }
    } catch (e) {
      const d = e.response?.data?.detail
      if (d && typeof d === 'object' && Array.isArray(d.missing)) {
        showToast(`موارد ناقص: ${d.missing.join('، ')}`, 'error')
      } else {
        showToast(typeof d === 'string' ? d : (e.message || 'خطا در ثبت'), 'error')
      }
    }
  }, [studentProfile?.extra_data?.primary_instance_id, primaryJourney?.detail?.instance_id, stepFormValues, loadPrimaryJourney])

  const profileLearningSummary = useMemo(() => {
    const sessions = Array.isArray(onlineSessions) ? onlineSessions : []
    const assigns = Array.isArray(assignments) ? assignments : []
    const sessionCount = sessions.length
    const assignmentCount = assigns.length
    const interviewSessions = sessions.filter((s) => s.kind === 'interview')
    let nearestSession = null
    if (sessionCount > 0) {
      const sorted = [...sessions].sort((a, b) => {
        const ta = Date.parse(a.starts_at || a.session_starts_at || a.session_date || '') || Number.MAX_SAFE_INTEGER
        const tb = Date.parse(b.starts_at || b.session_starts_at || b.session_date || '') || Number.MAX_SAFE_INTEGER
        return ta - tb
      })
      const f = sorted[0]
      nearestSession = f.starts_at || f.session_date || f.session_starts_at || null
    }
    let nearestDue = null
    const withDue = assigns.filter((a) => a.due_at)
    if (withDue.length > 0) {
      const sorted = [...withDue].sort((a, b) => {
        const ta = Date.parse(a.due_at) || 0
        const tb = Date.parse(b.due_at) || 0
        return ta - tb
      })
      nearestDue = sorted[0].due_at
    }
    return {
      sessionCount,
      assignmentCount,
      nearestSession,
      nearestDue,
      interviewSessions,
    }
  }, [onlineSessions, assignments])

  const goToOnlineSessions = useCallback(() => {
    setActiveTab('sessions')
  }, [])

  const openActionInboxItem = useCallback((item) => {
    if (!item) return
    if (item.kind === 'hint' || !item.instance_id) {
      goToOnlineSessions()
      return
    }
    setActiveTab('processes')
    viewInstance(item.instance_id)
  }, [goToOnlineSessions, viewInstance])

  const activeEvaluationInstance = useMemo(
    () => activeProcesses.find(
      (p) => p.process_code === 'student_instructor_evaluation'
        && p.current_state === 'evaluation_open',
    ),
    [activeProcesses],
  )

  const activeFullLeaveInstance = useMemo(
    () => activeProcesses.find((p) => p.process_code === 'full_education_leave'),
    [activeProcesses],
  )

  const fullLeaveCompleted = useMemo(
    () => completedProcesses.some((p) => p.process_code === 'full_education_leave'),
    [completedProcesses],
  )

  const activeReturnInstance = useMemo(
    () => activeProcesses.find((p) => p.process_code === 'return_to_full_education'),
    [activeProcesses],
  )

  const activeInternshipPromissory = useMemo(
    () => activeProcesses.find(
      (p) => p.process_code === 'internship_readiness_consultation'
        && p.current_state === 'promissory_note',
    ),
    [activeProcesses],
  )

  const activeSessionPaymentInstance = useMemo(
    () => activeProcesses.find(
      (p) => p.process_code === 'session_payment' && !p.is_completed && !p.is_cancelled,
    ) || null,
    [activeProcesses],
  )

  const activeTermEndInstance = useMemo(
    () => activeProcesses.find(
      (p) => (p.process_code === 'introductory_term_end' || p.process_code === 'comprehensive_term_end')
        && !p.is_completed && !p.is_cancelled,
    ) || null,
    [activeProcesses],
  )

  const [termEndDetail, setTermEndDetail] = useState(null)

  useEffect(() => {
    const instanceId = activeTermEndInstance?.instance_id
    if (!instanceId) {
      setTermEndDetail(null)
      return undefined
    }
    let cancelled = false
    processExecApi.instance(instanceId)
      .then((r) => {
        if (!cancelled) setTermEndDetail(r.data || null)
      })
      .catch(() => {
        if (!cancelled) setTermEndDetail(null)
      })
    return () => {
      cancelled = true
    }
  }, [activeTermEndInstance?.instance_id])

  const openTermEndInstance = useCallback((instanceId) => {
    setActiveTab('processes')
    const id = instanceId || activeTermEndInstance?.instance_id
    if (id) viewInstance(id)
  }, [activeTermEndInstance?.instance_id, viewInstance])

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '4rem' }}>
        <div className="loading-spinner" />
      </div>
    )
  }

  const activeNavGroup = STUDENT_TAB_TO_GROUP[activeTab] || 'journey'
  const installmentLockActive = Boolean(studentProfile?.extra_data?.installment_portal_lock?.active)

  const roadmapStates = processDefinition ? buildRoadmapStates(processDefinition) : []
  const roadmapProgress = instanceDetail && roadmapStates.length
    ? Math.min(100, Math.round((roadmapStates.findIndex(s => s.code === instanceDetail.current_state) + 1) / roadmapStates.length * 100))
    : 0
  const nextStepHintBox = getStudentNextStepHintBox(availableTransitions)
  const stepFormLockedProcess = isStudentStepFormLocked(instanceDetail?.context_data, instanceDetail?.current_state)
  const stepFormLockedPrimary = isStudentStepFormLocked(primaryJourney?.detail?.context_data, primaryJourney?.detail?.current_state)
  const docsResubmitProcess = Array.isArray(instanceDetail?.context_data?.[CTX_DOCUMENTS_RESUBMIT_FIELDS])
    && instanceDetail.context_data[CTX_DOCUMENTS_RESUBMIT_FIELDS].length
    ? instanceDetail.context_data[CTX_DOCUMENTS_RESUBMIT_FIELDS]
    : null
  const processTransitionBlocked = instanceDetail && stepFormsBlockTransition(instanceForms, stepFormValues, {
    lockedSubmitted: stepFormLockedProcess,
    resubmitFieldNames: docsResubmitProcess || undefined,
    contextData: instanceDetail?.context_data,
  })
  const instanceDetailDone = !!(instanceDetail?.is_completed || instanceDetail?.is_cancelled)
  const showProcessTransitionCta = instanceDetail && showStudentTransitionCta({
    transitions: availableTransitions,
    transitionBlocked: Boolean(processTransitionBlocked),
    detailDone: instanceDetailDone,
  })
  const selectedProcessTransition = availableTransitions[selectedProcessTransitionIdx] ?? availableTransitions[0]

  // قبل از buildStudentGuidance — در غیر این صورت TDZ: Cannot access before initialization
  const introGate = studentProfile?.intro_registration_gate
  const introGateClosed = Boolean(
    studentProfile?.course_type === 'introductory' &&
      introGate &&
      introGate.allowed === false,
  )
  const introGateReason =
    introGate?.reason_fa ||
    primaryJourney?.registrationGate?.reason_fa ||
    'ثبت‌نام دورهٔ آشنایی پس از انتشار تقویم آموزشی باز می‌شود.'

  const primaryGuidance =
    studentProfile && primaryJourney?.detail && primaryJourney?.definition
      ? buildStudentGuidance({
          definition: primaryJourney.definition,
          detail: primaryJourney.detail,
          transitions: primaryJourney.transitions,
          forms: primaryJourney.forms,
          stepFormLocked: stepFormLockedPrimary,
          registrationGate: primaryJourney?.registrationGate || introGate,
        })
      : null

  const showSessionPaymentAfterTherapy =
    primaryJourney?.detail?.process_code === 'session_payment' &&
    primaryJourney?.detail?.context_data?.source === 'after_start_therapy_complete'

  const instanceGuidance =
    instanceDetail && processDefinition
      ? buildStudentGuidance({
          definition: processDefinition,
          detail: instanceDetail,
          transitions: availableTransitions,
          forms: instanceForms,
          stepFormLocked: stepFormLockedProcess,
          registrationGate:
            instanceDetail?.process_code === 'introductory_course_registration'
              ? introGate
              : null,
        })
      : null

  const accessCtx = { studentProfile, activeProcesses }
  const regCodeForProfile = studentProfile
    ? (studentProfile.course_type === 'comprehensive' ? 'comprehensive_course_registration' : 'introductory_course_registration')
    : null
  const showManualRegStart = Boolean(
    studentProfile &&
      !admissionRequired &&
      !primaryJourneyLoading &&
      !primaryJourney?.detail &&
      regCodeForProfile &&
      canStartProcess(regCodeForProfile, accessCtx).ok,
  )
  const registrationBlocking = studentProfile && hasActiveRegistrationProcess(activeProcesses)

  const primarySmsRefreshKey = primaryJourney?.detail
    ? `${primaryJourney.detail.instance_id || ''}-${primaryJourney.detail.current_state || ''}`
    : null
  const processSmsRefreshKey = instanceDetail
    ? `${instanceDetail.instance_id || selectedInstance || ''}-${instanceDetail.current_state || ''}`
    : null

  const quickActionItems = [
    { code: 'lesson_start_per_term', icon: '📘', label: 'ثبت درس این ترم' },
    { code: 'session_payment', icon: '💳', label: 'پرداخت جلسات' },
    { code: 'therapy_completion', icon: '🏁', label: 'خاتمه درمان آموزشی' },
    { code: 'educational_leave', icon: '🏖️', label: 'درخواست مرخصی' },
    { code: 'full_education_leave', icon: '🛑', label: 'مرخصی از کل آموزش' },
    { code: 'extra_session', icon: '➕', label: 'جلسه اضافی درمان' },
    { code: 'extra_supervision_session', icon: '➕', label: 'جلسه اضافی سوپرویژن' },
    { code: 'therapy_session_increase', icon: '📈', label: 'افزایش جلسات هفتگی درمان' },
    { code: 'supervision_session_increase', icon: '📈', label: 'افزایش جلسات هفتگی سوپرویژن' },
    { code: 'supervision_session_reduction', icon: '📉', label: 'کاهش جلسات هفتگی سوپرویژن' },
    { code: 'student_session_cancellation', icon: '🚫', label: 'کنسل جلسه درمان' },
    { code: 'student_supervision_cancellation', icon: '🚫', label: 'کنسل جلسه سوپرویژن' },
    { code: 'upgrade_to_ta', icon: '📚', label: 'ارتقا به کمک‌مدرس' },
    { code: 'ta_track_change', icon: '🔀', label: 'تغییر/اضافه رسته کمک‌مدرس' },
    { code: 'supervision_interruption', icon: '⏸️', label: 'وقفه سوپرویژن' },
  ]
  const allowedQuickActionItems = quickActionItems.filter((item) => canStartProcess(item.code, accessCtx).ok)

  /** رزرو وقت مصاحبه اکنون داخل کارت مسیر (StudentQuestCard) است */
  const dashboardUrgentAlertItems = []
  if (studentProfile?.extra_data?.academic_calendar_published) {
    dashboardUrgentAlertItems.push({
      key: 'academic-calendar-published',
      node: (
        <div
          className="card student-portal-alert-card student-portal-alert-card--info"
          role="status"
          data-testid="student-academic-calendar-alert"
        >
          <strong className="student-portal-alert-card-title student-portal-alert-card-title--info">
            تقویم آموزشی منتشر شد
          </strong>
          <p className="student-portal-alert-card-p">
            تاریخ‌های ترم و مهلت ثبت‌نام در صفحهٔ «تقویم آموزشی» به‌روز است. در صورت باز بودن
            مهلت، می‌توانید از تب فرایندها ثبت‌نام ترم را ادامه دهید.
          </p>
          <Link
            to="/panel/academic-calendar"
            className="btn btn-primary btn-sm"
            style={{ marginTop: '0.5rem', display: 'inline-block' }}
            data-testid="student-academic-calendar-alert-link"
          >
            مشاهده تقویم آموزشی
          </Link>
        </div>
      ),
    })
  }
  if (activeEvaluationInstance) {
    dashboardUrgentAlertItems.push({
      key: 'instructor-evaluation',
      node: (
        <div
          className="card student-portal-alert-card student-portal-alert-card--info"
          role="status"
          data-testid="student-evaluation-alert"
        >
          <strong className="student-portal-alert-card-title student-portal-alert-card-title--info">
            مهلت ارزیابی اساتید
          </strong>
          <p className="student-portal-alert-card-p">
            پنجرهٔ ارزیابی مدرسین باز است. فرم را در تب «فرایندها» تکمیل کنید (اختیاری اما توصیه‌شده).
          </p>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            style={{ marginTop: '0.5rem' }}
            onClick={() => setActiveTab('processes')}
          >
            رفتن به فرایند ارزیابی
          </button>
        </div>
      ),
    })
  }
  if (interviewBookings.length > 0) {
    const nextInterview = [...interviewBookings].sort((a, b) => {
      const ta = Date.parse(a.starts_at || '') || Number.MAX_SAFE_INTEGER
      const tb = Date.parse(b.starts_at || '') || Number.MAX_SAFE_INTEGER
      return ta - tb
    })[0]
    const isOnline = nextInterview.mode === 'online'
    const joinReady = isOnline && Boolean(nextInterview.meeting_link_is_visible && (nextInterview.meeting_link || '').trim())
    const courseLabel = nextInterview.course_type === 'comprehensive'
      ? 'مصاحبهٔ پذیرش — دوره جامع'
      : nextInterview.course_type === 'introductory'
        ? 'مصاحبهٔ پذیرش — دوره آشنایی'
        : 'مصاحبهٔ پذیرش'
    dashboardUrgentAlertItems.push({
      key: 'upcoming-interview',
      node: (
        <div
          className="card student-portal-alert-card student-portal-alert-card--success"
          role="status"
          data-testid="student-interview-online-sessions-alert"
        >
          <strong className="student-portal-alert-card-title student-portal-alert-card-title--success">
            مصاحبهٔ شما ثبت شد
          </strong>
          <p className="student-portal-alert-card-p">
            {nextInterview.label_fa || courseLabel}
            {nextInterview.starts_at ? (
              <>
                {' '}
                · زمان:{' '}
                {new Date(nextInterview.starts_at).toLocaleString('fa-IR', { dateStyle: 'medium', timeStyle: 'short' })}
              </>
            ) : null}
            {isOnline
              ? (joinReady
                ? ' — لینک ورود اکنون فعال است.'
                : ' — جزئیات و لینک ورود (۳۰ دقیقه قبل از شروع) در بخش «جلسات آنلاین» نمایش داده می‌شود.')
              : ` — نوع حضوری${nextInterview.location_fa ? ` · محل: ${nextInterview.location_fa}` : ''}. جزئیات در «جلسات آنلاین» و «پروفایل».`}
          </p>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            style={{ marginTop: '0.5rem' }}
            data-testid="student-interview-goto-online-sessions"
            onClick={goToOnlineSessions}
          >
            رفتن به جلسات آنلاین
          </button>
        </div>
      ),
    })
  }

  const profileSecondaryAlertItems = []
  if (showSessionPaymentAfterTherapy) {
    profileSecondaryAlertItems.push({
      key: 'payment-after-therapy',
      node: (
        <div
          className="card student-portal-alert-card student-portal-alert-card--success"
          role="status"
        >
          <strong className="student-portal-alert-card-title student-portal-alert-card-title--success">مرحله بعد پس از آغاز درمان</strong>
          <p className="student-portal-alert-card-p">
            آغاز درمان آموزشی شما ثبت شد. مسیر فعلی شما «پرداخت برای جلسات آتی درمان آموزشی» است؛
            هزینهٔ جلسات پیشِ رو را از کارت مسیر در داشبورد یا از تب «فرایندها» تکمیل کنید تا لینک جلسات و حضور فعال بماند.
          </p>
        </div>
      ),
    })
  }
  if (studentProfile?.extra_data?.dashboard_therapy_hint_fa) {
    profileSecondaryAlertItems.push({
      key: 'therapy-hint',
      node: (
        <div
          className="card student-portal-alert-card student-portal-alert-card--info"
          role="status"
        >
          <strong className="student-portal-alert-card-title student-portal-alert-card-title--info">پس از پرداخت جلسات</strong>
          <p className="student-portal-alert-card-p">{studentProfile.extra_data.dashboard_therapy_hint_fa}</p>
        </div>
      ),
    })
  }
  if (studentProfile?.therapy_started && studentProfile?.therapy_hours_progress_fa) {
    profileSecondaryAlertItems.push({
      key: 'therapy-hours',
      node: (
        <div
          className="card student-portal-alert-card student-portal-alert-card--neutral"
          role="status"
        >
          <strong className="student-portal-alert-card-title student-portal-alert-card-title--neutral">پیشرفت ساعات درمان آموزشی</strong>
          <p className="student-portal-alert-card-p">{studentProfile.therapy_hours_progress_fa}</p>
        </div>
      ),
    })
  }
  if (activeFullLeaveInstance) {
    const returnStartCheck = canStartProcess('return_to_full_education', {
      studentProfile,
      activeProcesses,
      completedProcesses,
    })
    profileSecondaryAlertItems.push({
      key: 'full-education-leave',
      node: (
        <div className="card student-portal-alert-card student-portal-alert-card--info" role="status">
          <strong className="student-portal-alert-card-title student-portal-alert-card-title--info">
            مرخصی از کل آموزش
          </strong>
          <p className="student-portal-alert-card-p">
            فرایند مرخصی کامل آموزش در پروندهٔ شما فعال است. وضعیت فعلی:{' '}
            {labelState(activeFullLeaveInstance.current_state)} — جزئیات را در تب «فرایندها» ببینید.
          </p>
          {returnStartCheck.ok && (
            <button
              type="button"
              className="btn btn-primary btn-sm"
              style={{ marginTop: '0.65rem' }}
              data-testid="start-return-to-full-education"
              onClick={() => startProcess('return_to_full_education')}
            >
              شروع بازگشت به کل آموزش
            </button>
          )}
        </div>
      ),
    })
  }
  if (!activeReturnInstance && (fullLeaveCompleted || studentProfile?.extra_data?.on_full_education_leave)) {
    const returnStartCheck = canStartProcess('return_to_full_education', {
      studentProfile,
      activeProcesses,
      completedProcesses,
    })
    if (returnStartCheck.ok) {
      profileSecondaryAlertItems.push({
        key: 'return-to-full-education-cta',
        node: (
          <div className="card student-portal-alert-card student-portal-alert-card--info" role="status">
            <strong className="student-portal-alert-card-title student-portal-alert-card-title--info">
              بازگشت به کل آموزش
            </strong>
            <p className="student-portal-alert-card-p">
              برای بازگشت به کلاس‌ها و فعالیت‌های آموزشی، فرایند «بازگشت به کل آموزش پس از مرخصی» را آغاز کنید.
            </p>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              style={{ marginTop: '0.65rem' }}
              data-testid="start-return-to-full-education-dashboard"
              onClick={() => startProcess('return_to_full_education')}
            >
              شروع بازگشت به کل آموزش
            </button>
          </div>
        ),
      })
    }
  }
  if (activeInternshipPromissory) {
    profileSecondaryAlertItems.push({
      key: 'intern-promissory',
      node: (
        <div className="card student-portal-alert-card student-portal-alert-card--info" role="status">
          <strong className="student-portal-alert-card-title student-portal-alert-card-title--info">
            تحویل سفته کارورزی
          </strong>
          <p className="student-portal-alert-card-p">
            سفته را حضوری تحویل دهید. پس از ثبت توسط کمیته پیشرفت، مرحلهٔ بعد در همان فرایند فعال می‌شود.
          </p>
        </div>
      ),
    })
  }

  return (
    <div>

      <ResolvedProcessHistoryBanner
        instanceDetail={instanceDetail}
        availableTransitions={availableTransitions}
      />

      {showNewRequestModal && studentProfile && (
        <div
          className="modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="student-new-request-title"
          onClick={() => setShowNewRequestModal(false)}
        >
          <div className="modal modal-sm" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 id="student-new-request-title">شروع درخواست جدید</h3>
              <button
                type="button"
                className="modal-close"
                onClick={() => setShowNewRequestModal(false)}
                aria-label="بستن"
              >
                &times;
              </button>
            </div>
            <div className="modal-body">
              {allowedQuickActionItems.length === 0 ? (
                <>
                  <p className="muted" style={{ marginBottom: '1rem', lineHeight: 1.65 }}>
                    با وضعیت فعلی، فرایند جدیدی از این میان‌بر برای شما باز نیست. سایر درخواست‌ها را در «درخواست‌های دیگر» ببینید.
                  </p>
                  <button
                    type="button"
                    className="btn btn-primary"
                    data-testid="student-quick-action-goto-requests-empty"
                    onClick={() => {
                      setShowNewRequestModal(false)
                      setActiveTab('requests')
                    }}
                  >
                    رفتن به درخواست‌های دیگر
                  </button>
                </>
              ) : (
                <ul className="student-new-request-list">
                  {allowedQuickActionItems.map((item) => (
                    <li key={item.code}>
                      <button
                        type="button"
                        className="student-new-request-item-btn"
                        data-testid={`student-quick-action-start-${item.code}`}
                        onClick={() => {
                          setShowNewRequestModal(false)
                          startProcess(item.code)
                        }}
                      >
                        <span className="student-new-request-item-icon" aria-hidden="true">{item.icon}</span>
                        <span>{item.label}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <div className="student-new-request-modal-footer">
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  data-testid="student-new-request-modal-goto-requests"
                  onClick={() => {
                    setShowNewRequestModal(false)
                    setActiveTab('requests')
                  }}
                >
                  درخواست‌های دیگر
                </button>
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  data-testid="student-new-request-modal-goto-profile"
                  onClick={() => {
                    setShowNewRequestModal(false)
                    setActiveTab('profile')
                  }}
                >
                  مشاهده پروفایل
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">پنل آموزشی</h1>
          <p className="page-subtitle">
            {admissionRequired
              ? `${user?.full_name_fa || user?.username || 'کاربر گرامی'} — فرم پذیرش را در کارت زیر تکمیل کنید تا مسیر دوره برایتان فعال شود.`
              : studentProfile
                ? `${user?.full_name_fa || user?.username} · کد: ${formatStudentCodeDisplay(studentProfile.student_code)} · دورهٔ ${studentProfile.course_type === 'comprehensive' ? 'جامع' : 'آشنایی'}`
                : 'پروفایل دانشجو یافت نشد — با واحد اداری تماس بگیرید.'}
          </p>
        </div>
      </div>

      {admissionRequired && (
        <div
          className="card"
          style={{
            marginBottom: '1.25rem',
            padding: '0',
            borderRadius: '12px',
            border: '1px solid rgba(59, 130, 246, 0.4)',
            background: 'linear-gradient(135deg, rgba(239, 246, 255, 0.98) 0%, rgba(255, 255, 255, 0.99) 100%)',
            overflow: 'hidden',
          }}
        >
          <div style={{ padding: '1rem 1.25rem 0.5rem', borderBottom: '1px solid rgba(59, 130, 246, 0.2)' }}>
            <h3 className="card-title" style={{ marginBottom: '0.35rem' }}>وضعیت فعلی</h3>
            <p className="muted" style={{ margin: 0, fontSize: '0.95rem', lineHeight: 1.65, maxWidth: '48rem' }}>
              پس از ارسال، مسیر ثبت‌نام دوره معمولاً خودکار باز می‌شود. اگر در داشبورد مسیر را ندیدید، از همان‌جا دکمهٔ «شروع فرایند ثبت‌نام» را بزنید.
            </p>
          </div>
          <div style={{ padding: '1rem 1.25rem 1.25rem' }}>
            <StudentRegistration mode="panel" embedded onPanelSuccess={loadData} />
          </div>
        </div>
      )}

      {installmentLockActive && (
        <div
          role="alert"
          data-testid="student-installment-portal-lock-banner"
          style={{
            marginBottom: '1rem',
            padding: '0.85rem 1.1rem',
            borderRadius: '10px',
            background: '#fef2f2',
            borderRight: '4px solid #dc2626',
            color: '#991b1b',
            fontSize: '0.9rem',
            lineHeight: 1.75,
          }}
        >
          <strong>پنل به‌دلیل قسط معوق شهریه محدود شده است.</strong>
          {' '}
          برای ادامه، قسط معوق را از بخش «فرایندها» یا «پروفایل → پلن مالی و اقساط» پرداخت کنید.
        </div>
      )}

      {/* ناوبری گروه‌بندی‌شدهٔ پنل آموزشی */}
      <div className="student-portal-nav" data-testid="student-portal-tab-bar">
        <div className="student-portal-nav-groups" role="tablist" aria-label="بخش‌های پنل آموزشی">
          {STUDENT_NAV_GROUPS.map(g => (
            <button
              key={g.id}
              type="button"
              role="tab"
              aria-selected={activeNavGroup === g.id}
              data-testid={`student-portal-group-${g.id}`}
              className={`student-portal-nav-group-btn ${activeNavGroup === g.id ? 'active' : ''}`}
              onClick={() => setActiveTab(STUDENT_DEFAULT_TAB_BY_GROUP[g.id])}
            >
              <span className="student-portal-nav-group-icon" aria-hidden="true">{g.icon}</span>
              {g.label}
            </button>
          ))}
        </div>
        <div className="tab-bar student-portal-nav-sub" role="tablist" aria-label="زیربخش">
          {(STUDENT_SUB_TABS_BY_GROUP[activeNavGroup] || []).map(tab => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              data-testid={`student-portal-tab-${tab.id}`}
              className={`tab-item ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <span style={{ marginLeft: '0.35rem' }}>{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Dashboard Tab — فقط مسیر جاری + حداکثر یک یادآور فوری */}
      {activeTab === 'dashboard' && (
        <>
          {studentProfile && !admissionRequired && studentProfile.conditional_therapy_required && (
            <StudentConditionalTherapyCard
              studentProfile={studentProfile}
              onOpened={async ({ instanceId }) => {
                if (!instanceId) return
                try {
                  await loadData()
                } catch {
                  /* ignore */
                }
                await viewInstance(instanceId)
                await loadPrimaryJourney(instanceId)
                setActiveTab('processes')
              }}
            />
          )}
          {studentProfile && !admissionRequired && (
            primaryJourneyLoading ? (
              <StudentQuestCard
                loading
                detail={primaryJourney?.detail}
                definition={primaryJourney?.definition}
                transitions={primaryJourney?.transitions}
                forms={primaryJourney?.forms}
                stepFormLocked={stepFormLockedPrimary}
                stepFormValues={stepFormValues}
                onStepFieldChange={handleStepFieldChange}
                onFormRegisterSubmit={async () => {}}
                decisionNotes={decisionNotes}
                onDecisionNotesChange={setDecisionNotes}
                onTrigger={triggerPrimaryTransition}
                onOpenProcesses={() => setActiveTab('processes')}
                extraData={studentProfile.extra_data}
                studentId={studentProfile?.id}
                courseType={studentProfile.course_type}
                onInterviewBooked={handleInterviewBooked}
                smsRefreshKey={primarySmsRefreshKey}
                registrationGate={primaryJourney?.registrationGate || introGate}
                termEndDetail={termEndDetail}
                onOpenTermEnd={openTermEndInstance}
                onGoToOnlineSessions={goToOnlineSessions}
              />
            ) : introGateClosed && !primaryJourney?.detail ? (
              <div
                className="card student-portal-alert-card student-portal-alert-card--info"
                role="status"
                data-testid="student-intro-registration-gate-closed"
                style={{ marginBottom: '1.25rem' }}
              >
                <strong className="student-portal-alert-card-title student-portal-alert-card-title--info">
                  ثبت‌نام دورهٔ آشنایی هنوز باز نشده
                </strong>
                <p className="student-portal-alert-card-p">{introGateReason}</p>
              </div>
            ) : showManualRegStart ? (
              <div
                className="card"
                style={{
                  marginBottom: '1.25rem',
                  border: '1px solid rgba(59, 130, 246, 0.35)',
                  borderRadius: '12px',
                  background: 'linear-gradient(135deg, rgba(239, 246, 255, 0.95) 0%, rgba(255, 255, 255, 0.98) 100%)',
                }}
              >
                <div className="card-header">
                  <h3 className="card-title">وضعیت فعلی</h3>
                  <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.95rem', lineHeight: 1.65, maxWidth: '46rem' }}>
                    مسیر ثبت‌نام هنوز به پروفایل وصل نشده. با دکمهٔ زیر، فرایند ثبت‌نام دورهٔ {studentProfile.course_type === 'comprehensive' ? 'جامع' : 'آشنایی'} را شروع کنید.
                  </p>
                </div>
                <div style={{ padding: '0 1.25rem 1.25rem' }}>
                  <button
                    type="button"
                    className="btn btn-primary"
                    data-testid={
                      regCodeForProfile
                        ? `student-dashboard-start-process-${regCodeForProfile}`
                        : 'student-dashboard-start-registration'
                    }
                    onClick={() => regCodeForProfile && startProcess(regCodeForProfile)}
                  >
                    شروع {regCodeForProfile ? labelProcess(regCodeForProfile) : 'فرایند ثبت‌نام'}
                  </button>
                </div>
              </div>
            ) : (
              <StudentQuestCard
                loading={false}
                detail={primaryJourney?.detail}
                definition={primaryJourney?.definition}
                transitions={primaryJourney?.transitions}
                forms={primaryJourney?.forms}
                stepFormLocked={stepFormLockedPrimary}
                stepFormValues={stepFormValues}
                onStepFieldChange={handleStepFieldChange}
                onFormRegisterSubmit={registerPrimaryStepForms}
                decisionNotes={decisionNotes}
                onDecisionNotesChange={setDecisionNotes}
                onTrigger={triggerPrimaryTransition}
                onOpenProcesses={() => setActiveTab('processes')}
                extraData={studentProfile.extra_data}
                studentId={studentProfile?.id}
                courseType={studentProfile.course_type}
                onInterviewBooked={handleInterviewBooked}
                smsRefreshKey={primarySmsRefreshKey}
                registrationGate={primaryJourney?.registrationGate || introGate}
                termEndDetail={termEndDetail}
                onOpenTermEnd={openTermEndInstance}
                onGoToOnlineSessions={goToOnlineSessions}
              />
            )
          )}

          {studentProfile?.therapy_started && !admissionRequired && (
            <StudentTherapyJourneyPanel
              studentProfile={studentProfile}
              activeProcesses={activeProcesses}
              completedProcesses={completedProcesses}
              active={activeTab === 'dashboard'}
              onStartProcess={(code) => startProcess(code)}
              onOpenSessionPayment={(id) => {
                setActiveTab('processes')
                if (id) viewInstance(id)
              }}
              onGoToOnlineSessions={goToOnlineSessions}
              onOpenTherapyCompletion={(id) => {
                setActiveTab('processes')
                if (id) viewInstance(id)
              }}
            />
          )}

          {studentProfile && !admissionRequired && primaryJourney?.detail?.instance_id && !showManualRegStart && (
            <StudentDynamicFormsSection
              instanceId={primaryJourney.detail.instance_id}
              onSubmitted={() => loadPrimaryJourney(primaryJourney.detail.instance_id)}
            />
          )}

          {studentProfile && !admissionRequired && (
            <StudentActionInbox
              items={actionInboxItems}
              loading={actionInboxLoading}
              onOpenItem={openActionInboxItem}
            />
          )}

          {dashboardUrgentAlertItems.length > 0 && (
            <div className="student-portal-alert-stack">
              <h2 className="student-portal-section-title">یادآور فوری</h2>
              {dashboardUrgentAlertItems.map(({ key, node }) => (
                <div key={key} className="student-portal-alert-item">
                  {node}
                </div>
              ))}
            </div>
          )}

        </>
      )}

      {/* Processes Tab */}
      {activeTab === 'processes' && (
        <div style={{ display: 'grid', gridTemplateColumns: selectedInstance ? '1fr 1.5fr' : '1fr', gap: '1.5rem' }}>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">همه فرایندها</h3>
            </div>

            {displayActiveProcesses.length > 0 && (
              <>
                <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--warning)', marginBottom: '0.5rem' }}>
                  فعال ({displayActiveProcesses.length})
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1.5rem' }}>
                  {displayActiveProcesses.map(p => (
                    <button
                      key={p.instance_id}
                      onClick={() => viewInstance(p.instance_id)}
                      style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '0.75rem 1rem', borderRadius: '8px', cursor: 'pointer',
                        textAlign: 'right',
                        border: selectedInstance === p.instance_id ? '2px solid var(--primary)' : '1px solid #e5e7eb',
                        background: selectedInstance === p.instance_id ? 'var(--primary-light)' : '#fff',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 500 }}>{labelProcess(p.process_code)}</div>
                        <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>وضعیت: {labelState(p.current_state)}</div>
                      </div>
                      <span className="badge badge-warning" style={{ fontSize: '0.7rem' }}>فعال</span>
                    </button>
                  ))}
                </div>
              </>
            )}

            {completedProcesses.length > 0 && (
              <>
                <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--success)', marginBottom: '0.5rem' }}>
                  تکمیل‌شده ({completedProcesses.length})
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', marginBottom: '1rem' }}>
                  {completedProcesses.slice(0, 10).map(p => (
                    <button
                      key={p.instance_id}
                      onClick={() => viewInstance(p.instance_id)}
                      style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '0.5rem 0.75rem', borderRadius: '6px', cursor: 'pointer',
                        textAlign: 'right', border: '1px solid #d1fae5', background: '#f0fdf4',
                        fontSize: '0.85rem',
                      }}
                    >
                      <span>{labelProcess(p.process_code)}</span>
                      <span className="badge badge-success" style={{ fontSize: '0.65rem' }}>تکمیل</span>
                    </button>
                  ))}
                </div>
              </>
            )}

            {displayActiveProcesses.length === 0 && completedProcesses.length === 0 && (
              <div className="empty-state" style={{ padding: '2rem' }}>
                <p>فرایندی ثبت نشده است</p>
              </div>
            )}
          </div>

          {/* Instance Detail Panel */}
          {instanceDetail && (
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">
                  {labelProcess(instanceDetail.process_code)}
                </h3>
                <button onClick={() => {
                  setSelectedInstance(null)
                  setInstanceDetail(null)
                  setProcessDefinition(null)
                  setReviewRoadmapFocus(null)
                }}
                  className="btn btn-outline btn-sm">بستن</button>
              </div>

              {instanceGuidance && (
                <div style={{ padding: '0 0 1rem' }}>
                  <StudentProcessGuidancePanel guidance={instanceGuidance} variant="light" />
                </div>
              )}

              {typeof instanceDetail.context_data?.student_portal_alert_fa === 'string'
                && instanceDetail.context_data.student_portal_alert_fa.trim() && (
                <div
                  role="alert"
                  style={{
                    marginBottom: '1.25rem',
                    padding: '1rem 1.25rem',
                    borderRadius: '10px',
                    borderRight: '4px solid #d97706',
                    background: 'linear-gradient(135deg, #fffbeb 0%, #fff7ed 100%)',
                    fontSize: '0.9rem',
                    lineHeight: 1.75,
                    color: '#78350f',
                  }}
                >
                  <strong style={{ display: 'block', marginBottom: '0.35rem' }}>توجه</strong>
                  {instanceDetail.context_data.student_portal_alert_fa}
                </div>
              )}

              {processDefinition && roadmapStates.length > 0 && (
                <div style={{ marginBottom: '1.5rem' }}>
                  <h4 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.75rem' }}>مسیر این فرایند</h4>
                  <div style={{ marginBottom: '0.5rem', fontSize: '0.75rem', color: '#6b7280' }}>
                    پیشرفت تقریبی مسیر: {roadmapProgress}%
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
                    {roadmapStates.map((st, i) => {
                      const curIdx = roadmapStates.findIndex(s => s.code === instanceDetail.current_state)
                      const isCurrent = st.code === instanceDetail.current_state
                      const past = curIdx >= 0 && i < curIdx
                      return (
                        <div key={st.code} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          <div
                            role={past ? 'button' : undefined}
                            tabIndex={past ? 0 : undefined}
                            onClick={past ? () => setReviewRoadmapFocus(st.code) : undefined}
                            onKeyDown={past ? (e) => {
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault()
                                setReviewRoadmapFocus(st.code)
                              }
                            } : undefined}
                            style={{
                              padding: '0.35rem 0.6rem', borderRadius: '8px', fontSize: '0.78rem', fontWeight: isCurrent ? 700 : 500,
                              background: isCurrent ? 'var(--primary-light)' : past ? '#ecfdf5' : '#f3f4f6',
                              border: isCurrent ? '2px solid var(--primary)' : '1px solid #e5e7eb',
                              cursor: past ? 'pointer' : 'default',
                            }}
                            title={past ? 'مشاهدهٔ همان مرحله در حالت مرور (فقط خواندنی)' : undefined}
                          >
                            {i + 1}. {st.name_fa || st.code}
                          </div>
                          {i < roadmapStates.length - 1 && <span style={{ color: '#9ca3af' }}>→</span>}
                        </div>
                      )
                    })}
                  </div>
                  {nextStepHintBox && (
                    <div style={{ marginTop: '1rem', padding: '0.75rem 1rem', background: '#fffbeb', borderRadius: '8px', borderRight: '4px solid #f59e0b', fontSize: '0.85rem', lineHeight: 1.7 }}>
                      <strong style={{ color: '#b45309' }}>راهنمای قدم بعد:</strong>{' '}
                      {nextStepHintBox}
                    </div>
                  )}
                </div>
              )}

              <StudentProcessStepReview
                detail={instanceDetail}
                definition={processDefinition}
                focusStateCode={reviewRoadmapFocus}
                onFocusConsumed={consumeReviewRoadmapFocus}
              />

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
                  <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>وضعیت فعلی</label>
                  <div style={{ fontWeight: 700, color: 'var(--primary)', fontSize: '0.95rem' }}>{labelState(instanceDetail.current_state)}</div>
                </div>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
                  <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>تاریخ شروع</label>
                  <div style={{ fontWeight: 500 }}>{instanceDetail.started_at ? new Date(instanceDetail.started_at).toLocaleDateString('fa-IR') : '-'}</div>
                </div>
                <div style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px' }}>
                  <label style={{ fontSize: '0.7rem', color: '#6b7280', display: 'block', marginBottom: '0.25rem' }}>وضعیت کلی</label>
                  {instanceDetail.is_completed
                    ? <span className="badge badge-success">تکمیل‌شده</span>
                    : instanceDetail.is_cancelled
                      ? <span className="badge badge-danger">لغو شده</span>
                      : <span className="badge badge-warning">در جریان</span>
                  }
                </div>
              </div>

              <StudentSmsHistorySection
                className="student-sms-history--process-tab"
                refreshKey={processSmsRefreshKey}
              />

              <InstanceContextSummary
                contextData={instanceDetail.context_data}
                history={instanceDetail.history}
                forms={instanceForms}
                extraLabelForms={instanceContextExtraLabelForms}
                portalRole={user?.role}
                instanceDetail={instanceDetail}
                showTechnicalContext={user?.role === 'admin'}
                showOperatorCaseFacts={false}
                title="پرونده و سابقه (قبل از اقدام)"
              />

              <ProcessRestartSection
                user={user}
                instanceDetail={instanceDetail}
                onRestart={handleProcessRestart}
                busy={restartBusy}
              />

              {instanceDetail.process_code === 'session_payment' && !instanceDetailDone && (
                <>
                  <div style={{ marginBottom: '1.25rem' }}>
                    <StudentSessionPaymentPanel
                      detail={instanceDetail}
                      stepFormValues={stepFormValues}
                      active={activeTab === 'processes'}
                    />
                  </div>
                  {instanceDetail.current_state === 'awaiting_payment' && studentProfile?.id && (() => {
                    const ctx = instanceDetail.context_data || {}
                    const amountRial = ctx.payment_amount_rial != null
                      ? Number(ctx.payment_amount_rial)
                      : Math.round(Number(ctx.invoice_amount || 0) * 10)
                    return (
                      <div style={{ marginBottom: '1.25rem' }} data-testid="student-process-tab-sep-payment">
                        <SepPaymentPanel
                          instanceId={instanceDetail.instance_id}
                          studentId={studentProfile.id}
                          amountRial={amountRial}
                          description="پرداخت جلسات درمان آموزشی"
                        />
                      </div>
                    )
                  })()}
                </>
              )}

              {instanceDetail.process_code === 'attendance_tracking' && studentProfile?.therapy_started && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentTherapyHoursPanel
                    therapyHoursProgressFa={studentProfile.therapy_hours_progress_fa}
                    active={activeTab === 'processes'}
                    compact
                  />
                </div>
              )}

              {instanceDetail.process_code === 'therapy_completion' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentTherapyCompletionPanel
                    detail={instanceDetail}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'therapy_session_reduction' && !instanceDetailDone && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentTherapyReductionPanel
                    detail={instanceDetail}
                    stepFormValues={stepFormValues}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'therapy_interruption' && !instanceDetailDone && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentTherapyInterruptionPanel
                    detail={instanceDetail}
                    stepFormValues={stepFormValues}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'student_session_cancellation' && !instanceDetailDone && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentSessionCancellationPanel
                    detail={instanceDetail}
                    stepFormValues={stepFormValues}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'student_supervision_cancellation' && !instanceDetailDone && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentSupervisionCancellationPanel
                    detail={instanceDetail}
                    stepFormValues={stepFormValues}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'supervisor_session_cancellation' && !instanceDetailDone && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <SupervisorSessionCancellationPanel
                    detail={instanceDetail}
                    stepFormValues={stepFormValues}
                    active={activeTab === 'processes'}
                    portalRole="student"
                  />
                </div>
              )}

              {instanceDetail.process_code === 'supervision_session_increase' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentSupervisionSessionIncreasePanel
                    detail={instanceDetail}
                    stepFormValues={stepFormValues}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'supervision_session_reduction' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentSupervisionSessionReductionPanel
                    detail={instanceDetail}
                    stepFormValues={stepFormValues}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'supervision_interruption' && !instanceDetailDone && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentSupervisionInterruptionPanel
                    detail={instanceDetail}
                    stepFormValues={stepFormValues}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'extra_supervision_session' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentExtraSupervisionSessionPanel
                    detail={instanceDetail}
                    stepFormValues={stepFormValues}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'introductory_course_registration' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentIntroductoryCourseRegistrationPanel
                    detail={instanceDetail}
                    stepFormValues={stepFormValues}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'comprehensive_course_registration' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentComprehensiveCourseRegistrationPanel
                    detail={instanceDetail}
                    stepFormValues={stepFormValues}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'introductory_term_end' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentIntroductoryTermEndPanel
                    detail={instanceDetail}
                    extraData={studentProfile?.extra_data}
                    active={activeTab === 'processes'}
                    studentId={studentProfile?.id}
                    activeProcesses={activeProcesses}
                    onGoToProfile={() => setActiveTab('profile')}
                    onGoToProcesses={() => setActiveTab('processes')}
                    onViewInstance={openTermEndInstance}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'comprehensive_term_end' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentComprehensiveTermEndPanel
                    detail={instanceDetail}
                    extraData={studentProfile?.extra_data}
                    active={activeTab === 'processes'}
                    studentId={studentProfile?.id}
                    activeProcesses={activeProcesses}
                    onGoToProfile={() => setActiveTab('profile')}
                    onGoToProcesses={() => setActiveTab('processes')}
                    onViewInstance={openTermEndInstance}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'intro_second_semester_registration' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentIntroSecondSemesterRegistrationPanel
                    detail={instanceDetail}
                    stepFormValues={stepFormValues}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'comprehensive_term_start' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentComprehensiveTermStartPanel
                    detail={instanceDetail}
                    studentProfile={studentProfile}
                    stepFormValues={stepFormValues}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'lesson_start_per_term' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentLessonStartPerTermPanel
                    detail={instanceDetail}
                    studentProfile={studentProfile}
                    stepFormValues={stepFormValues}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'class_attendance' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentClassAttendancePanel
                    detail={instanceDetail}
                    studentProfile={studentProfile}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'student_non_registration' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentNonRegistrationPanel
                    detail={instanceDetail}
                    activeProcesses={activeProcesses}
                    active={activeTab === 'processes'}
                    onStartLeave={() => startProcess('educational_leave')}
                    onStartFullLeave={() => startProcess('full_education_leave')}
                    onGoToRegistration={(p) => viewInstance(p.instance_id)}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'student_instructor_evaluation' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentInstructorEvaluationPanel
                    detail={instanceDetail}
                    instanceId={selectedInstance}
                    studentProfile={studentProfile}
                    active={activeTab === 'processes'}
                    showToast={showToast}
                    onRefreshInstance={() => viewInstance(selectedInstance)}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'violation_registration' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentViolationRegistrationPanel
                    detail={instanceDetail}
                    extraData={studentProfile?.extra_data || instanceDetail?.student_extra_data}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'intern_bulk_patient_referral' && !instanceDetailDone && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentInternBulkPatientReferralPanel
                    detail={instanceDetail}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'introductory_course_completion' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentIntroductoryCourseCompletionPanel
                    detail={instanceDetail}
                    extraData={studentProfile?.extra_data}
                    active={activeTab === 'processes'}
                    onGoToProfile={() => setActiveTab('profile')}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'article_writing_completion' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentArticleWritingCompletionPanel
                    detail={instanceDetail}
                    active={activeTab === 'processes'}
                    onOpenProcesses={() => setActiveTab('processes')}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'ta_track_completion' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <TaTrackCompletionInstancePanel
                    detail={instanceDetail}
                    portalRole="student"
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'film_observation_course_completion' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentFilmObservationCourseCompletionPanel
                    detail={instanceDetail}
                    instanceId={selectedInstance}
                    showToast={showToast}
                    onRefreshInstance={() => viewInstance(selectedInstance)}
                    stepFormValues={stepFormValues}
                    onFieldChange={handleStepFieldChange}
                    stepFormLocked={stepFormLockedProcess}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'live_therapy_observation_course_completion' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentLiveTherapyObservationCourseCompletionPanel
                    detail={instanceDetail}
                    instanceId={selectedInstance}
                    showToast={showToast}
                    onRefreshInstance={() => viewInstance(selectedInstance)}
                    stepFormValues={stepFormValues}
                    onFieldChange={handleStepFieldChange}
                    stepFormLocked={stepFormLockedProcess}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'skills_course_completion' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentSkillsCourseCompletionPanel
                    detail={instanceDetail}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'theory_course_completion' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentTheoryCourseCompletionPanel
                    detail={instanceDetail}
                    instanceId={selectedInstance}
                    availableTransitions={availableTransitions}
                    showToast={showToast}
                    onRefreshInstance={() => viewInstance(selectedInstance)}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'group_supervision_course_completion' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentGroupSupervisionCourseCompletionPanel
                    detail={instanceDetail}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'live_supervision_course_completion' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentLiveSupervisionCoursePanel
                    detail={instanceDetail}
                    extraData={studentProfile?.extra_data}
                    active={activeTab === 'processes'}
                  />
                  <StudentLiveSupervisionMirrorWritePanel
                    detail={instanceDetail}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'thesis_defense_request' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentThesisDefenseRequestPanel
                    detail={instanceDetail}
                    extraData={studentProfile?.extra_data}
                    active={activeTab === 'processes'}
                    onGoToProfile={() => setActiveTab('profile')}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'extra_supervision_session'
                && !instanceDetailDone
                && instanceDetail.current_state === 'payment_required'
                && studentProfile?.id && (() => {
                  const ctx = instanceDetail.context_data || {}
                  const amountRial = ctx.payment_amount_rial != null
                    ? Number(ctx.payment_amount_rial)
                    : Math.round(Number(ctx.invoice_amount || 0) * 10)
                  return (
                    <div style={{ marginBottom: '1.25rem' }} data-testid="student-extra-supervision-sep-payment">
                      <SepPaymentPanel
                        instanceId={instanceDetail.instance_id}
                        studentId={studentProfile.id}
                        amountRial={amountRial}
                        description="پرداخت جلسه اضافی سوپرویژن"
                      />
                    </div>
                  )
                })()}

              {instanceDetail.process_code === 'supervisor_session_cancellation'
                && !instanceDetailDone
                && instanceDetail.current_state === 'payment_pending'
                && studentProfile?.id && (() => {
                  const ctx = instanceDetail.context_data || {}
                  const amountRial = ctx.payment_amount_rial != null
                    ? Number(ctx.payment_amount_rial)
                    : Math.round(Number(ctx.invoice_amount || ctx.session_fee_toman || 0) * 10)
                  return (
                    <div style={{ marginBottom: '1.25rem' }} data-testid="student-supervisor-cancel-sep-payment">
                      <SepPaymentPanel
                        instanceId={instanceDetail.instance_id}
                        studentId={studentProfile.id}
                        amountRial={amountRial > 0 ? amountRial : undefined}
                        description="پرداخت جلسه جبرانی سوپرویژن"
                      />
                    </div>
                  )
                })()}

              {instanceDetail.process_code === 'supervision_block_transition' && !instanceDetailDone && (
                <>
                  <div style={{ marginBottom: '1.25rem' }}>
                    <StudentSupervisionBlockTransitionPanel
                      detail={instanceDetail}
                      stepFormValues={stepFormValues}
                      extraData={studentProfile?.extra_data}
                      studentId={studentProfile?.id}
                      active={activeTab === 'processes'}
                    />
                  </div>
                  {['slot_selected', 'new_block_first_paid'].includes(instanceDetail.current_state)
                    && studentProfile?.id && (() => {
                      const ctx = instanceDetail.context_data || {}
                      const amountRial = ctx.payment_amount_rial != null
                        ? Number(ctx.payment_amount_rial)
                        : Math.round(Number(ctx.invoice_amount || 0) * 10)
                      const desc = instanceDetail.current_state === 'slot_selected'
                        ? 'پرداخت جلسه اول دوره سوپرویژن جدید'
                        : 'پرداخت جلسه ۵۰ام دوره سوپرویژن فعلی'
                      return (
                        <div style={{ marginBottom: '1.25rem' }} data-testid="student-supervision-block-sep-payment">
                          <SepPaymentPanel
                            instanceId={instanceDetail.instance_id}
                            studentId={studentProfile.id}
                            amountRial={amountRial}
                            description={desc}
                          />
                        </div>
                      )
                    })()}
                </>
              )}

              {(instanceDetail.process_code === 'committees_review'
                || instanceDetail.process_code === 'specialized_commission_review')
                && !instanceDetailDone && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentCommitteesRestartPanel
                    detail={instanceDetail}
                    studentId={studentProfile?.id}
                    active={activeTab === 'processes'}
                    showToast={showToast}
                    onAfterStart={() => {
                      if (selectedInstance) viewInstance(selectedInstance)
                      loadData()
                    }}
                  />
                </div>
              )}

              {(instanceDetail.process_code === 'fee_determination'
                || instanceDetail.process_code === 'attendance_tracking'
                || instanceDetail.process_code === 'student_session_cancellation')
                && studentProfile?.therapy_started && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentFeeDeterminationPanel active={activeTab === 'processes'} compact />
                </div>
              )}

              {instanceDetail.process_code === 'internship_readiness_consultation' && !instanceDetailDone && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentInternshipReadinessConsultationPanel
                    detail={instanceDetail}
                    studentProfile={studentProfile}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'upgrade_to_educational_therapist' && !instanceDetailDone && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentEducationalTherapistUpgradePanel
                    detail={instanceDetail}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'start_therapy' && !instanceDetailDone && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentStartTherapyPanel
                    detail={instanceDetail}
                    studentProfile={studentProfile}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'return_to_full_education' && !instanceDetailDone && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentReturnToFullEducationPanel
                    detail={instanceDetail}
                    studentProfile={studentProfile}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'full_education_leave' && !instanceDetailDone && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentFullEducationLeavePanel
                    detail={instanceDetail}
                    active={activeTab === 'processes'}
                    canStartReturn={canStartProcess('return_to_full_education', {
                      studentProfile,
                      activeProcesses,
                      completedProcesses,
                    }).ok}
                    onStartReturn={() => startProcess('return_to_full_education')}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'upgrade_to_ta' && !instanceDetailDone && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentUpgradeToTaPanel
                    detail={instanceDetail}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'ta_track_change' && !instanceDetailDone && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentTaTrackChangePanel
                    detail={instanceDetail}
                    studentProfile={studentProfile}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {instanceDetail.process_code === 'ta_to_instructor_auto' && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <StudentTaToInstructorAutoPanel
                    detail={instanceDetail}
                    extraData={studentProfile?.extra_data}
                    active={activeTab === 'processes'}
                  />
                </div>
              )}

              {filterFormsForStudent(instanceForms || []).length > 0 && stepFormLockedProcess
                && instanceDetail.process_code !== 'film_observation_course_completion'
                && instanceDetail.process_code !== 'student_instructor_evaluation' && (
                <div className="psf-locked-banner" role="status" style={{
                  marginBottom: '1.25rem', padding: '1rem 1.25rem', borderRadius: '10px',
                  background: 'linear-gradient(135deg, #ecfdf5 0%, #f0fdf4 100%)',
                  borderRight: '4px solid #16a34a', fontSize: '0.9rem', lineHeight: 1.7,
                }}>
                  اطلاعات این مرحله قبلاً ثبت شده است. برای ویرایش، مسئول مربوط (اداری) باید از پنل کارمندان، امکان ویرایش را برای شما باز کند؛ سپس همین صفحه را تازه کنید.
                </div>
              )}
              {!stepFormLockedProcess
                && instanceDetail.process_code !== 'film_observation_course_completion'
                && instanceDetail.process_code !== 'student_instructor_evaluation' && (
                <>
                  <ProcessStepForms
                    forms={instanceForms}
                    values={stepFormValues}
                    onFieldChange={handleStepFieldChange}
                    disabled={false}
                    hasAvailableTransitions={(availableTransitions?.length || 0) > 0}
                    instanceId={selectedInstance}
                    resubmitFieldNames={docsResubmitProcess || null}
                    contextData={instanceDetail?.context_data}
                    currentState={instanceDetail?.current_state}
                    onRegisterSubmit={async ({ ok, missing }) => {
                      if (!ok) {
                        showToast(`موارد ناقص: ${missing.join('، ')}`, 'error')
                        return
                      }
                      if (!selectedInstance) {
                        showToast('فرایند انتخاب نشده است', 'error')
                        return
                      }
                      try {
                        const regRes = await processExecApi.registerStudentStepForms(selectedInstance, { form_values: stepFormValues })
                        await viewInstance(selectedInstance)
                        if (regRes.data?.auto_advanced_to_documents_review) {
                          showToast(
                            'مدارک در پرونده ثبت شد و به‌صورت خودکار برای بررسی پذیرش ارسال شد. در پنل کارمند در «بررسی مدارک» دیده می‌شود.',
                            'success',
                          )
                        } else {
                          showToast(
                            'اطلاعات این مرحله ثبت شد. اگر دکمهٔ «ادامه و ثبت مرحله» را می‌بینید همان را بزنید تا پرونده برای پذیرش برود؛ در غیر این صورت منتظر اقدام اداری بمانید.',
                            'success',
                          )
                        }
                      } catch (e) {
                        const d = e.response?.data?.detail
                        if (d && typeof d === 'object' && Array.isArray(d.missing)) {
                          showToast(`موارد ناقص: ${d.missing.join('، ')}`, 'error')
                        } else {
                          showToast(typeof d === 'string' ? d : (e.message || 'خطا در ثبت'), 'error')
                        }
                      }
                    }}
                  />
                  {processTransitionBlocked && (availableTransitions?.length || 0) > 0
                    && filterFormsForStudent(instanceForms || []).length > 0 && (
                    <p
                      style={{
                        fontSize: '0.82rem',
                        color: '#b45309',
                        marginTop: '0.75rem',
                        marginBottom: '1rem',
                        lineHeight: 1.6,
                      }}
                    >
                      ابتدا فرم بالا را تکمیل کنید؛ سپس دکمهٔ ثبت مرحله در همین پنل ظاهر می‌شود.
                    </p>
                  )}
                </>
              )}

              {/* Available Actions — یک دکمه؛ چند مسیر = انتخابگر + همان دکمه */}
              {showProcessTransitionCta && selectedProcessTransition && (
                <div
                  style={{
                    padding: '1.25rem', background: 'linear-gradient(135deg, var(--primary-light) 0%, #f0f4ff 100%)',
                    borderRadius: '10px', marginBottom: '1.5rem', borderRight: '4px solid var(--primary)',
                  }}
                  data-testid="process-detail-transition-block"
                >
                  <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.5rem', color: 'var(--primary)' }}>
                    قدم بعد در مسیر
                  </h4>
                  <p style={{ fontSize: '0.8rem', color: '#475569', marginBottom: '0.85rem', lineHeight: 1.75 }}>
                    {STUDENT_TRANSITION_CTA_INTRO}
                  </p>
                  {availableTransitions.length > 1 && (
                    <div style={{ marginBottom: '0.85rem' }}>
                      <label
                        htmlFor="process-detail-transition-select"
                        style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, marginBottom: '0.35rem', color: 'var(--text-secondary)' }}
                      >
                        انتخاب مسیر بعدی
                      </label>
                      <select
                        id="process-detail-transition-select"
                        data-testid="process-detail-transition-select"
                        value={Math.min(selectedProcessTransitionIdx, availableTransitions.length - 1)}
                        onChange={(e) => setSelectedProcessTransitionIdx(Number(e.target.value))}
                        style={{
                          width: '100%',
                          padding: '0.5rem 0.75rem',
                          borderRadius: '8px',
                          border: '1px solid var(--border)',
                          fontSize: '0.9rem',
                          background: 'var(--bg)',
                        }}
                      >
                        {availableTransitions.map((t, idx) => (
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
                  <DecisionNotesBlock
                    value={decisionNotes}
                    onChange={setDecisionNotes}
                    title="توضیح همراه اقدام (اختیاری)"
                    hint="با زدن دکمه، این متن به‌عنوان یادداشت همراه انتقال ثبت می‌شود (با مقادیر فرم ادغام می‌شود)."
                  />
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      data-testid={`process-detail-transition-${selectedProcessTransition.to_state || selectedProcessTransition.trigger_event || selectedProcessTransitionIdx}`}
                      onClick={() => triggerTransition(selectedProcessTransition)}
                      className="btn btn-primary"
                      style={{
                        fontSize: '0.85rem',
                        display: 'inline-flex',
                        flexDirection: 'column',
                        alignItems: 'stretch',
                        gap: '0.2rem',
                      }}
                      title={getStudentTransitionTooltip(selectedProcessTransition)}
                    >
                      <span>{getStudentTransitionButtonMain(selectedProcessTransition, 1)}</span>
                      {selectedProcessTransition.to_state && (
                        <span style={{ fontSize: '0.7rem', opacity: 0.88 }}>
                          {getStudentTransitionButtonSub(selectedProcessTransition)}
                        </span>
                      )}
                    </button>
                  </div>
                </div>
              )}

            </div>
          )}
        </div>
      )}

      {/* Online sessions */}
      {activeTab === 'sessions' && (
        <StudentOnlineSessionsPanel
          studentProfile={studentProfile}
          active={activeTab === 'sessions'}
          onSessionsLoaded={handleOnlineSessionsLoaded}
        />
      )}

      {/* Assignments */}
      {activeTab === 'assignments' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">تکالیف</h3>
          </div>
          {!studentProfile ? (
            <div className="empty-state" style={{ padding: '2rem' }}>پروفایل دانشجو یافت نشد.</div>
          ) : assignments.length === 0 ? (
            <p style={{ padding: '1rem', color: 'var(--text-secondary)' }}>تکلیفی تعیین نشده است.</p>
          ) : (
            <AssignmentList assignments={assignments} showToast={showToast} />
          )}
        </div>
      )}

      {/* Request Tab — فقط وقتی مجاز است واقعاً شروع می‌شود؛ بقیه با توضیح قفل */}
      {activeTab === 'requests' && (
        <div className="card">
          <div className="card-header student-requests-card-header">
            <h3 className="card-title">درخواست‌های تکمیلی</h3>
            <div className="student-requests-header-actions">
              <button
                type="button"
                className="btn btn-primary btn-sm"
                data-testid="student-open-new-request-modal"
                onClick={() => setShowNewRequestModal(true)}
              >
                شروع درخواست جدید
              </button>
              <input
                type="text"
                placeholder="جستجو..."
                value={processFilter}
                onChange={e => setProcessFilter(e.target.value)}
                className="form-input"
                style={{ width: '250px', minWidth: '180px' }}
              />
            </div>
          </div>
          {!studentProfile ? (
            <div className="empty-state" style={{ padding: '3rem' }}>
              <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>⚠️</div>
              <p style={{ fontSize: '1.1rem', fontWeight: 500 }}>پروفایل دانشجو یافت نشد</p>
              <p style={{ marginTop: '0.5rem' }}>لطفاً با بخش اداری تماس بگیرید تا پروفایل شما ایجاد شود.</p>
            </div>
          ) : (
            <>
              <div className="requests-intro">
                <p>
                  مسیر اصلی را از <button type="button" className="link-like" onClick={() => setActiveTab('dashboard')}>داشبورد</button>
                  {' '}و کارت «مسیر فعلی» جلو ببرید. اینجا برای شروع فرایندهای جانبی (مثلاً مرخصی) است؛ اگر دکمه قفل است، علت در همان کارت نوشته شده.
                </p>
                {registrationBlocking && (
                  <div className="requests-banner" role="status">
                    فرایند ثبت‌نام دوره هنوز باز است؛ تا تکمیل آن، شروع فرایندهای دیگر از اینجا غیرفعال است. مسیر را از داشبورد جلو ببرید.
                  </div>
                )}
              </div>
              <div className="requests-grid">
                {availableProcesses
                  .filter(p => {
                    if (!processFilter) return true
                    const label = p.name_fa || labelProcess(p.code)
                    return label.includes(processFilter) || p.code.includes(processFilter)
                  })
                  .map(p => {
                    const hasActive = activeProcesses.some(a => a.process_code === p.code)
                    const { ok, reasonFa } = canStartProcess(p.code, accessCtx)
                    const canClick = !hasActive && ok
                    return (
                      <div
                        key={p.code || p.id}
                        className={`requests-card ${hasActive ? 'requests-card--active' : ''} ${!canClick && !hasActive ? 'requests-card--locked' : ''}`}
                      >
                        <div className="requests-card-title">
                          {p.name_fa || labelProcess(p.code)}
                        </div>
                        <div className="requests-card-desc">
                          {p.description || `کد: ${p.code}`}
                        </div>
                        {hasActive ? (
                          <span className="badge badge-warning">فرایند فعال دارید — از «فرایندها» ادامه دهید</span>
                        ) : canClick ? (
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            data-testid={`student-request-start-${p.code}`}
                            onClick={() => startProcess(p.code)}
                          >
                            آغاز فرایند
                          </button>
                        ) : (
                          <div className="requests-locked">
                            <span className="badge" style={{ background: '#f1f5f9', color: '#64748b' }}>قفل در این مرحله</span>
                            <p className="requests-lock-reason">{reasonFa}</p>
                          </div>
                        )}
                      </div>
                    )
                  })}
                {availableProcesses.length === 0 && (
                  <div className="empty-state" style={{ padding: '2rem', gridColumn: '1 / -1' }}>
                    <p>فرایندی تعریف نشده است</p>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* Gamification Tab */}
      {activeTab === 'gamification' && (
        <div ref={gamificationTabPanelRef} className="card gam-tab-card" id="student-gamification-panel">
          <div className="card-header">
            <h3 className="card-title">پیشرفت، رتبه و مدال‌ها</h3>
          </div>
          {studentProfile ? (
            <GamificationPanel extraData={studentProfile.extra_data} />
          ) : (
            <div className="empty-state" style={{ padding: '2rem' }}>
              <p>برای مشاهدهٔ پیشرفت، ابتدا پروفایل دانشجویی باید فعال باشد.</p>
            </div>
          )}
        </div>
      )}

      {/* Profile Tab */}
      {activeTab === 'profile' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {studentProfile && !admissionRequired && (
            primaryJourneyLoading ? (
              <StudentQuestCard
                loading
                detail={primaryJourney?.detail}
                definition={primaryJourney?.definition}
                transitions={primaryJourney?.transitions}
                forms={primaryJourney?.forms}
                stepFormLocked={stepFormLockedPrimary}
                stepFormValues={stepFormValues}
                onStepFieldChange={handleStepFieldChange}
                onFormRegisterSubmit={async () => {}}
                decisionNotes={decisionNotes}
                onDecisionNotesChange={setDecisionNotes}
                onTrigger={triggerPrimaryTransition}
                onOpenProcesses={() => setActiveTab('processes')}
                extraData={studentProfile.extra_data}
                studentId={studentProfile?.id}
                courseType={studentProfile.course_type}
                onInterviewBooked={handleInterviewBooked}
                smsRefreshKey={primarySmsRefreshKey}
                registrationGate={primaryJourney?.registrationGate || introGate}
                termEndDetail={termEndDetail}
                onOpenTermEnd={openTermEndInstance}
                hidePaidInterviewSummary
                onGoToOnlineSessions={goToOnlineSessions}
              />
            ) : introGateClosed && !primaryJourney?.detail ? (
              <div
                className="card student-portal-alert-card student-portal-alert-card--info"
                role="status"
                data-testid="student-profile-intro-registration-gate-closed"
              >
                <strong className="student-portal-alert-card-title student-portal-alert-card-title--info">
                  ثبت‌نام دورهٔ آشنایی هنوز باز نشده
                </strong>
                <p className="student-portal-alert-card-p">{introGateReason}</p>
              </div>
            ) : showManualRegStart ? (
              <div
                className="card"
                style={{
                  marginBottom: '0',
                  border: '1px solid rgba(59, 130, 246, 0.35)',
                  borderRadius: '12px',
                  background: 'linear-gradient(135deg, rgba(239, 246, 255, 0.95) 0%, rgba(255, 255, 255, 0.98) 100%)',
                }}
              >
                <div className="card-header">
                  <h3 className="card-title">مسیر ثبت‌نام</h3>
                  <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.95rem', lineHeight: 1.65, maxWidth: '46rem' }}>
                    مسیر ثبت‌نام هنوز به پروفایل وصل نشده. با دکمهٔ زیر، فرایند ثبت‌نام دورهٔ {studentProfile.course_type === 'comprehensive' ? 'جامع' : 'آشنایی'} را شروع کنید.
                  </p>
                </div>
                <div style={{ padding: '0 1.25rem 1.25rem' }}>
                  <button
                    type="button"
                    className="btn btn-primary"
                    data-testid={
                      regCodeForProfile
                        ? `student-profile-start-process-${regCodeForProfile}`
                        : 'student-profile-start-registration'
                    }
                    onClick={() => regCodeForProfile && startProcess(regCodeForProfile)}
                  >
                    شروع {regCodeForProfile ? labelProcess(regCodeForProfile) : 'فرایند ثبت‌نام'}
                  </button>
                </div>
              </div>
            ) : (
              <StudentQuestCard
                loading={false}
                detail={primaryJourney?.detail}
                definition={primaryJourney?.definition}
                transitions={primaryJourney?.transitions}
                forms={primaryJourney?.forms}
                stepFormLocked={stepFormLockedPrimary}
                stepFormValues={stepFormValues}
                onStepFieldChange={handleStepFieldChange}
                onFormRegisterSubmit={registerPrimaryStepForms}
                decisionNotes={decisionNotes}
                onDecisionNotesChange={setDecisionNotes}
                onTrigger={triggerPrimaryTransition}
                onOpenProcesses={() => setActiveTab('processes')}
                extraData={studentProfile.extra_data}
                studentId={studentProfile?.id}
                courseType={studentProfile.course_type}
                onInterviewBooked={handleInterviewBooked}
                smsRefreshKey={primarySmsRefreshKey}
                registrationGate={primaryJourney?.registrationGate || introGate}
                hidePaidInterviewSummary
                onGoToOnlineSessions={goToOnlineSessions}
              />
            )
          )}
          {studentProfile && (
            <InterviewPaidBookingSummary
              testId="student-profile-interview-booking"
              onGoToOnlineSessions={goToOnlineSessions}
            />
          )}
          {studentProfile && !admissionRequired && primaryJourney?.detail?.instance_id && !showManualRegStart && (
            <StudentDynamicFormsSection
              instanceId={primaryJourney.detail.instance_id}
              onSubmitted={() => loadPrimaryJourney(primaryJourney.detail.instance_id)}
            />
          )}
          {studentProfile && (
            <StudentAcademicCalendarPanel onOpenProcesses={() => setActiveTab('processes')} />
          )}
          {studentProfile && (
            <StudentTranscriptsPanel studentId={studentProfile.id} />
          )}
          {studentProfile && (
            <StudentCourseStatusPanel
              extraData={studentProfile.extra_data}
              activeProcesses={activeProcesses}
            />
          )}
          {studentProfile && (
            <StudentTaTrackPortfolioSection
              extraData={studentProfile.extra_data}
              active={activeTab === 'profile'}
            />
          )}
          {studentProfile?.therapy_started && (
            <StudentTherapyJourneyPanel
              studentProfile={studentProfile}
              activeProcesses={activeProcesses}
              completedProcesses={completedProcesses}
              active={activeTab === 'profile'}
              onStartProcess={(code) => startProcess(code)}
              onOpenSessionPayment={(id) => {
                setActiveTab('processes')
                if (id) viewInstance(id)
              }}
              onGoToOnlineSessions={goToOnlineSessions}
              onOpenTherapyCompletion={(id) => {
                setActiveTab('processes')
                if (id) viewInstance(id)
              }}
            />
          )}
          {studentProfile?.therapy_started && (
            <StudentTherapyHoursPanel
              therapyHoursProgressFa={studentProfile.therapy_hours_progress_fa}
              active={activeTab === 'profile'}
            />
          )}
          {studentProfile?.therapy_started && (
            <StudentSessionPaymentPanel
              detail={activeSessionPaymentInstance || (
                primaryJourney?.detail?.process_code === 'session_payment'
                  ? primaryJourney.detail
                  : null
              )}
              stepFormValues={
                primaryJourney?.detail?.process_code === 'session_payment'
                  ? stepFormValues
                  : null
              }
              active={activeTab === 'profile'}
            />
          )}
          {studentProfile?.therapy_started && (
            <StudentFeeDeterminationPanel active={activeTab === 'profile'} />
          )}
          {studentProfile && (
            <StudentFinancialPlanPanel
              studentId={studentProfile.id}
              active={activeTab === 'profile'}
            />
          )}
          {studentProfile && (
            <div className="card student-profile-summary-card">
              <div className="card-header">
                <h3 className="card-title">خلاصه وضعیت</h3>
              </div>
              <div className="student-profile-summary-grid">
                <div className="student-profile-summary-item">
                  <span className="student-profile-summary-label">فرایند فعال</span>
                  <button
                    type="button"
                    className="student-profile-summary-value link-like"
                    onClick={() => setActiveTab('processes')}
                  >
                    {activeProcesses.length.toLocaleString('fa-IR')}
                  </button>
                </div>
                <div className="student-profile-summary-item">
                  <span className="student-profile-summary-label">تکمیل‌شده</span>
                  <button
                    type="button"
                    className="student-profile-summary-value link-like"
                    onClick={() => setActiveTab('processes')}
                  >
                    {completedProcesses.length.toLocaleString('fa-IR')}
                  </button>
                </div>
                <div className="student-profile-summary-item">
                  <span className="student-profile-summary-label">ترم فعلی</span>
                  <span className="student-profile-summary-value">{studentProfile.current_term ?? '—'}</span>
                </div>
                <div className="student-profile-summary-item">
                  <span className="student-profile-summary-label">جلسه در هفته</span>
                  <span className="student-profile-summary-value">{studentProfile.weekly_sessions ?? '—'}</span>
                </div>
              </div>
            </div>
          )}
          {studentProfile && (
            <div className="card" data-testid="student-profile-learning-summary">
              <div className="card-header">
                <h3 className="card-title">کلاس و یادگیری (خلاصه)</h3>
              </div>
              <div style={{ padding: '0 1.25rem 1.25rem', fontSize: '0.92rem', lineHeight: 1.75, color: 'var(--text-secondary)' }}>
                <p style={{ margin: '0 0 0.75rem' }}>
                  <strong>جلسات آنلاین ثبت‌شده:</strong>{' '}
                  {profileLearningSummary.sessionCount.toLocaleString('fa-IR')}
                  {profileLearningSummary.nearestSession && (
                    <span>
                      {' '}
                      · نزدیک‌ترین:{' '}
                      {typeof profileLearningSummary.nearestSession === 'string' && profileLearningSummary.nearestSession.includes('T')
                        ? new Date(profileLearningSummary.nearestSession).toLocaleString('fa-IR', { dateStyle: 'medium', timeStyle: 'short' })
                        : profileLearningSummary.nearestSession}
                    </span>
                  )}
                </p>
                <p style={{ margin: '0 0 0.75rem' }}>
                  <strong>تکالیف:</strong>{' '}
                  {profileLearningSummary.assignmentCount.toLocaleString('fa-IR')}
                  {profileLearningSummary.nearestDue && (
                    <span>
                      {' '}
                      · نزدیک‌ترین مهلت:{' '}
                      {new Date(profileLearningSummary.nearestDue).toLocaleDateString('fa-IR')}
                    </span>
                  )}
                </p>
                {studentProfile.therapy_hours_progress_fa && (
                  <p style={{ margin: '0 0 0.75rem' }}>{studentProfile.therapy_hours_progress_fa}</p>
                )}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.5rem' }}>
                  <button
                    type="button"
                    className="btn btn-outline btn-sm"
                    data-testid="student-profile-goto-sessions"
                    onClick={() => {
                      setActiveTab('sessions')
                    }}
                  >
                    جلسات آنلاین
                  </button>
                  <button
                    type="button"
                    className="btn btn-outline btn-sm"
                    data-testid="student-profile-goto-assignments"
                    onClick={() => {
                      setActiveTab('assignments')
                    }}
                  >
                    تکالیف
                  </button>
                </div>
              </div>
            </div>
          )}
          {profileSecondaryAlertItems.length > 0 && (
            <div className="student-portal-alert-stack">
              <h2 className="student-portal-section-title">اعلان‌ها و وضعیت تکمیلی</h2>
              {profileSecondaryAlertItems.map(({ key, node }) => (
                <div key={key} className="student-portal-alert-item">
                  {node}
                </div>
              ))}
            </div>
          )}
          {primaryGuidance && (
            <div className="card" style={{ padding: '1rem 1.25rem' }}>
              <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.75, color: 'var(--text-secondary)' }}>
                کارت «مسیر فعلی» در بالای همین تب همان راهنما و اقدامات لازم را دارد؛ جزئیات همهٔ فرایندها را در{' '}
                <button type="button" className="link-like" onClick={() => setActiveTab('processes')}>فرایندها</button>
                {' '}و در{' '}
                <button type="button" className="link-like" onClick={() => setActiveTab('dashboard')}>داشبورد</button>
                {' '}هم می‌بینید. خلاصهٔ جلسات و تکالیف در بخش «کلاس و یادگیری» همین تب است.
              </p>
            </div>
          )}
          {studentProfile && (
            <div className="card" data-testid="student-registration-profile-card">
              <div className="card-header">
                <h3 className="card-title">اطلاعات ثبت‌نام</h3>
              </div>
              <div style={{ padding: '0 1.25rem 1.25rem' }}>
                <StudentRegistrationProfileView
                  extraData={studentProfile.extra_data}
                  email={user?.email}
                />
              </div>
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">اطلاعات شخصی</h3>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <ProfileField label="نام و نام خانوادگی" value={user?.full_name_fa || '-'} />
              <ProfileField label="نام کاربری" value={user?.username || '-'} />
              <ProfileField label="ایمیل" value={user?.email || '-'} dir="ltr" />
              <ProfileField label="شماره تماس" value={user?.phone || '-'} dir="ltr" />
              <ProfileField label="نقش" value="دانشجو" />
            </div>
          </div>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">اطلاعات تحصیلی</h3>
            </div>
            {studentProfile ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <ProfileField label="کد دانشجویی" value={formatStudentCodeDisplay(studentProfile.student_code)} />
                <ProfileField label="نوع دوره" value={studentProfile.course_type === 'comprehensive' ? 'جامع' : 'آشنایی'} />
                <ProfileField label="ترم فعلی" value={`${studentProfile.current_term} از ${studentProfile.term_count}`} />
                <ProfileField label="جلسات هفتگی" value={`${studentProfile.weekly_sessions} جلسه`} />
                <ProfileField label="درمان آغاز شده" value={studentProfile.therapy_started ? 'بله' : 'خیر'} />
                <ProfileField label="کارآموز" value={studentProfile.is_intern ? 'بله' : 'خیر'} />
              </div>
            ) : (
              <div className="empty-state" style={{ padding: '2rem' }}>
                <p>پروفایل دانشجو هنوز ایجاد نشده است</p>
              </div>
            )}
          </div>
          </div>
          {studentProfile?.extra_data?.primary_instance_id && (
            <StudentProfileDocumentsSection instanceId={studentProfile.extra_data.primary_instance_id} />
          )}
        </div>
      )}
    </div>
  )
}

function AssignmentList({ assignments, showToast }) {
  const [texts, setTexts] = useState({})
  const submit = async (id) => {
    try {
      await assignmentApi.submit(id, { body_text: texts[id] || '' })
      showToast('تکلیف ارسال شد')
    } catch (e) {
      showToast(e.response?.data?.detail || 'خطا', 'error')
    }
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {assignments.map(a => (
        <div key={a.id} style={{ padding: '1rem', border: '1px solid var(--border)', borderRadius: '8px' }}>
          <div style={{ fontWeight: 600 }}>{a.title_fa}</div>
          {a.description && <p style={{ fontSize: '0.85rem', marginTop: '0.5rem' }}>{a.description}</p>}
          {a.due_at && (
            <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
              مهلت: {new Date(a.due_at).toLocaleDateString('fa-IR')}
            </div>
          )}
          <textarea
            value={texts[a.id] || ''}
            onChange={e => setTexts({ ...texts, [a.id]: e.target.value })}
            placeholder="پاسخ یا توضیح تکلیف..."
            style={{
              width: '100%', marginTop: '0.75rem', minHeight: '80px', padding: '0.5rem',
              borderRadius: '6px', border: '1px solid #d1d5db', fontFamily: 'inherit',
            }}
          />
          <button type="button" className="btn btn-primary btn-sm" style={{ marginTop: '0.5rem' }} onClick={() => submit(a.id)}>
            ارسال تکلیف
          </button>
        </div>
      ))}
    </div>
  )
}

function ProfileField({ label, value, dir }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '0.75rem 1rem', background: 'var(--bg)', borderRadius: '8px',
    }}>
      <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 500 }}>{label}</span>
      <span style={{ fontWeight: 600, direction: dir || 'rtl' }}>{value}</span>
    </div>
  )
}
