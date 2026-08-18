import React, { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useToast } from '../contexts/ToastContext'
import SemesterPrepReadinessPanel from '../components/SemesterPrepReadinessPanel'
import SemesterPrepCatalogPanel from '../components/SemesterPrepCatalogPanel'
import CourseCommitteeRosterPanel from '../components/CourseCommitteeRosterPanel'
import InterviewerPoolPanel from '../components/InterviewerPoolPanel'
import InstituteActivityLicensePanel from '../components/InstituteActivityLicensePanel'
import { semesterPrepApi } from '../services/api'

function scrollToHash() {
  const hash = window.location.hash?.replace('#', '')
  if (!hash) return
  const el = document.getElementById(hash)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

export default function SemesterPrepReadinessPage() {
  const { showToast } = useToast()
  const [readiness, setReadiness] = useState(null)

  const reloadReadiness = useCallback(async () => {
    try {
      const res = await semesterPrepApi.getReadiness()
      setReadiness(res.data)
    } catch {
      setReadiness(null)
    }
  }, [])

  useEffect(() => {
    reloadReadiness()
  }, [reloadReadiness])

  useEffect(() => {
    const t = setTimeout(scrollToHash, 150)
    return () => clearTimeout(t)
  }, [readiness])

  const handleDataUpdated = () => {
    reloadReadiness()
  }

  return (
    <div
      className="page-container"
      style={{ maxWidth: 960, margin: '0 auto', padding: '1.25rem' }}
      data-testid="semester-prep-readiness-page"
    >
      <div style={{ marginBottom: '1rem' }}>
        <Link to="/panel/semester-prep" className="muted" style={{ fontSize: '0.82rem' }}>
          ← بازگشت به آماده‌سازی ترم
        </Link>
      </div>

      <h1 style={{ fontSize: '1.35rem', marginBottom: '0.35rem' }}>آمادگی پیش‌نیازهای آماده‌سازی ترم</h1>
      <p className="muted" style={{ marginBottom: '1.25rem', lineHeight: 1.7 }}>
        داده‌های زیر منبع پیش‌فرض فرم‌های فرایند آماده‌سازی پاییز و زمستان هستند.
        درس، رسته، مدرس و کمک‌مدرس را می‌توانید اینجا یا در مرحلهٔ «لیست دروس، مدرسین، کمک‌مدرسین»
        اضافه و حذف کنید. مصاحبه‌گر از استخر همین صفحه انتخاب می‌شود.
      </p>

      <SemesterPrepReadinessPanel readiness={readiness} onReload={setReadiness} showTitle={false} />

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', marginTop: '1.5rem' }}>
        <div className="card" style={{ padding: '1rem 1.15rem' }}>
          <SemesterPrepCatalogPanel showToast={showToast} onUpdated={handleDataUpdated} />
        </div>

        <div id="roster" className="card" style={{ padding: '1rem 1.15rem' }}>
          <CourseCommitteeRosterPanel showToast={showToast} embedded onUpdated={handleDataUpdated} />
        </div>

        <div className="card" style={{ padding: '1rem 1.15rem' }}>
          <InstituteActivityLicensePanel showToast={showToast} onUpdated={handleDataUpdated} />
        </div>

        <div className="card" style={{ padding: '1rem 1.15rem' }}>
          <InterviewerPoolPanel showToast={showToast} onUpdated={handleDataUpdated} />
        </div>
      </div>

      <div style={{ marginTop: '1.25rem' }}>
        <Link to="/panel/semester-prep/workbench?process_code=fall_semester_preparation" className="btn btn-primary">
          ادامه آماده‌سازی ترم پاییز
        </Link>
      </div>
    </div>
  )
}
