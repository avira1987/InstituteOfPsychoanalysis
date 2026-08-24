import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { useParams, useSearchParams, Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { usePortalInstanceDeepLink } from '../hooks/usePortalInstanceDeepLink'
import { useProcessCodeUrlFilter } from '../hooks/useProcessCodeUrlFilter'
import { processExecApi, studentApi, userApi, auditApi, assignmentApi, panelApi, semesterPrepApi } from '../services/api'
import { mergeInterviewBranchPayload } from '../utils/transitionInterviewPayload'
import {
  mergeInterviewResultFormPayload,
} from '../utils/interviewResultPayload'
import {
  canSubmitInterviewResult,
  filterInterviewResultTransitions,
} from '../utils/interviewResultAccess'
import { notesPayload } from '../utils/decisionPayload'
import { mergeEducationalLeaveTriggerPayload } from '../utils/educationalLeaveTriggerPayload'
import { mergeFullEducationLeaveTriggerPayload } from '../utils/fullEducationLeaveTriggerPayload'
import { mergeReferralTriggerPayload } from '../utils/internBulkPatientReferralTriggerPayload'
import { mergeLiveSessionPrepTriggerPayload } from '../utils/liveSessionPrepTriggerPayload'
import { mergeMentorPrivateSessionsTriggerPayload } from '../utils/mentorPrivateSessionsTriggerPayload'
import { mergeUpgradeToTaTriggerPayload } from '../utils/upgradeToTaTriggerPayload'
import { mergeTaTrackChangeTriggerPayload } from '../utils/taTrackChangeTriggerPayload'
import LiveSessionPrepPanel from '../components/LiveSessionPrepPanel'
import TaUpgradeCourseCommitteePanel from '../components/TaUpgradeCourseCommitteePanel'
import StudentTaTrackChangePanel from '../components/StudentTaTrackChangePanel'
import TaTrackChangeCommitteePanel from '../components/TaTrackChangeCommitteePanel'
import { labelProcess, labelState, formatStudentCodeDisplay, formatStudentFullNameFa } from '../utils/processDisplay'
import { operatorDocumentReviewToastFa } from '../utils/documentReviewStates'
import { useToast } from '../contexts/ToastContext'
import InterviewSlotsManageSection from '../components/InterviewSlotsManageSection'
import EducationalTherapistSlotsAdmin from '../components/EducationalTherapistSlotsAdmin'
import DocumentsReviewPanel from '../components/DocumentsReviewPanel'
import OperatorPortalReminderBanner from '../components/OperatorPortalReminderBanner'
import OperatorFollowupSection from '../components/OperatorFollowupSection'
import OperatorProcessInstancePanel from '../components/OperatorProcessInstancePanel'
import Supervision50hCompletionPanel from '../components/Supervision50hCompletionPanel'
import InstructorLessonAttendancePanel from '../components/InstructorLessonAttendancePanel'
import InstructorClassSessionCancellationPanel from '../components/InstructorClassSessionCancellationPanel'
import InstructorClassAttendanceInboxHint from '../components/InstructorClassAttendanceInboxHint'
import LiveTherapyObservationTaAttendancePanel from '../components/LiveTherapyObservationTaAttendancePanel'
import FilmObservationTaAttendancePanel from '../components/FilmObservationTaAttendancePanel'
import FilmObservationCourseCompletionPanel from '../components/FilmObservationCourseCompletionPanel'
import LiveTherapyObservationCourseCompletionPanel from '../components/LiveTherapyObservationCourseCompletionPanel'
import SkillsCourseCompletionPanel from '../components/SkillsCourseCompletionPanel'
import TheoryCourseCompletionPanel from '../components/TheoryCourseCompletionPanel'
import GroupSupervisionCourseCompletionPanel from '../components/GroupSupervisionCourseCompletionPanel'
import TaEssayUploadPanel from '../components/TaEssayUploadPanel'
import MentorPrivateSessionsPanel from '../components/MentorPrivateSessionsPanel'
import TaConceptualQuestionsPanel from '../components/TaConceptualQuestionsPanel'
import ArticleWritingCompletionPanel from '../components/ArticleWritingCompletionPanel'
import LiveSupervisionCourseCompletionPanel from '../components/LiveSupervisionCourseCompletionPanel'
import LiveSupervisionDualAttendancePanel from '../components/LiveSupervisionDualAttendancePanel'
import LiveSupervisionMirrorEvalPanel from '../components/LiveSupervisionMirrorEvalPanel'
import LiveSupervisionFinalEvalPanel from '../components/LiveSupervisionFinalEvalPanel'
import IntroductoryTermEndFollowupPanel from '../components/IntroductoryTermEndFollowupPanel'
import AcademicDeclineFollowupForm from '../components/AcademicDeclineFollowupForm'
import InternBulkPatientReferralCoordinationPanel from '../components/InternBulkPatientReferralCoordinationPanel'
import TaClassDutiesPanel from '../components/TaClassDutiesPanel'
import TherapistAssignmentReviewPanel from '../components/TherapistAssignmentReviewPanel'
import TaToAssistantFacultyTaPanel from '../components/TaToAssistantFacultyTaPanel'
import TaToInstructorAutoReportPanel from '../components/TaToInstructorAutoReportPanel'
import ResolvedProcessHistoryBanner from '../components/ResolvedProcessHistoryBanner'
import CourseCommitteePrepPanel from '../components/CourseCommitteePrepPanel'
import CourseCommitteeRosterPanel from '../components/CourseCommitteeRosterPanel'
import InstructionSemesterCoursesPanel from '../components/InstructionSemesterCoursesPanel'
import InstructionTaPortfolioPanel from '../components/InstructionTaPortfolioPanel'
import TaTrackCompletionInstancePanel from '../components/TaTrackCompletionInstancePanel'
import InstructorEvaluationResultsPanel from '../components/InstructorEvaluationResultsPanel'
import InstructorEvaluationCommitteePanel from '../components/InstructorEvaluationCommitteePanel'
import { formatShamsiTehran } from '../utils/shamsiDateTime'
import {
  buildStaffTabsForLane,
  getStaffLaneConfig,
  getStaffLanePath,
  stateMatchesStaffLane,
} from '../utils/portalStaffLanes'
import {
  getPendingTaskDestination,
  isSemesterPrepWorkbenchDestination,
  resolvePendingInstanceId,
} from '../utils/operatorFollowupDeepLinks'
import { resolveSemesterPrepWorkbenchHref } from '../utils/semesterPrepPortalLinks'

const STAFF_DEEP_LINK_TABS = [
  'dashboard',
  'pending',
  'students',
  'processes',
  'roster',
  'interviewSlots',
  'etTherapistSlots',
  'documentsReview',
  'onlineClasses',
  'activity',
]

const staffReviewStates = [
  'staff_review', 'staff_verification', 'pending_staff',
  'office_review', 'payment_verification', 'payment_required',
  'awaiting_payment', 'document_check',
]

export default function StaffPortal() {
  const { lane: laneParam } = useParams()
  const navigate = useNavigate()
  const lane = laneParam || 'admissions'
  const laneConfig = getStaffLaneConfig(lane) || getStaffLaneConfig('admissions')
  const portalPath = getStaffLanePath(lane)
  const isCourseCommitteeLane = lane === 'course-committee'
  const isInstructionLane = lane === 'instruction'
  const { user } = useAuth()
  const [searchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState('pending')
  const [allStudents, setAllStudents] = useState([])
  const [allUsers, setAllUsers] = useState([])
  const [pendingActions, setPendingActions] = useState([])
  const [processInboxItems, setProcessInboxItems] = useState([])
  const [operatorReadinessAlerts, setOperatorReadinessAlerts] = useState([])
  const [allActiveInstances, setAllActiveInstances] = useState([])
  const [recentLogs, setRecentLogs] = useState([])
  const [selectedInstance, setSelectedInstance] = useState(null)
  const [instanceDetail, setInstanceDetail] = useState(null)
  const [availableTransitions, setAvailableTransitions] = useState([])
  const [decisionNotes, setDecisionNotes] = useState('')
  const [interviewResultForm, setInterviewResultForm] = useState({
    interviewer_notes: '',
  })
  const [loading, setLoading] = useState(true)
  const [unlockFormsBusy, setUnlockFormsBusy] = useState(false)
  const [rollbackBusy, setRollbackBusy] = useState(false)
  const [restartBusy, setRestartBusy] = useState(false)
  const [studentSearch, setStudentSearch] = useState('')
  const [showNewStudent, setShowNewStudent] = useState(false)
  const [newStudent, setNewStudent] = useState({
    user_id: '', student_code: '', course_type: 'introductory',
    weekly_sessions: 1, term_count: 1, current_term: 1,
  })
  const [newAssignment, setNewAssignment] = useState({ student_id: '', title_fa: '', description: '' })
  const [semesterPrepProcesses, setSemesterPrepProcesses] = useState(null)
  const { showToast } = useToast()

  useEffect(() => { loadData() }, [])

  const reloadFollowup = useCallback(() => (
    panelApi
      .myOperatorFollowup()
      .then((inboxRes) => {
        const inboxItems = inboxRes.data?.items || []
        setProcessInboxItems(inboxItems)
        setOperatorReadinessAlerts(inboxRes.data?.readiness_alerts || [])
      })
      .catch(() => {
        setProcessInboxItems([])
        setOperatorReadinessAlerts([])
      })
  ), [])

  useEffect(() => {
    if (!isCourseCommitteeLane) return
    let cancelled = false
    semesterPrepApi.getStatus()
      .then((res) => {
        if (!cancelled) setSemesterPrepProcesses(res.data?.processes || {})
      })
      .catch(() => {
        if (!cancelled) setSemesterPrepProcesses({})
      })
    return () => { cancelled = true }
  }, [isCourseCommitteeLane])

  useEffect(() => {
    setInterviewResultForm({ interviewer_notes: '' })
  }, [selectedInstance, instanceDetail?.current_state])

  const loadData = async () => {
    try {
      const [studentsRes, usersRes, logsRes] = await Promise.all([
        studentApi.list().catch(() => ({ data: [] })),
        userApi.list().catch(() => ({ data: [] })),
        auditApi.list({ limit: 10, offset: 0 }).catch(() => ({ data: { logs: [] } })),
      ])
      const students = studentsRes.data || []
      setAllStudents(students)
      setAllUsers(usersRes.data || [])
      setRecentLogs(logsRes.data?.logs || [])

      const pending = []
      const allActive = []
      for (const s of students) {
        try {
          const instRes = await processExecApi.studentInstances(s.id)
          const instances = instRes.data?.instances || []
          for (const inst of instances) {
            if (!inst.is_completed && !inst.is_cancelled) {
              allActive.push({ ...inst, student_code: s.student_code, student_id: s.id })
              if (isWaitingForStaff(inst.current_state, inst.process_code)) {
                pending.push({ ...inst, student_code: s.student_code, student_id: s.id })
              }
            }
          }
        } catch { /* skip */ }
      }

      let inboxItems = []
      try {
        const inboxRes = await panelApi.myOperatorFollowup()
        inboxItems = inboxRes.data?.items || []
        setProcessInboxItems(inboxItems)
        setOperatorReadinessAlerts(inboxRes.data?.readiness_alerts || [])
      } catch {
        setProcessInboxItems([])
        setOperatorReadinessAlerts([])
      }

      const inboxProcess = inboxItems.filter((i) => i.kind === 'process')
      const ordered = []
      const seen = new Set()
      for (const i of inboxProcess) {
        ordered.push({
          instance_id: i.instance_id,
          student_id: i.student_id,
          student_code: i.student_code,
          current_state: i.state_code,
          process_code: i.process_code,
          responsible_role_code: i.responsible_role_code,
          is_completed: false,
          is_cancelled: false,
        })
        seen.add(i.instance_id)
      }
      for (const p of pending) {
        const pid = resolvePendingInstanceId(p)
        if (pid && !seen.has(pid)) ordered.push(p)
      }
      setPendingActions(ordered)
      setAllActiveInstances(allActive)
    } catch (err) {
      console.error('Load error:', err)
    } finally {
      setLoading(false)
    }
  }

  const isWaitingForStaff = (state, processCode) => {
    return stateMatchesStaffLane(state, lane, processCode)
  }

  const viewInstance = async (instanceId) => {
    if (!instanceId) return
    setSelectedInstance(instanceId)
    try {
      const [statusRes, transRes] = await Promise.all([
        processExecApi.status(instanceId),
        processExecApi.transitions(instanceId),
      ])
      setInstanceDetail(statusRes.data)
      setAvailableTransitions(transRes.data?.transitions || [])
    } catch (err) {
      console.error('View error:', err)
    }
  }

  const openPendingTask = (task) => {
    const dest = getPendingTaskDestination(task)
    if (isSemesterPrepWorkbenchDestination(dest.href)) {
      navigate(dest.href)
      return
    }
    const instanceId = resolvePendingInstanceId(task)
    if (instanceId) {
      viewInstance(instanceId)
      const allowedTabs = laneConfig?.tabIds || STAFF_DEEP_LINK_TABS
      let tab = 'pending'
      try {
        const q = dest.href.includes('?') ? dest.href.split('?')[1] : ''
        const tabParam = new URLSearchParams(q).get('tab')
        if (tabParam && allowedTabs.includes(tabParam)) tab = tabParam
      } catch { /* keep pending */ }
      setActiveTab(tab)
    }
  }

  usePortalInstanceDeepLink({
    loading,
    setActiveTab,
    viewInstance,
    allowedTabs: laneConfig?.tabIds || STAFF_DEEP_LINK_TABS,
  })

  const { processCodeFilter, filteredItems: pendingActionsFiltered } = useProcessCodeUrlFilter({
    loading,
    items: pendingActions,
    getProcessCode: (p) => p.process_code,
    getInstanceId: (p) => p.instance_id || p.id,
    viewInstance,
    setActiveTab,
    tabWhenFiltered: 'pending',
  })

  const displayPendingActions = processCodeFilter ? pendingActionsFiltered : pendingActions

  useEffect(() => {
    const sid = searchParams.get('student_id')
    if (sid) setNewAssignment(prev => ({ ...prev, student_id: sid }))
  }, [searchParams])

  const unlockStudentFormsForInstance = async () => {
    if (!selectedInstance) return
    setUnlockFormsBusy(true)
    try {
      await processExecApi.unlockStudentStepFormsEdit(selectedInstance, {})
      showToast('امکان ویرایش فرم مرحله برای دانشجو باز شد')
      await viewInstance(selectedInstance)
      loadData()
    } catch (e) {
      const d = e.response?.data?.detail
      showToast(typeof d === 'string' ? d : (e.message || 'خطا'), 'error')
    } finally {
      setUnlockFormsBusy(false)
    }
  }

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
      const sessionPrepMerge = mergeLiveSessionPrepTriggerPayload(
        instanceDetail,
        triggerEvent,
        payload,
      )
      if (sessionPrepMerge.error) {
        showToast(sessionPrepMerge.error, 'error')
        return
      }
      payload = sessionPrepMerge.payload
      const mentorMerge = mergeMentorPrivateSessionsTriggerPayload(
        instanceDetail,
        triggerEvent,
        payload,
      )
      if (mentorMerge.error) {
        showToast(mentorMerge.error, 'error')
        return
      }
      payload = mentorMerge.payload
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
      const effectiveToState = payload.to_state || toState
      payload = mergeInterviewBranchPayload(payload, effectiveToState, triggerEvent)
      payload = mergeInterviewResultFormPayload(
        payload,
        interviewResultForm,
        toState,
        triggerEvent,
      )
      if (effectiveToState) payload.to_state = effectiveToState
      const res = await processExecApi.trigger(selectedInstance, {
        trigger_event: triggerEvent,
        payload,
        ...(effectiveToState ? { to_state: effectiveToState } : {}),
      })
      if (res.data.success) {
        showToast(
          operatorDocumentReviewToastFa(triggerEvent, {
            studentCodeDisplay: formatStudentCodeDisplay(instanceDetail?.student_code),
            toStateLabel: labelState(res.data.to_state),
          }) || `عملیات انجام شد: ${labelState(res.data.to_state)}`,
        )
        viewInstance(selectedInstance)
        loadData()
      } else {
        showToast(res.data.error || 'خطا', 'error')
      }
    } catch (err) {
      showToast(err.response?.data?.detail || 'خطا', 'error')
    }
  }

  const handleCreateAssignment = async () => {
    if (!newAssignment.student_id || !newAssignment.title_fa) {
      showToast('شناسه دانشجو و عنوان تکلیف الزامی است', 'error')
      return
    }
    try {
      await assignmentApi.create({
        student_id: newAssignment.student_id,
        title_fa: newAssignment.title_fa,
        description: newAssignment.description || undefined,
      })
      showToast('تکلیف ثبت شد')
      setNewAssignment({ student_id: '', title_fa: '', description: '' })
    } catch (e) {
      showToast(e.response?.data?.detail || 'خطا', 'error')
    }
  }

  const handleCreateStudent = async () => {
    try {
      await studentApi.create(newStudent)
      showToast('دانشجو با موفقیت ایجاد شد')
      setShowNewStudent(false)
      setNewStudent({ user_id: '', student_code: '', course_type: 'introductory', weekly_sessions: 1, term_count: 1, current_term: 1 })
      loadData()
    } catch (err) {
      showToast(err.response?.data?.detail || 'خطا در ایجاد دانشجو', 'error')
    }
  }

  /** باید قبل از هر return زودهنگام باشد — وگرنه تعداد هوک‌ها بین رندرها عوض می‌شود (React #310). */
  const documentReviewQueue = useMemo(
    () =>
      allActiveInstances.filter(
        i =>
          i.process_code === 'introductory_course_registration' &&
          ['documents_review', 'documents_incomplete'].includes(i.current_state),
      ),
    [allActiveInstances],
  )

  const tabs = useMemo(
    () => buildStaffTabsForLane(lane, {
      pending: displayPendingActions.length,
      documentsReview: documentReviewQueue.length,
    }),
    [lane, displayPendingActions.length, documentReviewQueue.length],
  )

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '4rem' }}>
        <div className="loading-spinner" />
      </div>
    )
  }

  const studentUserIds = new Set(allStudents.map(s => s.user_id))
  const nonStudentUsers = allUsers.filter(u => !studentUserIds.has(u.id) && u.role === 'student')

  const filteredStudents = allStudents.filter(s => {
    if (!studentSearch) return true
    return s.student_code?.includes(studentSearch) || s.course_type?.includes(studentSearch) || (s.full_name_fa || '').includes(studentSearch)
  })

  return (
    <div>

      <ResolvedProcessHistoryBanner
        instanceDetail={instanceDetail}
        availableTransitions={availableTransitions}
      />

      <div className="page-header">
        <div>
          <h1 className="page-title">{laneConfig?.title || 'پنل کارمند'}</h1>
          <p className="page-subtitle">
            {user?.full_name_fa || user?.username} | {laneConfig?.subtitle || 'مدیریت دانشجویان'}
          </p>
        </div>
      </div>

      <OperatorPortalReminderBanner portalPath={portalPath} pendingTab="pending" />

      <OperatorFollowupSection
        items={processInboxItems}
        readinessAlerts={operatorReadinessAlerts}
        inboxTitle={isCourseCommitteeLane ? 'صندوق اقدام (آماده‌سازی ترم و پرونده‌ها)' : 'صندوق اقدام (پرونده‌های باز شما)'}
      />

      {isCourseCommitteeLane && <CourseCommitteePrepPanel showToast={showToast} />}

      {isCourseCommitteeLane && <InstructorEvaluationCommitteePanel showToast={showToast} />}

      {isInstructionLane && activeTab !== 'onlineClasses' && <InstructionSemesterCoursesPanel />}

      {isInstructionLane && <InstructionTaPortfolioPanel user={user} />}

      {isInstructionLane && <InstructorEvaluationResultsPanel showToast={showToast} />}

      {isInstructionLane && (
        <InstructorClassAttendanceInboxHint pendingActions={displayPendingActions} />
      )}

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
              onClick={() => setActiveTab('pending')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('pending') } }}
              title="مشاهده وظایف منتظر"
            >
              <div className="stat-icon warning">📥</div>
              <div>
                <div className="stat-value">{displayPendingActions.length}</div>
                <div className="stat-label">وظایف منتظر</div>
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
                <div className="stat-label">تعداد دانشجویان</div>
              </div>
            </div>
            <div
              className="stat-card stat-card-clickable"
              role="button"
              tabIndex={0}
              onClick={() => setActiveTab('processes')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('processes') } }}
              title="مشاهده فرایندهای فعال"
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
              onClick={() => setActiveTab('activity')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('activity') } }}
              title="مشاهده فعالیت‌های اخیر"
            >
              <div className="stat-icon success">👥</div>
              <div>
                <div className="stat-value">{allUsers.length}</div>
                <div className="stat-label">کاربران سیستم</div>
              </div>
            </div>
          </div>

          {!isCourseCommitteeLane && (
            <div className="card" style={{ marginBottom: '1.5rem' }}>
              <div className="card-header">
                <h3 className="card-title">تکلیف جدید برای دانشجو</h3>
              </div>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                شناسه دانشجو را از لیست انتخاب کنید (همان UUID در دیتابیس؛ از ستون دانشجویان قابل کپی است).
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxWidth: '560px' }}>
                <select
                  className="form-input"
                  value={newAssignment.student_id}
                  onChange={e => setNewAssignment({ ...newAssignment, student_id: e.target.value })}
                >
                  <option value="">— انتخاب دانشجو —</option>
                  {allStudents.map(s => (
                    <option key={s.id} value={s.id}>{s.student_code} ({s.id.slice(0, 8)}…)</option>
                  ))}
                </select>
                <input
                  className="form-input"
                  placeholder="عنوان تکلیف"
                  value={newAssignment.title_fa}
                  onChange={e => setNewAssignment({ ...newAssignment, title_fa: e.target.value })}
                />
                <textarea
                  className="form-input"
                  placeholder="توضیح (اختیاری)"
                  rows={2}
                  value={newAssignment.description}
                  onChange={e => setNewAssignment({ ...newAssignment, description: e.target.value })}
                />
                <button type="button" className="btn btn-primary btn-sm" style={{ alignSelf: 'flex-start' }} onClick={handleCreateAssignment}>
                  ثبت تکلیف
                </button>
              </div>
            </div>
          )}

          <div className="dashboard-grid">
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">وظایف فوری</h3>
                {displayPendingActions.length > 0 && (
                  <button className="btn btn-outline btn-sm" onClick={() => setActiveTab('pending')}>
                    مشاهده همه
                  </button>
                )}
              </div>
              {displayPendingActions.length === 0 ? (
                <div className="empty-state" style={{ padding: '2rem' }}>
                  <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>✅</div>
                  <p>{isCourseCommitteeLane ? 'وظیفه پرونده‌ای منتظر نیست — کار اصلی در کارت آماده‌سازی ترم بالاست.' : 'وظیفه منتظری وجود ندارد'}</p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {displayPendingActions.slice(0, 6).map(p => {
                    const pid = resolvePendingInstanceId(p)
                    return (
                    <button
                      key={pid}
                      onClick={() => openPendingTask(p)}
                      style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '0.6rem 0.75rem', borderRadius: '6px', cursor: 'pointer',
                        textAlign: 'right', border: '1px solid #fde68a', background: '#fffbeb',
                        fontSize: '0.85rem',
                      }}
                    >
                      <div>
                        <span style={{ fontWeight: 500 }}>{labelProcess(p.process_code)}</span>
                        <span style={{ fontSize: '0.7rem', color: '#6b7280', marginRight: '0.5rem' }}>
                          | {formatStudentCodeDisplay(p.student_code)}
                        </span>
                      </div>
                      <span className="badge badge-warning" style={{ fontSize: '0.65rem' }}>منتظر</span>
                    </button>
                    )
                  })}
                </div>
              )}
            </div>

            <div className="card">
              <div className="card-header">
                <h3 className="card-title">فعالیت‌های اخیر</h3>
              </div>
              {recentLogs.length === 0 ? (
                <div className="empty-state" style={{ padding: '2rem' }}>
                  <p>فعالیتی ثبت نشده</p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                  {recentLogs.slice(0, 8).map(log => (
                    <div key={log.id} className="activity-item" style={{ paddingTop: '0.5rem', paddingBottom: '0.5rem' }}>
                      <div className="activity-dot" />
                      <div style={{ flex: 1, fontSize: '0.82rem' }}>
                        <span className={`badge ${log.action_type === 'transition' ? 'badge-info' : 'badge-primary'}`}
                          style={{ fontSize: '0.65rem', marginLeft: '0.5rem' }}>
                          {log.action_type === 'transition' ? 'انتقال' : log.action_type}
                        </span>
                        <span style={{ fontWeight: 500 }}>{labelProcess(log.process_code)}</span>
                        {log.from_state && (
                          <span style={{ color: '#6b7280', fontSize: '0.75rem' }}>
                            {' '}{labelState(log.from_state)} → {labelState(log.to_state)}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="card" style={{ marginTop: '1.5rem' }}>
            <div className="card-header">
              <h3 className="card-title">دسترسی سریع</h3>
            </div>
            <div className="quick-actions-grid">
              {isCourseCommitteeLane ? (
                <>
                  <Link
                    className="quick-action-btn"
                    to={resolveSemesterPrepWorkbenchHref(semesterPrepProcesses)}
                    style={{ textDecoration: 'none' }}
                  >
                    <span className="quick-action-icon">📆</span>
                    <span>workbench آماده‌سازی</span>
                  </Link>
                  <button className="quick-action-btn" onClick={() => setActiveTab('pending')}>
                    <span className="quick-action-icon">📥</span>
                    <span>کارهای منتظر</span>
                  </button>
                  <Link className="quick-action-btn" to="/panel/semester-prep" style={{ textDecoration: 'none' }}>
                    <span className="quick-action-icon">📋</span>
                    <span>هاب آماده‌سازی ترم</span>
                  </Link>
                </>
              ) : (
                <>
                  <button className="quick-action-btn" onClick={() => { setActiveTab('students'); setShowNewStudent(true) }}>
                    <span className="quick-action-icon">➕</span>
                    <span>ایجاد دانشجو</span>
                  </button>
                  <button className="quick-action-btn" onClick={() => setActiveTab('pending')}>
                    <span className="quick-action-icon">📥</span>
                    <span>بررسی وظایف</span>
                  </button>
                  <button className="quick-action-btn" onClick={() => setActiveTab('students')}>
                    <span className="quick-action-icon">👨‍🎓</span>
                    <span>لیست دانشجویان</span>
                  </button>
                  <button className="quick-action-btn" onClick={() => setActiveTab('processes')}>
                    <span className="quick-action-icon">🔄</span>
                    <span>فرایندهای فعال</span>
                  </button>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {/* Pending Tab */}
      {activeTab === 'pending' && (
        <div style={{ display: 'grid', gridTemplateColumns: instanceDetail ? '1fr 1.5fr' : '1fr', gap: '1.5rem' }}>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">وظایف منتظر ({displayPendingActions.length})</h3>
            </div>
            {pendingActions.length === 0 ? (
              <div className="empty-state" style={{ padding: '3rem' }}>
                <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>✅</div>
                <p>همه وظایف انجام شده‌اند</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {displayPendingActions.map(p => {
                  const pid = resolvePendingInstanceId(p)
                  return (
                  <button
                    key={pid}
                    onClick={() => openPendingTask(p)}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '0.75rem 1rem', borderRadius: '8px', cursor: 'pointer',
                      textAlign: 'right',
                      border: selectedInstance === pid ? '2px solid var(--primary)' : '1px solid var(--border)',
                      background: selectedInstance === pid ? 'var(--primary-light)' : '#fff',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 500 }}>{labelProcess(p.process_code)}</div>
                      <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                        دانشجو: {formatStudentCodeDisplay(p.student_code)} | وضعیت: {labelState(p.current_state)}
                      </div>
                    </div>
                    <span className="badge badge-warning" style={{ fontSize: '0.7rem' }}>منتظر</span>
                  </button>
                  )
                })}
              </div>
            )}
          </div>
          {instanceDetail && <DetailPanel
            user={user}
            instanceDetail={instanceDetail}
            availableTransitions={availableTransitions}
            decisionNotes={decisionNotes}
            setDecisionNotes={setDecisionNotes}
            interviewResultForm={interviewResultForm}
            setInterviewResultForm={setInterviewResultForm}
            triggerTransition={triggerTransition}
            onUnlockStudentForms={unlockStudentFormsForInstance}
            unlockFormsBusy={unlockFormsBusy}
            onRollback={handleProcessRollback}
            rollbackBusy={rollbackBusy}
            onRestart={handleProcessRestart}
            restartBusy={restartBusy}
            onClose={() => { setSelectedInstance(null); setInstanceDetail(null) }}
            showToast={showToast}
            onRefreshInstance={() => viewInstance(selectedInstance)}
          />}
        </div>
      )}

      {/* Students Tab */}
      {activeTab === 'students' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">مدیریت دانشجویان ({allStudents.length})</h3>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <input
                type="text"
                placeholder="جستجو..."
                value={studentSearch}
                onChange={e => setStudentSearch(e.target.value)}
                className="form-input"
                style={{ width: '180px' }}
              />
              <button className="btn btn-primary btn-sm" onClick={() => setShowNewStudent(!showNewStudent)}>
                {showNewStudent ? 'لغو' : '+ دانشجوی جدید'}
              </button>
            </div>
          </div>

          {showNewStudent && (
            <div style={{
              padding: '1.5rem', background: 'var(--bg)', borderRadius: '10px',
              marginBottom: '1.5rem', border: '1px solid var(--border)',
            }}>
              <h4 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '1rem' }}>ایجاد دانشجوی جدید</h4>
              <div className="inline-form">
                <div className="form-group">
                  <label className="form-label">کاربر</label>
                  <select className="form-input" value={newStudent.user_id}
                    onChange={e => setNewStudent({ ...newStudent, user_id: e.target.value })}>
                    <option value="">انتخاب کنید...</option>
                    {nonStudentUsers.map(u => (
                      <option key={u.id} value={u.id}>{u.full_name_fa || u.username} ({u.username})</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">کد دانشجویی</label>
                  <input className="form-input" value={newStudent.student_code}
                    onChange={e => setNewStudent({ ...newStudent, student_code: e.target.value })}
                    placeholder="خالی = خودکار STU-1001…" />
                </div>
                <div className="form-group">
                  <label className="form-label">نوع دوره</label>
                  <select className="form-input" value={newStudent.course_type}
                    onChange={e => setNewStudent({ ...newStudent, course_type: e.target.value })}>
                    <option value="introductory">آشنایی</option>
                    <option value="comprehensive">جامع</option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">جلسات هفتگی</label>
                  <input className="form-input" type="number" min="1" max="7"
                    value={newStudent.weekly_sessions}
                    onChange={e => setNewStudent({ ...newStudent, weekly_sessions: parseInt(e.target.value) || 1 })} />
                </div>
              </div>
              <button className="btn btn-success" style={{ marginTop: '1rem' }} onClick={handleCreateStudent}>
                ایجاد دانشجو
              </button>
            </div>
          )}

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>کد دانشجویی</th>
                  <th>نام</th>
                  <th>نوع دوره</th>
                  <th>ترم</th>
                  <th>جلسات</th>
                  <th>درمان</th>
                  <th>کارآموز</th>
                  <th>عملیات</th>
                </tr>
              </thead>
              <tbody>
                {filteredStudents.map(s => (
                  <tr key={s.id}>
                    <td style={{ fontWeight: 600 }}>{formatStudentCodeDisplay(s.student_code)}</td>
                    <td>{formatStudentFullNameFa(s.full_name_fa)}</td>
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
                    <td>
                      <button className="btn btn-outline btn-sm" onClick={() => {
                        setActiveTab('processes')
                        // Filter will show processes for this student
                      }}>
                        فرایندها
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Processes Tab */}
      {activeTab === 'roster' && isCourseCommitteeLane && (
        <CourseCommitteeRosterPanel showToast={showToast} />
      )}

      {activeTab === 'processes' && (
        <div style={{ display: 'grid', gridTemplateColumns: instanceDetail ? '1fr 1.5fr' : '1fr', gap: '1.5rem' }}>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">فرایندهای فعال ({allActiveInstances.length})</h3>
            </div>
            {allActiveInstances.length === 0 ? (
              <div className="empty-state" style={{ padding: '2rem' }}>
                <p>فرایند فعالی وجود ندارد</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '600px', overflowY: 'auto' }}>
                {allActiveInstances.map(p => (
                  <button
                    key={p.instance_id}
                    onClick={() => viewInstance(p.instance_id)}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '0.65rem 0.75rem', borderRadius: '8px', cursor: 'pointer',
                      textAlign: 'right',
                      border: selectedInstance === p.instance_id ? '2px solid var(--primary)' : '1px solid var(--border)',
                      background: selectedInstance === p.instance_id ? 'var(--primary-light)' : '#fff',
                      fontSize: '0.85rem',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 500 }}>{labelProcess(p.process_code)}</div>
                      <div style={{ fontSize: '0.7rem', color: '#6b7280' }}>
                        {formatStudentCodeDisplay(p.student_code)} | {labelState(p.current_state)}
                      </div>
                    </div>
                    <span className={`badge ${isWaitingForStaff(p.current_state, p.process_code) ? 'badge-warning' : 'badge-info'}`}
                      style={{ fontSize: '0.65rem' }}>
                      {isWaitingForStaff(p.current_state, p.process_code) ? 'منتظر شما' : 'در جریان'}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
          {instanceDetail && <DetailPanel
            user={user}
            instanceDetail={instanceDetail}
            availableTransitions={availableTransitions}
            decisionNotes={decisionNotes}
            setDecisionNotes={setDecisionNotes}
            interviewResultForm={interviewResultForm}
            setInterviewResultForm={setInterviewResultForm}
            triggerTransition={triggerTransition}
            onUnlockStudentForms={unlockStudentFormsForInstance}
            unlockFormsBusy={unlockFormsBusy}
            onRollback={handleProcessRollback}
            rollbackBusy={rollbackBusy}
            onRestart={handleProcessRestart}
            restartBusy={restartBusy}
            onClose={() => { setSelectedInstance(null); setInstanceDetail(null) }}
            showToast={showToast}
            onRefreshInstance={() => viewInstance(selectedInstance)}
          />}
        </div>
      )}

      {activeTab === 'interviewSlots' && (
        <InterviewSlotsManageSection showToast={showToast} onCapacityChanged={reloadFollowup} />
      )}

      {activeTab === 'etTherapistSlots' && (
        <EducationalTherapistSlotsAdmin showToast={showToast} />
      )}

      {activeTab === 'documentsReview' && (
        <DocumentsReviewPanel
          queue={documentReviewQueue}
          onRefresh={loadData}
          showToast={showToast}
        />
      )}

      {activeTab === 'onlineClasses' && (
        <InstructionSemesterCoursesPanel />
      )}

      {/* Activity Tab */}
      {activeTab === 'activity' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">سوابق فعالیت</h3>
          </div>
          {recentLogs.length === 0 ? (
            <div className="empty-state" style={{ padding: '2rem' }}>
              <p>فعالیتی ثبت نشده</p>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>نوع</th>
                    <th>فرایند</th>
                    <th>از وضعیت</th>
                    <th>به وضعیت</th>
                    <th>بازیگر</th>
                    <th>زمان</th>
                  </tr>
                </thead>
                <tbody>
                  {recentLogs.map(log => (
                    <tr key={log.id}>
                      <td>
                        <span className={`badge ${log.action_type === 'transition' ? 'badge-info' : 'badge-primary'}`}>
                          {log.action_type === 'transition' ? 'انتقال' : log.action_type}
                        </span>
                      </td>
                      <td style={{ fontWeight: 500 }}>
                        {labelProcess(log.process_code)}
                      </td>
                      <td style={{ fontSize: '0.82rem' }}>{log.from_state ? labelState(log.from_state) : '-'}</td>
                      <td style={{ fontSize: '0.82rem' }}>{log.to_state ? labelState(log.to_state) : '-'}</td>
                      <td style={{ fontSize: '0.82rem' }}>{log.actor_name || log.actor_role || '-'}</td>
                      <td style={{ fontSize: '0.78rem', color: '#6b7280' }}>
                        {formatShamsiTehran(log.timestamp)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function DetailPanel({
  user,
  instanceDetail,
  availableTransitions,
  decisionNotes,
  setDecisionNotes,
  interviewResultForm,
  setInterviewResultForm,
  triggerTransition,
  onUnlockStudentForms,
  unlockFormsBusy,
  onRollback,
  rollbackBusy,
  onRestart,
  restartBusy,
  onClose,
  showToast,
  onRefreshInstance,
}) {
  const isIntroReg = instanceDetail.process_code === 'introductory_course_registration'
  const isTaEssay = instanceDetail.process_code === 'ta_essay_upload'
  const isTaConceptual = instanceDetail.process_code === 'ta_conceptual_questions'
  const instanceContext = instanceDetail.context_data || {}
  const showInterviewAdvance =
    isIntroReg && instanceDetail.current_state === 'interview_payment_confirmed'
  const showInterviewResultForm =
    isIntroReg
    && instanceDetail.current_state === 'interview_completed'
    && canSubmitInterviewResult(user, instanceContext)
  const interviewTimeReachedTransition = availableTransitions.find(
    (t) => t.trigger_event === 'interview_time_reached',
  )

  const filterTransitionsForPanel = (trans) => {
    let filtered = filterInterviewResultTransitions(trans, user, instanceContext)
    if (showInterviewAdvance) {
      filtered = filtered.filter((t) => t.trigger_event !== 'interview_time_reached')
    }
    return filtered
  }

  const triggerWithTaEssayValidation = async (transition) => {
    if (
      isTaEssay
      && instanceDetail.current_state === 'instructor_review'
      && transition.trigger_event === 'rejected'
      && !(decisionNotes || '').trim()
    ) {
      showToast?.('برای «غیر قابل قبول»، ثبت توضیح رد الزامی است.', 'error')
      return
    }
    if (isTaConceptual && instanceDetail.current_state === 'instructor_review') {
      const triggerEvent = typeof transition === 'string' ? transition : transition.trigger_event
      const ctx = instanceDetail.context_data || {}
      const statuses = [1, 2, 3].map((n) => ctx[`question_${n}_status`])
      const anyRejected = statuses.some((s) => s === 'rejected')
      const allOk = statuses.every((s) => s === 'accepted')
      if (triggerEvent === 'all_accepted' && !allOk) {
        showToast?.('برای «تأیید همه»، هر سه سوال باید «قابل قبول» باشند. ابتدا فرم را ثبت کنید.', 'error')
        return
      }
      if (triggerEvent === 'question_rejected' && !anyRejected) {
        showToast?.('برای «رد»، حداقل یک سوال باید «غیر قابل قبول» باشد و توضیح رد در فرم ثبت شود.', 'error')
        return
      }
      if (triggerEvent === 'question_rejected' && anyRejected) {
        const missingNote = [1, 2, 3].some(
          (n) => ctx[`question_${n}_status`] === 'rejected'
            && !(String(ctx[`question_${n}_rejection_note`] || '').trim()),
        )
        if (missingNote) {
          showToast?.('برای هر سوال ردشده، توضیح رد در فرم الزامی است.', 'error')
          return
        }
      }
    }
    return triggerTransition(transition)
  }

  return (
    <>
      <TaClassDutiesPanel detail={instanceDetail} user={user} />
      <TaTrackCompletionInstancePanel
        detail={instanceDetail}
        studentId={instanceDetail?.student_id}
        studentName={instanceDetail?.student_code}
        portalRole={user?.role}
        active={instanceDetail?.process_code === 'ta_track_completion'}
      />
      <TherapistAssignmentReviewPanel detail={instanceDetail} />
      <StudentTaTrackChangePanel
        detail={instanceDetail}
        active={instanceDetail?.process_code === 'ta_track_change'}
      />
      <TaToInstructorAutoReportPanel
        detail={instanceDetail}
        active={instanceDetail?.process_code === 'ta_to_instructor_auto'}
        audience="staff"
      />
      <Supervision50hCompletionPanel
        detail={instanceDetail}
        active={instanceDetail?.process_code === 'supervision_50h_completion'}
      />
      <TaEssayUploadPanel
        detail={instanceDetail}
        portalRole={user?.role}
        active={isTaEssay}
      />
      <MentorPrivateSessionsPanel
        detail={instanceDetail}
        user={user}
        active={instanceDetail?.process_code === 'mentor_private_sessions'}
      />
      <TaConceptualQuestionsPanel
        detail={instanceDetail}
        portalRole={user?.role}
        active={isTaConceptual}
      />
      <ArticleWritingCompletionPanel
        detail={instanceDetail}
        portalRole={user?.role}
        active={instanceDetail?.process_code === 'article_writing_completion'}
      />
      <LiveSupervisionCourseCompletionPanel
        detail={instanceDetail}
        portalRole={user?.role}
        active={instanceDetail?.process_code === 'live_supervision_course_completion'}
      />
      <LiveSupervisionMirrorEvalPanel
        detail={instanceDetail}
        active={instanceDetail?.process_code === 'live_supervision_course_completion'}
      />
      <LiveSupervisionFinalEvalPanel
        detail={instanceDetail}
        active={instanceDetail?.process_code === 'live_supervision_course_completion'}
      />
      <InstructorLessonAttendancePanel
        detail={instanceDetail}
        instanceId={instanceDetail?.instance_id}
        availableTransitions={availableTransitions}
        showToast={showToast}
        onRefreshInstance={onRefreshInstance}
        active={
          instanceDetail?.process_code === 'class_attendance'
          && (instanceDetail?.context_data?.course_type || '').toLowerCase() !== 'live_supervision'
          && !instanceDetail?.context_data?.live_supervision_session
        }
      />
      <InstructorClassSessionCancellationPanel
        detail={instanceDetail}
        active={instanceDetail?.process_code === 'class_session_cancellation'}
      />
      <LiveSupervisionDualAttendancePanel
        detail={instanceDetail}
        instanceId={instanceDetail?.instance_id}
        availableTransitions={availableTransitions}
        showToast={showToast}
        onRefreshInstance={onRefreshInstance}
        active={instanceDetail?.process_code === 'class_attendance'}
      />
      <LiveTherapyObservationTaAttendancePanel
        detail={instanceDetail}
        instanceId={instanceDetail?.instance_id}
        availableTransitions={availableTransitions}
        showToast={showToast}
        onRefreshInstance={onRefreshInstance}
        active={instanceDetail?.process_code === 'live_therapy_observation_ta_attendance_completion'}
      />
      <FilmObservationTaAttendancePanel
        detail={instanceDetail}
        instanceId={instanceDetail?.instance_id}
        availableTransitions={availableTransitions}
        showToast={showToast}
        onRefreshInstance={onRefreshInstance}
        active={instanceDetail?.process_code === 'film_observation_ta_attendance_completion'}
      />
      <FilmObservationCourseCompletionPanel
        detail={instanceDetail}
        instanceId={instanceDetail?.instance_id}
        availableTransitions={availableTransitions}
        showToast={showToast}
        onRefreshInstance={onRefreshInstance}
        active={instanceDetail?.process_code === 'film_observation_course_completion'}
      />
      <LiveTherapyObservationCourseCompletionPanel
        detail={instanceDetail}
        instanceId={instanceDetail?.instance_id}
        availableTransitions={availableTransitions}
        showToast={showToast}
        onRefreshInstance={onRefreshInstance}
        active={instanceDetail?.process_code === 'live_therapy_observation_course_completion'}
      />
      <SkillsCourseCompletionPanel
        detail={instanceDetail}
        instanceId={instanceDetail?.instance_id}
        availableTransitions={availableTransitions}
        showToast={showToast}
        onRefreshInstance={onRefreshInstance}
        active={instanceDetail?.process_code === 'skills_course_completion'}
      />
      <TheoryCourseCompletionPanel
        detail={instanceDetail}
        instanceId={instanceDetail?.instance_id}
        availableTransitions={availableTransitions}
        showToast={showToast}
        onRefreshInstance={onRefreshInstance}
        active={instanceDetail?.process_code === 'theory_course_completion'}
      />
      <GroupSupervisionCourseCompletionPanel
        detail={instanceDetail}
        instanceId={instanceDetail?.instance_id}
        availableTransitions={availableTransitions}
        showToast={showToast}
        onRefreshInstance={onRefreshInstance}
        active={instanceDetail?.process_code === 'group_supervision_course_completion'}
      />
      <OperatorProcessInstancePanel
        user={user}
        instanceDetail={instanceDetail}
        availableTransitions={availableTransitions}
        onClose={onClose}
        showToast={showToast}
        onRefreshInstance={onRefreshInstance}
        onTriggerTransition={triggerWithTaEssayValidation}
        decisionNotes={decisionNotes}
        setDecisionNotes={setDecisionNotes}
        filterTransitions={filterTransitionsForPanel}
        showUnlockStudentForms
        onUnlockStudentForms={onUnlockStudentForms}
        unlockFormsBusy={unlockFormsBusy}
        showRollback
        onRollback={onRollback}
        rollbackBusy={rollbackBusy}
        showRestart
        onRestart={onRestart}
        restartBusy={restartBusy}
        renderExtraBeforeActions={({ triggerTransition: trig, transitionsForActions }) => (
        <>
          <IntroductoryTermEndFollowupPanel detail={instanceDetail} user={user} />
          <AcademicDeclineFollowupForm
            detail={instanceDetail}
            user={user}
            showToast={showToast}
            onUpdated={onRefreshInstance}
          />
          <InternBulkPatientReferralCoordinationPanel detail={instanceDetail} user={user} />
          <LiveSessionPrepPanel detail={instanceDetail} user={user} />
          <TaUpgradeCourseCommitteePanel detail={instanceDetail} user={user} />
          <TaTrackChangeCommitteePanel detail={instanceDetail} user={user} />

          {showInterviewAdvance && (
            <div
              style={{
                padding: '1rem 1.25rem',
                marginBottom: '1.25rem',
                background: '#eff6ff',
                borderRadius: '10px',
                borderRight: '4px solid #2563eb',
              }}
            >
              <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.5rem', color: '#1e40af' }}>
                ثبت برگزاری مصاحبه
              </h4>
              <p style={{ fontSize: '0.85rem', lineHeight: 1.65, margin: '0 0 0.75rem', color: '#334155' }}>
                پس از برگزاری مصاحبه (یا برای تست بدون انتظار تا زمان قرار)، این دکمه را بزنید تا مرحلهٔ ثبت نتیجه برای مصاحبه‌گر باز شود.
              </p>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                data-testid="staff-advance-interview-completed"
                disabled={!interviewTimeReachedTransition}
                onClick={() => {
                  if (interviewTimeReachedTransition) trig(interviewTimeReachedTransition)
                }}
              >
                ثبت برگزاری مصاحبه و باز کردن ثبت نتیجه
              </button>
            </div>
          )}

          {showInterviewResultForm && (
            <div
              style={{
                padding: '1rem 1.25rem',
                marginBottom: '1.25rem',
                background: '#faf5ff',
                borderRadius: '10px',
                borderRight: '4px solid #7c3aed',
              }}
            >
              <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.75rem', color: '#5b21b6' }}>
                فرم محرمانهٔ نتیجهٔ مصاحبه
              </h4>
              <label style={{ display: 'block', fontSize: '0.88rem' }}>
                <span style={{ fontWeight: 600 }}>یادداشت مصاحبه‌گر (اختیاری)</span>
                <textarea
                  className="form-input"
                  rows={3}
                  style={{ width: '100%', marginTop: '0.35rem' }}
                  dir="rtl"
                  value={interviewResultForm.interviewer_notes}
                  onChange={(e) =>
                    setInterviewResultForm((prev) => ({
                      ...prev,
                      interviewer_notes: e.target.value,
                    }))
                  }
                />
              </label>
            </div>
          )}
        </>
      )}
    />
    </>
  )
}
