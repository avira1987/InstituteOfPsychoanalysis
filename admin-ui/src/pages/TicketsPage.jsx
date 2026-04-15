import React, { useState, useEffect, useCallback } from 'react'
import { ticketApi } from '../services/api'
import { useAuth } from '../contexts/AuthContext'
import PopupToast from '../components/PopupToast'

const CATEGORY_LABELS = {
  profile_edit_unlock: 'باز کردن پروفایل / ویرایش مرحلهٔ ثبت‌شده',
  process_general: 'فرایند و مراحل',
  data_correction: 'اصلاح داده',
  access_request: 'دسترسی یا مجوز',
  other: 'سایر',
}

const STATUS_LABELS = {
  open: 'باز',
  in_progress: 'در حال رسیدگی',
  resolved: 'رفع‌شده',
  closed: 'بسته',
}

const PRIORITY_LABELS = { low: 'کم', normal: 'عادی', high: 'بالا' }

const ROLE_LABELS = {
  admin: 'مدیر',
  staff: 'کارمند',
  finance: 'مالی',
  therapist: 'درمانگر',
  supervisor: 'سوپروایزر',
  site_manager: 'مسئول سایت',
  progress_committee: 'کمیته',
  education_committee: 'کمیته',
  supervision_committee: 'کمیته',
  specialized_commission: 'کمیسیون',
  therapy_committee_chair: 'کمیته درمان',
  therapy_committee_executor: 'مجری',
  deputy_education: 'معاون آموزش',
  monitoring_committee_officer: 'کمیته نظارت',
}

function formatUser(u) {
  if (!u) return '—'
  const name = u.full_name_fa || u.username
  const rl = ROLE_LABELS[u.role] || u.role
  return `${name} (${rl})`
}

function formatDateTime(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString('fa-IR', { dateStyle: 'medium', timeStyle: 'short' })
  } catch {
    return iso
  }
}

