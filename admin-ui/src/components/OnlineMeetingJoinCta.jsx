import React, { useEffect, useState } from 'react'
import { formatShamsiTehran } from '../utils/shamsiDateTime'

export function formatMeetingTimeTehran(iso) {
  return formatShamsiTehran(iso)
}

function formatOpenTimeTehran(iso) {
  return formatShamsiTehran(iso)
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

function firstWord(text, fallback = '') {
  const t = String(text || '').trim()
  if (!t) return fallback
  return t.split(/\s+/)[0]
}

function lockedJoinHintText(meetingLinkOpenAt, startsAt) {
  let text = `ورود پس از فعال‌سازی توسط مصاحبه‌گر/پذیرش، یا از ${formatOpenTimeTehran(meetingLinkOpenAt)}`
  if (startsAt) {
    text += ` (۳۰ دقیقه قبل از شروع مصاحبه در ${formatMeetingTimeTehran(startsAt)})`
  }
  return `${text} فعال می‌شود.`
}

function CompactTip({ compact, title, children }) {
  if (!compact || !title) return children
  return (
    <span className="online-meeting-join-cta__tip" data-tip={title} title={title}>
      {children}
    </span>
  )
}

function MeetingLinkCopyButton({ meetingLink, compact = false }) {
  const [copied, setCopied] = useState(false)
  const fullLabel = copied ? 'کپی شد' : 'کپی لینک کامل الوکام'

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
    <CompactTip compact={compact} title={fullLabel}>
      <button
        type="button"
        className={`online-meeting-join-cta__copy-btn${compact ? ' online-meeting-join-cta__copy-btn--compact' : ''}`}
        onClick={handleCopy}
        data-testid="online-meeting-copy-btn"
        title={compact ? undefined : fullLabel}
        aria-label={fullLabel}
      >
        {compact ? 'کپی' : (copied ? 'کپی شد' : 'کپی لینک')}
      </button>
    </CompactTip>
  )
}

function StudentJoinOpenControl({
  studentJoinOpen,
  onToggleStudentJoinOpen,
  togglingStudentJoin = false,
  compact = false,
}) {
  if (!onToggleStudentJoinOpen) return null
  return (
    <label
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.35rem',
        fontSize: compact ? '0.75rem' : '0.82rem',
        marginTop: '0.35rem',
        cursor: togglingStudentJoin ? 'wait' : 'pointer',
      }}
      title="با فعال‌سازی، دانشجو می‌تواند قبل از ۳۰ دقیقه مانده به مصاحبه وارد جلسه شود."
    >
      <input
        type="checkbox"
        checked={!!studentJoinOpen}
        disabled={togglingStudentJoin}
        onChange={(e) => onToggleStudentJoinOpen(e.target.checked)}
        data-testid="student-join-open-toggle"
      />
      <span>{studentJoinOpen ? 'ورود زودهنگام دانشجو: فعال' : 'ورود زودهنگام دانشجو'}</span>
    </label>
  )
}

/**
 * دکمهٔ برجستهٔ ورود به جلسهٔ آنلاین.
 * دانشجو: قبل از زمان مجاز (۳۰ دقیقه قبل یا فعال‌سازی دستی) غیرفعال است.
 * پذیرش/ادمین (allowStaffCopy): همیشه می‌توانند وارد شوند.
 */
