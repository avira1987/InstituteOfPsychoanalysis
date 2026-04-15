import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { publicApi } from '../../services/api'

export default function HomePage() {
  const [stats, setStats] = useState({ students: 0, processes: 0, staff: 0, processes_in_progress: 0 })

  useEffect(() => {
    publicApi.stats().then(r => setStats(r.data)).catch(() => {})
  }, [])

  return (
    <>
      {/* ─── Hero ─── */}
      <section className="pub-hero">
        <div className="pub-hero-inner">
          <div className="pub-hero-content">
            <div className="pub-hero-badge">
              سامانه اتوماسیون آموزشی
            </div>
            <h1>
              انستیتو <span>روانکاوی</span> تهران
            </h1>
            <p className="pub-hero-desc">
              سامانه جامع مدیریت آموزشی انستیتو روانکاوی تهران. ثبت‌نام، پیگیری فرآیندها،
              مدیریت جلسات درمانی و سوپرویژن به صورت آنلاین و یکپارچه. ورود با کد یکبار مصرف پیامکی
              و پنل نقش‌محور برای دانشجو، کادر و کمیته‌ها.
            </p>
            <div className="pub-hero-actions">
              <Link to="/register" className="pub-hero-btn primary">
                ثبت‌نام دانشجو
              </Link>
              <Link to="/guide" className="pub-hero-btn outline">
                راهنمای سامانه
              </Link>
              <Link to="/student-lifecycle" className="pub-hero-btn outline">
                مسیر تحصیلی و نقش‌ها
              </Link>
            </div>
          </div>

          <div className="pub-hero-visual">
            <div className="pub-hero-card">
              <div className="pub-hero-stats">
                <div className="pub-hero-stat">
                  <span className="pub-hero-stat-value">{stats.students || '۰'}</span>
                  <span className="pub-hero-stat-label">دانشجو</span>
                </div>
                <div className="pub-hero-stat">
                  <span className="pub-hero-stat-value">{stats.processes || '۰'}</span>
                  <span className="pub-hero-stat-label">فرآیند فعال</span>
                </div>
                <div className="pub-hero-stat">
                  <span className="pub-hero-stat-value">{stats.staff || '۰'}</span>
                  <span className="pub-hero-stat-label">کارشناس</span>
                </div>
                <div className="pub-hero-stat">
                  <span className="pub-hero-stat-value">{stats.processes_in_progress ?? 0}</span>
                  <span className="pub-hero-stat-label">فرایند در جریان</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── Features ─── */}
      <section className="pub-section">
        <div className="pub-section-header">
          <div className="pub-section-badge">امکانات سامانه</div>
          <h2>مدیریت هوشمند فرآیندهای آموزشی</h2>
          <p>تمامی فرآیندهای آموزشی و اداری انستیتو در یک سامانه یکپارچه</p>
        </div>

        <div className="pub-features-grid">
          <div className="pub-feature-card">
            <div className="pub-feature-icon" style={{ background: 'var(--primary-light)', color: 'var(--primary)' }}>
              📋
            </div>
            <h3>مدیریت فرآیندها</h3>
            <p>تعریف و مدیریت فرآیندهای آموزشی با ماشین حالت هوشمند. پیگیری خودکار مراحل و اعلان وضعیت.</p>
          </div>

          <div className="pub-feature-card">
            <div className="pub-feature-icon" style={{ background: 'var(--success-light)', color: 'var(--success)' }}>
              🎓
            </div>
            <h3>پورتال دانشجو</h3>
            <p>پرونده آموزشی، مسیر تحصیلی، فرم‌های مرحله‌ای فرایندها، جلسات و تکالیف، و پیگیری درخواست‌ها در یک پنل.</p>
          </div>

          <div className="pub-feature-card">
            <div className="pub-feature-icon" style={{ background: 'var(--warning-light)', color: 'var(--warning)' }}>
              📊
            </div>
            <h3>گزارش‌گیری</h3>
            <p>داشبورد مدیریتی با آمار لحظه‌ای، گزارش‌های مالی، حضور و غیاب و عملکرد دانشجویان.</p>
          </div>

          <div className="pub-feature-card">
            <div className="pub-feature-icon" style={{ background: 'var(--info-light)', color: 'var(--info)' }}>
              🔔
            </div>
            <h3>اطلاع‌رسانی پیامکی</h3>
            <p>ارسال خودکار پیامک برای اعلان وضعیت فرآیندها، یادآوری جلسات و اطلاعیه‌های مهم.</p>
          </div>

          <div className="pub-feature-card">
            <div className="pub-feature-icon" style={{ background: 'var(--danger-light)', color: 'var(--danger)' }}>
              🏥
            </div>
            <h3>مدیریت جلسات درمانی</h3>
            <p>ثبت و مدیریت جلسات روان‌درمانی، پیگیری حضور و غیاب و مدیریت مالی جلسات.</p>
          </div>

          <div className="pub-feature-card">
            <div className="pub-feature-icon" style={{ background: '#faf5ff', color: '#9333ea' }}>
              👥
            </div>
            <h3>سوپرویژن و کمیته‌ها</h3>
            <p>مدیریت فرآیند سوپرویژن، برگزاری جلسات کمیته‌ها و ثبت تصمیمات به صورت سیستماتیک.</p>
          </div>
        </div>
      </section>

      {/* ─── Steps ─── */}
      <section className="pub-section" style={{ background: 'var(--bg)', paddingTop: '2rem' }}>
        <div className="pub-section-header">
          <div className="pub-section-badge">مراحل ثبت‌نام</div>
          <h2>چگونه شروع کنیم؟</h2>
          <p>فرآیند ساده ثبت‌نام و شروع دوره آموزشی</p>
        </div>

        <div className="pub-steps">
          <div className="pub-step">
            <div className="pub-step-num">۱</div>
            <div className="pub-step-content">
              <h3>ثبت‌نام اولیه</h3>
              <p>فرم ثبت‌نام آنلاین را تکمیل کنید. اطلاعات شخصی و تحصیلی خود را وارد نمایید.</p>
            </div>
          </div>

          <div className="pub-step">
            <div className="pub-step-num">۲</div>
            <div className="pub-step-content">
              <h3>بررسی مدارک</h3>
              <p>کارشناسان انستیتو مدارک و اطلاعات شما را بررسی و نتیجه را اطلاع‌رسانی می‌کنند.</p>
            </div>
          </div>

          <div className="pub-step">
            <div className="pub-step-num">۳</div>
            <div className="pub-step-content">
              <h3>مصاحبه و ارزیابی</h3>
              <p>در صورت تأیید اولیه، برای مصاحبه و ارزیابی حضوری دعوت خواهید شد.</p>
            </div>
          </div>

          <div className="pub-step">
            <div className="pub-step-num">۴</div>
            <div className="pub-step-content">
              <h3>شروع دوره</h3>
              <p>پس از پذیرش نهایی، دسترسی به پنل دانشجویی و شروع دوره آموزشی فراهم می‌شود.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ─── CTA ─── */}
      <section className="pub-section">
        <div className="pub-cta">
          <h2>آماده شروع هستید؟</h2>
          <p>همین حالا ثبت‌نام کنید و وارد دنیای روانکاوی شوید</p>
          <Link to="/register" className="pub-cta-btn">
            ثبت‌نام دانشجو
          </Link>
        </div>
      </section>
    </>
  )
}
