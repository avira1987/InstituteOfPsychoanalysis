import React, { useEffect, useState } from 'react'
import { Navigate, useParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { panelApi, processExecApi, studentApi } from '../services/api'
import { labelProcess } from '../utils/processDisplay'
import { resolveProcessLandingHref } from '../utils/processNavLinks'

/**
 * صفحهٔ میانی سایدبار فرایند — redirect به پورتال/workbench مناسب.
 */
export default function ProcessNavLandingPage() {
  const { processCode: rawCode } = useParams()
  const processCode = decodeURIComponent(rawCode || '').trim().toLowerCase()
  const { user } = useAuth()
  const [error, setError] = useState(null)
  const [redirectTo, setRedirectTo] = useState(null)

  useEffect(() => {
    if (!processCode || !user) return
    let cancelled = false

    async function resolve() {
      setError(null)
      try {
        let pendingItem = null
        const role = (user.role || '').toLowerCase()

        if (role === 'student') {
          const meRes = await studentApi.me()
          const profile = meRes.data
          if (profile?.id) {
            const instancesRes = await processExecApi.studentInstances(profile.id)
            const instances = instancesRes.data?.instances || []
            const active = instances.find(
              (p) => (p.process_code || '').toLowerCase() === processCode
                && !p.is_completed
                && !p.is_cancelled,
            )
            if (active) {
              pendingItem = {
                process_code: processCode,
                instance_id: active.instance_id,
                student_id: profile.id,
                state_code: active.current_state,
                responsible_role_code: 'student',
              }
            }
          }
        } else {
          const inboxRes = await panelApi.myProcessInbox({ process_limit: 200 })
          const items = inboxRes.data?.items || []
          pendingItem = items.find(
            (it) => it.kind === 'process'
              && (it.process_code || '').toLowerCase() === processCode,
          )
        }

        let primaryAssignedRole = ''
        try {
          const navRes = await panelApi.processNavItems()
          const match = (navRes.data?.items || []).find(
            (it) => (it.process_code || '').toLowerCase() === processCode,
          )
          primaryAssignedRole = match?.primary_assigned_role || ''
        } catch {
          /* optional */
        }

        const dest = resolveProcessLandingHref({
          processCode,
          portalRole: role,
          primaryAssignedRole,
          pendingItem,
        })

        if (!cancelled && dest?.href) {
          setRedirectTo(dest.href)
        }
      } catch (e) {
        if (!cancelled) {
          setError(e?.response?.data?.detail || e?.message || 'خطا در هدایت به فرایند')
        }
      }
    }

    void resolve()
    return () => { cancelled = true }
  }, [processCode, user])

  if (redirectTo) {
    return <Navigate to={redirectTo} replace />
  }

  if (!processCode) {
    return <Navigate to="/panel" replace />
  }

  if (error) {
    return (
      <div className="card" style={{ margin: '2rem', maxWidth: 520 }}>
        <h2 className="card-title">{labelProcess(processCode)}</h2>
        <p className="text-danger">{error}</p>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '40vh' }}>
      <div className="loading-spinner" aria-label={`در حال باز کردن ${labelProcess(processCode)}`} />
    </div>
  )
}
