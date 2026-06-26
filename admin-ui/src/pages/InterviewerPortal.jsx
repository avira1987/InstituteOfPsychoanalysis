import React, { useState, useEffect, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import InterviewBookingsPanel from '../components/InterviewBookingsPanel'
import InterviewSlotRecurringRules from '../components/InterviewSlotRecurringRules'
import InterviewSlotsAdmin from '../components/InterviewSlotsAdmin'
import OperatorFollowupSection from '../components/OperatorFollowupSection'
import InterviewerResultPanel from '../components/InterviewerResultPanel'
import PopupToast from '../components/PopupToast'
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
  const [toast, setToast] = useState(null)
  const [inboxItems, setInboxItems] = useState([])
  const [readinessAlerts, setReadinessAlerts] = useState([])
  const [followupLoading, setFollowupLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('dashboard')
  const [selectedInstance, setSelectedInstance] = useState(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

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
      if (next.get('tab') === 'result') next.set('tab', 'dashboard')
      return next
    })
    setActiveTab('dashboard')
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

  return (
    <div>
      <PopupToast toast={toast} />

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
                به‌عنوان مدیر سیستم می‌توانید وقت مصاحبه را اینجا یا از{' '}
                <Link to="/panel/portal/staff/admissions?tab=interviewSlots">پنل پذیرش — وقت مصاحبه</Link> تعریف کنید.
                برای ثبت نتیجه از <strong>صندوق اقدام</strong> همان پرونده را باز کنید.
              </>
            ) : (
              <>
                تعریف وقت مصاحبه از{' '}
                <Link to="/panel/portal/staff/admissions?tab=interviewSlots">پنل پذیرش</Link> انجام می‌شود.
                پس از برگزاری مصاحبه، از صندوق زیر «ثبت نتیجه» را در همین صفحه تکمیل کنید.
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
          onClick={() => setActiveTab('result')}
          disabled={!selectedInstance}
        >
          ثبت نتیجهٔ مصاحبه
        </button>
      </div>

      {activeTab === 'result' && selectedInstance && (
        <InterviewerResultPanel
          user={user}
          instanceId={selectedInstance}
          onClose={closeResultPanel}
          showToast={showToast}
          onAfterTransition={reloadFollowup}
        />
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
            <>
              <InterviewSlotRecurringRules showToast={showToast} onCapacityChanged={reloadFollowup} />
              <InterviewSlotsAdmin showToast={showToast} onCapacityChanged={reloadFollowup} />
            </>
          ) : null}

          <InterviewBookingsPanel showToast={showToast} />
        </>
      )}
    </div>
  )
}
