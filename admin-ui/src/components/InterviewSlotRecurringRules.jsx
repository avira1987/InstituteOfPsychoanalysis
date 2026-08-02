import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { canManageInterviewSlots } from '../utils/interviewSlotAccess'
import { interviewSlotsApi } from '../services/api'
import { labelRoleFa } from '../utils/roleLabels'

/** همان قرارداد بک‌اند: weekday پایتون تقویم میلادی در تهران، دوشنبه=0 … یکشنبه=6 — نمایش از شنبه. */
const WEEKDAY_OPTS = [
  { v: 5, label: 'شنبه' },
  { v: 6, label: 'یکشنبه' },
  { v: 0, label: 'دوشنبه' },
  { v: 1, label: 'سه‌شنبه' },
  { v: 2, label: 'چهارشنبه' },
  { v: 3, label: 'پنجشنبه' },
  { v: 4, label: 'جمعه' },
]

function roleFa(role) {
  return labelRoleFa(role)
}

function sortDays(arr) {
  return [...arr].sort((a, b) => a - b)
}

export default function InterviewSlotRecurringRules({ showToast, onCapacityChanged }) {
  const { user } = useAuth()
  const canPickRuleOwner = canManageInterviewSlots(user?.role)
  const [interviewers, setInterviewers] = useState([])
  const [targetIvId, setTargetIvId] = useState('')

  const interviewerLabelById = useMemo(() => {
    const m = new Map()
    interviewers.forEach((u) => {
      const name = u.full_name_fa || u.username || u.id
      m.set(u.id, u.role ? `${name} (${roleFa(u.role)})` : name)
    })
    return m
  }, [interviewers])

  const [rules, setRules] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [selectedDays, setSelectedDays] = useState(() => new Set([5, 2]))
  const [startT, setStartT] = useState('10:00')
  const [endT, setEndT] = useState('11:00')
  const [courseType, setCourseType] = useState('')
  const [mode, setMode] = useState('online')
  const [locationFa, setLocationFa] = useState('')
  const [labelFa, setLabelFa] = useState('مصاحبه تکراری')
  const [horizonDays, setHorizonDays] = useState(21)
  const [isActive, setIsActive] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    interviewSlotsApi
      .recurringRulesList()
      .then((r) => setRules(r.data?.rules || []))
      .catch((e) => {
        const st = e.response?.status
        if (st === 403) setError('دسترسی به این بخش برای نقش شما فعال نیست.')
        else setError('بارگذاری الگوها ناموفق بود.')
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!canPickRuleOwner) return
    interviewSlotsApi
      .recurringRuleCandidateOwners()
      .then((res) => {
        const arr = Array.isArray(res.data?.users) ? res.data.users : []
        setInterviewers(arr)
        setTargetIvId((prev) => {
          if (prev && arr.some((x) => x.id === prev)) return prev
          return arr[0]?.id || ''
        })
      })
      .catch(() => setInterviewers([]))
  }, [canPickRuleOwner])

  useEffect(() => {
    load()
  }, [load])

  const resetNew = useCallback(() => {
    setEditingId(null)
    setSelectedDays(new Set([5, 2]))
    setStartT('10:00')
    setEndT('11:00')
    setCourseType('')
    setMode('online')
    setLocationFa('')
    setLabelFa('مصاحبه تکراری')
    setHorizonDays(21)
    setIsActive(true)
    if (canPickRuleOwner) {
      setTargetIvId(interviewers[0]?.id || '')
    }
  }, [canPickRuleOwner, interviewers])

  const startEdit = (row) => {
    setEditingId(row.id)
    if (canPickRuleOwner && row.interviewer_user_id) setTargetIvId(row.interviewer_user_id)
    setSelectedDays(new Set(row.days_of_week || []))
    setStartT(row.start_local_time || '09:00')
    setEndT(row.end_local_time || '10:00')
    setCourseType(row.course_type || '')
    setMode(row.mode === 'in_person' ? 'in_person' : 'online')
    setLocationFa(row.location_fa || '')
    setLabelFa(row.label_fa || '')
    setHorizonDays(Number(row.horizon_days) || 21)
    setIsActive(row.is_active !== false)
  }

  const toggleDay = (v) => {
    setSelectedDays((prev) => {
      const n = new Set(prev)
      if (n.has(v)) n.delete(v)
      else n.add(v)
      return n
    })
  }

  const submit = async (e) => {
    e.preventDefault()
    const days = sortDays([...selectedDays])
    if (!days.length) {
      showToast?.('حداقل یک روز هفته را انتخاب کنید.', 'error')
      return
    }
    const body = {
      days_of_week: days,
      start_local_time: startT,
      end_local_time: endT,
      course_type: courseType || null,
      mode,
      location_fa: mode === 'in_person' ? (locationFa || null) : null,
      meeting_link: null,
      label_fa: labelFa || null,
      is_active: isActive,
      horizon_days: Number(horizonDays) || 21,
    }
    if (canPickRuleOwner && !editingId) {
      if (!targetIvId) {
        showToast?.('انتخاب مصاحبه‌گر برای الگو الزامی است.', 'error')
        return
      }
      body.interviewer_user_id = targetIvId
    }
    setSaving(true)
    try {
      if (editingId) {
        await interviewSlotsApi.recurringRuleUpdate(editingId, body)
        showToast?.('الگو به‌روز شد؛ وقت‌های آزاد آیندهٔ همین الگو بازسازی شد.')
      } else {
        await interviewSlotsApi.recurringRuleCreate(body)
        showToast?.('الگو ثبت شد؛ وقت‌ها در پس‌زمینه ساخته می‌شوند.')
      }
      resetNew()
      load()
      onCapacityChanged?.()
    } catch (err) {
      const d = err.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'ذخیره ناموفق بود.', 'error')
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id) => {
    if (!window.confirm('حذف این الگو؟ وقت‌های ساخته‌شده در تقویم دانشجو دست‌نخورده می‌مانند (فقط پیوند الگو قطع می‌شود).')) return
    try {
      await interviewSlotsApi.recurringRuleDelete(id)
      showToast?.('الگو حذف شد.')
      if (editingId === id) resetNew()
      load()
      onCapacityChanged?.()
    } catch (err) {
      const d = err.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'حذف ناموفق بود.', 'error')
    }
  }

  if (error) {
    return (
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem' }}>
        <p className="muted" style={{ margin: 0 }}>{error}</p>
      </div>
    )
  }

  return (
    <div className="card" style={{ marginBottom: '1.5rem' }}>
      <div className="card-header">
        <h3 className="card-title">الگوی زمانی تکراری مصاحبه</h3>
        <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.88rem', maxWidth: '48rem', lineHeight: 1.55 }}>
          روزهای هفته و بازهٔ ساعت را در <strong>زمان محلی ایران (تهران)</strong> مشخص کنید؛ سامانه به‌صورت دوره‌ای (چند دقیقه یک‌بار) برای چند روز آینده
          وقت آزاد ثبت می‌کند تا دانشجو انتخاب کند. اگر الگویی فعال نباشد، از این مسیر چیزی ساخته نمی‌شود.
          ثبت دستیٔ تک وقت در بخش پایین همچنان ممکن است؛ با هر ثبت دستیٔ مصاحبه‌گر، فقط زمان‌های آزاد <em>دستی</em> قبلیٔ همان مصاحبه‌گر پاک می‌شود، نه وقت‌های آمده از الگو.
          {canPickRuleOwner && (
            <>
              {' '}
              <strong>اختیاری:</strong> می‌توانید مالک الگو را روی یک مصاحبه‌گر بگذارید؛ در غیر این صورت الگو برای خودتان ثبت می‌شود.
            </>
          )}
        </p>
      </div>
      <div style={{ padding: '0 1.25rem 1rem' }}>
        <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem', maxWidth: '56rem' }}>
          {editingId && (
            <p className="muted" style={{ margin: 0, fontSize: '0.86rem', padding: '0.35rem 0.5rem', background: 'var(--bg-muted)', borderRadius: '8px' }}>
              ویرایش الگوی انتخاب‌شده —{' '}
              <button type="button" className="btn btn-link btn-sm" style={{ padding: 0 }} onClick={resetNew}>
                الگوی جدید
              </button>
            </p>
          )}
          {canPickRuleOwner && !editingId && (
            <label style={{ margin: 0, maxWidth: '28rem' }}>
              <span style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.82rem', fontWeight: 600 }}>
                مالک الگو (اختیاری — مصاحبه‌گر)
              </span>
              <select
                className="psf-input"
                style={{ width: '100%', minHeight: '2.35rem' }}
                value={targetIvId}
                onChange={(e) => setTargetIvId(e.target.value)}
              >
                <option value="">— انتخاب کنید —</option>
                {interviewers.map((iv) => (
                  <option key={iv.id} value={iv.id}>
                    {iv.full_name_fa || iv.username || iv.id}
                    {iv.role ? ` — ${roleFa(iv.role)}` : ''}
                  </option>
                ))}
              </select>
              {!interviewers.length && (
                <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.82rem', lineHeight: 1.65 }}>
                  مصاحبه‌گر فعالی برای انتخاب نیست؛ الگو بدون انتخاب مالک برای خودتان ثبت می‌شود.
                </p>
              )}
            </label>
          )}
          <div style={{ fontSize: '0.82rem', fontWeight: 600 }}>روزهای هفته</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem 0.6rem' }}>
            {WEEKDAY_OPTS.map(({ v, label }) => (
              <label key={v} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.88rem', cursor: 'pointer' }}>
                <input type="checkbox" checked={selectedDays.has(v)} onChange={() => toggleDay(v)} />
                {label}
              </label>
            ))}
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(10rem, 1fr))',
              gap: '0.5rem',
            }}
          >
            <label style={{ margin: 0 }}>
              <span style={{ display: 'block', marginBottom: '0.2rem', fontSize: '0.82rem' }}>شروع (تهران)</span>
              <input className="psf-input" type="time" value={startT} onChange={(e) => setStartT(e.target.value)} />
            </label>
            <label style={{ margin: 0 }}>
              <span style={{ display: 'block', marginBottom: '0.2rem', fontSize: '0.82rem' }}>پایان (تهران)</span>
              <input className="psf-input" type="time" value={endT} onChange={(e) => setEndT(e.target.value)} />
            </label>
            <label style={{ margin: 0 }}>
              <span style={{ display: 'block', marginBottom: '0.2rem', fontSize: '0.82rem' }}>چند روز آینده؟</span>
              <input
                className="psf-input"
                type="number"
                min={1}
                max={90}
                value={horizonDays}
                onChange={(e) => setHorizonDays(Number(e.target.value))}
              />
            </label>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.88rem' }}>
            <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
            الگو فعال باشد (غیرفعال = هیچ وقت جدیدی از این الگو ساخته نمی‌شود)
          </label>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(11rem, 1fr))',
              gap: '0.45rem',
            }}
          >
            <label style={{ margin: 0 }}>
              <span style={{ display: 'block', marginBottom: '0.2rem', fontSize: '0.82rem' }}>نوع دوره</span>
              <select className="psf-input" value={courseType} onChange={(e) => setCourseType(e.target.value)} style={{ width: '100%', minHeight: '2.35rem' }}>
                <option value="">هر دو / عمومی</option>
                <option value="introductory">آشنایی</option>
                <option value="comprehensive">جامع</option>
              </select>
            </label>
            <label style={{ margin: 0 }}>
              <span style={{ display: 'block', marginBottom: '0.2rem', fontSize: '0.82rem' }}>برگزاری</span>
              <select className="psf-input" value={mode} onChange={(e) => setMode(e.target.value)} style={{ width: '100%', minHeight: '2.35rem' }}>
                <option value="online">آنلاین</option>
                <option value="in_person">حضوری</option>
              </select>
            </label>
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(14rem, 1fr))',
              gap: '0.45rem',
            }}
          >
            {mode === 'in_person' && (
              <label style={{ margin: 0 }}>
                <span style={{ display: 'block', marginBottom: '0.2rem', fontSize: '0.82rem' }}>مکان (حضوری)</span>
                <input className="psf-input" value={locationFa} onChange={(e) => setLocationFa(e.target.value)} dir="rtl" />
              </label>
            )}
            {mode === 'online' && (
              <p className="muted" style={{ margin: 0, fontSize: '0.8rem', lineHeight: 1.6, alignSelf: 'end' }}>
                لینک جلسهٔ آنلاین پس از پرداخت دانشجو به‌صورت خودکار در الوکام ساخته می‌شود.
              </p>
            )}
          </div>
          <label style={{ margin: 0, maxWidth: '28rem' }}>
            <span style={{ display: 'block', marginBottom: '0.2rem', fontSize: '0.82rem' }}>برچسب روی وقت</span>
            <input className="psf-input" value={labelFa} onChange={(e) => setLabelFa(e.target.value)} dir="rtl" />
          </label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'در حال ذخیره…' : editingId ? 'ذخیرهٔ الگو' : 'ثبت الگو'}
            </button>
          </div>
        </form>
      </div>
      <div style={{ padding: '0 1.25rem 1.25rem' }}>
        <h4 style={{ margin: '0 0 0.6rem' }}>الگوهای ثبت‌شده</h4>
        {loading ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table" style={{ width: '100%', fontSize: '0.86rem' }}>
              <thead>
                <tr>
                  {canPickRuleOwner && <th>مالک الگو</th>}
                  <th>روزها</th>
                  <th>ساعت</th>
                  <th>افق (روز)</th>
                  <th>فعال</th>
                  <th>دوره</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rules.map((row) => {
                  const dayLabels = sortDays(row.days_of_week || [])
                    .map((d) => WEEKDAY_OPTS.find((o) => o.v === d)?.label || d)
                    .join('، ')
                  return (
                    <tr key={row.id}>
                      {canPickRuleOwner && (
                        <td style={{ fontSize: '0.82rem' }}>
                          {interviewerLabelById.get(row.interviewer_user_id) || row.interviewer_user_id?.slice(0, 8) || '—'}
                        </td>
                      )}
                      <td>{dayLabels || '—'}</td>
                      <td>
                        {row.start_local_time} – {row.end_local_time}
                      </td>
                      <td>{row.horizon_days}</td>
                      <td>{row.is_active ? 'بله' : 'خیر'}</td>
                      <td>{row.course_type || 'عمومی'}</td>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        <button type="button" className="btn btn-outline btn-sm" onClick={() => startEdit(row)}>
                          ویرایش
                        </button>{' '}
                        <button type="button" className="btn btn-outline btn-sm" onClick={() => remove(row.id)}>
                          حذف
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {!rules.length && <p className="muted" style={{ marginTop: '0.5rem' }}>الگویی ثبت نشده؛ وقت خودکار ساخته نمی‌شود.</p>}
          </div>
        )}
      </div>
    </div>
  )
}
