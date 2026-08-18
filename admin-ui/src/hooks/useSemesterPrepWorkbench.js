import { useCallback, useEffect, useMemo, useState } from 'react'
import { processExecApi, semesterPrepApi } from '../services/api'

export const SEMESTER_PREP_CODES = [
  'fall_semester_preparation',
  'winter_semester_preparation',
]

export function operatorTransitions(transitions) {
  return (transitions || []).filter(
    (t) => t.trigger_event !== 'sla_expired' && t.required_role !== 'system',
  )
}

/**
 * بارگذاری وضعیت آماده‌سازی ترم + جزئیات instance فعال برای workbench.
 * @param {string | null} processCode - کد فرایند؛ اگر null باشد اولین فرایند فعال انتخاب می‌شود.
 */
export function useSemesterPrepWorkbench(processCode) {
  const [status, setStatus] = useState(null)
  const [readiness, setReadiness] = useState(null)
  const [instanceDetail, setInstanceDetail] = useState(null)
  const [transitions, setTransitions] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const resolvedCode = useMemo(() => {
    if (processCode && SEMESTER_PREP_CODES.includes(processCode)) return processCode
    if (!status?.processes) return processCode || SEMESTER_PREP_CODES[0]
    for (const code of SEMESTER_PREP_CODES) {
      const entry = status.processes[code]
      if (entry?.active && entry?.instance_id) return code
    }
    return processCode || SEMESTER_PREP_CODES[0]
  }, [processCode, status])

  const entry = status?.processes?.[resolvedCode] || {}
  const instanceId = entry.instance_id || entry.completed_instance_id
  const currentState = entry.current_state || entry.completed_current_state
  const isActive = Boolean(entry.active && entry.instance_id && entry.current_state)
  const isCompletedEditable = Boolean(
    !entry.active && entry.completed_instance_id && entry.completed_current_state,
  )

  const loadInstance = useCallback(async (id) => {
    if (!id) {
      setInstanceDetail(null)
      setTransitions([])
      return
    }
    const [statusRes, transRes] = await Promise.all([
      processExecApi.status(id),
      processExecApi.transitions(id),
    ])
    setInstanceDetail(statusRes.data)
    setTransitions(transRes.data?.transitions || [])
  }, [])

  const applyInstanceContext = useCallback((ctx) => {
    if (!ctx || typeof ctx !== 'object') return
    setInstanceDetail((prev) => (prev ? { ...prev, context_data: ctx } : prev))
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await semesterPrepApi.getStatus()
      setStatus(res.data)
      setReadiness(res.data?.readiness || null)
      const code =
        processCode && SEMESTER_PREP_CODES.includes(processCode)
          ? processCode
          : SEMESTER_PREP_CODES.find((c) => res.data?.processes?.[c]?.active) ||
            processCode ||
            SEMESTER_PREP_CODES[0]
      const instEntry = res.data?.processes?.[code] || {}
      const loadableId =
        (instEntry.active && instEntry.instance_id) || instEntry.completed_instance_id
      if (loadableId) {
        await loadInstance(loadableId)
      } else {
        setInstanceDetail(null)
        setTransitions([])
      }
    } catch {
      setStatus(null)
      setReadiness(null)
      setInstanceDetail(null)
      setTransitions([])
    } finally {
      setLoading(false)
    }
  }, [loadInstance, processCode])

  useEffect(() => {
    load()
  }, [load])

  const actionTransitions = useMemo(() => operatorTransitions(transitions), [transitions])

  const reloadReadiness = useCallback(async () => {
    try {
      const res = await semesterPrepApi.getReadiness()
      setReadiness(res.data)
      return res.data
    } catch {
      setReadiness(null)
      return null
    }
  }, [])

  const startProcess = useCallback(
    async (code) => {
      setBusy(true)
      try {
        await semesterPrepApi.start(code)
        await load()
        return { ok: true }
      } catch (e) {
        const d = e?.response?.data?.detail
        return { ok: false, error: typeof d === 'string' ? d : 'خطا در شروع فرایند' }
      } finally {
        setBusy(false)
      }
    },
    [load],
  )

  const triggerTransition = useCallback(
    async (transition, notesPayloadFn) => {
      if (!instanceId) return { ok: false, error: 'instance یافت نشد' }
      setBusy(true)
      try {
        const triggerEvent = transition.trigger_event
        const toState = transition.to_state
        const payload = { ...notesPayloadFn(''), ...(toState ? { to_state: toState } : {}) }
        const res = await processExecApi.trigger(instanceId, {
          trigger_event: triggerEvent,
          payload,
          ...(toState ? { to_state: toState } : {}),
        })
        if (res.data?.success) {
          await load()
          return { ok: true, toState: res.data.to_state }
        }
        return { ok: false, error: res.data?.error || 'انتقال انجام نشد' }
      } catch (e) {
        const d = e?.response?.data?.detail
        return { ok: false, error: typeof d === 'string' ? d : 'خطا در ثبت مرحله' }
      } finally {
        setBusy(false)
      }
    },
    [instanceId, load],
  )

  return {
    status,
    readiness,
    entry,
    resolvedCode,
    instanceId,
    currentState,
    isActive,
    isCompletedEditable,
    instanceDetail,
    transitions,
    actionTransitions,
    loading,
    busy,
    load,
    loadInstance,
    applyInstanceContext,
    reloadReadiness,
    startProcess,
    triggerTransition,
  }
}
