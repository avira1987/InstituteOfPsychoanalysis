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

  if (resultRecorded) {
    return (
      <div className={`online-meeting-join-cta online-meeting-join-cta--closed${compact ? ' online-meeting-join-cta--compact' : ''}`}>
        <div className="online-meeting-join-cta__actions">
          <button
            type="button"
            className="online-meeting-join-cta__btn"
            disabled
            aria-disabled="true"
            data-testid="online-meeting-closed-btn"
          >
            <span className="online-meeting-join-cta__icon" aria-hidden>🔒</span>
            {label}
          </button>
        </div>
        <p className="online-meeting-join-cta__hint">{resultRecordedText}</p>
      </div>
    )
  }

  const openMs = meetingLinkOpenAt ? new Date(meetingLinkOpenAt).getTime() : null
  const studentCanEnterByTime = studentJoinOpen || openMs == null || now >= openMs
  const canEnterByTime = studentCanEnterByTime || allowStaffCopy
  const linkPresent = Boolean((meetingLink || '').trim())
  const linkReady = meetingLinkReady == null ? linkPresent : Boolean(meetingLinkReady)
  const linkVisibleForViewer = meetingLinkIsVisible || (allowStaffCopy && linkReady)
  const canJoin = linkPresent && linkVisibleForViewer && canEnterByTime
  const showStaffCopy = allowStaffCopy && linkPresent && linkVisibleForViewer
  const studentJoinControl = allowStaffCopy ? (
    <StudentJoinOpenControl
      studentJoinOpen={studentJoinOpen}
      onToggleStudentJoinOpen={onToggleStudentJoinOpen}
      togglingStudentJoin={togglingStudentJoin}
      compact={compact}
    />
  ) : null

  if (!studentCanEnterByTime && meetingLinkOpenAt && !studentJoinOpen && !allowStaffCopy) {
    return (
      <div className={`online-meeting-join-cta online-meeting-join-cta--locked${compact ? ' online-meeting-join-cta--compact' : ''}`}>
        <div className="online-meeting-join-cta__actions">
          <button type="button" className="online-meeting-join-cta__btn" disabled aria-disabled="true">
            <span className="online-meeting-join-cta__icon" aria-hidden>🎥</span>
            {label}
          </button>
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
        {studentJoinControl}
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
          {allowStaffCopy && !studentCanEnterByTime
            ? 'ورود برای شما باز است؛ دانشجو هنوز نمی‌تواند وارد شود مگر «ورود زودهنگام دانشجو» را فعال کنید.'
            : 'برای ورود به کلاس الوکام روی دکمه بالا کلیک کنید.'}
        </p>
        {studentJoinControl}
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
        {studentJoinControl}
      </div>
    )
  }

  return (
    <div className={`online-meeting-join-cta online-meeting-join-cta--waiting${compact ? ' online-meeting-join-cta--compact' : ''}`}>
      <p className="online-meeting-join-cta__hint">
        {preparingText}
      </p>
      {studentJoinControl}
    </div>
  )
}
