import { createPortal } from 'react-dom'

/**
 * پیام‌های سیستمی به صورت پاپ‌آپ ثابت در بالای صفحه (بالای مودال‌ها).
 * @param {{ toast: { msg: string, type?: string } | null }} props
 */
export default function PopupToast({ toast }) {
  if (!toast?.msg) return null
  const kind = toast.type === 'error' ? 'error' : 'success'
  return createPortal(
    <div className={`toast toast-${kind}`} role="alert">
      {toast.msg}
    </div>,
    document.body
  )
}
