import { useCallback, useEffect, useState } from 'react'
import { processExecApi } from '../services/api'

/**
 * Fetch student artifacts (transcripts, certificates) for portal display.
 */
export function useStudentArtifacts(studentId) {
  const [loading, setLoading] = useState(true)
  const [artifacts, setArtifacts] = useState([])
  const [error, setError] = useState(null)
  const [downloadingId, setDownloadingId] = useState(null)
  const [downloadError, setDownloadError] = useState(null)

  const reload = useCallback(() => {
    if (!studentId) {
      setArtifacts([])
      setLoading(false)
      return undefined
    }
    let cancelled = false
    setLoading(true)
    processExecApi
      .studentArtifacts(studentId)
      .then((r) => {
        if (cancelled) return
        setArtifacts(r.data?.artifacts || [])
        setError(null)
      })
      .catch(() => {
        if (cancelled) return
        setArtifacts([])
        setError('بارگذاری کارنامه‌ها و گواهی‌ها ممکن نشد.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [studentId])

  useEffect(() => {
    const cleanup = reload()
    return cleanup
  }, [reload])

  const downloadPdf = async (artifact) => {
    if (!studentId || !artifact?.id) return
    setDownloadingId(artifact.id)
    setDownloadError(null)
    try {
      const fallback = `${artifact.type || 'document'}.pdf`
      await processExecApi.downloadStudentDocumentPdf(studentId, artifact.id, fallback)
    } catch (_) {
      setDownloadError('دانلود PDF ممکن نشد. لطفاً دوباره تلاش کنید.')
    } finally {
      setDownloadingId(null)
    }
  }

  return {
    loading,
    artifacts,
    error,
    downloadingId,
    downloadError,
    downloadPdf,
    reload,
  }
}