export default function OnlineMeetingJoinCta({
  mode = 'online',
  locationFa = '',
  meetingLink = null,
  /** لینک ساخته شده ولی ممکن است هنوز به دلیل قفل زمانی برای بیننده فرستاده نشده باشد */
  meetingLinkReady = null,
  meetingLinkOpenAt = null,
  meetingLinkIsVisible = false,
  startsAt = null,
  label = 'ورود به جلسهٔ آنلاین',
  compact = false,
  preparing = false,
  preparingText = 'لینک آنلاین در حال آماده‌سازی است؛ همین صفحه را کمی بعد تازه کنید.',
  preparingErrorText = 'آماده‌سازی لینک آنلاین بیش از حد معمول طول کشید. لطفاً با پذیرش تماس بگیرید یا صفحه را تازه کنید.',
  preparingFailed = false,
  /** نتیجهٔ مصاحبه ثبت شده؛ کلاس بسته است تا رزرو وقت جدید */
  resultRecorded = false,
  resultRecordedText = 'نتیجهٔ این مصاحبه ثبت شده و کلاس آن بسته است. در صورت نیاز به مصاحبهٔ دوباره، وقت جدیدی رزرو کنید.',
  studentJoinOpen = false,
  /** برای پذیرش/ادمین: ورود و کپی لینک میزبان بدون محدودیت زمانی */
  allowStaffCopy = false,
  onToggleStudentJoinOpen = null,
  togglingStudentJoin = false,
  /** اگر داده شود، ورود با API احراز هویت انجام می‌شود و URL خام در href نیست */
  onAuthenticatedJoin = null,
  authenticatedJoinReady = false,
}) {
  const [now, setNow] = useState(() => Date.now())

  const [joining, setJoining] = useState(false)
  const [joinErr, setJoinErr] = useState(null)

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30000)
    return () => clearInterval(timer)
  }, [])

  const shortLabel = firstWord(label, 'ورود')
  const visibleLabel = compact ? shortLabel : label

  if (mode !== 'online') {
    const place = (locationFa || '').trim() || '—'
    if (compact) {
      return (
        <div className="online-meeting-join-cta online-meeting-join-cta--in-person online-meeting-join-cta--compact">
          <CompactTip compact title={place}>
            <span className="online-meeting-join-cta__chip" data-testid="online-meeting-location-chip" aria-label={place}>مکان</span>
          </CompactTip>
        </div>
      )
    }
    return (
      <div className="online-meeting-join-cta online-meeting-join-cta--in-person">
        <span className="online-meeting-join-cta__location-label">محل حضوری:</span>
        <span className="online-meeting-join-cta__location">{place}</span>
      </div>
    )
  }

  if (resultRecorded) {
    return (
      <div className={`online-meeting-join-cta online-meeting-join-cta--closed${compact ? ' online-meeting-join-cta--compact' : ''}`}>
        <div className="online-meeting-join-cta__actions">
          <CompactTip compact={compact} title={resultRecordedText}>
            <button
              type="button"
              className="online-meeting-join-cta__btn"
              disabled
              aria-disabled="true"
              data-testid="online-meeting-closed-btn"
              aria-label={resultRecordedText}
            >
              {compact ? null : <span className="online-meeting-join-cta__icon" aria-hidden>🔒</span>}
              {compact ? 'بسته' : label}
            </button>
          </CompactTip>
        </div>
        {compact ? null : <p className="online-meeting-join-cta__hint">{resultRecordedText}</p>}
      </div>
    )
  }

  const openMs = meetingLinkOpenAt ? new Date(meetingLinkOpenAt).getTime() : null
  const studentCanEnterByTime = studentJoinOpen || openMs == null || now >= openMs
  const canEnterByTime = studentCanEnterByTime || allowStaffCopy
  const linkPresent = Boolean((meetingLink || '').trim()) || Boolean(onAuthenticatedJoin && authenticatedJoinReady)
  const linkReady = meetingLinkReady == null ? linkPresent : Boolean(meetingLinkReady || authenticatedJoinReady)
  const linkVisibleForViewer = meetingLinkIsVisible || authenticatedJoinReady || (allowStaffCopy && linkReady)
  const canJoin = linkPresent && linkVisibleForViewer && canEnterByTime
  const showStaffCopy = allowStaffCopy && linkPresent && linkVisibleForViewer
  const studentJoinControl = !compact && allowStaffCopy ? (
    <StudentJoinOpenControl
      studentJoinOpen={studentJoinOpen}
      onToggleStudentJoinOpen={onToggleStudentJoinOpen}
      togglingStudentJoin={togglingStudentJoin}
      compact={compact}
    />
  ) : null

  if (!studentCanEnterByTime && meetingLinkOpenAt && !studentJoinOpen && !allowStaffCopy) {
    const lockedHint = lockedJoinHintText(meetingLinkOpenAt, startsAt)
    return (
      <div className={`online-meeting-join-cta online-meeting-join-cta--locked${compact ? ' online-meeting-join-cta--compact' : ''}`}>
        <div className="online-meeting-join-cta__actions">
          <CompactTip compact={compact} title={lockedHint}>
            <button
              type="button"
              className="online-meeting-join-cta__btn"
              disabled
              aria-disabled="true"
              aria-label={lockedHint}
            >
              {compact ? null : <span className="online-meeting-join-cta__icon" aria-hidden>🎥</span>}
              {visibleLabel}
            </button>
          </CompactTip>
        </div>
        {compact ? null : (
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
        )}
      </div>
    )
  }

  if (preparing && !linkReady) {
    const waitText = preparingFailed ? preparingErrorText : preparingText
    return (
      <div className={`online-meeting-join-cta online-meeting-join-cta--waiting${compact ? ' online-meeting-join-cta--compact' : ''}`}>
        {compact ? (
          <CompactTip compact title={waitText}>
            <span
              className={`online-meeting-join-cta__chip${preparingFailed ? ' online-meeting-join-cta__chip--warn' : ''}`}
              data-testid="online-meeting-preparing-chip"
            >
              لینک
            </span>
          </CompactTip>
        ) : (
          <p className={`online-meeting-join-cta__hint${preparingFailed ? ' online-meeting-join-cta__hint--warn' : ''}`}>
            {waitText}
          </p>
        )}
        {studentJoinControl}
      </div>
    )
  }

  if (canJoin) {
    const handleAuthJoin = async (e) => {
      e.preventDefault()
      if (!onAuthenticatedJoin || joining) return
      setJoinErr(null)
      setJoining(true)
      try {
        const url = await onAuthenticatedJoin()
        if (url) window.open(url, '_blank', 'noopener,noreferrer')
      } catch (err) {
        setJoinErr(err?.response?.data?.detail || err?.message || 'ورود به کلاس ممکن نشد.')
      } finally {
        setJoining(false)
      }
    }
    const readyHint = allowStaffCopy && !studentCanEnterByTime
      ? 'ورود برای شما باز است؛ دانشجو هنوز نمی‌تواند وارد شود مگر «ورود زودهنگام دانشجو» را فعال کنید.'
      : 'برای ورود به کلاس روی دکمه بالا کلیک کنید.'
    const joinTip = compact ? label : undefined
    const joinInnerLabel = compact ? shortLabel : (joining ? 'در حال ورود…' : label)
    const joinControl = onAuthenticatedJoin ? (
      <CompactTip compact={compact} title={joinTip}>
        <button
          type="button"
          className="online-meeting-join-cta__btn online-meeting-join-cta__btn--active"
          data-testid="online-meeting-join-btn"
          disabled={joining}
          onClick={handleAuthJoin}
          aria-label={label}
        >
          {compact ? null : <span className="online-meeting-join-cta__icon" aria-hidden>▶</span>}
          {joinInnerLabel}
        </button>
      </CompactTip>
    ) : (
      <CompactTip compact={compact} title={joinTip}>
        <a
          href={meetingLink}
          target="_blank"
          rel="noopener noreferrer"
          className="online-meeting-join-cta__btn online-meeting-join-cta__btn--active"
          data-testid="online-meeting-join-btn"
          aria-label={label}
        >
          {compact ? null : <span className="online-meeting-join-cta__icon" aria-hidden>▶</span>}
          {joinInnerLabel}
        </a>
      </CompactTip>
    )
    return (
      <div className={`online-meeting-join-cta online-meeting-join-cta--ready${compact ? ' online-meeting-join-cta--compact' : ''}`}>
        <div className="online-meeting-join-cta__actions">
          {joinControl}
          {showStaffCopy ? <MeetingLinkCopyButton meetingLink={meetingLink} compact={compact} /> : null}
        </div>
        {compact ? null : (
          <p className="online-meeting-join-cta__hint online-meeting-join-cta__hint--success">
            {readyHint}
          </p>
        )}
        {joinErr ? (
          compact ? (
            <CompactTip compact title={joinErr}>
              <span className="online-meeting-join-cta__chip online-meeting-join-cta__chip--warn">خطا</span>
            </CompactTip>
          ) : (
            <p className="online-meeting-join-cta__hint online-meeting-join-cta__hint--warn">{joinErr}</p>
          )
        ) : null}
        {studentJoinControl}
      </div>
    )
  }

  if (showStaffCopy) {
    return (
      <div className={`online-meeting-join-cta online-meeting-join-cta--ready${compact ? ' online-meeting-join-cta--compact' : ''}`}>
        <MeetingLinkCopyButton meetingLink={meetingLink} compact={compact} />
        {compact ? null : (
          <p className="online-meeting-join-cta__hint">
            لینک میزبان آماده است؛ برای ورود از «کپی لینک» استفاده کنید.
          </p>
        )}
        {studentJoinControl}
      </div>
    )
  }

  return (
    <div className={`online-meeting-join-cta online-meeting-join-cta--waiting${compact ? ' online-meeting-join-cta--compact' : ''}`}>
      {compact ? (
        <CompactTip compact title={preparingText}>
          <span className="online-meeting-join-cta__chip" data-testid="online-meeting-preparing-chip">لینک</span>
        </CompactTip>
      ) : (
        <p className="online-meeting-join-cta__hint">{preparingText}</p>
      )}
      {studentJoinControl}
    </div>
  )
}
