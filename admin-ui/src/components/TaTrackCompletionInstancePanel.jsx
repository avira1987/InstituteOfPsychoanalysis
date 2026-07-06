import React, { useEffect, useState } from 'react'
import { studentApi, processExecApi } from '../services/api'
import TaTrackPortfolioPanel from './TaTrackPortfolioPanel'

/**
 * پنل فرایند ۵۲ هنگام باز کردن پرونده — بارگذاری portfolio و نمایش بنر وضعیت.
 */
export default function TaTrackCompletionInstancePanel({
  detail = null,
  studentId = null,
  studentName = '',
  portalRole = 'student',
  active = true,
  compact = false,
}) {
  const [portfolio, setPortfolio] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!active) return
    let cancelled = false
    const load = async () => {
      setLoading(true)
      try {
        if (detail?.instance_id) {
          const dashRes = await processExecApi.dashboard(detail.instance_id)
          if (!cancelled && dashRes.data?.ta_portfolio) {
            setPortfolio(dashRes.data.ta_portfolio)
            return
          }
        }
        if (studentId && portalRole !== 'student') {
          const res = await studentApi.taPortfolioFor(studentId)
          if (!cancelled) setPortfolio(res.data)
        } else {
          const res = await studentApi.taPortfolio()
          if (!cancelled) setPortfolio(res.data)
        }
      } catch {
        if (!cancelled) setPortfolio(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [active, studentId, portalRole, detail?.instance_id])

  if (!active || !detail || detail.process_code !== 'ta_track_completion') {
    return null
  }

  const readOnlyNote = portalRole !== 'student'
    ? 'فرایند ۱۰۰٪ خودکار است؛ نیازی به تأیید یا اقدام اپراتور نیست. این نما فقط برای مشاهدهٔ پرونده کمک‌مدرسی است.'
    : null

  return (
    <TaTrackPortfolioPanel
      portfolio={portfolio}
      studentName={studentName}
      portalRole={portalRole}
      instanceDetail={detail}
      compact={compact}
      loading={loading}
      readOnlyNote={readOnlyNote}
    />
  )
}
