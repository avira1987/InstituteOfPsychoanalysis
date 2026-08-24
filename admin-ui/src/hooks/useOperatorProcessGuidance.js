import { useEffect, useState } from 'react'
import { processExecApi } from '../services/api'
import { buildOperatorGuidance } from '../utils/operatorProcessGuidance'

/**
 * بارگذاری تعریف فرایند + فرم‌های مرحله برای ساخت راهنمای اپراتور.
 */
export function useOperatorProcessGuidance({
  instanceDetail,
  portalRole,
  portalRoles,
  user,
  availableTransitions = [],
  stepFormLocked = false,
}) {
  const [guidance, setGuidance] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const pcode = instanceDetail?.process_code
    const state = instanceDetail?.current_state
    if (!pcode || !state) {
      setGuidance(null)
      setLoading(false)
      return undefined
    }

    let cancelled = false
    setLoading(true)

    ;(async () => {
      try {
        const [defRes, formsRes] = await Promise.all([
          processExecApi.getDefinition(pcode),
          processExecApi.getProcessFormsForState(pcode, state),
        ])
        if (cancelled) return
        const forms = formsRes.data?.forms ?? formsRes.data ?? []
        const built = buildOperatorGuidance({
          definition: defRes.data,
          detail: instanceDetail,
          transitions: availableTransitions,
          forms: Array.isArray(forms) ? forms : [],
          portalRole,
          portalRoles,
          user,
          stepFormLocked,
        })
        setGuidance(built)
      } catch {
        if (!cancelled) setGuidance(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [
    instanceDetail,
    portalRole,
    portalRoles,
    user,
    availableTransitions,
    stepFormLocked,
  ])

  return { guidance, loading }
}
