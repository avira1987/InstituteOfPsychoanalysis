import React, { useState, useEffect, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import InterviewBookingsPanel from '../components/InterviewBookingsPanel'
import InterviewerAssignedSlotsPanel from '../components/InterviewerAssignedSlotsPanel'
import InterviewSlotsManageSection from '../components/InterviewSlotsManageSection'
import OperatorFollowupSection from '../components/OperatorFollowupSection'
import InterviewerResultPanel from '../components/InterviewerResultPanel'
import InterviewResultQueuePanel from '../components/InterviewResultQueuePanel'
import { useToast } from '../contexts/ToastContext'
import { panelApi } from '../services/api'
import { canManageInterviewSlots } from '../utils/interviewSlotAccess'
import { usePortalInstanceDeepLink } from '../hooks/usePortalInstanceDeepLink'

const DEEP_LINK_TABS = ['dashboard', 'result']

/**
 * پنل مصاحبه‌گر — تعریف وقت، رزروها، و ثبت نتیجهٔ مصاحبه در همین پنل.
 */
export default function InterviewerPortal() {
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const { showToast } = useToast()
  const [inboxItems, setInboxItems] = useState([])
  const [readinessAlerts, setReadinessAlerts] = useState([])
  const [followupLoading, setFollowupLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('dashboard')
  const [selectedInstance, setSelectedInstance] = useState(null)

  const reloadFollowup = React.useCallback(() => {
    setFollowupLoading(true)
    return panelApi
      .myOperatorFollowup()
      .then((r) => {
        setInboxItems(r.data?.items || [])
        setReadinessAlerts(r.data?.readiness_alerts || [])
      })
      .catch(() => {
        setInboxItems([])
        setReadinessAlerts([])
      })
      .finally(() => setFollowupLoading(false))
  }, [])

  useEffect(() => {
    reloadFollowup()
  }, [user?.id, reloadFollowup])

  const viewInstance = useCallback((instanceId) => {
    setSelectedInstance(instanceId)
    setActiveTab('result')
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('tab', 'result')
      next.set('instance_id', instanceId)
      return next
    })
  }, [setSearchParams])

  const closeResultPanel = useCallback(() => {
    setSelectedInstance(null)
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete('instance_id')
      if (next.get('tab') === 'result') next.set('tab', 'result')
      return next
    })
  }, [setSearchParams])

  const openResultTab = useCallback(() => {
    setActiveTab('result')
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('tab', 'result')
      return next
    })
  }, [setSearchParams])

  usePortalInstanceDeepLink({
    loading: followupLoading,
    setActiveTab,
    viewInstance,
    allowedTabs: DEEP_LINK_TABS,
  })

  useEffect(() => {
    const id = searchParams.get('instance_id')
    if (id) setSelectedInstance(id)
  }, [searchParams])

  const canManageSlots = canManageInterviewSlots(user?.role)
  const isStaffCreator = user?.role === 'staff'

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">پنل مصاحبه‌گر</h1>
          <p className="page-subtitle">
            {user?.full_name_fa || user?.username}
            {' '}
            | زمان‌های مصاحبه، رزروها، و ثبت نتیجهٔ مصاحبه
          </p>
          <p className="muted" style={{ marginTop: '0.6rem', fontSize: '0.9rem', maxWidth: '46rem' }}>
            {canManageSlots ? (
              <>
                به‌عنوان مدیر می‌توانید وقت مصاحبه را اینجا یا از{' '}
                <Link to="/panel/portal/staff/admissions?tab=interviewSlots">پنل پذیرش — وقت مصاحبه</Link> تعریف کنید.
                برای ثبت نتیجه به تب <strong>ثبت نتیجهٔ مصاحبه</strong> بروید و پرونده را از فهرست انتخاب کنید.
              </>
            ) : isStaffCreator ? (
              <>
                به‌عنوان ایجادکنندهٔ وقت مصاحبه، از تب <strong>ثبت نتیجهٔ مصاحبه</strong> پرونده را انتخاب و نتیجه را ثبت کنید.
              </>
            ) : (
              <>
                تعریف وقت مصاحبه از{' '}
                <Link to="/panel/portal/staff/admissions?tab=interviewSlots">پنل پذیرش</Link> انجام می‌شود.
                برای ثبت نتیجه به تب <strong>ثبت نتیجهٔ مصاحبه</strong> بروید.
              </>
            )}
          </p>
        </div>
      </div>

      <div className="tab-bar" style={{ marginBottom: '1rem' }}>
        <button
          type="button"
          className={`tab-item ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
        >
          داشبورد
        </button>
        <button
          type="button"
          className={`tab-item ${activeTab === 'result' ? 'active' : ''}`}
          onClick={openResultTab}
          data-testid="interviewer-tab-result"
        >
          ثبت نتیجهٔ مصاحبه
        </button>
      </div>

      {activeTab === 'result' && (
        <>
          {!selectedInstance ? (
            <InterviewResultQueuePanel
              showToast={showToast}
              onOpenResult={viewInstance}
              onAfterAction={reloadFollowup}
            />
          ) : (
            <>
              <div style={{ marginBottom: '0.75rem' }}>
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  data-testid="interviewer-result-back-to-queue"
                  onClick={closeResultPanel}
                >
                  بازگشت به فهرست
                </button>
              </div>
              <InterviewerResultPanel
                user={user}
                instanceId={selectedInstance}
                onClose={closeResultPanel}
                showToast={showToast}
                onAfterTransition={reloadFollowup}
              />
            </>
          )}
        </>
      )}

      {activeTab === 'dashboard' && (
        <>
          <OperatorFollowupSection
            loading={followupLoading}
            items={inboxItems}
            readinessAlerts={readinessAlerts}
            inboxTitle="پرونده‌های باز — ثبت نتیجهٔ مصاحبه"
          />

          {canManageSlots ? (
            <InterviewSlotsManageSection
              showToast={showToast}
              onCapacityChanged={reloadFollowup}
              showBookings={false}
            />
          ) : null}

          {!canManageSlots ? <InterviewerAssignedSlotsPanel showToast={showToast} /> : null}

          <InterviewBookingsPanel showToast={showToast} onOpenResult={viewInstance} />
        </>
      )}
    </div>
  )
}
