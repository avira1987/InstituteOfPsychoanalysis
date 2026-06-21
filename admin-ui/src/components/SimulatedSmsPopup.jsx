import React, { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useAuth } from '../contexts/AuthContext'
import { panelApi } from '../services/api'
import { getSmsTemplateLabel } from '../utils/smsTemplateLabels'
import { formatShamsiTehran } from '../utils/shamsiDateTime'

/** @typedef {{ id: string, phone: string, message: string, kind?: string, template_key?: string | null, created_at?: string | null }} SimSmsEntry */

function formatWhen(iso) {
  if (!iso) return ''
  return formatShamsiTehran(iso)
}

/**
 * بدنهٔ پاپ‌آپ؛ دکمه × بستن
 * @param {{ entry: SimSmsEntry | null | undefined, onDismiss: () => void | Promise<void>, titleHtmlId: string, globalFeed?: boolean, queueRemaining?: number }} props
 */
function SimulatedSmsLayer({ entry, onDismiss, titleHtmlId, globalFeed, queueRemaining = 0 }) {
  if (!entry) return null
  const kindLabel =
    entry.kind === 'otp'
      ? 'کد ورود'
      : entry.kind === 'pattern'
        ? 'پترن'
        : entry.kind === 'notification'
          ? 'اعلان'
          : 'پیام'

  const templateLabel = getSmsTemplateLabel(entry.template_key, entry.kind)
  const when = formatWhen(entry.created_at)
  const moreCount = Math.max(0, (queueRemaining || 0) - 1)

  return createPortal(
    <div className="simulated-sms-overlay" data-testid="simulated-sms-overlay">
      <div className="simulated-sms-card" dir="rtl" role="dialog" aria-modal="true">
        <button
          type="button"
          className="simulated-sms-close"
          data-testid="simulated-sms-close"
          aria-label="بستن"
          title="بستن"
          onClick={() => onDismiss()}
        >
          ×
        </button>
        {moreCount > 0 ? (
          <div className="simulated-sms-queue-badge" data-testid="simulated-sms-queue-badge">
            {moreCount + 1} پیام در صف
          </div>
        ) : null}
        <h2 id={titleHtmlId} className="simulated-sms-title">
          {entry.kind === 'otp' ? 'پیامک کد ورود' : 'پیامک تستی'}
        </h2>
        <p className="simulated-sms-sub">
          {globalFeed
            ? 'فید یکپارچهٔ آزمایش: هر پیامک شبیه‌سازی‌شده به هر گیرنده همین‌جاست. برای خاموش کردن، در سرور SMS_SIMULATION_POPUP_SHOW_ALL=false یا کل SMS_SIMULATION_UI را ببندید.'
            : 'در حالت آزمایش، ارسال واقعی پیامک به ملی‌پیامک انجام نمی‌شود؛ متن همان پیام اینجاست.'}
        </p>
        <dl className="simulated-sms-meta">
          <div>
            <dt>گیرنده</dt>
            <dd dir="ltr">{entry.phone}</dd>
          </div>
          <div>
            <dt>نوع</dt>
            <dd>{kindLabel}</dd>
          </div>
          {entry.template_key || templateLabel !== kindLabel ? (
            <div>
              <dt>قالب</dt>
              <dd>{templateLabel}</dd>
            </div>
          ) : null}
          {when ? (
            <div>
              <dt>زمان</dt>
              <dd>{when}</dd>
            </div>
          ) : null}
        </dl>
        <div className="simulated-sms-body">
          <div className="simulated-sms-label">متن پیامک</div>
          <pre className="simulated-sms-pre" data-testid="simulated-sms-message">{entry.message}</pre>
        </div>
      </div>
    </div>,
    document.body
  )
}

export { SimulatedSmsLayer }

const POLL_MS = 30_000
let popupTitleSeq = 0
const LOCAL_DISMISSED_KEY = 'anistito_sim_sms_seen'

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

/**
 * پس از ورود: polling پیامک‌های شبیه‌سازی‌شده (فید سراسری برای نقش غیردانشجو یا فقط خط خود برای دانشجو)
 */
export default function SimulatedSmsPopupPoller() {
  const { user } = useAuth()
  const [pending, setPending] = useState([])
  const [enabled, setEnabled] = useState(false)
  const [globalFeed, setGlobalFeed] = useState(false)
  const titleIdRef = useRef(`sim-sms-${++popupTitleSeq}`)

  const load = useCallback(async () => {
    if (!user) {
      setPending([])
      setEnabled(false)
      setGlobalFeed(false)
      return
    }
    try {
      const r = await panelApi.simulatedSms({ limit: 50 })
      if (!r.data?.enabled) {
        setEnabled(false)
        setPending([])
        setGlobalFeed(false)
        return
      }
      setGlobalFeed(r.data?.feed_scope === 'global_all_recipients')
      setEnabled(true)
      const dismissed = readLocalDismissedIds()
      const items = (Array.isArray(r.data?.items) ? r.data.items : []).filter(
        (it) => it && !dismissed.has(String(it.id)),
      )
      setPending(items)
    } catch (_) {
      setPending([])
      setEnabled(false)
      setGlobalFeed(false)
    }
  }, [user])

  useEffect(() => {
    if (!user) return undefined
    load()
    const t = setInterval(load, POLL_MS)
    const onVis = () => {
      if (document.visibilityState === 'visible') load()
    }
    document.addEventListener('visibilitychange', onVis)
    return () => {
      clearInterval(t)
      document.removeEventListener('visibilitychange', onVis)
    }
  }, [load, user])

  const dismissFirst = useCallback(async () => {
    const cur = pending[0]
    if (!cur) return
    appendLocalDismissedId(cur.id)
    try {
      await panelApi.dismissSimulatedSms(cur.id)
    } catch (_) {
      /* پاپ‌آپ را حذف کن تا کاربر بتواند ادامه دهد حتی با خطای شبکه */
    }
    setPending((p) => p.filter((x) => x.id !== cur.id))
  }, [pending])

  if (!enabled || pending.length === 0) return null

  return (
    <SimulatedSmsLayer
      entry={pending[0]}
      onDismiss={dismissFirst}
      titleHtmlId={titleIdRef.current}
      globalFeed={globalFeed}
      queueRemaining={pending.length}
    />
  )
}

/**
 * پس از درخواست OTP روی لاگین — بدون نیاز به dismiss سرور (همان نشست قبلاً ثبت شده)
 * @param {{ entry: SimSmsEntry | null, onDismiss: () => void }} props
 */
export function SimulatedSmsPopupOnce({ entry, onDismiss }) {
  const titleIdRef = useRef(`sim-sms-login-${++popupTitleSeq}`)
  if (!entry) return null

  const close = () => {
    appendLocalDismissedId(entry?.id)
    if (typeof onDismiss === 'function') onDismiss()
  }

  return <SimulatedSmsLayer entry={entry} onDismiss={close} titleHtmlId={titleIdRef.current} queueRemaining={1} />
}
