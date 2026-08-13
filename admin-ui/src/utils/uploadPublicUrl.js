/** آیا مسیر آپلود نیاز به توکن دارد؟ (آواتار عمومی است) */
function isProtectedUploadPath(path) {
  if (!path || typeof path !== 'string') return false
  if (!path.startsWith('/uploads/')) return false
  if (path.startsWith('/uploads/avatars/')) return false
  return true
}

const _signedCache = new Map() // path -> { url, exp }

function _apiBase() {
  if (typeof window === 'undefined') return ''
  const base = (import.meta?.env?.VITE_API_BASE || '').replace(/\/$/, '')
  return base || ''
}

function _syncSignUpload(pathname) {
  const token = typeof localStorage !== 'undefined' ? localStorage.getItem('token') : null
  if (!token) return null
  const cached = _signedCache.get(pathname)
  const now = Math.floor(Date.now() / 1000)
  if (cached && cached.exp > now + 15) return cached.url
  try {
    const xhr = new XMLHttpRequest()
    const q = encodeURIComponent(pathname)
    xhr.open('GET', `${_apiBase()}/api/auth/upload-sign?path=${q}`, false)
    xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.send(null)
    if (xhr.status >= 200 && xhr.status < 300) {
      const data = JSON.parse(xhr.responseText || '{}')
      if (data.signed_url) {
        _signedCache.set(pathname, {
          url: data.signed_url,
          exp: data.expires_at || now + 240,
        })
        return data.signed_url
      }
    }
  } catch {
    /* ignore — caller gets empty / unsigned */
  }
  return null
}

/**
 * آدرس قابل نمایش در مرورگر برای مسیر نسبی آپلود (مثلاً `/uploads/...`).
 * برای مدارک محافظت‌شده از URL کوتاه‌عمر امضاشده استفاده می‌شود (نه JWT در query).
 */
export function resolveUploadPublicUrl(url) {
  if (!url || typeof url !== 'string') return ''
  if (url.startsWith('http://') || url.startsWith('https://')) {
    try {
      const u = new URL(url)
      // strip legacy JWT query params
      u.searchParams.delete('access_token')
      u.searchParams.delete('token')
      if (isProtectedUploadPath(u.pathname)) {
        const signed = _syncSignUpload(u.pathname)
        if (signed) {
          if (signed.startsWith('http')) return signed
          return `${u.origin}${signed}`
        }
      }
      return u.toString()
    } catch {
      return url
    }
  }

  let path = url.startsWith('/') ? url : `/${url}`
  const qIndex = path.indexOf('?')
  const pathname = qIndex >= 0 ? path.slice(0, qIndex) : path

  if (isProtectedUploadPath(pathname)) {
    const signed = _syncSignUpload(pathname)
    if (signed) return signed
  }

  return pathname
}

/**
 * حدس نوع محتوا از پسوند مسیر/URL وقتی فیلد mime در داده ذخیره نشده باشد.
 * @param {string|null|undefined} pathOrUrl
 * @returns {string} mime یا رشتهٔ خالی
 */
export function inferMimeFromUploadRef(pathOrUrl) {
  if (!pathOrUrl || typeof pathOrUrl !== 'string') return ''
  const base = pathOrUrl.split('?')[0].toLowerCase()
  if (base.endsWith('.pdf')) return 'application/pdf'
  if (base.endsWith('.png')) return 'image/png'
  if (base.endsWith('.jpg') || base.endsWith('.jpeg')) return 'image/jpeg'
  if (base.endsWith('.webp')) return 'image/webp'
  if (base.endsWith('.gif')) return 'image/gif'
  return ''
}

/**
 * مقدار فیلد file_upload در context_data — معمولاً شیء { url, mime, file_name }؛
 * گاهی رشتهٔ مسیر (/uploads/...) یا رشتهٔ JSON سِریال‌شده (import/قدیم).
 * @returns {{ url: string|null, mime: string, fileName: string|null, isLocalPlaceholder: boolean }}
 */
export function parseStepFileUploadValue(val) {
  const empty = { url: null, mime: '', fileName: null, isLocalPlaceholder: false }
  if (val == null) return empty
  if (typeof val === 'string') {
    const s = val.trim()
    if (!s) return empty
    if (s.startsWith('{')) {
      try {
        const o = JSON.parse(s)
        if (o && typeof o === 'object' && !Array.isArray(o)) return parseStepFileUploadValue(o)
      } catch {
        /* ignore */
      }
    }
    if (s.startsWith('/') || s.startsWith('http://') || s.startsWith('https://')) {
      return { url: s, mime: inferMimeFromUploadRef(s), fileName: null, isLocalPlaceholder: false }
    }
    // فقط رشته‌ای را «نام فایل محلی» در نظر بگیر که واقعاً پسوند فایل شناخته‌شده دارد؛
    // در غیر این صورت یک مقدار متنی معمولی است (مثلاً scheduled_notification، sms و…).
    if (inferMimeFromUploadRef(s)) {
      return { url: null, mime: '', fileName: s, isLocalPlaceholder: true }
    }
    return empty
  }
  if (typeof val === 'object' && !Array.isArray(val)) {
    const rawUrl = val.url ?? val.public_url ?? val.href
    const url = rawUrl != null && String(rawUrl).trim() ? String(rawUrl).trim() : null
    let mime = ''
    if (typeof val.mime === 'string') mime = val.mime
    else if (typeof val.content_type === 'string') mime = val.content_type
    const fileName = val.file_name != null ? String(val.file_name) : null
    const isLocalPlaceholder = Boolean(fileName || val.size != null) && !url
    const mimeFilled = mime || (url ? inferMimeFromUploadRef(url) : '')
    return { url, mime: mimeFilled, fileName, isLocalPlaceholder }
  }
  return empty
}
