import React, { useEffect, useState } from 'react'
import { studentApi } from '../services/api'
import TaTrackPortfolioPanel from './TaTrackPortfolioPanel'
import { userHasAnyRole } from '../utils/userRoles'

/**
 * نمای فشردهٔ پرونده کمک‌مدرسی برای مدرس/کمک‌مدرس در instruction lane.
 */
export default function InstructionTaPortfolioPanel({ user }) {
  const [portfolio, setPortfolio] = useState(null)
  const [loading, setLoading] = useState(false)
  const isTaRole = userHasAnyRole(user, [
    'teaching_assistant',
    'instructor',
    'assistant_faculty',
    'educational_instructor',
  ])

  useEffect(() => {
    if (!isTaRole) return
    let cancelled = false
    const load = async () => {
      setLoading(true)
      try {
        const res = await studentApi.taPortfolio()
        if (!cancelled) setPortfolio(res.data)
      } catch {
        if (!cancelled) setPortfolio(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [isTaRole])

  if (!isTaRole) return null
  if (!loading && !portfolio?.has_ta_data) return null

  return (
    <TaTrackPortfolioPanel
      portfolio={portfolio}
      portalRole={user?.role}
      compact
      loading={loading}
      readOnlyNote="سوابق کمک‌مدرسی شما — برای برنامه‌ریزی رسته‌های بعدی از این نما استفاده کنید."
    />
  )
}
