import { useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'

/**
 * ?tab=...&instance_id=... — پس از اتمام load اولیه، همان فرایند در پنل باز می‌شود.
 * allowedTabs باید ارجاع پایدار باشد (مثلاً ثابت سطح‌ماژول).
 */
export function usePortalInstanceDeepLink({ loading, setActiveTab, viewInstance, allowedTabs }) {
  const [searchParams] = useSearchParams()
  const viRef = useRef(viewInstance)
  viRef.current = viewInstance

  useEffect(() => {
    const tab = searchParams.get('tab')
    const allowed = new Set(allowedTabs)
    if (tab && allowed.has(tab)) setActiveTab(tab)
  }, [searchParams, setActiveTab, allowedTabs])

  useEffect(() => {
    if (loading) return
    const id = searchParams.get('instance_id')
    if (!id) return
    void viRef.current(id)
  }, [loading, searchParams])
}
