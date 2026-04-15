import React, { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import InterviewBookingsPanel from '../components/InterviewBookingsPanel'
import PopupToast from '../components/PopupToast'

/**
 * پنل مصاحبه‌گر — فهرست وقت‌های رزروشده توسط دانشجویان.
 */
export default function InterviewerPortal() {
  const { user } = useAuth()
  const [toast, setToast] = useState(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  return (
    <div>
      <PopupToast toast={toast} />

      <div className="page-header">
        <div>
          <h1 className="page-title">پنل مصاحبه‌گر</h1>
          <p className="page-subtitle">
            {user?.full_name_fa || user?.username}
            {' '}
            | زمان‌های انتخاب‌شده توسط متقاضیان برای مصاحبهٔ پذیرش
          </p>
        </div>
      </div>

      <InterviewBookingsPanel showToast={showToast} />
    </div>
  )
}
