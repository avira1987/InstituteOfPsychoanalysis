import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { courseCommitteeRosterApi, userApi } from '../services/api'

const KIND_LABELS = {
  instructor: 'مدرس',
  teaching_assistant: 'کمک‌مدرس',
}

function courseLabel(courseOptions, code) {
  const hit = (courseOptions || []).find((c) => c.value === code)
  return hit?.label_fa || code
}

function MemberTable({
  title,
  kind,
  rows,
  track,
  courseOptions,
  onUpdated,
  onDeleted,
  showToast,
}) {
  const [editingId, setEditingId] = useState(null)
  const [legacy, setLegacy] = useState(false)
  const [courses, setCourses] = useState([])
  const [saving, setSaving] = useState(false)

  const startEdit = (row) => {
    if (!row.user_id) {
      showToast?.('این عضو هنوز به کاربر سامانه متصل نیست — ابتدا از فرم افزودن، کاربر ایجاد یا متصل کنید.', 'error')
      return
    }
    setEditingId(row.user_id)
    setLegacy(Boolean(row.roster_legacy))
    setCourses(Array.isArray(row.authorized_courses) ? [...row.authorized_courses] : [])
  }

  const saveEdit = async () => {
    if (!editingId) return
    setSaving(true)
    try {
      await courseCommitteeRosterApi.updateMember(editingId, {
        track,
        kind,
        roster_legacy: legacy,
        authorized_courses: legacy ? [] : courses,
      })
      showToast?.('مجوزها به‌روز شد.')
      setEditingId(null)
      onUpdated?.()
    } catch (e) {
      const d = e?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در به‌روزرسانی', 'error')
    } finally {
      setSaving(false)
    }
  }

  const remove = async (row) => {
    const name = row.label_fa || ''
    if (!name) return
    if (!window.confirm(`«${name}» از چارت این رسته حذف شود؟`)) return
    try {
      await courseCommitteeRosterApi.deleteMember({ track, kind, name_fa: name })
      showToast?.('عضو از چارت حذف شد.')
      onDeleted?.()
    } catch (e) {
      const d = e?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در حذف', 'error')
    }
  }

  return (
    <section style={{ marginBottom: '1.25rem' }}>
      <h4 style={{ margin: '0 0 0.6rem', fontSize: '0.95rem', fontWeight: 700 }}>{title}</h4>
      {rows.length === 0 ? (
        <p className="muted" style={{ margin: 0, fontSize: '0.88rem' }}>عضوی ثبت نشده است.</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table" style={{ fontSize: '0.85rem' }}>
            <thead>
              <tr>
                <th>نام</th>
                <th>پرسنل موجود</th>
                <th>دروس مجاز</th>
                <th>کاربر سامانه</th>
                <th style={{ width: 140 }}>عملیات</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const isEditing = editingId === row.user_id
                return (
                  <tr key={`${kind}-${row.value}-${row.roster_key || ''}`}>
                    <td>{row.label_fa}</td>
                    <td>{row.roster_legacy ? 'بله' : 'خیر'}</td>
                    <td>
                      {row.roster_legacy ? (
                        <span className="muted">همه دروس</span>
                      ) : (row.authorized_courses || []).length ? (
                        (row.authorized_courses || []).map((c) => courseLabel(courseOptions, c)).join('، ')
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>{row.user_id ? 'متصل' : 'فقط چارت'}</td>
                    <td>
                      {isEditing ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', minWidth: 200 }}>
                          <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem' }}>
                            <input
                              type="checkbox"
                              checked={legacy}
                              onChange={(e) => setLegacy(e.target.checked)}
                            />
                            پرسنل موجود (همه دروس)
                          </label>
                          {!legacy && (
                            <select
                              multiple
                              value={courses}
                              onChange={(e) =>
                                setCourses(Array.from(e.target.selectedOptions, (o) => o.value))
                              }
                              style={{ minHeight: 72, fontSize: '0.8rem' }}
                            >
                              {(courseOptions || []).map((c) => (
                                <option key={c.value} value={c.value}>
                                  {c.label_fa}
                                </option>
                              ))}
                            </select>
                          )}
                          <div style={{ display: 'flex', gap: '0.35rem' }}>
                            <button type="button" className="btn btn-primary btn-sm" disabled={saving} onClick={saveEdit}>
                              ذخیره
                            </button>
                            <button type="button" className="btn btn-secondary btn-sm" onClick={() => setEditingId(null)}>
                              انصراف
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                          <button type="button" className="btn btn-secondary btn-sm" onClick={() => startEdit(row)}>
                            مجوزها
                          </button>
                          <button type="button" className="btn btn-danger btn-sm" onClick={() => remove(row)}>
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
    </section>
  )
}

/**
 * پنل مدیریت چارت مدرسین و کمک‌مدرسین — ثبت اولیه پرسنل موجود بدون فرایند ۴۷/۴۹.
 */
export default function CourseCommitteeRosterPanel({ showToast, embedded = true }) {
  const [tracks, setTracks] = useState([])
  const [track, setTrack] = useState('')
  const [roster, setRoster] = useState({ instructors: [], teaching_assistants: [] })
  const [courseOptions, setCourseOptions] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const [addMode, setAddMode] = useState('create')
  const [addKind, setAddKind] = useState('teaching_assistant')
  const [addName, setAddName] = useState('')
  const [addUserQuery, setAddUserQuery] = useState('')
  const [userHits, setUserHits] = useState([])
  const [selectedUserId, setSelectedUserId] = useState('')
  const [addLegacy, setAddLegacy] = useState(true)
  const [addCourses, setAddCourses] = useState([])

  const loadMeta = useCallback(async () => {
    try {
      const [tracksRes, coursesRes] = await Promise.all([
        courseCommitteeRosterApi.listTracks(),
        courseCommitteeRosterApi.listCourses(),
      ])
      const trackRows = tracksRes.data?.tracks || []
      setTracks(trackRows)
      setCourseOptions(coursesRes.data?.courses || [])
      if (!track && trackRows.length) {
        setTrack(trackRows[0].value)
      }
    } catch {
      showToast?.('خطا در بارگذاری رسته‌ها', 'error')
    }
  }, [showToast, track])

  const loadRoster = useCallback(async () => {
    if (!track) {
      setRoster({ instructors: [], teaching_assistants: [] })
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const res = await courseCommitteeRosterApi.getDetail(track)
      setRoster(res.data?.roster || { instructors: [], teaching_assistants: [] })
    } catch {
      showToast?.('خطا در بارگذاری چارت', 'error')
      setRoster({ instructors: [], teaching_assistants: [] })
    } finally {
      setLoading(false)
    }
  }, [showToast, track])

  useEffect(() => {
    loadMeta()
  }, [loadMeta])

  useEffect(() => {
    loadRoster()
  }, [loadRoster])

  useEffect(() => {
    if (addMode !== 'link') return undefined
    const q = addUserQuery.trim()
    if (q.length < 2) {
      setUserHits([])
      return undefined
    }
    const t = setTimeout(async () => {
      try {
        const res = await userApi.list({ search: q, limit: 12 })
        const rows = Array.isArray(res.data) ? res.data : res.data?.users || []
        setUserHits(rows)
      } catch {
        setUserHits([])
      }
    }, 300)
    return () => clearTimeout(t)
  }, [addMode, addUserQuery])

  const trackLabel = useMemo(() => {
    const hit = tracks.find((t) => t.value === track)
    return hit?.label_fa || track
  }, [tracks, track])

  const resetAddForm = () => {
    setAddName('')
    setAddUserQuery('')
    setSelectedUserId('')
    setUserHits([])
    setAddLegacy(true)
    setAddCourses([])
  }

  const submitAdd = async (e) => {
    e.preventDefault()
    if (!track) {
      showToast?.('رسته را انتخاب کنید.', 'error')
      return
    }
    const payload = {
      track,
      kind: addKind,
      roster_legacy: addLegacy,
      authorized_courses: addLegacy ? [] : addCourses,
    }
    setBusy(true)
    try {
      if (addMode === 'link') {
        if (!selectedUserId) {
          showToast?.('کاربر را انتخاب کنید.', 'error')
          return
        }
        await courseCommitteeRosterApi.linkMember({ ...payload, user_id: selectedUserId })
        showToast?.('کاربر به چارت متصل شد.')
      } else {
        const name = addName.trim()
        if (!name) {
          showToast?.('نام فارسی را وارد کنید.', 'error')
          return
        }
        await courseCommitteeRosterApi.createMember({ ...payload, name_fa: name })
        showToast?.('عضو جدید ثبت شد.')
      }
      resetAddForm()
      await loadRoster()
    } catch (err) {
      const d = err?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در ثبت عضو', 'error')
    } finally {
      setBusy(false)
    }
  }

  const wrapStyle = embedded
    ? {
        marginBottom: '1.25rem',
        padding: '1rem 1.15rem',
        borderRight: '4px solid #0d9488',
        background: 'linear-gradient(180deg, #f0fdfa 0%, #fff 100%)',
      }
    : { padding: '1rem 0' }

  return (
    <div className="card" style={wrapStyle} data-testid="course-committee-roster-panel">
      <div style={{ marginBottom: '0.85rem' }}>
        <h3 style={{ margin: '0 0 0.35rem', fontSize: '1.05rem' }}>چارت مدرسین و کمک‌مدرسین</h3>
        <p className="muted" style={{ margin: 0, fontSize: '0.88rem', lineHeight: 1.55 }}>
          ثبت اولیه پرسنل موجود — بدون نیاز به فرایند ارتقا. کمک‌مدرس و مدرس جدید پس از راه‌اندازی از
          فرایندهای ۴۷ و ۴۹ تعریف می‌شوند.
        </p>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', marginBottom: '1rem' }}>
        <label style={{ fontSize: '0.88rem', fontWeight: 600 }}>
          رسته:{' '}
          <select value={track} onChange={(e) => setTrack(e.target.value)} style={{ minWidth: 220 }}>
            {tracks.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label_fa}
              </option>
            ))}
          </select>
        </label>
        <span className="muted" style={{ fontSize: '0.82rem' }}>{trackLabel}</span>
      </div>

      {loading ? (
        <p className="muted">در حال بارگذاری چارت…</p>
      ) : (
        <>
          <MemberTable
            title="مدرسین"
            kind="instructor"
            rows={roster.instructors || []}
            track={track}
            courseOptions={courseOptions}
            onUpdated={loadRoster}
            onDeleted={loadRoster}
            showToast={showToast}
          />
          <MemberTable
            title="کمک‌مدرسین"
            kind="teaching_assistant"
            rows={roster.teaching_assistants || []}
            track={track}
            courseOptions={courseOptions}
            onUpdated={loadRoster}
            onDeleted={loadRoster}
            showToast={showToast}
          />
        </>
      )}

      <form
        onSubmit={submitAdd}
        style={{
          marginTop: '1rem',
          padding: '0.85rem',
          border: '1px solid #e2e8f0',
          borderRadius: 8,
          background: '#f8fafc',
        }}
      >
        <h4 style={{ margin: '0 0 0.65rem', fontSize: '0.92rem' }}>افزودن عضو</h4>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.65rem', marginBottom: '0.65rem' }}>
          <label style={{ fontSize: '0.85rem' }}>
            <input
              type="radio"
              name="addMode"
              checked={addMode === 'create'}
              onChange={() => setAddMode('create')}
            />{' '}
            ایجاد کاربر جدید
          </label>
          <label style={{ fontSize: '0.85rem' }}>
            <input
              type="radio"
              name="addMode"
              checked={addMode === 'link'}
              onChange={() => setAddMode('link')}
            />{' '}
            اتصال کاربر موجود
          </label>
          <label style={{ fontSize: '0.85rem' }}>
            نوع:{' '}
            <select value={addKind} onChange={(e) => setAddKind(e.target.value)}>
              <option value="teaching_assistant">{KIND_LABELS.teaching_assistant}</option>
              <option value="instructor">{KIND_LABELS.instructor}</option>
            </select>
          </label>
        </div>

        {addMode === 'create' ? (
          <label style={{ display: 'block', marginBottom: '0.55rem', fontSize: '0.85rem' }}>
            نام فارسی
            <input
              type="text"
              value={addName}
              onChange={(e) => setAddName(e.target.value)}
              style={{ display: 'block', width: '100%', maxWidth: 320, marginTop: '0.25rem' }}
              placeholder="مثلاً علی احمدی"
            />
          </label>
        ) : (
          <div style={{ marginBottom: '0.55rem' }}>
            <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.25rem' }}>
              جست‌وجوی کاربر (نام یا نام کاربری)
            </label>
            <input
              type="text"
              value={addUserQuery}
              onChange={(e) => {
                setAddUserQuery(e.target.value)
                setSelectedUserId('')
              }}
              style={{ width: '100%', maxWidth: 360 }}
            />
            {userHits.length > 0 && (
              <ul
                style={{
                  listStyle: 'none',
                  margin: '0.35rem 0 0',
                  padding: 0,
                  maxWidth: 360,
                  border: '1px solid #e2e8f0',
                  borderRadius: 6,
                  background: '#fff',
                }}
              >
                {userHits.map((u) => (
                  <li key={u.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedUserId(u.id)
                        setAddUserQuery(u.full_name_fa || u.username || u.id)
                        setUserHits([])
                      }}
                      style={{
                        width: '100%',
                        textAlign: 'right',
                        padding: '0.4rem 0.55rem',
                        border: 'none',
                        background: selectedUserId === u.id ? '#e0f2fe' : 'transparent',
                        cursor: 'pointer',
                        fontSize: '0.84rem',
                      }}
                    >
                      {u.full_name_fa || u.username}{' '}
                      <span className="muted">({u.role})</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', marginBottom: '0.45rem' }}>
          <input type="checkbox" checked={addLegacy} onChange={(e) => setAddLegacy(e.target.checked)} />
          پرسنل موجود — مجاز برای همه دروس (بدون محدودیت فرایند)
        </label>

        {!addLegacy && (
          <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.55rem' }}>
            دروس مجاز
            <select
              multiple
              value={addCourses}
              onChange={(e) => setAddCourses(Array.from(e.target.selectedOptions, (o) => o.value))}
              style={{ display: 'block', width: '100%', maxWidth: 420, minHeight: 88, marginTop: '0.25rem' }}
            >
              {courseOptions.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label_fa}
                </option>
              ))}
            </select>
          </label>
        )}

        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'در حال ثبت…' : 'ثبت در چارت'}
        </button>
      </form>
    </div>
  )
}
