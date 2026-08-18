import React, { useCallback, useEffect, useId, useMemo, useState } from 'react'
import { courseCommitteeRosterApi, userApi } from '../services/api'

const KIND_LABELS = {
  instructor: 'مدرس',
  teaching_assistant: 'کمک‌مدرس',
  educational_instructor: 'مدرس آموزشی',
}

function courseLabel(courseOptions, code) {
  const hit = (courseOptions || []).find((c) => String(c.value) === String(code))
  return hit?.label_fa || code
}

function memberEditKey(row) {
  return row.user_id || row.roster_key || row.label_fa || row.value
}

function memberCourseCount(row) {
  if (typeof row.course_count === 'number') return row.course_count
  return Array.isArray(row.authorized_courses) ? row.authorized_courses.length : 0
}

function courseOptionValue(opt) {
  return String(typeof opt === 'object' ? (opt?.value ?? '') : opt)
}

function courseOptionLabel(opt) {
  if (typeof opt === 'object') return opt.label_fa || opt.value || ''
  return String(opt || '')
}

/**
 * انتخاب چنددرس — نباید داخل <label> بیرونی قرار گیرد (باگ فقط‌گزینهٔ‌اول).
 */
function CourseCheckboxEditor({ courseOptions, selected, onChange }) {
  const uid = useId()
  const [filter, setFilter] = useState('')

  const selectedSet = useMemo(
    () => new Set((selected || []).map((v) => String(v))),
    [selected],
  )

  const uniqueOptions = useMemo(() => {
    const seen = new Set()
    const out = []
    for (const opt of courseOptions || []) {
      const v = courseOptionValue(opt)
      if (!v || seen.has(v)) continue
      seen.add(v)
      out.push(opt)
    }
    return out
  }, [courseOptions])

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase()
    if (!q) return uniqueOptions
    return uniqueOptions.filter((opt) =>
      courseOptionLabel(opt).toLowerCase().includes(q),
    )
  }, [uniqueOptions, filter])

  const toggle = useCallback(
    (rawValue) => {
      const v = String(rawValue)
      if (!v) return
      if (selectedSet.has(v)) {
        onChange((selected || []).filter((x) => String(x) !== v))
      } else {
        onChange([...(selected || []), v])
      }
    },
    [onChange, selected, selectedSet],
  )

  const selectAllFiltered = () => {
    const next = new Set(selectedSet)
    for (const opt of filtered) next.add(courseOptionValue(opt))
    onChange([...next])
  }

  const clearFiltered = () => {
    const drop = new Set(filtered.map(courseOptionValue))
    onChange((selected || []).filter((x) => !drop.has(String(x))))
  }

  if (!uniqueOptions.length) {
    return (
      <p className="muted" style={{ margin: 0, fontSize: '0.8rem' }}>
        درسی برای این رسته در کاتالوگ نیست.
      </p>
    )
  }

  return (
    <div
      role="group"
      aria-label="انتخاب دروس مجاز"
      onMouseDown={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '0.35rem',
        minWidth: 220,
        maxWidth: 420,
      }}
      data-testid="roster-course-checkbox-editor"
    >
      <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <input
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="جست‌وجوی درس…"
          aria-label="جست‌وجوی درس"
          data-testid="roster-course-filter"
          style={{
            flex: '1 1 8rem',
            minWidth: 0,
            fontSize: '0.8rem',
            padding: '0.28rem 0.45rem',
            border: '1px solid #cbd5e1',
            borderRadius: 6,
          }}
        />
        <button type="button" className="btn btn-sm btn-outline" onClick={selectAllFiltered}>
          همه
        </button>
        <button type="button" className="btn btn-sm btn-outline" onClick={clearFiltered}>
          پاک کردن
        </button>
      </div>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '0.2rem',
          maxHeight: 220,
          overflowY: 'auto',
          overscrollBehavior: 'contain',
          padding: '0.35rem 0.45rem',
          border: '1px solid #e2e8f0',
          borderRadius: 6,
          background: '#fff',
          position: 'relative',
          zIndex: 2,
        }}
      >
        {filtered.map((c, idx) => {
          const v = courseOptionValue(c)
          const checked = selectedSet.has(v)
          const inputId = `${uid}-course-${idx}-${v}`
          return (
            <label
              key={v}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                fontSize: '0.8rem',
                padding: '0.12rem 0',
                cursor: 'pointer',
                userSelect: 'none',
                margin: 0,
                lineHeight: 1.4,
              }}
              onClick={(e) => e.stopPropagation()}
              onMouseDown={(e) => e.stopPropagation()}
            >
              <input
                id={inputId}
                type="checkbox"
                checked={checked}
                onChange={() => toggle(v)}
                onClick={(e) => e.stopPropagation()}
                style={{ flexShrink: 0, cursor: 'pointer' }}
              />
              <span>{courseOptionLabel(c)}</span>
            </label>
          )
        })}
        {!filtered.length && (
          <p className="muted" style={{ margin: 0, fontSize: '0.78rem' }}>
            درسی با این جست‌وجو نیست.
          </p>
        )}
      </div>
      <p className="muted" style={{ margin: 0, fontSize: '0.72rem' }}>
        {selectedSet.size.toLocaleString('fa-IR')} از {uniqueOptions.length.toLocaleString('fa-IR')} درس انتخاب شده
      </p>
    </div>
  )
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
  const [editingKey, setEditingKey] = useState(null)
  const [courses, setCourses] = useState([])
  const [saving, setSaving] = useState(false)
  const [kindSavingKey, setKindSavingKey] = useState(null)

  const trackCourses = useMemo(() => {
    const all = courseOptions || []
    const forTrack = all.filter((c) => !c.track || c.track === track)
    return forTrack.length ? forTrack : all
  }, [courseOptions, track])

  const memberName = (row) =>
    (row.name_fa || row.label_fa || '').trim()

  const currentRoleCode = (row) => {
    if (row.role_code && KIND_LABELS[row.role_code]) return row.role_code
    if (kind === 'teaching_assistant') return 'teaching_assistant'
    const key = String(row.roster_key || '')
    if (key === 'educational_instructor' || row.tier === 0) return 'educational_instructor'
    return 'instructor'
  }

  const startEdit = (row) => {
    const key = memberEditKey(row)
    setEditingKey(key)
    setCourses(Array.isArray(row.authorized_courses) ? [...row.authorized_courses] : [])
  }

  const saveEdit = async (row) => {
    const name = memberName(row)
    if (!name) {
      showToast?.('نام عضو نامعتبر است.', 'error')
      return
    }
    setSaving(true)
    try {
      await courseCommitteeRosterApi.updateMemberCourses({
        track,
        kind,
        name_fa: name,
        authorized_courses: courses,
        ...(row.user_id ? { user_id: row.user_id } : {}),
      })
      showToast?.('دروس مجاز به‌روز شد.')
      setEditingKey(null)
      onUpdated?.()
    } catch (e) {
      const d = e?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در به‌روزرسانی دروس', 'error')
    } finally {
      setSaving(false)
    }
  }

  const changeKind = async (row, newRole) => {
    const name = memberName(row)
    if (!name) {
      showToast?.('نام عضو نامعتبر است.', 'error')
      return
    }
    const prev = currentRoleCode(row)
    if (newRole === prev) return
    const key = memberEditKey(row)
    setKindSavingKey(key)
    try {
      await courseCommitteeRosterApi.updateMemberKind({
        track,
        kind,
        name_fa: name,
        new_role: newRole,
        ...(row.user_id ? { user_id: row.user_id } : {}),
        ...(Array.isArray(row.authorized_courses)
          ? { authorized_courses: row.authorized_courses }
          : {}),
      })
      showToast?.(`نوع به «${KIND_LABELS[newRole] || newRole}» تغییر کرد.`)
      onUpdated?.()
    } catch (e) {
      const d = e?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در تغییر نوع', 'error')
    } finally {
      setKindSavingKey(null)
    }
  }

  const remove = async (row) => {
    const name = memberName(row)
    if (!name && !row.user_id && !row.roster_key) return
    const label = name || row.label_fa || 'این عضو'
    if (!window.confirm(`«${label}» از چارت این رسته حذف شود؟`)) return
    try {
      await courseCommitteeRosterApi.deleteMember({
        track,
        kind,
        name_fa: name || '',
        ...(row.user_id ? { user_id: row.user_id } : {}),
        ...(row.roster_key ? { roster_key: row.roster_key } : {}),
      })
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
          <table className="data-table" style={{ fontSize: '0.85rem', width: '100%' }}>
            <thead>
              <tr>
                <th style={{ width: '22%' }}>نام</th>
                <th>دروس مجاز (قابل ویرایش)</th>
                <th style={{ width: '10%' }}>تعداد دروس</th>
                <th style={{ width: '16%' }}>نوع (قابل ویرایش)</th>
                <th style={{ width: 170 }}>عملیات</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const key = memberEditKey(row)
                const isEditing = editingKey === key
                const selectedLabels = (row.authorized_courses || []).map((c) =>
                  courseLabel(courseOptions, c),
                )
                const courseCount = memberCourseCount(row)
                const roleCode = currentRoleCode(row)
                const kindBusy = kindSavingKey === key
                return (
                  <tr key={`${kind}-${key}`}>
                    <td>{row.label_fa || row.name_fa}</td>
                    <td
                      style={{
                        minWidth: 280,
                        position: isEditing ? 'relative' : undefined,
                        zIndex: isEditing ? 5 : undefined,
                        background: isEditing ? '#fff' : undefined,
                      }}
                    >
                      {isEditing ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
                          <CourseCheckboxEditor
                            courseOptions={trackCourses}
                            selected={courses}
                            onChange={setCourses}
                          />
                          <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                            <button
                              type="button"
                              className="btn btn-primary btn-sm"
                              disabled={saving}
                              onClick={() => saveEdit(row)}
                              data-testid={`roster-save-courses-${key}`}
                            >
                              {saving ? '…' : 'ذخیره دروس'}
                            </button>
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              disabled={saving}
                              onClick={() => setEditingKey(null)}
                            >
                              انصراف
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => startEdit(row)}
                          title="برای ویرایش دروس کلیک کنید"
                          data-testid={`roster-edit-courses-cell-${key}`}
                          style={{
                            display: 'block',
                            width: '100%',
                            textAlign: 'right',
                            padding: '0.45rem 0.55rem',
                            border: '1px dashed #94a3b8',
                            borderRadius: 6,
                            background: '#f8fafc',
                            cursor: 'pointer',
                            fontSize: '0.82rem',
                            lineHeight: 1.55,
                            color: 'inherit',
                          }}
                        >
                          {selectedLabels.length ? (
                            <span>{selectedLabels.join('، ')}</span>
                          ) : (
                            <span className="muted">هنوز درسی انتخاب نشده — کلیک برای انتخاب</span>
                          )}
                          <span
                            className="muted"
                            style={{ display: 'block', marginTop: 4, fontSize: '0.75rem' }}
                          >
                            ویرایش دروس ✏️
                          </span>
                        </button>
                      )}
                    </td>
                    <td style={{ textAlign: 'center', fontWeight: 600 }}>
                      {courseCount.toLocaleString('fa-IR')}
                    </td>
                    <td>
                      <select
                        value={roleCode}
                        disabled={kindBusy}
                        onChange={(e) => changeKind(row, e.target.value)}
                        title="تغییر نوع مدرس / کمک‌مدرس / مدرس آموزشی"
                        data-testid={`roster-kind-select-${key}`}
                        style={{
                          width: '100%',
                          minWidth: 130,
                          fontSize: '0.82rem',
                          padding: '0.3rem 0.4rem',
                        }}
                      >
                        <option value="instructor">{KIND_LABELS.instructor}</option>
                        <option value="teaching_assistant">{KIND_LABELS.teaching_assistant}</option>
                        <option value="educational_instructor">
                          {KIND_LABELS.educational_instructor}
                        </option>
                      </select>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                        {!isEditing && (
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => startEdit(row)}
                            data-testid={`roster-edit-courses-${key}`}
                          >
                            ویرایش دروس
                          </button>
                        )}
                        <button type="button" className="btn btn-danger btn-sm" onClick={() => remove(row)}>
                          حذف
                        </button>
                      </div>
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
 * پنل مدیریت چارت مدرسین و کمک‌مدرسین.
 */
