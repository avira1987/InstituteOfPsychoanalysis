import { useEffect, useState } from 'react'
import { processExecApi } from '../services/api'
import { buildStudentProcessVisitSequence } from '../utils/studentProcessStepReview'

/**
 * فرم‌های مرحلهٔ جاری + فرم‌های وضعیت‌های طی‌شده برای نقشهٔ برچسب فارسی در خلاصهٔ پرونده.
 */
export function useOperatorContextFormLabels(instanceDetail) {
  const [forms, setForms] = useState([])
  const [extraLabelForms, setExtraLabelForms] = useState([])

  useEffect(() => {
    const pcode = instanceDetail?.process_code
    const state = instanceDetail?.current_state
    const instanceId = instanceDetail?.instance_id
    if (!pcode || !state) {
      setForms([])
      setExtraLabelForms([])
      return undefined
    }

    let cancelled = false

    ;(async () => {
      try {
        const [defRes, formsRes] = await Promise.all([
          processExecApi.getDefinition(pcode),
          processExecApi.getProcessFormsForState(pcode, state, instanceId),
        ])
        if (cancelled) return

        const def = defRes.data
        const currentForms = formsRes.data?.forms ?? formsRes.data ?? []
        setForms(Array.isArray(currentForms) ? currentForms : [])

        const seq = buildStudentProcessVisitSequence(
          instanceDetail.history,
          def,
          instanceDetail.current_state,
        )
        const states = [...new Set(seq)]
        if (!states.length) {
          setExtraLabelForms([])
          return
        }

        const results = await Promise.all(
          states.map((s) =>
            processExecApi.getProcessFormsForState(pcode, s, instanceId)
              .then((r) => r.data?.forms || [])
              .catch(() => []),
          ),
        )
        if (!cancelled) setExtraLabelForms(results)
      } catch {
        if (!cancelled) {
          setForms([])
          setExtraLabelForms([])
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [
    instanceDetail?.instance_id,
    instanceDetail?.process_code,
    instanceDetail?.current_state,
    instanceDetail?.history,
  ])

  return { forms, extraLabelForms }
}
