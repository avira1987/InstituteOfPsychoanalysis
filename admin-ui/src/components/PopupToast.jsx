import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'

const DEFAULT_DURATION_MS = 10_000

/**
 * پیام‌های سیستمی به صورت پاپ‌آپ ثابت در بالای صفحه (بالای مودال‌ها).
 * @param {{
 *   toast?: { msg: string, type?: string } | null,
 *   message?: string,
 *   type?: string,
 *   onClose?: () => void,
 *   duration?: number,
 * }} props
 */
export default function PopupToast({
  toast,
  message,
  type,
  onClose,
  duration = DEFAULT_DURATION_MS,
}) {
  const msg = toast?.msg ?? message
  const kind = toast?.type === 'error' || type === 'error' ? 'error' : 'success'
  const timerRef = useRef(null)

  useEffect(() => {
    if (!msg || !onClose || duration <= 0) return undefined
    timerRef.current = setTimeout(onClose, duration)
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [msg, kind, onClose, duration])

  if (!msg) return null

  const handleClose = () => {
    if (timerRef.current) clearTimeout(timerRef.current)
    onClose?.()
  }

  return createPortal(
    <div className={`toast toast-${kind}`} role="alert">
      <span className="toast-body">{msg}</span>
      {onClose ? (
        <button
          type="button"
          className="toast-close"
          aria-label="بستن"
          title="بستن"
          onClick={handleClose}
        >
          ×
        </button>
      ) : null}
    </div>,
    document.body,
  )
}

export { DEFAULT_DURATION_MS as TOAST_DEFAULT_DURATION_MS }
