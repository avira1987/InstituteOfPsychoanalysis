import React, { useEffect, useState } from 'react'
import { studentApi } from '../services/api'
import { shouldShowTaPortfolio } from '../utils/taTrackCompletionDisplay'
import TaTrackPortfolioPanel from './TaTrackPortfolioPanel'

/**
 * بخش پرونده کمک‌مدرسی در پروفایل دانشجو — فرایند ۵۲.
 */
export default function StudentTaTrackPortfolioSection({
  extraData = null,
  active = true,
  compact = false,
}) {
  const [portfolio, setPortfolio] = useState(null)
  const [loading, setLoading] = useState(false)

  const mayShow = shouldShowTaPortfolio(extraData, portfolio)

  useEffect(() => {
    if (!active || !extraData) return
    if (!shouldShowTaPortfolio(extraData, null)) return
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
  }, [active, extraData, extraData?.rank, extraData?.ta_portfolio])

  if (!active) return null
  if (!mayShow && !loading && !portfolio?.has_ta_data) return null

  return (
    <TaTrackPortfolioPanel
      portfolio={portfolio}
      portalRole="student"
      compact={compact}
      loading={loading}
    />
  )
}
