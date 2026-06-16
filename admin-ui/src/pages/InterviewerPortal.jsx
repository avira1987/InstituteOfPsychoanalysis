import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import InterviewBookingsPanel from '../components/InterviewBookingsPanel'
import InterviewSlotRecurringRules from '../components/InterviewSlotRecurringRules'
import InterviewSlotsAdmin from '../components/InterviewSlotsAdmin'
import OperatorFollowupSection from '../components/OperatorFollowupSection'
import PopupToast from '../components/PopupToast'
import { panelApi } from '../services/api'
import { canManageInterviewSlots } from '../utils/interviewSlotAccess'

/**
 * پنل مصاحبه‌گر — تعریف وقت، رزروها، و لینک به پروندهٔ فرایند.
 */
export default function InterviewerPortal() {
  const { user } = useAuth()
  const [toast, setToast] = useState(null)
  const [inboxItems, setInboxItems] = useState([])
  const [readinessAlerts, setReadinessAlerts] = useState([])
  const [followupLoading, setFollowupLoading] = useState(true)

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
            | زمان‌های مصاحبه، رزروها، و ادامهٔ فرایند پذیرش
          </p>
          <p className="muted" style={{ marginTop: '0.6rem', fontSize: '0.9rem', maxWidth: '46rem' }}>
            {canManageSlots ? (
              <>
                به‌عنوان مدیر سیستم می‌توانید وقت مصاحبه را اینجا یا از{' '}
                <Link to="/panel/portal/staff/admissions?tab=interviewSlots">پنل پذیرش — وقت مصاحبه</Link> تعریف و ویرایش کنید.
                پس از برگزاری، برای ثبت نتیجه از{' '}
                <strong>لینک صندوق اقدام</strong> همان نمونهٔ فرایند را باز کنید.
                ثبت نتیجه فقط برای مصاحبه‌گر همان وقت یا مدیر سیستم امکان‌پذیر است.
              </>
            ) : (
              <>
                تعریف وقت مصاحبه فقط از{' '}
                <Link to="/panel/portal/staff/admissions?tab=interviewSlots">پنل پذیرش — وقت مصاحبه</Link>{' '}
                انجام می‌شود. در اینجا رزروها و ادامهٔ فرایند پذیرش را می‌بینید؛ پس از برگزاری، برای ثبت نتیجه از{' '}
                <strong>لینک صندوق اقدام</strong> همان نمونهٔ فرایند را باز کنید.
                ثبت نتیجه فقط برای مصاحبه‌گر همان وقت امکان‌پذیر است.
              </>
            )}
          </p>
        </div>
      </div>

      <OperatorFollowupSection
        loading={followupLoading}
        items={inboxItems}
        readinessAlerts={readinessAlerts}
        inboxTitle="پرونده‌های باز مرتبط با نقش شما"
      />

      {canManageSlots ? (
        <>
          <InterviewSlotRecurringRules showToast={showToast} onCapacityChanged={reloadFollowup} />
          <InterviewSlotsAdmin showToast={showToast} onCapacityChanged={reloadFollowup} />
        </>
      ) : null}

      <InterviewBookingsPanel showToast={showToast} />
    </div>
  )
}
