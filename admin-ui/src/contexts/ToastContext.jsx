import React, { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { panelApi } from '../services/api'
import PopupToast, { TOAST_DEFAULT_DURATION_MS } from '../components/PopupToast'

const ToastContext = createContext(null)

export const PANEL_FLASH_CREATED_EVENT = 'panel-flash-created'

function dispatchFlashCreated() {
  try {
    window.dispatchEvent(new CustomEvent(PANEL_FLASH_CREATED_EVENT))
  } catch {
    /* ignore */
  }
}

export function ToastProvider({ children }) {
  const { user } = useAuth()
  const location = useLocation()
  const [toast, setToast] = useState(null)

  const dismiss = useCallback(() => setToast(null), [])

  const showToast = useCallback(
    (message, type = 'success') => {
      const msg = String(message ?? '').trim()
      if (!msg) return
      const lvl = type === 'error' ? 'error' : 'success'
      setToast({ msg, type: lvl })
      if (user) {
        const sourcePath = `${location.pathname || ''}${location.search || ''}` || null
        panelApi
          .createFlashMessage({
            message: msg,
            level: lvl,
            source_path: sourcePath,
            category: 'popup',
          })
          .then(() => dispatchFlashCreated())
          .catch(() => {
            /* fire-and-forget */
          })
      }
    },
    [user, location.pathname, location.search],
  )

  const value = useMemo(() => ({ showToast }), [showToast])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <PopupToast
        toast={toast}
        onClose={dismiss}
        duration={TOAST_DEFAULT_DURATION_MS}
      />
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return ctx
}
