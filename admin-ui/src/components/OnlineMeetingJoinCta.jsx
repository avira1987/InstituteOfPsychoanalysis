import React, { useEffect, useState } from 'react'

export function formatMeetingTimeTehran(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString('fa-IR', {
      timeZone: 'Asia/Tehran',
      weekday: 'short',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function formatOpenTimeTehran(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString('fa-IR', {
      timeZone: 'Asia/Tehran',
      hour: '2-digit',
      minute: '2-digit',
      month: 'long',
      day: 'numeric',
    })
  } catch {
    return iso
  }
}

async function copyTextToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  const el = document.createElement('textarea')
  el.value = text
  el.setAttribute('readonly', '')
  el.style.position = 'fixed'
  el.style.left = '-9999px'
  document.body.appendChild(el)
  el.select()
  document.execCommand('copy')
  document.body.removeChild(el)
}

function MeetingLinkCopyButton({ meetingLink, compact = false }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async (e) => {
    e.preventDefault()
    e.stopPropagation()
    const url = (meetingLink || '').trim()
    if (!url) return
    try {
      await copyTextToClipboard(url)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  return (
    <button
      type="button"
      className={`online-meeting-join-cta__copy-btn${compact ? ' online-meeting-join-cta__copy-btn--compact' : ''}`}
      onClick={handleCopy}
      data-testid="online-meeting-copy-btn"
      title="کپی لینک کامل الوکام"
    >
      {copied ? 'کپی شد' : 'کپی لینک'}
    </button>
  )
}

/**
 * دکمهٔ برجستهٔ ورود به جلسهٔ آنلاین؛ قبل از زمان مجاز غیرفعال است.
 */
export default function OnlineMeetingJoinCta({
  mode = 'online',
  locationFa = '',
  meetingLink = null,
  meetingLinkOpenAt = null,
  meetingLinkIsVisible = false,
  startsAt = null,
  label = 'ورود به جلسهٔ آنلاین',
  compact = false,
  preparing = false,
  preparingText = 'لینک آنلاین در حال آماده‌سازی است؛ همین صفحه را کمی بعد تازه کنید.',
  preparingErrorText = 'آماده‌سازی لینک آنلاین بیش از حد معمول طول کشید. لطفاً با پذیرش تماس بگیرید یا صفحه را تازه کنید.',
  preparingFailed = false,
  studentJoinOpen = false,
  /** برای پذیرش/ادمین: کپی لینک میزبان حتی قبل از باز شدن پنجرهٔ ورود */
  allowStaffCopy = false,
}) {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30000)
    return () => clearInterval(timer)
  }, [])

  if (mode !== 'online') {
    return (
      <div className={`online-meeting-join-cta online-meeting-join-cta--in-person${compact ? ' online-meeting-join-cta--compact' : ''}`}>
        <span className="online-meeting-join-cta__location-label">محل حضوری:</span>
        <span className="online-meeting-join-cta__location">{locationFa || '—'}</span>
      </div>
    )
  }

  const openMs = meetingLinkOpenAt ? new Date(meetingLinkOpenAt).getTime() : null
  const canEnterByTime = studentJoinOpen || openMs == null || now >= openMs
  const linkReady = Boolean((meetingLink || '').trim())
  const canJoin = linkReady && meetingLinkIsVisible && canEnterByTime
  const showStaffCopy = allowStaffCopy && linkReady && meetingLinkIsVisible

  if (!canEnterByTime && meetingLinkOpenAt && !studentJoinOpen) {
    return (
      <div className={`online-meeting-join-cta online-meeting-join-cta--locked${compact ? ' online-meeting-join-cta--compact' : ''}`}>
        <div className="online-meeting-join-cta__actions">
          <button type="button" className="online-meeting-join-cta__btn" disabled aria-disabled="true">
            <span className="online-meeting-join-cta__icon" aria-hidden>🎥</span>
            {label}
          </button>
          {showStaffCopy ? <MeetingLinkCopyButton meetingLink={meetingLink} compact={compact} /> : null}
        </div>
        <p className="online-meeting-join-cta__hint">
          ورود پس از فعال‌سازی توسط مصاحبه‌گر/پذیرش، یا از{' '}
          <strong>{formatOpenTimeTehran(meetingLinkOpenAt)}</strong>
          {startsAt ? (
            <>
              {' '}
              (۳۰ دقیقه قبل از شروع مصاحبه در{' '}
              <strong>{formatMeetingTimeTehran(startsAt)}</strong>)
            </>
          ) : null}
          {' '}فعال می‌شود.
        </p>
      </div>
    )
  }

  if (preparing && !linkReady) {
    return (
      <div className={`online-meeting-join-cta online-meeting-join-cta--waiting${compact ? ' online-meeting-join-cta--compact' : ''}`}>
        <p className={`online-meeting-join-cta__hint${preparingFailed ? ' online-meeting-join-cta__hint--warn' : ''}`}>
          {preparingFailed ? preparingErrorText : preparingText}
        </p>
      </div>
    )
  }

  if (canJoin) {
    return (
      <div className={`online-meeting-join-cta online-meeting-join-cta--ready${compact ? ' online-meeting-join-cta--compact' : ''}`}>
        <div className="online-meeting-join-cta__actions">
          <a
            href={meetingLink}
            target="_blank"
            rel="noopener noreferrer"
            className="online-meeting-join-cta__btn online-meeting-join-cta__btn--active"
            data-testid="online-meeting-join-btn"
          >
            <span className="online-meeting-join-cta__icon" aria-hidden>▶</span>
            {label}
          </a>
          {showStaffCopy ? <MeetingLinkCopyButton meetingLink={meetingLink} compact={compact} /> : null}
        </div>
        <p className="online-meeting-join-cta__hint online-meeting-join-cta__hint--success">
          برای ورود به کلاس الوکام روی دکمه بالا کلیک کنید.
        </p>
      </div>
    )
  }

  if (showStaffCopy) {
    return (
      <div className={`online-meeting-join-cta online-meeting-join-cta--ready${compact ? ' online-meeting-join-cta--compact' : ''}`}>
        <MeetingLinkCopyButton meetingLink={meetingLink} compact={compact} />
        <p className="online-meeting-join-cta__hint">
          لینک میزبان آماده است؛ برای ورود از «کپی لینک» استفاده کنید.
        </p>
      </div>
    )
  }

  return (
    <div className={`online-meeting-join-cta online-meeting-join-cta--waiting${compact ? ' online-meeting-join-cta--compact' : ''}`}>
      <p className="online-meeting-join-cta__hint">
        {preparingText}
      </p>
    </div>
  )
}
