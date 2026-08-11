import React, { useCallback, useEffect, useState } from 'react'
import { courseCommitteeRosterApi } from '../services/api'

export default function SemesterPrepCatalogPanel({ showToast, onUpdated }) {
  const [courses, setCourses] = useState([])
  const [tracks, setTracks] = useState([])
  const [loading, setLoading] = useState(true)
  const [courseName, setCourseName] = useState('')
  const [courseTrack, setCourseTrack] = useState('')
  const [trackName, setTrackName] = useState('')
  const [busy, setBusy] = useState(null)
  const [editingCourse, setEditingCourse] = useState(null)
  const [editName, setEditName] = useState('')
  const [editTrack, setEditTrack] = useState('')

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

  const trackLabelByCode = Object.fromEntries(
    tracks.map((t) => [t.value, t.label_fa || t.value]),
  )

  const notifyUpdated = async () => {
    await load()
    onUpdated?.()
  }

  const addCourse = async (e) => {
    e.preventDefault()
    const name = courseName.trim()
    const track = courseTrack.trim()
    if (!name) {
      showToast?.('نام درس را وارد کنید.', 'error')
      return
    }
    if (!track) {
      showToast?.('برای ایجاد درس باید یکی از رسته‌های موجود را انتخاب کنید.', 'error')
      return
    }
    if (tracks.length === 0) {
      showToast?.('ابتدا حداقل یک رسته ثبت کنید، سپس درس را اضافه کنید.', 'error')
      return
    }
    setBusy('course')
    try {
      await courseCommitteeRosterApi.createCourse({ name_fa: name, track })
      showToast?.('درس به کاتالوگ اضافه شد.')
      setCourseName('')
      setCourseTrack('')
      await notifyUpdated()
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
      await notifyUpdated()
    } catch (err) {
      const d = err?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در افزودن رسته', 'error')
    } finally {
      setBusy(null)
    }
  }

  const startEditCourse = (course) => {
    setEditingCourse(course.value)
    setEditName(course.label_fa || '')
    setEditTrack(course.track || '')
  }

  const cancelEditCourse = () => {
    setEditingCourse(null)
    setEditName('')
    setEditTrack('')
  }

  const saveEditCourse = async () => {
    if (!editingCourse) return
    const name = editName.trim()
    const track = editTrack.trim()
    if (!name) {
      showToast?.('نام درس را وارد کنید.', 'error')
      return
    }
    if (!track) {
      showToast?.('انتخاب رسته الزامی است.', 'error')
      return
    }
    setBusy(`edit:${editingCourse}`)
    try {
      await courseCommitteeRosterApi.updateCourse(editingCourse, {
        name_fa: name,
        track,
      })
      showToast?.('درس به‌روز شد.')
      cancelEditCourse()
      await notifyUpdated()
    } catch (err) {
      const d = err?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در ویرایش درس', 'error')
    } finally {
      setBusy(null)
    }
  }

  const deleteCourse = async (course) => {
    const label = course.label_fa || course.value
    if (!window.confirm(`درس «${label}» از کاتالوگ حذف شود؟`)) return
    setBusy(`del-course:${course.value}`)
    try {
      await courseCommitteeRosterApi.deleteCourse(course.value)
      showToast?.('درس حذف شد.')
      if (editingCourse === course.value) cancelEditCourse()
      await notifyUpdated()
    } catch (err) {
      const d = err?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در حذف درس', 'error')
    } finally {
      setBusy(null)
    }
  }

  const deleteTrack = async (track) => {
    const label = track.label_fa || track.value
    if (!window.confirm(`رسته «${label}» حذف شود؟ (فقط اگر عضو و درس وابسته نداشته باشد)`)) return
    setBusy(`del-track:${track.value}`)
    try {
      await courseCommitteeRosterApi.deleteTrack(track.value)
      showToast?.('رسته حذف شد.')
      if (courseTrack === track.value) setCourseTrack('')
      if (editTrack === track.value) setEditTrack('')
      await notifyUpdated()
    } catch (err) {
      const d = err?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در حذف رسته', 'error')
    } finally {
      setBusy(null)
    }
  }

  return (
    <section id="courses" data-testid="semester-prep-catalog-panel">
      <h3 style={{ fontSize: '1.05rem', margin: '0 0 0.35rem' }}>کاتالوگ دروس و رسته‌ها</h3>
      <p className="muted" style={{ margin: '0 0 1rem', fontSize: '0.88rem', lineHeight: 1.65 }}>
        دروس و رسته‌های ثبت‌شده در فرم «لیست دروس» فرایند آماده‌سازی قابل انتخاب هستند.
        می‌توانید درس و رسته را اضافه، ویرایش یا حذف کنید.
      </p>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: '1rem',
          marginBottom: '1.15rem',
        }}
      >
        <form
          onSubmit={addCourse}
          style={{ padding: '0.85rem', border: '1px solid #e2e8f0', borderRadius: 8, background: '#f8fafc' }}
        >
          <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.92rem' }}>افزودن درس</h4>
          <input
            type="text"
            value={courseName}
            onChange={(e) => setCourseName(e.target.value)}
            placeholder="نام درس"
            style={{ width: '100%', marginBottom: '0.5rem' }}
            data-testid="catalog-course-name"
          />
          <select
            value={courseTrack}
            onChange={(e) => setCourseTrack(e.target.value)}
            required
            disabled={tracks.length === 0}
            style={{ width: '100%', marginBottom: '0.5rem' }}
            data-testid="catalog-course-track"
            aria-label="رسته درس"
          >
            <option value="">
              {tracks.length === 0 ? 'ابتدا یک رسته ثبت کنید' : 'انتخاب رسته (الزامی)'}
            </option>
            {tracks.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label_fa || t.value}
              </option>
            ))}
          </select>
          <button
            type="submit"
            className="btn btn-primary btn-sm"
            disabled={busy === 'course' || tracks.length === 0}
          >
            {busy === 'course' ? '…' : 'ثبت درس'}
          </button>
        </form>

        <form
          onSubmit={addTrack}
          style={{ padding: '0.85rem', border: '1px solid #e2e8f0', borderRadius: 8, background: '#f8fafc' }}
        >
          <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.92rem' }}>افزودن رسته</h4>
          <input
            type="text"
            value={trackName}
            onChange={(e) => setTrackName(e.target.value)}
            placeholder="نام رسته"
            style={{ width: '100%', marginBottom: '0.5rem' }}
            data-testid="catalog-track-name"
          />
          <button type="submit" className="btn btn-primary btn-sm" disabled={busy === 'track'}>
            {busy === 'track' ? '…' : 'ثبت رسته'}
          </button>
        </form>
      </div>

      {loading ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.15rem' }}>
          <div>
            <strong style={{ fontSize: '0.9rem', display: 'block', marginBottom: '0.45rem' }}>
              دروس ({courses.length})
            </strong>
            {courses.length === 0 ? (
              <p className="muted" style={{ margin: 0, fontSize: '0.82rem' }}>
                هنوز درسی ثبت نشده.
              </p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table" style={{ fontSize: '0.84rem', width: '100%' }}>
                  <thead>
                    <tr>
                      <th>نام درس</th>
                      <th>رسته</th>
                      <th style={{ width: 160 }}>عملیات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {courses.map((c) => {
                      const isEditing = editingCourse === c.value
                      return (
                        <tr key={c.value} data-testid={`catalog-course-row-${c.value}`}>
                          <td>
                            {isEditing ? (
                              <input
                                type="text"
                                value={editName}
                                onChange={(e) => setEditName(e.target.value)}
                                style={{ width: '100%', minWidth: 140 }}
                                data-testid="catalog-course-edit-name"
                              />
                            ) : (
                              c.label_fa
                            )}
                          </td>
                          <td>
                            {isEditing ? (
                              <select
                                value={editTrack}
                                onChange={(e) => setEditTrack(e.target.value)}
                                style={{ width: '100%', minWidth: 140 }}
                                data-testid="catalog-course-edit-track"
                              >
                                <option value="">انتخاب رسته</option>
                                {tracks.map((t) => (
                                  <option key={t.value} value={t.value}>
                                    {t.label_fa || t.value}
                                  </option>
                                ))}
                              </select>
                            ) : c.track ? (
                              trackLabelByCode[c.track] || c.track
                            ) : (
                              <span className="muted">—</span>
                            )}
                          </td>
                          <td>
                            {isEditing ? (
                              <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                                <button
                                  type="button"
                                  className="btn btn-primary btn-sm"
                                  disabled={busy === `edit:${c.value}`}
                                  onClick={saveEditCourse}
                                >
                                  ذخیره
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-secondary btn-sm"
                                  onClick={cancelEditCourse}
                                >
                                  انصراف
                                </button>
                              </div>
                            ) : (
                              <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                                <button
                                  type="button"
                                  className="btn btn-secondary btn-sm"
                                  onClick={() => startEditCourse(c)}
                                >
                                  ویرایش
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-danger btn-sm"
                                  disabled={busy === `del-course:${c.value}`}
                                  onClick={() => deleteCourse(c)}
                                  data-testid={`catalog-course-delete-${c.value}`}
                                >
                                  حذف
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div>
            <strong style={{ fontSize: '0.9rem', display: 'block', marginBottom: '0.45rem' }}>
              رسته‌ها ({tracks.length})
            </strong>
            {tracks.length === 0 ? (
              <p className="muted" style={{ margin: 0, fontSize: '0.82rem' }}>
                هنوز رسته‌ای ثبت نشده.
              </p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table" style={{ fontSize: '0.84rem', width: '100%' }}>
                  <thead>
                    <tr>
                      <th>نام رسته</th>
                      <th>کد</th>
                      <th style={{ width: 100 }}>عملیات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tracks.map((t) => (
                      <tr key={t.value} data-testid={`catalog-track-row-${t.value}`}>
                        <td>{t.label_fa}</td>
                        <td>
                          <span className="muted" style={{ fontSize: '0.78rem' }}>
                            {t.value}
                          </span>
                        </td>
                        <td>
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            disabled={busy === `del-track:${t.value}`}
                            onClick={() => deleteTrack(t)}
                            data-testid={`catalog-track-delete-${t.value}`}
                          >
                            حذف
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
