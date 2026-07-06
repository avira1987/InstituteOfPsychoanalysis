import React, { useEffect, useState } from 'react'
import { studentApi } from '../services/api'
import TaTrackPortfolioPanel from './TaTrackPortfolioPanel'

/**
 * نمای فشردهٔ پرونده کمک‌مدرسی برای مدرس/کمک‌مدرس در instruction lane.
 */
export default function InstructionTaPortfolioPanel({ user }) {
  const [portfolio, setPortfolio] = useState(null)
  const [loading, setLoading] = useState(false)
  const role = (user?.role || '').trim()
  const isTaRole = role === 'teaching_assistant' || role === 'instructor' || role === 'assistant_faculty'

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
      portalRole={role}
      compact
      loading={loading}
      readOnlyNote="سوابق کمک‌مدرسی شما — برای برنامه‌ریزی رسته‌های بعدی از این نما استفاده کنید."
    />
  )
}
