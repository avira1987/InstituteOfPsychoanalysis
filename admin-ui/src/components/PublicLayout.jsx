import React, { useState, useEffect } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { getSiteLogoUrl } from '../utils/siteLogo'

const NAV_ITEMS = [
  { path: '/', label: 'خانه' },
  { path: '/blog', label: 'مقالات' },
  { path: '/guide', label: 'راهنما' },
  { path: '/student-lifecycle', label: 'مسیر تحصیلی' },
]

const roleLabels = {
  admin: 'مدیر سیستم',
  staff: 'کارمند دفتر',
  therapist: 'درمانگر',
  student: 'دانشجو',
  supervisor: 'سوپروایزر',
  site_manager: 'مسئول سایت',
  progress_committee: 'کمیته پیشرفت',
  education_committee: 'کمیته آموزش',
  supervision_committee: 'کمیته نظارت',
  specialized_commission: 'کمیسیون تخصصی',
  therapy_committee_chair: 'مسئول کمیته درمان',
  therapy_committee_executor: 'مجری کمیته درمان',
  deputy_education: 'معاون آموزش',
  monitoring_committee_officer: 'مسئول کمیته نظارت',
  finance: 'اپراتور مالی',
}

export default function PublicLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  return (
    <div className="pub-page">
      {/* ─── Navbar ─── */}
      <nav className={`pub-navbar ${scrolled ? 'scrolled' : ''}`}>
        <div className="pub-navbar-inner">
          <Link to="/" className="pub-navbar-brand">
            <div className="pub-navbar-logo">
              <img src={getSiteLogoUrl()} alt="" className="site-logo-img" width={42} height={48} />
            </div>
            <div>
              <div className="pub-navbar-title">انستیتو روانکاوی تهران</div>
              <div className="pub-navbar-subtitle">Tehran Institute of Psychoanalysis</div>
            </div>
          </Link>

          <div className={`pub-navbar-links ${menuOpen ? 'open' : ''}`}>
            {NAV_ITEMS.map(item => (
              <Link
                key={item.path}
                to={item.path}
                className={`pub-navbar-link ${location.pathname === item.path ? 'active' : ''}`}
              >
                {item.label}
              </Link>
            ))}
            {user ? (
              <button
                className="pub-navbar-cta"
                onClick={() => navigate('/panel')}
              >
                پنل {roleLabels[user.role] || user.role}
              </button>
            ) : (
              <Link to="/login" className="pub-navbar-cta">
                ورود و ثبت‌نام
              </Link>
            )}
          </div>

          <button
            className="pub-mobile-toggle"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            {menuOpen ? '✕' : '☰'}
          </button>
        </div>
      </nav>

      {/* ─── Main Content ─── */}
      <Outlet />

      {/* ─── Footer ─── */}
      <footer className="pub-footer">
        <div className="pub-footer-inner">
          <div className="pub-footer-grid">
            <div className="pub-footer-brand">
              <div className="pub-footer-logo-wrap">
                <img src={getSiteLogoUrl()} alt="" className="site-logo-img pub-footer-logo" width={48} height={56} loading="lazy" decoding="async" />
              </div>
              <h3>انستیتو روانکاوی تهران</h3>
              <p>
                انستیتو روانکاوی تهران (Tehran Institute of Psychoanalysis) با هدف آموزش و
                پژوهش در حوزه روانکاوی و روان‌درمانی تحلیلی فعالیت می‌کند.
              </p>
            </div>
            <div className="pub-footer-col">
              <h4>دسترسی سریع</h4>
              <Link to="/">صفحه اصلی</Link>
              <Link to="/blog">مقالات و اخبار</Link>
              <Link to="/guide">راهنمای سامانه</Link>
              <Link to="/student-lifecycle">مسیر تحصیلی و نقش‌ها</Link>
            </div>
            <div className="pub-footer-col">
              <h4>خدمات</h4>
              <Link to="/register">ثبت‌نام دانشجو</Link>
              <Link to="/login">ورود به سامانه</Link>
              <Link to="/register">شرایط پذیرش</Link>
            </div>
            <div className="pub-footer-col">
              <h4>تماس با ما</h4>
              <p>تهران، ایران</p>
              <p>تلفن: ۰۲۱-XXXXXXXX</p>
              <p>ایمیل: info@psychoanalysis.ir</p>
            </div>
          </div>
          <div className="pub-footer-bottom">
            تمامی حقوق محفوظ است &copy; {new Date().getFullYear()} انستیتو روانکاوی تهران
          </div>
        </div>
      </footer>
    </div>
  )
}
