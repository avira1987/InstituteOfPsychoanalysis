import React, { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useAuth } from './AuthContext'
import { panelApi, publicApi } from '../services/api'
import { subscribeSimulatedSms } from '../utils/simulatedSmsBridge'
import { SimulatedSmsLayer } from '../components/SimulatedSmsPopup'

const SimulatedSmsContext = createContext(null)

const POLL_MS = 5_000
const LOCAL_DISMISSED_KEY = 'anistito_sim_sms_seen'
let popupTitleSeq = 0

function readLocalDismissedIds() {
  try {
    const raw = sessionStorage.getItem(LOCAL_DISMISSED_KEY)
    const arr = JSON.parse(raw || '[]')
    return new Set(Array.isArray(arr) ? arr.map(String) : [])
  } catch (_) {
    return new Set()
  }
}

function appendLocalDismissedId(id) {
  if (!id) return
  try {
    const cur = new Set([...readLocalDismissedIds(), String(id)])
    sessionStorage.setItem(LOCAL_DISMISSED_KEY, JSON.stringify([...cur].slice(-120)))
  } catch (_) {
    /* ignore */
  }
}

function entryKey(entry) {
  if (!entry) return ''
  if (entry.id) return String(entry.id)
  return `${entry.phone || ''}|${entry.message || ''}|${entry.created_at || ''}`
}

export function SimulatedSmsProvider({ children }) {
  const { user } = useAuth()
  const [queue, setQueue] = useState([])
  const [enabled, setEnabled] = useState(false)
  const [globalFeed, setGlobalFeed] = useState(false)
  const [serverSimOff, setServerSimOff] = useState(false)
  const seenRef = useRef(new Set(readLocalDismissedIds()))
  const titleIdRef = useRef(`sim-sms-${++popupTitleSeq}`)

  const enqueue = useCallback((entry) => {
    if (!entry?.message) return
    const key = entryKey(entry)
    if (seenRef.current.has(key)) return
    setQueue((prev) => {
      if (prev.some((x) => entryKey(x) === key)) return prev
      return [...prev, entry]
    })
  }, [])

  useLayoutEffect(() => {
    return subscribeSimulatedSms(enqueue)
  }, [enqueue])

  useEffect(() => {
    let cancelled = false
    publicApi
      .smsSimulationStatus()
      .then((r) => {
        if (cancelled) return
        const on = Boolean(r.data?.enabled)
        setServerSimOff(!on)
        if (!on && import.meta.env.DEV) {
          console.warn(
            '[anistito] SMS popup OFF — set SMS_SIMULATION_UI=true and SMS_PROVIDER=log (or mirror with mellipayamak), then restart backend',
          )
        }
      })
      .catch(() => {
        if (!cancelled) setServerSimOff(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const loadPending = useCallback(async () => {
    if (!user) {
      setEnabled(false)
      setGlobalFeed(false)
      return
    }
    try {
      const r = await panelApi.simulatedSms({ limit: 50 })
      if (!r.data?.enabled) {
        setEnabled(false)
        setGlobalFeed(false)
        return
      }
      setGlobalFeed(r.data?.feed_scope === 'global_all_recipients')
      setEnabled(true)
      const items = (Array.isArray(r.data?.items) ? r.data.items : []).filter((it) => {
        if (!it?.message) return false
        const key = entryKey(it)
        return !seenRef.current.has(key)
      })
      if (items.length) {
        setQueue((prev) => {
          const keys = new Set(prev.map(entryKey))
          const merged = [...prev]
          items.forEach((it) => {
            const k = entryKey(it)
            if (!keys.has(k)) {
              keys.add(k)
              merged.push(it)
            }
          })
          return merged
        })
      }
    } catch (err) {
      if (import.meta.env.DEV) {
        console.warn('[anistito] simulated SMS poll failed:', err?.message || err)
      }
    }
  }, [user])

  useEffect(() => {
    if (!user) return undefined
    loadPending()
    const t = setInterval(loadPending, POLL_MS)
    const onVis = () => {
      if (document.visibilityState === 'visible') loadPending()
    }
    document.addEventListener('visibilitychange', onVis)
    return () => {
      clearInterval(t)
      document.removeEventListener('visibilitychange', onVis)
    }
  }, [loadPending, user])

  const dismissFirst = useCallback(async () => {
    const cur = queue[0]
    if (!cur) return
    const key = entryKey(cur)
    seenRef.current.add(key)
    appendLocalDismissedId(cur.id || key)
    if (cur.id && user) {
      try {
        await panelApi.dismissSimulatedSms(cur.id)
      } catch (_) {
        /* پاپ‌آپ را ببند حتی با خطای شبکه */
      }
    }
    setQueue((p) => p.filter((x) => entryKey(x) !== key))
  }, [queue, user])

  const current = queue[0] || null
  const showLayer = Boolean(current)

  return (
    <SimulatedSmsContext.Provider value={{ enqueue, enabled, globalFeed }}>
      {children}
      {serverSimOff && import.meta.env.DEV ? (
        <div className="simulated-sms-dev-hint" data-testid="simulated-sms-dev-off">
          پاپ‌آپ پیامک تستی خاموش است — SMS_SIMULATION_UI=true و SMS_PROVIDER=log یا SMS_SIMULATION_MIRROR_REAL_SEND=true
        </div>
      ) : null}
      {showLayer ? (
        <SimulatedSmsLayer
          entry={current}
          onDismiss={dismissFirst}
          titleHtmlId={titleIdRef.current}
          globalFeed={globalFeed || !user}
          queueRemaining={queue.length}
        />
      ) : null}
    </SimulatedSmsContext.Provider>
  )
}

export function useSimulatedSms() {
  return useContext(SimulatedSmsContext)
}