export default function TicketsPage() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const isStudent = user?.role === 'student'
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')
  const [mineFilter, setMineFilter] = useState('all')
  const [assignable, setAssignable] = useState([])
  const [triageInfo, setTriageInfo] = useState(null)
  const [directAssignAdmin, setDirectAssignAdmin] = useState(false)
  const [toast, setToast] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState({
    title: '',
    description: '',
    category: 'profile_edit_unlock',
    priority: 'normal',
    assignee_id: '',
    student_id: '',
    process_instance_id: '',
  })
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [commentText, setCommentText] = useState('')

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      const params = {}
      if (statusFilter) params.status = statusFilter
      if (!isAdmin && !isStudent) params.mine = mineFilter
      const res = await ticketApi.list(params)
      setList(res.data)
    } catch (e) {
      console.error(e)
      showToast(e.response?.data?.detail || 'خطا در بارگذاری تیکت‌ها', 'error')
    } finally {
      setLoading(false)
    }
  }, [statusFilter, mineFilter, isAdmin, isStudent])

  const loadAssignable = useCallback(async () => {
    try {
      const res = await ticketApi.assignableUsers()
      setAssignable(res.data || [])
    } catch (e) {
      console.error(e)
    }
  }, [])

  useEffect(() => {
    loadList()
  }, [loadList])

  useEffect(() => {
    loadAssignable()
  }, [loadAssignable])

  useEffect(() => {
    if (!showCreate) return
    setDirectAssignAdmin(false)
    ticketApi
      .triage()
      .then((r) => setTriageInfo(r.data))
      .catch(() => setTriageInfo(null))
  }, [showCreate])

  const openDetail = async (id) => {
    setDetailLoading(true)
    setDetail(null)
    try {
      const res = await ticketApi.get(id)
      setDetail(res.data)
    } catch (e) {
      showToast(e.response?.data?.detail || 'خطا', 'error')
    } finally {
      setDetailLoading(false)
    }
  }

  const closeDetail = () => {
    setDetail(null)
    setCommentText('')
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    if (isAdmin && directAssignAdmin && !createForm.assignee_id) {
      showToast('برای ارجاع مستقیم، مسئول را انتخاب کنید', 'error')
      return
    }
    try {
      const payload = {
        title: createForm.title,
        description: createForm.description || null,
        category: createForm.category,
        priority: createForm.priority,
      }
      if (isAdmin && directAssignAdmin && createForm.assignee_id) {
        payload.assignee_id = createForm.assignee_id
      }
      if (!isStudent) {
        payload.student_id = createForm.student_id.trim() || null
        payload.process_instance_id = createForm.process_instance_id.trim() || null
      } else if (createForm.process_instance_id.trim()) {
        payload.process_instance_id = createForm.process_instance_id.trim()
      }
      await ticketApi.create(payload)
      showToast('تیکت ثبت شد و به مسئول واحد رسید')
      setShowCreate(false)
      setCreateForm({
        title: '',
        description: '',
        category: 'profile_edit_unlock',
        priority: 'normal',
        assignee_id: '',
        student_id: '',
        process_instance_id: '',
      })
      loadList()
    } catch (err) {
      showToast(err.response?.data?.detail || 'خطا در ثبت', 'error')
    }
  }

  const patchTicket = async (id, data) => {
    try {
      await ticketApi.patch(id, data)
      showToast('ذخیره شد')
      loadList()
      if (detail?.id === id) {
        const res = await ticketApi.get(id)
        setDetail(res.data)
      }
    } catch (err) {
      showToast(err.response?.data?.detail || 'خطا', 'error')
    }
  }

  const sendComment = async () => {
    if (!detail || !commentText.trim()) return
    try {
      await ticketApi.addComment(detail.id, { body: commentText.trim() })
      setCommentText('')
      const res = await ticketApi.get(detail.id)
      setDetail(res.data)
      loadList()
    } catch (err) {
      showToast(err.response?.data?.detail || 'خطا', 'error')
    }
  }

  const canReassign =
    user &&
    detail &&
    (isAdmin ||
      user.id === detail.assignee?.id ||
      (user.id === detail.requester?.id && !isStudent))

  return (
    <div className="page tickets-page" dir="rtl">
      <PopupToast toast={toast} />
      <header className="page-header">
        <div>
          <h1 className="page-title">تیکت‌ها و درخواست‌های داخلی</h1>
          <p className="page-subtitle muted">
            {isStudent
              ? 'درخواست شما ابتدا به مسئول واحد می‌رسد؛ ایشان در صورت نیاز آن را به فرد دارای دسترسی ارجاع می‌دهد. پیگیری در همین صفحه و با پیام‌های سیستمی مشخص است.'
              : 'تیکت جدید به مسئول واحد (یک نفر) می‌رسد تا پس از بررسی به فرد مناسب ارجاع شود. ارجاع مستقیم فقط برای مدیر در صورت نیاز فعال است.'}
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
          تیکت جدید
        </button>
      </header>

      <div className="filters-row" style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
        <label>
          <span className="muted" style={{ marginLeft: '0.5rem' }}>وضعیت</span>
          <select
            className="input"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">همه</option>
            {Object.entries(STATUS_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </label>
        {!isAdmin && !isStudent && (
          <label>
            <span className="muted" style={{ marginLeft: '0.5rem' }}>نمایش</span>
            <select className="input" value={mineFilter} onChange={(e) => setMineFilter(e.target.value)}>
              <option value="all">همهٔ مرتبط با من</option>
              <option value="created">فقط ثبت‌شده توسط من</option>
              <option value="assigned">فقط ارجاع‌شده به من</option>
            </select>
          </label>
        )}
        {isStudent && (
          <span className="muted" style={{ alignSelf: 'center' }}>فقط تیکت‌های مربوط به خودتان</span>
        )}
        {isAdmin && (
          <span className="muted" style={{ alignSelf: 'center' }}>مدیر: همهٔ تیکت‌ها را می‌بینید</span>
        )}
      </div>

      {loading ? (
        <div className="loading-spinner-wrap"><div className="loading-spinner" /></div>
      ) : (
        <div className="card-list">
          {list.length === 0 ? (
            <p className="muted">تیکتی نیست.</p>
          ) : (
            list.map((t) => (
              <button
                key={t.id}
                type="button"
                className="card ticket-card"
                onClick={() => openDetail(t.id)}
                style={{
                  textAlign: 'right',
                  width: '100%',
                  cursor: 'pointer',
                  border: '1px solid var(--border, #e5e7eb)',
                  borderRadius: '12px',
                  padding: '1rem 1.25rem',
                  background: 'var(--card-bg, #fff)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap', alignItems: 'flex-start' }}>
                  <strong style={{ flex: '1 1 200px' }}>{t.title}</strong>
                  <span className={`ticket-badge status-${t.status}`}>
                    {STATUS_LABELS[t.status] || t.status}
                  </span>
                </div>
                <div style={{ marginTop: '0.5rem', fontSize: '0.88rem' }} className="muted">
                  {PRIORITY_LABELS[t.priority] || t.priority} · {CATEGORY_LABELS[t.category] || t.category}
                  {t.student_code && (
                    <span style={{ marginRight: '0.75rem' }}>دانشجو: {t.student_code}</span>
                  )}
                </div>
                <div style={{ marginTop: '0.35rem', fontSize: '0.85rem' }} className="muted">
                  از {formatUser(t.requester)} ← مسئول فعلی: {formatUser(t.assignee)}
                </div>
              </button>
            ))
          )}
        </div>
      )}

      {showCreate && (
        <div className="modal-overlay" role="presentation" onClick={() => setShowCreate(false)}>
          <div
            className="modal ticket-modal-shell"
            role="dialog"
            aria-labelledby="ticket-create-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="ticket-modal-head">
              <h2 id="ticket-create-title">ثبت تیکت جدید</h2>
              <p>
                همهٔ تیکت‌ها ابتدا به <strong>مسئول واحد</strong> می‌رسند؛ همان فرد می‌تواند در صورت نیاز تیک را به
                همکار دیگر ارجاع دهد.
              </p>
            </div>
            <div className="ticket-modal-body">
              {triageInfo?.primary_handler && (
                <div className="ticket-form-section">
                  <span className="ticket-form-section-label">مسئول اولیهٔ رسیدگی</span>
                  <div className="ticket-triage-card">
                    <span className="ticket-triage-icon" aria-hidden="true">📌</span>
                    <div>
                      <strong>
                        {triageInfo.primary_handler.full_name_fa || triageInfo.primary_handler.username}
                      </strong>
                      <span className="muted" style={{ display: 'block', marginTop: '0.2rem' }}>
                        {ROLE_LABELS[triageInfo.primary_handler.role] || triageInfo.primary_handler.role}
                      </span>
                      <p className="muted" style={{ margin: '0.5rem 0 0', fontSize: '0.82rem' }}>
                        {triageInfo.hint_fa}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              <form id="ticket-create-form" onSubmit={handleCreate}>
                <div className="ticket-form-section">
                  <span className="ticket-form-section-label">عنوان درخواست</span>
                  <input
                    className="ticket-input"
                    required
                    value={createForm.title}
                    onChange={(e) => setCreateForm((f) => ({ ...f, title: e.target.value }))}
                    placeholder={isStudent ? 'مثلاً باز کردن ویرایش فرم مرحلهٔ ثبت‌شده' : 'خلاصهٔ واضح درخواست'}
                  />
                </div>

                <div className="ticket-form-section">
                  <span className="ticket-form-section-label">نوع</span>
                  <select
                    className="ticket-input"
                    value={createForm.category}
                    onChange={(e) => setCreateForm((f) => ({ ...f, category: e.target.value }))}
                  >
                    {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
                      <option key={k} value={k}>{v}</option>
                    ))}
                  </select>
                </div>

                <div className="ticket-grid-2">
                  <div className="ticket-form-section">
                    <span className="ticket-form-section-label">اولویت</span>
                    <select
                      className="ticket-input"
                      value={createForm.priority}
                      onChange={(e) => setCreateForm((f) => ({ ...f, priority: e.target.value }))}
                    >
                      {Object.entries(PRIORITY_LABELS).map(([k, v]) => (
                        <option key={k} value={k}>{v}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="ticket-form-section">
                  <span className="ticket-form-section-label">توضیحات</span>
                  <textarea
                    className="ticket-input"
                    rows={4}
                    value={createForm.description}
                    onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
                    placeholder="شماره دانشجویی، نام فرایند، مرحله، یا هر جزئیات لازم برای پیگیری…"
                  />
                </div>

                {!isStudent && (
                  <>
                    <div className="ticket-grid-2">
                      <div className="ticket-form-section">
                        <span className="ticket-form-section-label">شناسهٔ دانشجو (اختیاری)</span>
                        <input
                          className="ticket-input"
                          dir="ltr"
                          value={createForm.student_id}
                          onChange={(e) => setCreateForm((f) => ({ ...f, student_id: e.target.value }))}
                          placeholder="UUID"
                        />
                      </div>
                      <div className="ticket-form-section">
                        <span className="ticket-form-section-label">شناسهٔ نمونهٔ فرایند (اختیاری)</span>
                        <input
                          className="ticket-input"
                          dir="ltr"
                          value={createForm.process_instance_id}
                          onChange={(e) => setCreateForm((f) => ({ ...f, process_instance_id: e.target.value }))}
                          placeholder="UUID"
                        />
                      </div>
                    </div>
                  </>
                )}
                {isStudent && (
                  <div className="ticket-form-section">
                    <span className="ticket-form-section-label">شناسهٔ نمونهٔ فرایند (اختیاری)</span>
                    <input
                      className="ticket-input"
                      dir="ltr"
                      placeholder="در صورت نیاز از بخش فرایندها کپی کنید"
                      value={createForm.process_instance_id}
                      onChange={(e) => setCreateForm((f) => ({ ...f, process_instance_id: e.target.value }))}
                    />
                  </div>
                )}

                {isAdmin && (
                  <div
                    className="ticket-form-section"
                    style={{
                      padding: '0.85rem 1rem',
                      background: '#fffbeb',
                      border: '1px solid #fcd34d',
                      borderRadius: '10px',
                    }}
                  >
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontWeight: 600 }}>
                      <input
                        type="checkbox"
                        checked={directAssignAdmin}
                        onChange={(e) => setDirectAssignAdmin(e.target.checked)}
                      />
                      ارجاع مستقیم (مدیر) — بدون صف واحد
                    </label>
                    {directAssignAdmin && (
                      <div style={{ marginTop: '0.75rem' }}>
                        <span className="ticket-form-section-label">مسئول مستقیم</span>
                        <select
                          className="ticket-input"
                          required={directAssignAdmin}
                          value={createForm.assignee_id}
                          onChange={(e) => setCreateForm((f) => ({ ...f, assignee_id: e.target.value }))}
                        >
                          <option value="">— انتخاب —</option>
                          {assignable.map((u) => (
                            <option key={u.id} value={u.id}>
                              {(u.full_name_fa || u.username) + ` (${ROLE_LABELS[u.role] || u.role})`}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>
                )}
              </form>
            </div>
            <div className="ticket-modal-footer">
              <button type="button" className="btn btn-ghost" onClick={() => setShowCreate(false)}>
                انصراف
              </button>
              <button type="submit" form="ticket-create-form" className="btn btn-primary">
                ثبت تیکت
              </button>
            </div>
          </div>
        </div>
      )}

      {(detail || detailLoading) && (
        <div className="modal-overlay" role="presentation" onClick={closeDetail}>
          <div
            className="modal ticket-detail-sheet"
            role="dialog"
            onClick={(e) => e.stopPropagation()}
            style={{ maxHeight: '92vh', overflow: 'auto' }}
          >
            {detailLoading ? (
              <div className="loading-spinner-wrap" style={{ padding: '3rem' }}><div className="loading-spinner" /></div>
            ) : detail ? (
              <>
                <div className="ticket-detail-head">
                  <h2>{detail.title}</h2>
                  <div className="ticket-badges">
                    <span className={`ticket-badge status-${detail.status}`}>
                      {STATUS_LABELS[detail.status] || detail.status}
                    </span>
                    <span className="ticket-badge">{PRIORITY_LABELS[detail.priority] || detail.priority}</span>
                    <span className="ticket-badge">{CATEGORY_LABELS[detail.category] || detail.category}</span>
                    {detail.student_code && (
                      <span className="ticket-badge">دانشجو: {detail.student_code}</span>
                    )}
                  </div>
                  <p style={{ margin: '0.75rem 0 0', fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
                    <span className="muted">ثبت‌کننده:</span> {formatUser(detail.requester)}
                    {' · '}
                    <span className="muted">مسئول فعلی:</span> {formatUser(detail.assignee)}
                  </p>
                </div>

                <div style={{ padding: '1.25rem 1.5rem' }}>
                  {detail.description && (
                    <div
                      style={{
                        whiteSpace: 'pre-wrap',
                        background: 'var(--bg)',
                        padding: '1rem',
                        borderRadius: '12px',
                        marginBottom: '1.25rem',
                        border: '1px solid var(--border)',
                        fontSize: '0.95rem',
                      }}
                    >
                      {detail.description}
                    </div>
                  )}

                  <h3 style={{ fontSize: '0.95rem', fontWeight: 800, marginBottom: '0.75rem' }}>پیگیری و سوابق</h3>
                  <p className="muted" style={{ fontSize: '0.82rem', marginBottom: '1rem' }}>
                    پیام‌های سیستمی وضعیت را نشان می‌دهند؛ با تغییر وضعیت به «در حال رسیدگی» یعنی تیکت در حال پیگیری است.
                  </p>

                  <ul className="ticket-timeline">
                    {(detail.comments || []).map((c) => {
                      const isSys = (c.kind || 'user') === 'system'
                      return (
                      <li
                        key={c.id}
                        className={`ticket-timeline-item ${isSys ? 'system' : ''}`}
                      >
                        <span className="ticket-timeline-dot" aria-hidden="true" />
                        <div className="ticket-timeline-meta">
                          {isSys ? (
                            <span>رخداد سیستمی — {formatDateTime(c.created_at)}</span>
                          ) : (
                            <span>
                              {formatUser(c.author)} — {formatDateTime(c.created_at)}
                            </span>
                          )}
                        </div>
                        <div className="ticket-timeline-body">{c.body}</div>
                      </li>
                      )
                    })}
                  </ul>

                  <div className="ticket-comment-box">
                    <span className="ticket-form-section-label">پیام شما</span>
                    <textarea
                      className="ticket-input"
                      rows={3}
                      placeholder="توضیح یا پرسش…"
                      value={commentText}
                      onChange={(e) => setCommentText(e.target.value)}
                    />
                    <button type="button" className="btn btn-secondary" style={{ marginTop: '0.5rem' }} onClick={sendComment}>
                      ارسال پیام
                    </button>
                  </div>

                  <div style={{ marginTop: '1.35rem' }}>
                    <span className="ticket-form-section-label">تغییر وضعیت</span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.35rem' }}>
                      {(isStudent && user?.id === detail.requester?.id
                        ? Object.entries(STATUS_LABELS).filter(([key]) => key === 'resolved' || key === 'closed')
                        : Object.entries(STATUS_LABELS)
                      ).map(([k, v]) => (
                        <button
                          key={k}
                          type="button"
                          className="btn btn-ghost btn-sm"
                          disabled={detail.status === k}
                          onClick={() => patchTicket(detail.id, { status: k })}
                        >
                          {v}
                        </button>
                      ))}
                    </div>
                  </div>

                  {canReassign && (
                    <div style={{ marginTop: '1rem' }}>
                      <span className="ticket-form-section-label">ارجاع به همکار دیگر</span>
                      <select
                        className="ticket-input"
                        style={{ marginTop: '0.35rem' }}
                        value={detail.assignee?.id || ''}
                        onChange={(e) => patchTicket(detail.id, { assignee_id: e.target.value })}
                      >
                        {assignable.map((u) => (
                          <option key={u.id} value={u.id}>
                            {(u.full_name_fa || u.username) + ` (${ROLE_LABELS[u.role] || u.role})`}
                          </option>
                        ))}
                      </select>
                      <p className="muted" style={{ fontSize: '0.8rem', marginTop: '0.35rem' }}>
                        مسئول فعلی یا مدیر می‌تواند تیک را به فرد دارای دسترسی بسپارد.
                      </p>
                    </div>
                  )}

                  <div style={{ marginTop: '1.25rem', textAlign: 'left' }}>
                    <button type="button" className="btn btn-ghost" onClick={closeDetail}>
                      بستن
                    </button>
                  </div>
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}
