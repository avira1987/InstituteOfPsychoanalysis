import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { courseCommitteeRosterApi } from '../services/api'

const PROGRAM_OPTIONS = [
  { value: 'introductory', label: 'آشنایی' },
  { value: 'comprehensive', label: 'جامع' },
]

const TERM_OPTIONS = [1, 2, 3, 4, 5, 6, 7, 8]

function programLabel(kind) {
  if (kind === 'introductory') return 'آشنایی'
  if (kind === 'comprehensive') return 'جامع'
  return '—'
}

function emptyCurriculum() {
  return {
    units: '2',
    curriculum_term: '',
    program_kind: 'introductory',
    class_hours: '',
    retake_exam: false,
    prerequisite_notes: '',
    subtitle_fa: '',
  }
}

function SopCurriculumPreview({ courses }) {
  const [open, setOpen] = useState(false)
  const term1 = useMemo(
    () => (Array.isArray(courses) ? courses : []).filter((c) => Number(c.curriculum_term) === 1),
    [courses],
  )
  const term2 = useMemo(
    () => (Array.isArray(courses) ? courses : []).filter((c) => Number(c.curriculum_term) === 2),
    [courses],
  )
  return (
    <div
      style={{
        marginBottom: '1rem',
        padding: '0.75rem 0.9rem',
        borderRadius: 8,
        border: '1px solid #bfdbfe',
        background: '#eff6ff',
      }}
      data-testid="sop-curriculum-load-panel"
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          data-testid="load-sop-curriculum-preview"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? 'بستن پیش‌نمایش SOP' : 'بارگذاری برنامه SOP در جدول دروس'}
        </button>
        <span className="muted" style={{ fontSize: '0.8rem' }}>
          ترم ۱: {term1.length.toLocaleString('fa-IR')} درس — ترم ۲: {term2.length.toLocaleString('fa-IR')} درس
        </span>
      </div>
      {open && (
        <div style={{ marginTop: '0.75rem', fontSize: '0.82rem', lineHeight: 1.65, color: '#1e3a8a' }}>
          <p style={{ margin: '0 0 0.5rem' }}>
            اگر جدول لیست دروس آماده‌سازی خالی باشد، همین ردیف‌ها (با واحد) در فرم مرحله پر می‌شوند.
            اپراتور فقط مدرس / روز / ساعت را تکمیل می‌کند.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0.75rem' }}>
            <div>
              <strong>پاییز (ترم ۱)</strong>
              <ul style={{ margin: '0.35rem 0 0', paddingInlineStart: '1.1rem' }}>
                {term1.map((c) => (
                  <li key={c.value}>
                    {c.label_fa || c.value}
                    {c.units != null ? ` — ${Number(c.units).toLocaleString('fa-IR')} واحد` : ''}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <strong>زمستان (ترم ۲)</strong>
              <ul style={{ margin: '0.35rem 0 0', paddingInlineStart: '1.1rem' }}>
                {term2.map((c) => (
                  <li key={c.value}>
                    {c.label_fa || c.value}
                    {c.units != null ? ` — ${Number(c.units).toLocaleString('fa-IR')} واحد` : ''}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function curriculumFromCourse(course) {
  return {
    units: course?.units != null ? String(course.units) : '',
    curriculum_term: course?.curriculum_term != null ? String(course.curriculum_term) : '',
    program_kind: course?.program_kind || '',
    class_hours: course?.class_hours || '',
    retake_exam: Boolean(course?.retake_exam),
    prerequisite_notes: course?.prerequisite_notes || '',
    subtitle_fa: course?.subtitle_fa || '',
  }
}

function curriculumPayload(fields) {
  const body = {}
  const units = Number(fields.units)
  if (Number.isFinite(units) && units >= 1) body.units = units
  const term = Number(fields.curriculum_term)
  if (Number.isFinite(term) && term >= 1) body.curriculum_term = term
  if (fields.program_kind) body.program_kind = fields.program_kind
  if (fields.class_hours.trim()) body.class_hours = fields.class_hours.trim()
  body.retake_exam = Boolean(fields.retake_exam)
  if (fields.prerequisite_notes.trim()) body.prerequisite_notes = fields.prerequisite_notes.trim()
  if (fields.subtitle_fa.trim()) body.subtitle_fa = fields.subtitle_fa.trim()
  return body
}

const catalogFieldLabelStyle = {
  display: 'block',
  fontSize: '0.75rem',
  fontWeight: 600,
  color: '#475569',
  marginBottom: '0.2rem',
}

function CatalogFieldLabel({ htmlFor, children }) {
  return (
    <span className="form-label" id={htmlFor ? `${htmlFor}-label` : undefined} style={catalogFieldLabelStyle}>
      {children}
    </span>
  )
}

function CurriculumFields({ value, onChange, idPrefix }) {
  const set = (key, next) => onChange({ ...value, [key]: next })
  const unitsId = `${idPrefix}-units`
  const termId = `${idPrefix}-term`
  const programId = `${idPrefix}-program`
  const hoursId = `${idPrefix}-hours`
  const subtitleId = `${idPrefix}-subtitle`
  const prereqId = `${idPrefix}-prereq`
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
        gap: '0.55rem 0.45rem',
        marginBottom: '0.5rem',
      }}
    >
      <label htmlFor={unitsId} style={{ display: 'block', margin: 0 }}>
        <CatalogFieldLabel htmlFor={unitsId}>تعداد واحد</CatalogFieldLabel>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <input
            id={unitsId}
            type="number"
            min={1}
            max={20}
            value={value.units}
            onChange={(e) => set('units', e.target.value)}
            placeholder="مثلاً ۲"
            aria-label="تعداد واحد"
            style={{ width: '100%' }}
            data-testid={unitsId}
          />
          <span className="muted" style={{ fontSize: '0.78rem', whiteSpace: 'nowrap' }}>
            واحد
          </span>
        </div>
      </label>
      <label htmlFor={termId} style={{ display: 'block', margin: 0 }}>
        <CatalogFieldLabel htmlFor={termId}>ترم برنامه</CatalogFieldLabel>
        <select
          id={termId}
          value={value.curriculum_term}
          onChange={(e) => set('curriculum_term', e.target.value)}
          aria-label="ترم برنامه"
          style={{ width: '100%' }}
          data-testid={termId}
        >
          <option value="">انتخاب ترم</option>
          {TERM_OPTIONS.map((n) => (
            <option key={n} value={n}>
              ترم {n}
            </option>
          ))}
        </select>
      </label>
      <label htmlFor={programId} style={{ display: 'block', margin: 0 }}>
        <CatalogFieldLabel htmlFor={programId}>نوع دوره</CatalogFieldLabel>
        <select
          id={programId}
          value={value.program_kind}
          onChange={(e) => set('program_kind', e.target.value)}
          aria-label="نوع دوره"
          style={{ width: '100%' }}
          data-testid={programId}
        >
          <option value="">انتخاب دوره</option>
          {PROGRAM_OPTIONS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
      </label>
      <label htmlFor={hoursId} style={{ display: 'block', margin: 0 }}>
        <CatalogFieldLabel htmlFor={hoursId}>مدت کلاس</CatalogFieldLabel>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <input
            id={hoursId}
            type="text"
            value={value.class_hours}
            onChange={(e) => set('class_hours', e.target.value)}
            placeholder="مثلاً 1:30"
            aria-label="مدت کلاس"
            style={{ width: '100%' }}
            data-testid={hoursId}
          />
          <span className="muted" style={{ fontSize: '0.78rem', whiteSpace: 'nowrap' }}>
            ساعت
          </span>
        </div>
      </label>
      <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.82rem', margin: 0 }}>
        <input
          type="checkbox"
          checked={value.retake_exam}
          onChange={(e) => set('retake_exam', e.target.checked)}
          data-testid={`${idPrefix}-retake`}
        />
        امتحان مجدد دارد
      </label>
      <label htmlFor={subtitleId} style={{ display: 'block', margin: 0, gridColumn: '1 / -1' }}>
        <CatalogFieldLabel htmlFor={subtitleId}>زیرعنوان درس</CatalogFieldLabel>
        <input
          id={subtitleId}
          type="text"
          value={value.subtitle_fa}
          onChange={(e) => set('subtitle_fa', e.target.value)}
          placeholder="در صورت نیاز"
          style={{ width: '100%' }}
          data-testid={subtitleId}
        />
      </label>
      <label htmlFor={prereqId} style={{ display: 'block', margin: 0, gridColumn: '1 / -1' }}>
        <CatalogFieldLabel htmlFor={prereqId}>پیش‌نیاز</CatalogFieldLabel>
        <input
          id={prereqId}
          type="text"
          value={value.prerequisite_notes}
          onChange={(e) => set('prerequisite_notes', e.target.value)}
          placeholder="توضیح پیش‌نیاز"
          style={{ width: '100%' }}
          data-testid={prereqId}
        />
      </label>
    </div>
  )
}

export default function SemesterPrepCatalogPanel({ showToast, onUpdated }) {
  const [courses, setCourses] = useState([])
  const [tracks, setTracks] = useState([])
  const [loading, setLoading] = useState(true)
  const [courseName, setCourseName] = useState('')
  const [courseTrack, setCourseTrack] = useState('')
  const [addCurriculum, setAddCurriculum] = useState(emptyCurriculum)
  const [trackName, setTrackName] = useState('')
  const [busy, setBusy] = useState(null)
  const [editingCourse, setEditingCourse] = useState(null)
  const [editName, setEditName] = useState('')
  const [editTrack, setEditTrack] = useState('')
  const [editCurriculum, setEditCurriculum] = useState(emptyCurriculum)
  const [termFilter, setTermFilter] = useState('')

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

  const filteredCourses = useMemo(() => {
    if (!termFilter) return courses
    return courses.filter((c) => String(c.curriculum_term || '') === termFilter)
  }, [courses, termFilter])

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
      await courseCommitteeRosterApi.createCourse({
        name_fa: name,
        track,
        ...curriculumPayload(addCurriculum),
      })
      showToast?.('درس به کاتالوگ اضافه شد.')
      setCourseName('')
      setCourseTrack('')
      setAddCurriculum(emptyCurriculum())
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
    setEditCurriculum(curriculumFromCourse(course))
  }

  const cancelEditCourse = () => {
    setEditingCourse(null)
    setEditName('')
    setEditTrack('')
    setEditCurriculum(emptyCurriculum())
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
        ...curriculumPayload(editCurriculum),
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
        منبع واحد و ترم درس‌ها جداول SOP «درس‌های ترم‌ها» است. شهریه هر درس = تعداد واحد × هزینه هر واحد.
        از همین‌جا درس جدید وارد کنید یا واحد/ترم درس موجود را ویرایش کنید.
        در مرحلهٔ «لیست دروس» آماده‌سازی ترم، اگر جدول خالی باشد برنامهٔ ترم ۱ (پاییز) و ترم ۲ (زمستان)
        از همین کاتالوگ به‌صورت خودکار بارگذاری می‌شود.
      </p>

      <SopCurriculumPreview courses={courses} />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '1rem',
          marginBottom: '1.15rem',
        }}
      >
        <form
          onSubmit={addCourse}
          style={{ padding: '0.85rem', border: '1px solid #e2e8f0', borderRadius: 8, background: '#f8fafc' }}
        >
          <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.92rem' }}>افزودن درس</h4>
          <label htmlFor="catalog-course-name" style={{ display: 'block', marginBottom: '0.5rem' }}>
            <CatalogFieldLabel htmlFor="catalog-course-name">نام درس</CatalogFieldLabel>
            <input
              id="catalog-course-name"
              type="text"
              value={courseName}
              onChange={(e) => setCourseName(e.target.value)}
              placeholder="مثلاً آسیب‌شناسی"
              style={{ width: '100%' }}
              data-testid="catalog-course-name"
            />
          </label>
          <label htmlFor="catalog-course-track" style={{ display: 'block', marginBottom: '0.5rem' }}>
            <CatalogFieldLabel htmlFor="catalog-course-track">رسته</CatalogFieldLabel>
            <select
              id="catalog-course-track"
              value={courseTrack}
              onChange={(e) => setCourseTrack(e.target.value)}
              required
              disabled={tracks.length === 0}
              style={{ width: '100%' }}
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
          </label>
          <CurriculumFields
            value={addCurriculum}
            onChange={setAddCurriculum}
            idPrefix="catalog-course"
          />
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
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: '0.75rem',
                flexWrap: 'wrap',
                marginBottom: '0.45rem',
              }}
            >
              <strong style={{ fontSize: '0.9rem' }}>دروس ({filteredCourses.length})</strong>
              <select
                value={termFilter}
                onChange={(e) => setTermFilter(e.target.value)}
                aria-label="فیلتر ترم"
                data-testid="catalog-term-filter"
              >
                <option value="">همه ترم‌ها</option>
                {TERM_OPTIONS.map((n) => (
                  <option key={n} value={String(n)}>
                    ترم {n}
                  </option>
                ))}
              </select>
            </div>
            {filteredCourses.length === 0 ? (
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
                      <th>دوره</th>
                      <th>ترم</th>
                      <th>واحد</th>
                      <th>ساعت</th>
                      <th style={{ width: 160 }}>عملیات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCourses.map((c) => {
                      const isEditing = editingCourse === c.value
                      return (
                        <tr key={c.value} data-testid={`catalog-course-row-${c.value}`}>
                          <td>
                            {isEditing ? (
                              <>
                                <label htmlFor="catalog-course-edit-name" style={{ display: 'block', marginBottom: '0.35rem' }}>
                                  <CatalogFieldLabel htmlFor="catalog-course-edit-name">نام درس</CatalogFieldLabel>
                                  <input
                                    id="catalog-course-edit-name"
                                    type="text"
                                    value={editName}
                                    onChange={(e) => setEditName(e.target.value)}
                                    style={{ width: '100%', minWidth: 140 }}
                                    data-testid="catalog-course-edit-name"
                                  />
                                </label>
                                <CurriculumFields
                                  value={editCurriculum}
                                  onChange={setEditCurriculum}
                                  idPrefix="catalog-course-edit"
                                />
                              </>
                            ) : (
                              <>
                                {c.label_fa}
                                {c.subtitle_fa ? (
                                  <div className="muted" style={{ fontSize: '0.75rem' }}>
                                    {c.subtitle_fa}
                                  </div>
                                ) : null}
                              </>
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
                          <td>{programLabel(c.program_kind)}</td>
                          <td>{c.curriculum_term || '—'}</td>
                          <td>{c.units != null ? c.units : '—'}</td>
                          <td>{c.class_hours || '—'}</td>
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
