import React, { useCallback, useEffect, useState } from 'react'
import { courseCommitteeRosterApi } from '../services/api'

export default function SemesterPrepCatalogPanel({ showToast, onUpdated }) {
  const [courses, setCourses] = useState([])
  const [tracks, setTracks] = useState([])
  const [loading, setLoading] = useState(true)
  const [courseName, setCourseName] = useState('')
  const [trackName, setTrackName] = useState('')
  const [busy, setBusy] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [coursesRes, tracksRes] = await Promise.all([
        courseCommitteeRosterApi.listCourses(),
        courseCommitteeRosterApi.listTracks(),
      ])
      setCourses(coursesRes.data?.courses || [])
      setTracks(tracksRes.data?.tracks || [])
    } catch {
      setCourses([])
      setTracks([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const addCourse = async (e) => {
    e.preventDefault()
    const name = courseName.trim()
    if (!name) return
    setBusy('course')
    try {
      await courseCommitteeRosterApi.createCourse({ name_fa: name })
      showToast?.('درس به کاتالوگ اضافه شد.')
      setCourseName('')
      await load()
      onUpdated?.()
    } catch (err) {
      const d = err?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در افزودن درس', 'error')
    } finally {
      setBusy(null)
    }
  }

  const addTrack = async (e) => {
    e.preventDefault()
    const name = trackName.trim()
    if (!name) return
    setBusy('track')
    try {
      await courseCommitteeRosterApi.createTrack({ name_fa: name })
      showToast?.('رسته اضافه شد.')
      setTrackName('')
      await load()
      onUpdated?.()
    } catch (err) {
      const d = err?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در افزودن رسته', 'error')
    } finally {
      setBusy(null)
    }
  }

  return (
    <section id="courses" data-testid="semester-prep-catalog-panel">
      <h3 style={{ fontSize: '1.05rem', margin: '0 0 0.35rem' }}>کاتالوگ دروس و رسته‌ها</h3>
      <p className="muted" style={{ margin: '0 0 1rem', fontSize: '0.88rem', lineHeight: 1.65 }}>
        دروس و رسته‌های ثبت‌شده در فرم «لیست دروس» فرایند آماده‌سازی قابل انتخاب هستند.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
        <form onSubmit={addCourse} style={{ padding: '0.85rem', border: '1px solid #e2e8f0', borderRadius: 8 }}>
          <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.92rem' }}>افزودن درس</h4>
          <input
            type="text"
            value={courseName}
            onChange={(e) => setCourseName(e.target.value)}
            placeholder="نام درس"
            style={{ width: '100%', marginBottom: '0.5rem' }}
          />
          <button type="submit" className="btn btn-primary btn-sm" disabled={busy === 'course'}>
            {busy === 'course' ? '…' : 'ثبت درس'}
          </button>
        </form>
        <form onSubmit={addTrack} style={{ padding: '0.85rem', border: '1px solid #e2e8f0', borderRadius: 8 }}>
          <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.92rem' }}>افزودن رسته</h4>
          <input
            type="text"
            value={trackName}
            onChange={(e) => setTrackName(e.target.value)}
            placeholder="نام رسته"
            style={{ width: '100%', marginBottom: '0.5rem' }}
          />
          <button type="submit" className="btn btn-primary btn-sm" disabled={busy === 'track'}>
            {busy === 'track' ? '…' : 'ثبت رسته'}
          </button>
        </form>
      </div>

      {loading ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
          <div>
            <strong style={{ fontSize: '0.88rem' }}>دروس ({courses.length})</strong>
            {courses.length === 0 ? (
              <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.82rem' }}>هنوز درسی ثبت نشده.</p>
            ) : (
              <ul style={{ margin: '0.35rem 0 0', paddingRight: '1.1rem', fontSize: '0.82rem', lineHeight: 1.6 }}>
                {courses.slice(0, 12).map((c) => (
                  <li key={c.value}>{c.label_fa}</li>
                ))}
                {courses.length > 12 ? <li className="muted">… و {courses.length - 12} مورد دیگر</li> : null}
              </ul>
            )}
          </div>
          <div>
            <strong style={{ fontSize: '0.88rem' }}>رسته‌ها ({tracks.length})</strong>
            {tracks.length === 0 ? (
              <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.82rem' }}>هنوز رسته‌ای ثبت نشده.</p>
            ) : (
              <ul style={{ margin: '0.35rem 0 0', paddingRight: '1.1rem', fontSize: '0.82rem', lineHeight: 1.6 }}>
                {tracks.map((t) => (
                  <li key={t.value}>{t.label_fa}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
