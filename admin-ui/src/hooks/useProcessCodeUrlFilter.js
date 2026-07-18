import { useEffect, useMemo, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'

/**
 * فیلتر ?process_code= در URL پورتال‌ها + باز کردن خودکار اولین instance مطابق.
 */
export function useProcessCodeUrlFilter({
  loading,
  items,
  getProcessCode,
  getInstanceId,
  viewInstance,
  setActiveTab,
  tabWhenFiltered = 'pending',
}) {
  const [searchParams] = useSearchParams()
  const processCodeFilter = (searchParams.get('process_code') || '').trim().toLowerCase()
  const instanceIdParam = searchParams.get('instance_id')
  const didAutoOpen = useRef(false)

  const filteredItems = useMemo(() => {
    if (!processCodeFilter) return items || []
    return (items || []).filter((it) => {
      const pc = (getProcessCode(it) || '').toLowerCase()
      return pc === processCodeFilter
    })
  }, [items, processCodeFilter, getProcessCode])

  useEffect(() => {
    didAutoOpen.current = false
  }, [processCodeFilter])

  useEffect(() => {
    if (loading || !processCodeFilter || instanceIdParam || didAutoOpen.current) return
    const match = filteredItems[0]
    const id = match ? getInstanceId(match) : null
    if (id && viewInstance) {
      didAutoOpen.current = true
      if (setActiveTab) setActiveTab(tabWhenFiltered)
      void viewInstance(id)
    } else if (setActiveTab && processCodeFilter) {
      setActiveTab(tabWhenFiltered)
    }
  }, [
    loading,
    processCodeFilter,
    instanceIdParam,
    filteredItems,
    viewInstance,
    setActiveTab,
    tabWhenFiltered,
    getInstanceId,
  ])

  return { processCodeFilter, filteredItems, hasProcessCodeFilter: !!processCodeFilter }
}
