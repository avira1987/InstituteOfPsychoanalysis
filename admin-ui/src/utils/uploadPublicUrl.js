/** آدرس قابل نمایش در مرورگر برای مسیر نسبی آپلود (مثلاً `/uploads/...`). */
export function resolveUploadPublicUrl(url) {
  if (!url || typeof url !== 'string') return ''
  if (url.startsWith('http')) return url
  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  return `${origin}${url.startsWith('/') ? '' : '/'}${url}`
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
    return { url: null, mime: '', fileName: s, isLocalPlaceholder: true }
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