export default function CourseCommitteeRosterPanel({ showToast, embedded = true, onUpdated }) {
  const [tracks, setTracks] = useState([])
  const [track, setTrack] = useState('')
  const [roster, setRoster] = useState({ instructors: [], teaching_assistants: [] })
  const [courseOptions, setCourseOptions] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const [addMode, setAddMode] = useState('link')
  const [addKind, setAddKind] = useState('teaching_assistant')
  const [addName, setAddName] = useState('')
  const [userFilter, setUserFilter] = useState('')
  const [siteUsers, setSiteUsers] = useState([])
  const [usersLoading, setUsersLoading] = useState(false)
  const [selectedUserId, setSelectedUserId] = useState('')
  const [addCourses, setAddCourses] = useState([])

  const notifyParent = useCallback(() => {
    onUpdated?.()
  }, [onUpdated])

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

  const loadSiteUsers = useCallback(async () => {
    setUsersLoading(true)
    try {
      const res = await userApi.list({ is_active: true, limit: 2000 })
      const rows = Array.isArray(res.data) ? res.data : res.data?.users || []
      rows.sort((a, b) =>
        String(a.full_name_fa || a.username || '').localeCompare(
          String(b.full_name_fa || b.username || ''),
          'fa',
        ),
      )
      setSiteUsers(rows)
    } catch {
      setSiteUsers([])
      showToast?.('خطا در بارگذاری فهرست کاربران', 'error')
    } finally {
      setUsersLoading(false)
    }
  }, [showToast])

  useEffect(() => {
    loadMeta()
  }, [loadMeta])

  useEffect(() => {
    loadRoster()
  }, [loadRoster])

  useEffect(() => {
    if (addMode === 'link') {
      loadSiteUsers()
    }
  }, [addMode, loadSiteUsers])

  const trackLabel = useMemo(() => {
    const hit = tracks.find((t) => t.value === track)
    return hit?.label_fa || track
  }, [tracks, track])

  const addTrackCourses = useMemo(() => {
    const all = courseOptions || []
    const forTrack = all.filter((c) => !c.track || c.track === track)
    return forTrack.length ? forTrack : all
  }, [courseOptions, track])

  const rosterUserIds = useMemo(() => {
    const ids = new Set()
    for (const row of [...(roster.instructors || []), ...(roster.teaching_assistants || [])]) {
      if (row.user_id) ids.add(String(row.user_id))
    }
    return ids
  }, [roster])

  const selectableUsers = useMemo(() => {
    const q = userFilter.trim().toLowerCase()
    return siteUsers.filter((u) => {
      if (rosterUserIds.has(String(u.id))) return false
      if (!q) return true
      const hay = `${u.full_name_fa || ''} ${u.username || ''} ${u.role || ''}`.toLowerCase()
      return hay.includes(q)
    })
  }, [siteUsers, rosterUserIds, userFilter])

  const resetAddForm = () => {
    setAddName('')
    setUserFilter('')
    setSelectedUserId('')
    setAddCourses([])
  }

  const afterMutation = async () => {
    await loadRoster()
    await loadMeta()
    notifyParent()
  }

  const submitAdd = async (e) => {
    e.preventDefault()
    if (!track) {
      showToast?.('رسته را انتخاب کنید.', 'error')
      return
    }
    if (addCourses.length === 0) {
      showToast?.('حداقل یک درس مجاز انتخاب کنید.', 'error')
      return
    }
    if (addMode === 'link' && !selectedUserId) {
      showToast?.('کاربر را انتخاب کنید.', 'error')
      return
    }
    const name = addName.trim()
    if (addMode === 'create' && !name) {
      showToast?.('نام فارسی را وارد کنید.', 'error')
      return
    }
    const payload = {
      track,
      kind: addKind,
      roster_legacy: false,
      authorized_courses: addCourses,
    }
    setBusy(true)
    try {
      if (addMode === 'link') {
        await courseCommitteeRosterApi.linkMember({ ...payload, user_id: selectedUserId })
        showToast?.('کاربر به چارت متصل شد.')
      } else {
        await courseCommitteeRosterApi.createMember({ ...payload, name_fa: name })
        showToast?.('عضو جدید ثبت شد.')
      }
      resetAddForm()
      await afterMutation()
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

  const handleMemberUpdated = async () => {
    await afterMutation()
  }

  return (
    <div className="card" style={wrapStyle} data-testid="course-committee-roster-panel">
      <div style={{ marginBottom: '0.85rem' }}>
        <h3 style={{ margin: '0 0 0.35rem', fontSize: '1.05rem' }}>چارت مدرسین و کمک‌مدرسین</h3>
        <p className="muted" style={{ margin: 0, fontSize: '0.88rem', lineHeight: 1.55 }}>
          در جدول، روی ستون «دروس مجاز» کلیک کنید تا درس‌ها را ویرایش کنید. ستون «نوع» هم با
          فهرست کشویی قابل تغییر است (مدرس / کمک‌مدرس / مدرس آموزشی).
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
            onUpdated={handleMemberUpdated}
            onDeleted={handleMemberUpdated}
            showToast={showToast}
          />
          <MemberTable
            title="کمک‌مدرسین"
            kind="teaching_assistant"
            rows={roster.teaching_assistants || []}
            track={track}
            courseOptions={courseOptions}
            onUpdated={handleMemberUpdated}
            onDeleted={handleMemberUpdated}
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
              checked={addMode === 'link'}
              onChange={() => setAddMode('link')}
            />{' '}
            انتخاب از کاربران سایت
          </label>
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
            نوع:{' '}
            <select value={addKind} onChange={(e) => setAddKind(e.target.value)}>
              <option value="teaching_assistant">{KIND_LABELS.teaching_assistant}</option>
              <option value="instructor">{KIND_LABELS.instructor}</option>
              <option value="educational_instructor">{KIND_LABELS.educational_instructor}</option>
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
              انتخاب کاربر موجود سایت
            </label>
            <input
              type="search"
              value={userFilter}
              onChange={(e) => setUserFilter(e.target.value)}
              placeholder="فیلتر نام / نام کاربری / نقش…"
              style={{ width: '100%', maxWidth: 420, marginBottom: '0.35rem' }}
              data-testid="roster-user-filter"
            />
            <select
              value={selectedUserId}
              onChange={(e) => setSelectedUserId(e.target.value)}
              disabled={usersLoading}
              style={{ width: '100%', maxWidth: 420 }}
              data-testid="roster-user-select"
              aria-label="کاربر موجود سایت"
            >
              <option value="">
                {usersLoading
                  ? 'در حال بارگذاری کاربران…'
                  : selectableUsers.length === 0
                    ? 'کاربری برای انتخاب نیست'
                    : `انتخاب کاربر (${selectableUsers.length.toLocaleString('fa-IR')} نفر)`}
              </option>
              {selectableUsers.map((u) => (
                <option key={u.id} value={u.id}>
                  {(u.full_name_fa || u.username || u.id)}
                  {u.username ? ` — ${u.username}` : ''}
                  {u.role ? ` (${u.role})` : ''}
                </option>
              ))}
            </select>
            <p className="muted" style={{ margin: '0.3rem 0 0', fontSize: '0.75rem' }}>
              کاربران فعال سایت در این لیست هستند؛ اعضای فعلی همین رسته نمایش داده نمی‌شوند.
            </p>
          </div>
        )}

        <div style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.55rem' }}>
          <div style={{ fontWeight: 600, marginBottom: '0.35rem' }}>دروس مجاز</div>
          <div style={{ maxWidth: 420 }}>
            <CourseCheckboxEditor
              courseOptions={addTrackCourses}
              selected={addCourses}
              onChange={setAddCourses}
            />
          </div>
        </div>

        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'در حال ثبت…' : 'ثبت در چارت'}
        </button>
      </form>
    </div>
  )
}
