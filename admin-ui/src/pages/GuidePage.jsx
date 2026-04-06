import React, { useState, useMemo, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'

const ALL_SECTIONS = [
  { id: 'intro', title: 'مقدمه و معرفی سامانه', roles: null },
  { id: 'concepts', title: 'مفاهیم کلیدی', roles: null },
  { id: 'step1', title: 'گام ۱: ورود به سیستم', roles: null },
  { id: 'role_student', title: 'راهنمای دانشجو', roles: ['student'] },
  { id: 'role_therapist', title: 'راهنمای درمانگر', roles: ['therapist'] },
  { id: 'role_supervisor', title: 'راهنمای سوپروایزر', roles: ['supervisor'] },
  { id: 'role_staff', title: 'راهنمای کارمند دفتر', roles: ['staff'] },
  { id: 'role_site_manager', title: 'راهنمای مسئول سایت', roles: ['site_manager'] },
  { id: 'role_finance', title: 'راهنمای اپراتور مالی', roles: ['finance'] },
  { id: 'role_committee', title: 'راهنمای کمیته‌ها', roles: ['progress_committee', 'education_committee', 'supervision_committee', 'specialized_commission', 'therapy_committee_chair', 'therapy_committee_executor', 'deputy_education', 'monitoring_committee_officer'] },
  { id: 'step2', title: 'گام ۲: ساخت فرایند جدید', roles: ['admin', 'staff'] },
  { id: 'step3', title: 'گام ۳: تعریف وضعیت‌ها (States)', roles: ['admin', 'staff'] },
  { id: 'step4', title: 'گام ۴: تعریف انتقال‌ها (Transitions)', roles: ['admin', 'staff'] },
  { id: 'step5', title: 'گام ۵: تعریف قوانین (Rules)', roles: ['admin'] },
  { id: 'step6', title: 'گام ۶: آزمایش و اجرای فرایند', roles: ['admin', 'staff'] },
  { id: 'step7', title: 'گام ۷: ردیابی و گزارش‌گیری', roles: ['admin', 'staff'] },
  { id: 'example', title: 'مثال کامل: ثبت یک فرایند واقعی', roles: ['admin', 'staff'] },
  { id: 'glossary', title: 'واژه‌نامه', roles: null },
  { id: 'faq', title: 'سوالات متداول', roles: null },
]

function getSectionsForRole(userRole) {
  if (!userRole) return ALL_SECTIONS.filter((s) => !s.roles || s.roles.length === 0)
  return ALL_SECTIONS.filter((s) => {
    if (!s.roles || s.roles.length === 0) return true
    if (userRole === 'admin') return true
    return s.roles.includes(userRole)
  })
}

export default function GuidePage() {
  const { user } = useAuth()
  const userRole = user?.role
  const sections = useMemo(() => getSectionsForRole(userRole), [userRole])
  const defaultSection = sections[0]?.id || 'intro'
  const [activeSection, setActiveSection] = useState(defaultSection)

  useEffect(() => {
    if (!sections.some((s) => s.id === activeSection)) {
      setActiveSection(defaultSection)
    }
  }, [sections, defaultSection, activeSection])

  const scrollToSection = (id) => {
    setActiveSection(id)
    const el = document.getElementById(id)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  // اگر بخش فعال در فهرست نقش فعلی نیست، اولین بخش را فعال کن
  const effectiveSection = sections.some((s) => s.id === activeSection) ? activeSection : defaultSection

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">راهنمای جامع استفاده از سامانه</h1>
          <p className="page-subtitle">
            آموزش گام‌به‌گام کار با سامانه: ورود با پیامک، پنل نقش‌ها، و تعریف فرایندها برای مدیران و کارمندان
            {userRole && userRole !== 'admin' && (
              <span style={{ display: 'block', marginTop: '0.35rem', fontSize: '0.9rem', opacity: 0.9 }}>
                نمایش مطالب مرتبط با نقش شما
              </span>
            )}
          </p>
        </div>
      </div>

      <div className="guide-layout">
        {/* Table of Contents - Sidebar */}
        <aside className="guide-toc">
          <div className="guide-toc-title">فهرست مطالب</div>
          {sections.map((s) => (
            <button
              key={s.id}
              className={`guide-toc-item ${effectiveSection === s.id ? 'active' : ''}`}
              onClick={() => scrollToSection(s.id)}
            >
              {s.title}
            </button>
          ))}
        </aside>

        {/* Main Content */}
        <div className="guide-content">

          {/* ────────────── مقدمه ────────────── */}
          <section id="intro" className="guide-section">
            <div className="guide-section-header">
              <span className="guide-section-icon">📖</span>
              <h2>مقدمه و معرفی سامانه</h2>
            </div>
            <div className="guide-card">
              <h3>سامانه انیستیتو روانکاوری تهران چیست؟</h3>
              <p>
                سامانه <strong>انیستیتو روانکاوری تهران (Tehran Institute of Psychoanalysis)</strong> یک سیستم اتوماسیون آموزشی مبتنی بر متادیتا (Metadata) است. این سامانه به شما اجازه می‌دهد
                <strong> فرایندهای آموزشی سازمان</strong> خود را به‌صورت دیجیتال تعریف کنید تا سیستم بتواند آن‌ها را به‌صورت خودکار
                مدیریت، ردیابی و گزارش‌گیری کند.
              </p>

              <div className="guide-highlight">
                <div className="guide-highlight-title">هدف اصلی</div>
                <p>
                  شما فرایندهایی دارید که الان به‌صورت سنتی (کاغذی، تلفنی، یا ذهنی) انجام می‌شوند.
                  هدف این سامانه این است که همان فرایندها را اینجا ثبت کنید تا سیستم بتواند:
                </p>
                <ul>
                  <li>وضعیت هر دانشجو را در هر لحظه نشان دهد</li>
                  <li>به‌صورت خودکار اعلان و یادآوری بفرستد</li>
                  <li>قوانین و شرایط را بررسی کند</li>
                  <li>گزارش و آمار دقیق تولید کند</li>
                  <li>تاریخچه کامل تمام اقدامات را ذخیره کند</li>
                </ul>
              </div>

              <div className="guide-callout info">
                <div className="guide-callout-icon">💡</div>
                <div>
                  <strong>نکته مهم:</strong> لازم نیست برنامه‌نویس باشید! این سامانه طوری طراحی شده که فقط با دانستن
                  فرایندهای کاری خودتان بتوانید آن‌ها را در سیستم تعریف کنید.
                </div>
              </div>

              <h3>تفاوت سیستم سنتی و سامانه انیستیتو روانکاوری تهران</h3>
              <div className="guide-compare-table">
                <table>
                  <thead>
                    <tr>
                      <th>موضوع</th>
                      <th>روش سنتی</th>
                      <th>سامانه انیستیتو</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>ثبت فرایند</td>
                      <td>در ذهن افراد یا دفترچه‌ها</td>
                      <td>دیجیتال و با نمودار بصری</td>
                    </tr>
                    <tr>
                      <td>پیگیری وضعیت</td>
                      <td>تماس تلفنی یا پرسش حضوری</td>
                      <td>مشاهده آنلاین در لحظه</td>
                    </tr>
                    <tr>
                      <td>اعلان‌ها</td>
                      <td>فراموشی و تاخیر</td>
                      <td>خودکار با پیامک و ایمیل</td>
                    </tr>
                    <tr>
                      <td>بررسی شرایط</td>
                      <td>بررسی دستی و احتمال خطا</td>
                      <td>بررسی خودکار با قوانین تعریف‌شده</td>
                    </tr>
                    <tr>
                      <td>گزارش‌گیری</td>
                      <td>وقت‌گیر و ناقص</td>
                      <td>فوری و دقیق</td>
                    </tr>
                    <tr>
                      <td>تاریخچه</td>
                      <td>ناقص یا ناموجود</td>
                      <td>کامل و قابل جستجو (حسابرسی)</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          {/* ────────────── مفاهیم ────────────── */}
          <section id="concepts" className="guide-section">
            <div className="guide-section-header">
              <span className="guide-section-icon">🧩</span>
              <h2>مفاهیم کلیدی</h2>
            </div>
            <div className="guide-card">
              <p>
                قبل از شروع، بیایید با چند مفهوم ساده آشنا شویم. نگران نباشید؛
                این مفاهیم دقیقاً همان چیزهایی هستند که در فرایندهای سنتی‌تان وجود دارند، فقط اینجا اسم‌های مشخص دارند.
              </p>

              <div className="guide-concepts-grid">
                <div className="guide-concept-card">
                  <div className="guide-concept-icon" style={{ background: 'var(--primary-light)', color: 'var(--primary)' }}>⚙️</div>
                  <h4>فرایند (Process)</h4>
                  <p>
                    یک فرایند، مجموعه‌ای از مراحل مشخص برای انجام یک کار است.
                    مثلاً «آغاز درمان آموزشی» یا «درخواست مرخصی» هر کدام یک فرایند هستند.
                  </p>
                  <div className="guide-concept-example">
                    <strong>مثال سنتی:</strong> وقتی دانشجویی می‌خواهد درمان آموزشی را شروع کند،
                    یک سری مراحل مشخص وجود دارد که باید طی شود. این مجموعه مراحل، یک «فرایند» است.
                  </div>
                </div>

                <div className="guide-concept-card">
                  <div className="guide-concept-icon" style={{ background: 'var(--success-light)', color: 'var(--success)' }}>📍</div>
                  <h4>وضعیت (State)</h4>
                  <p>
                    هر فرایند از چند «وضعیت» تشکیل شده. وضعیت یعنی الان کار در چه مرحله‌ای است.
                  </p>
                  <div className="guide-concept-example">
                    <strong>مثال سنتی:</strong> وقتی می‌پرسید «پرونده فلان دانشجو کجاست؟» جواب می‌دهند
                    «در انتظار تایید کمیته» یا «پرداخت انجام شده». هر کدام از این جواب‌ها یک «وضعیت» است.
                  </div>
                  <div className="guide-state-types">
                    <span className="badge badge-success">شروع (Initial)</span> اولین وضعیت فرایند
                    <br />
                    <span className="badge badge-info">میانی (Intermediate)</span> وضعیت‌های بین شروع و پایان
                    <br />
                    <span className="badge badge-danger">پایانی (Terminal)</span> وضعیت‌های نهایی فرایند
                  </div>
                </div>

                <div className="guide-concept-card">
                  <div className="guide-concept-icon" style={{ background: 'var(--info-light)', color: 'var(--info)' }}>🔄</div>
                  <h4>انتقال (Transition)</h4>
                  <p>
                    انتقال یعنی حرکت از یک وضعیت به وضعیت دیگر. هر انتقال یک «رویداد محرک» دارد
                    که باعث اجرای آن می‌شود.
                  </p>
                  <div className="guide-concept-example">
                    <strong>مثال سنتی:</strong> وقتی کمیته درخواست را «تایید» می‌کند، وضعیت از
                    «در انتظار بررسی» به «تایید شده» تغییر می‌کند. این تغییر یک «انتقال» است
                    و «تایید کمیته» رویداد محرک آن است.
                  </div>
                </div>

                <div className="guide-concept-card">
                  <div className="guide-concept-icon" style={{ background: 'var(--warning-light)', color: 'var(--warning)' }}>📋</div>
                  <h4>قانون (Rule)</h4>
                  <p>
                    قوانین شرایطی هستند که تعیین می‌کنند آیا یک انتقال مجاز است یا نه.
                  </p>
                  <div className="guide-concept-example">
                    <strong>مثال سنتی:</strong> «فقط دانشجویانی که ۳ ترم گذرانده‌اند می‌توانند درمان آموزشی شروع کنند.»
                    این یک «قانون» است که در سیستم تعریف می‌شود.
                  </div>
                </div>

                <div className="guide-concept-card">
                  <div className="guide-concept-icon" style={{ background: 'var(--danger-light)', color: 'var(--danger)' }}>👤</div>
                  <h4>نقش (Role)</h4>
                  <p>
                    هر وضعیت و انتقال مشخص می‌کند چه نقشی مسئول آن مرحله است.
                  </p>
                  <div className="guide-concept-example">
                    <strong>مثال سنتی:</strong> «تایید مرخصی بر عهده کمیته پیشرفت است» - اینجا
                    «کمیته پیشرفت» (progress_committee) یک نقش است.
                    <br /><br />
                    نقش‌های رایج: student (دانشجو)، therapist (درمانگر)، admin (مدیر)،
                    progress_committee (کمیته پیشرفت)، system (سیستم خودکار)
                  </div>
                </div>

                <div className="guide-concept-card">
                  <div className="guide-concept-icon" style={{ background: '#f0fdf4', color: '#16a34a' }}>🎬</div>
                  <h4>عملیات (Action)</h4>
                  <p>
                    عملیاتی که بعد از هر انتقال به‌صورت خودکار انجام می‌شود.
                  </p>
                  <div className="guide-concept-example">
                    <strong>مثال سنتی:</strong> وقتی درخواست تایید شد، باید «به دانشجو پیامک بزنیم». این
                    ارسال پیامک یک «عملیات» خودکار است.
                    <br /><br />
                    انواع عملیات: ارسال پیامک/ایمیل، شروع فرایند فرعی، مسدودسازی دسترسی، ثبت تخلف و...
                  </div>
                </div>
              </div>

              <div className="guide-callout success">
                <div className="guide-callout-icon">✅</div>
                <div>
                  <strong>خلاصه:</strong> یک <strong>فرایند</strong> از چند <strong>وضعیت</strong> تشکیل شده.
                  بین وضعیت‌ها <strong>انتقال</strong> وجود دارد.
                  هر انتقال ممکن است <strong>قوانین</strong> (شرایط) داشته باشد و بعد از اجرا <strong>عملیاتی</strong> انجام شود.
                  هر مرحله یک <strong>نقش</strong> مسئول دارد.
                </div>
              </div>
            </div>
          </section>

          {/* ────────────── گام ۱ ────────────── */}
          <section id="step1" className="guide-section">
            <div className="guide-section-header">
              <span className="guide-section-icon">🔐</span>
              <h2>گام ۱: ورود به سیستم</h2>
            </div>
            <div className="guide-card">
              <p>
                ورود پیش‌فرض با <strong>کد یکبار مصرف پیامکی (OTP)</strong> است: شماره موبایل ثبت‌شده را وارد می‌کنید،
                کد ۶ رقمی را دریافت و تأیید می‌کنید. پس از ورود، بسته به نقش شما به داشبورد، پنل تخصصی
                (مثلاً دانشجو یا مالی) یا آدرسی که مدیر برای «خانه نقش» تنظیم کرده هدایت می‌شوید.
              </p>
              <div className="guide-callout info">
                <div className="guide-callout-icon">🔑</div>
                <div>
                  <strong>ورود با رمز عبور:</strong> برای برخی کاربران پرسنلی، تب «ورود با رمز عبور» در همان صفحه فعال است
                  و ممکن است پس از نام کاربری و رمز، یک <strong>سؤال امنیتی (چالش ورود)</strong> نیز نمایش داده شود.
                </div>
              </div>
              <div className="guide-steps">
                <div className="guide-step">
                  <div className="guide-step-number">1</div>
                  <div className="guide-step-content">
                    <h4>باز کردن صفحه ورود</h4>
                    <p>آدرس سامانه را باز کنید و به صفحه «ورود» بروید.</p>
                  </div>
                </div>
                <div className="guide-step">
                  <div className="guide-step-number">2</div>
                  <div className="guide-step-content">
                    <h4>ورود با پیامک (پیش‌فرض)</h4>
                    <p>
                      شماره موبایل خود را وارد کنید، روی ارسال کد بزنید، کد ۶ رقمی را وارد و تأیید کنید.
                    </p>
                  </div>
                </div>
                <div className="guide-step">
                  <div className="guide-step-number">3</div>
                  <div className="guide-step-content">
                    <h4>ورود به پنل</h4>
                    <p>
                      پس از تأیید، به پنل مربوط به نقش شما (مثلاً داشبورد مدیریتی، پنل دانشجو، یا داشبورد مالی) هدایت می‌شوید.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* ────────────── راهنمای دانشجو ────────────── */}
          {sections.some((s) => s.id === 'role_student') && (
            <section id="role_student" className="guide-section">
              <div className="guide-section-header">
                <span className="guide-section-icon">🎓</span>
                <h2>راهنمای دانشجو</h2>
              </div>
              <div className="guide-card">
                <p>این بخش مخصوص کاربران با نقش <strong>دانشجو</strong> است. با استفاده از پنل دانشجو می‌توانید:</p>
                <ul>
                  <li><strong>داشبورد و مسیر تحصیلی:</strong> کارت «مسیر فعلی»، پیشرفت تقریبی و خلاصه وضعیت پرونده را ببینید</li>
                  <li><strong>فرایندها:</strong> درخواست مرخصی، آغاز درمان آموزشی، ثبت‌نام دوره، جلسه اضافی، تغییرات درمان، سوپرویژن و سایر موارد مجاز را شروع یا ادامه دهید؛ در هر مرحله ممکن است <strong>فرم مرحله‌ای</strong> و «راهنمای قدم بعد» نمایش داده شود</li>
                  <li><strong>جلسات درمان و تکالیف:</strong> از تب‌های مربوطه جلسات ثبت‌شده و تکلیف/ارجاع‌ها را پیگیری کنید</li>
                  <li><strong>گام‌افزاری (مسیر آموزشی):</strong> در تب اختصاصی، امتیاز و مراحل انگیزشی مسیر را ببینید</li>
                  <li>کارتابل اقدامات لازم (تأیید، بارگذاری مدرک، پرداخت و غیره) را دنبال کنید</li>
                  <li>در صورت واجد شرایط، درخواست‌هایی مانند ارتقا به کمک‌مدرس ثبت کنید</li>
                </ul>
                <div className="guide-callout info">
                  <div className="guide-callout-icon">💡</div>
                  <div>
                    <strong>نکته:</strong> از منوی سمت راست «پنل دانشجو» را انتخاب کنید. بسیاری از فرایندها تا زمانی که مسیر اصلی
                    (مثلاً ثبت‌نام) باز است قفل می‌مانند؛ ابتدا مسیر را از داشبورد جلو ببرید.
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* ────────────── راهنمای درمانگر ────────────── */}
          {sections.some((s) => s.id === 'role_therapist') && (
            <section id="role_therapist" className="guide-section">
              <div className="guide-section-header">
                <span className="guide-section-icon">💊</span>
                <h2>راهنمای درمانگر</h2>
              </div>
              <div className="guide-card">
                <p>این بخش مخصوص کاربران با نقش <strong>درمانگر آموزشی</strong> است. در پنل درمانگر:</p>
                <ul>
                  <li>لیست دانشجویان تحت نظر و کارتابل اقدامات را مشاهده کنید</li>
                  <li>درخواست‌های آغاز درمان، جلسه اضافی و تغییرات درمان را تأیید یا رد کنید</li>
                  <li>حضور و غیاب و جلسات درمان آموزشی را ثبت و پیگیری کنید (هم‌راستا با اتوماسیون فرایند)</li>
                  <li>مرخصی، وقفه و وضعیت فرایندهای مرتبط با دانشجویان را رصد کنید</li>
                </ul>
                <div className="guide-callout info">
                  <div className="guide-callout-icon">💡</div>
                  <div>
                    <strong>نکته:</strong> از منو «پنل درمانگر» را انتخاب کنید. کارتابل اقدامات در انتظار، در همان پنل نمایش داده می‌شود.
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* ────────────── راهنمای سوپروایزر ────────────── */}
          {sections.some((s) => s.id === 'role_supervisor') && (
            <section id="role_supervisor" className="guide-section">
              <div className="guide-section-header">
                <span className="guide-section-icon">👁️</span>
                <h2>راهنمای سوپروایزر</h2>
              </div>
              <div className="guide-card">
                <p>این بخش مخصوص کاربران با نقش <strong>سوپروایزر</strong> است. در پنل سوپروایزر:</p>
                <ul>
                  <li>دانشجویان تحت سوپرویژن خود را مشاهده کنید</li>
                  <li>گزارش جلسات و طرح‌های درمانی را بررسی و تایید کنید</li>
                  <li>درخواست‌های مرتبط با سوپرویژن (جلسه اضافی و غیره) را پیگیری کنید</li>
                  <li>وضعیت کلی دانشجویان تحت نظر خود را رصد کنید</li>
                </ul>
                <div className="guide-callout info">
                  <div className="guide-callout-icon">💡</div>
                  <div>
                    <strong>نکته:</strong> از منو «پنل سوپروایزر» را انتخاب کنید تا به کارتابل و خلاصه دانشجویان دسترسی داشته باشید.
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* ────────────── راهنمای کارمند دفتر ────────────── */}
          {sections.some((s) => s.id === 'role_staff') && (
            <section id="role_staff" className="guide-section">
              <div className="guide-section-header">
                <span className="guide-section-icon">🏢</span>
                <h2>راهنمای کارمند دفتر</h2>
              </div>
              <div className="guide-card">
                <p>این بخش مخصوص کاربران با نقش <strong>کارمند دفتر</strong> است. شما می‌توانید:</p>
                <ul>
                  <li>لیست دانشجویان و جستجوی پرونده را در «ردیابی دانشجو» انجام دهید</li>
                  <li>پرداخت‌ها را مدیریت و تایید کنید</li>
                  <li>حضور و غیاب را ثبت و مدیریت کنید</li>
                  <li>فرایندها و نمونه‌های در حال اجرا را مشاهده کنید</li>
                  <li>در صورت دسترسی، فرایندهای جدید در سیستم تعریف کنید (گام‌های ۲ تا ۷ این راهنما)</li>
                </ul>
                <div className="guide-callout info">
                  <div className="guide-callout-icon">💡</div>
                  <div>
                    <strong>نکته:</strong> از منو به «مدیریت فرایندها»، «ردیابی دانشجو» و «گزارش حسابرسی» دسترسی دارید.
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* ────────────── راهنمای مسئول سایت ────────────── */}
          {sections.some((s) => s.id === 'role_site_manager') && (
            <section id="role_site_manager" className="guide-section">
              <div className="guide-section-header">
                <span className="guide-section-icon">🏗️</span>
                <h2>راهنمای مسئول سایت</h2>
              </div>
              <div className="guide-card">
                <p>این بخش مخصوص کاربران با نقش <strong>مسئول سایت</strong> است. در پنل خود:</p>
                <ul>
                  <li>هشدارهای مربوط به حضور و غیاب را مشاهده کنید</li>
                  <li>پیگیری حضور درمانگران را انجام و ثبت کنید</li>
                  <li>وضعیت پیگیری را به‌روز کنید (انجام شد / در انتظار)</li>
                </ul>
                <div className="guide-callout info">
                  <div className="guide-callout-icon">💡</div>
                  <div>
                    <strong>نکته:</strong> از منوی سمت راست به پنل مسئول سایت دسترسی دارید.
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* ────────────── راهنمای اپراتور مالی ────────────── */}
          {sections.some((s) => s.id === 'role_finance') && (
            <section id="role_finance" className="guide-section">
              <div className="guide-section-header">
                <span className="guide-section-icon">💵</span>
                <h2>راهنمای اپراتور مالی</h2>
              </div>
              <div className="guide-card">
                <p>این بخش مخصوص کاربران با نقش <strong>اپراتور مالی</strong> است. پس از ورود، معمولاً مستقیماً به <strong>داشبورد مالی</strong> هدایت می‌شوید.</p>
                <ul>
                  <li>مرور تراکنش‌ها، بدهی و بستانکاری و مانده دانشجویان</li>
                  <li>هم‌ترازی و گزارش‌گیری مالی در ارتباط با فرایندهای ثبت‌شده در سامانه</li>
                  <li>دسترسی محدود به بخش مالی؛ سایر بخش‌های پنل در صورت عدم تخصیص نقش اضافه در دسترس نیست</li>
                </ul>
                <div className="guide-callout info">
                  <div className="guide-callout-icon">💡</div>
                  <div>
                    <strong>نکته:</strong> از منوی سمت راست گزینه «داشبورد مالی» را انتخاب کنید. مدیر سیستم نیز به این بخش دسترسی دارد.
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* ────────────── راهنمای کمیته‌ها ────────────── */}
          {sections.some((s) => s.id === 'role_committee') && (
            <section id="role_committee" className="guide-section">
              <div className="guide-section-header">
                <span className="guide-section-icon">📋</span>
                <h2>راهنمای کمیته‌ها</h2>
              </div>
              <div className="guide-card">
                <p>این بخش مخصوص اعضای <strong>کمیته‌های آموزش، پیشرفت، نظارت و نقش‌های مرتبط</strong> است. بسته به نوع کمیته:</p>
                <ul>
                  <li><strong>کمیته پیشرفت:</strong> بررسی درخواست مرخصی، تایید/رد، تنظیم جلسه، بررسی تغییرات درمان و بازگشت به درمان</li>
                  <li><strong>کمیته آموزش:</strong> بررسی احکام نهایی، صدور حکم ادامه یا ختم آموزش</li>
                  <li><strong>کمیته نظارت:</strong> بررسی پرونده‌های انضباطی، تعیین زمان جلسه، ارجاع به کمیته آموزش</li>
                  <li><strong>معاون آموزش:</strong> دریافت هشدارهای SLA، مشاهده درخواست مرخصی، پیگیری تاخیر کمیته‌ها</li>
                  <li><strong>کمیته درمان (مسئول/مجری):</strong> پیگیری دانشجویان، ثبت گزارش مجری، تعیین توقف قطعی یا بازگشت</li>
                </ul>
                <div className="guide-callout info">
                  <div className="guide-callout-icon">💡</div>
                  <div>
                    <strong>نکته:</strong> از منو «پنل کمیته» را انتخاب کنید. کارتابل اقدامات در انتظار و خلاصه دانشجویان در همان پنل نمایش داده می‌شود.
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* ────────────── گام ۲ ────────────── */}
          {sections.some((s) => s.id === 'step2') && (
          <section id="step2" className="guide-section">
            <div className="guide-section-header">
              <span className="guide-section-icon">🏗️</span>
              <h2>گام ۲: ساخت فرایند جدید</h2>
            </div>
            <div className="guide-card">
              <div className="guide-callout warning">
                <div className="guide-callout-icon">⚠️</div>
                <div>
                  <strong>قبل از شروع:</strong> فرایند مورد نظرتان را روی کاغذ یا در ذهنتان مرور کنید.
                  بدانید چه مراحلی دارد، چه کسی مسئول هر مرحله است، و چه شرایطی باعث حرکت
                  از یک مرحله به مرحله بعد می‌شود.
                </div>
              </div>

              <h3>آماده‌سازی اطلاعات فرایند</h3>
              <p>قبل از ورود به سیستم، این اطلاعات را آماده کنید:</p>

              <div className="guide-checklist">
                <div className="guide-checklist-item">
                  <span className="guide-check">☑</span>
                  <div>
                    <strong>نام فرایند به فارسی:</strong> مثلاً «آغاز درمان آموزشی»
                  </div>
                </div>
                <div className="guide-checklist-item">
                  <span className="guide-check">☑</span>
                  <div>
                    <strong>کد فرایند (انگلیسی):</strong> یک کد کوتاه و یکتا مانند <code>start_therapy</code>
                    (بدون فاصله، با خط‌زیر)
                  </div>
                </div>
                <div className="guide-checklist-item">
                  <span className="guide-check">☑</span>
                  <div>
                    <strong>شرح فرایند:</strong> توضیح مختصر از هدف این فرایند
                  </div>
                </div>
                <div className="guide-checklist-item">
                  <span className="guide-check">☑</span>
                  <div>
                    <strong>لیست مراحل (وضعیت‌ها):</strong> تمام مراحلی که این فرایند دارد
                  </div>
                </div>
                <div className="guide-checklist-item">
                  <span className="guide-check">☑</span>
                  <div>
                    <strong>نحوه حرکت بین مراحل:</strong> چه اتفاقی باعث حرکت از یک مرحله به مرحله بعد می‌شود
                  </div>
                </div>
              </div>

              <h3>مراحل ساخت فرایند در سیستم</h3>
              <div className="guide-steps">
                <div className="guide-step">
                  <div className="guide-step-number">1</div>
                  <div className="guide-step-content">
                    <h4>از منوی سمت راست، «مدیریت فرایندها» را انتخاب کنید</h4>
                    <p>صفحه لیست فرایندها باز می‌شود.</p>
                  </div>
                </div>
                <div className="guide-step">
                  <div className="guide-step-number">2</div>
                  <div className="guide-step-content">
                    <h4>روی دکمه «+ فرایند جدید» کلیک کنید</h4>
                    <p>فرم ساخت فرایند جدید ظاهر می‌شود.</p>
                  </div>
                </div>
                <div className="guide-step">
                  <div className="guide-step-number">3</div>
                  <div className="guide-step-content">
                    <h4>اطلاعات فرایند را پر کنید</h4>
                    <div className="guide-field-table">
                      <table>
                        <thead>
                          <tr><th>فیلد</th><th>توضیح</th><th>مثال</th></tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td><strong>کد فرایند</strong></td>
                            <td>کد یکتا به انگلیسی (بدون فاصله)</td>
                            <td><code>educational_leave</code></td>
                          </tr>
                          <tr>
                            <td><strong>نام فارسی</strong></td>
                            <td>نام قابل فهم فرایند</td>
                            <td>مرخصی آموزشی موقت</td>
                          </tr>
                          <tr>
                            <td><strong>نام انگلیسی</strong></td>
                            <td>نام به انگلیسی (اختیاری)</td>
                            <td>Educational Leave</td>
                          </tr>
                          <tr>
                            <td><strong>توضیحات</strong></td>
                            <td>شرح مختصر هدف فرایند</td>
                            <td>فرایند درخواست و مدیریت مرخصی آموزشی</td>
                          </tr>
                          <tr>
                            <td><strong>وضعیت شروع</strong></td>
                            <td>کد اولین وضعیت فرایند</td>
                            <td><code>request_form</code></td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
                <div className="guide-step">
                  <div className="guide-step-number">4</div>
                  <div className="guide-step-content">
                    <h4>دکمه «ایجاد» را بزنید</h4>
                    <p>فرایند ساخته می‌شود و به صفحه ویرایش آن منتقل می‌شوید.</p>
                  </div>
                </div>
              </div>
            </div>
          </section>
          )}

          {/* ────────────── گام ۳ ────────────── */}
          {sections.some((s) => s.id === 'step3') && (
          <section id="step3" className="guide-section">
            <div className="guide-section-header">
              <span className="guide-section-icon">📍</span>
              <h2>گام ۳: تعریف وضعیت‌ها (States)</h2>
            </div>
            <div className="guide-card">
              <p>
                بعد از ساخت فرایند، باید تمام «وضعیت‌ها» یا مراحل آن را تعریف کنید.
                هر وضعیت نشان‌دهنده یک مرحله در فرایند است.
              </p>

              <h3>نحوه تعریف وضعیت‌ها</h3>
              <div className="guide-steps">
                <div className="guide-step">
                  <div className="guide-step-number">1</div>
                  <div className="guide-step-content">
                    <h4>در صفحه ویرایش فرایند، تب «وضعیت‌ها» را بزنید</h4>
                  </div>
                </div>
                <div className="guide-step">
                  <div className="guide-step-number">2</div>
                  <div className="guide-step-content">
                    <h4>روی «+ وضعیت جدید» کلیک کنید</h4>
                  </div>
                </div>
                <div className="guide-step">
                  <div className="guide-step-number">3</div>
                  <div className="guide-step-content">
                    <h4>اطلاعات وضعیت را پر کنید</h4>
                    <div className="guide-field-table">
                      <table>
                        <thead>
                          <tr><th>فیلد</th><th>توضیح</th><th>مثال</th></tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td><strong>کد</strong></td>
                            <td>کد یکتا (انگلیسی، بدون فاصله)</td>
                            <td><code>committee_review</code></td>
                          </tr>
                          <tr>
                            <td><strong>نام فارسی</strong></td>
                            <td>نام قابل فهم وضعیت</td>
                            <td>بررسی کمیته پیشرفت</td>
                          </tr>
                          <tr>
                            <td><strong>نوع</strong></td>
                            <td>شروع، میانی یا پایانی</td>
                            <td>میانی (intermediate)</td>
                          </tr>
                          <tr>
                            <td><strong>نقش مسئول</strong></td>
                            <td>چه نقشی مسئول این مرحله است</td>
                            <td><code>progress_committee</code></td>
                          </tr>
                          <tr>
                            <td><strong>SLA (ساعت)</strong></td>
                            <td>حداکثر زمان مجاز برای این مرحله (اختیاری)</td>
                            <td>168 (یک هفته)</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>

              <h3>انواع وضعیت‌ها</h3>
              <div className="guide-state-types-detail">
                <div className="guide-state-type-card initial">
                  <h4><span className="badge badge-success">شروع (Initial)</span></h4>
                  <p>
                    اولین مرحله فرایند. هر فرایند باید <strong>دقیقاً یک</strong> وضعیت شروع داشته باشد.
                    وقتی فرایندی برای یک دانشجو آغاز می‌شود، از این نقطه شروع می‌شود.
                  </p>
                  <div className="guide-concept-example">
                    مثال: «ثبت درخواست اولیه» - دانشجو فرم درخواست را پر می‌کند.
                  </div>
                </div>
                <div className="guide-state-type-card intermediate">
                  <h4><span className="badge badge-info">میانی (Intermediate)</span></h4>
                  <p>
                    مراحل بین شروع و پایان. بیشتر وضعیت‌های فرایند از این نوع هستند.
                    فرایند ممکن است در هر کدام از این مراحل متوقف شود تا عملی انجام شود.
                  </p>
                  <div className="guide-concept-example">
                    مثال: «بررسی کمیته»، «در انتظار پرداخت»، «تنظیم اولین جلسه»
                  </div>
                </div>
                <div className="guide-state-type-card terminal">
                  <h4><span className="badge badge-danger">پایانی (Terminal)</span></h4>
                  <p>
                    آخرین مرحله فرایند. وقتی فرایند به این نقطه برسد، تمام شده محسوب می‌شود.
                    یک فرایند می‌تواند <strong>چند وضعیت پایانی</strong> داشته باشد (مثلاً «تایید شده» و «رد شده»).
                  </p>
                  <div className="guide-concept-example">
                    مثال: «درمان فعال»، «رد درخواست»، «ثبت تخلف»
                  </div>
                </div>
              </div>

              <div className="guide-callout info">
                <div className="guide-callout-icon">💡</div>
                <div>
                  <strong>راهنمای انتخاب نقش مسئول:</strong>
                  <ul>
                    <li><code>student</code> - مراحلی که دانشجو باید اقدامی انجام دهد</li>
                    <li><code>therapist</code> - مراحلی که درمانگر مسئول است</li>
                    <li><code>admin</code> - مراحلی که مدیر سیستم مسئول است</li>
                    <li><code>progress_committee</code> - مراحلی که کمیته پیشرفت تصمیم‌گیر است</li>
                    <li><code>system</code> - مراحلی که سیستم به‌صورت خودکار انجام می‌دهد</li>
                  </ul>
                </div>
              </div>
            </div>
          </section>
          )}

          {/* ────────────── گام ۴ ────────────── */}
          {sections.some((s) => s.id === 'step4') && (
          <section id="step4" className="guide-section">
            <div className="guide-section-header">
              <span className="guide-section-icon">🔄</span>
              <h2>گام ۴: تعریف انتقال‌ها (Transitions)</h2>
            </div>
            <div className="guide-card">
              <p>
                انتقال‌ها مشخص می‌کنند چگونه فرایند از یک وضعیت به وضعیت دیگر حرکت می‌کند.
                هر انتقال سه جزء اصلی دارد:
              </p>

              <div className="guide-transition-anatomy">
                <div className="guide-transition-part">
                  <span className="badge badge-info" style={{ fontSize: '0.9rem', padding: '0.4rem 0.8rem' }}>از وضعیت</span>
                  <span className="guide-transition-arrow">→</span>
                  <span className="badge badge-warning" style={{ fontSize: '0.9rem', padding: '0.4rem 0.8rem' }}>رویداد محرک</span>
                  <span className="guide-transition-arrow">→</span>
                  <span className="badge badge-success" style={{ fontSize: '0.9rem', padding: '0.4rem 0.8rem' }}>به وضعیت</span>
                </div>
              </div>

              <h3>نحوه تعریف انتقال</h3>
              <div className="guide-steps">
                <div className="guide-step">
                  <div className="guide-step-number">1</div>
                  <div className="guide-step-content">
                    <h4>تب «انتقال‌ها» را بزنید</h4>
                  </div>
                </div>
                <div className="guide-step">
                  <div className="guide-step-number">2</div>
                  <div className="guide-step-content">
                    <h4>روی «+ انتقال جدید» کلیک کنید</h4>
                  </div>
                </div>
                <div className="guide-step">
                  <div className="guide-step-number">3</div>
                  <div className="guide-step-content">
                    <h4>فیلدها را پر کنید</h4>
                    <div className="guide-field-table">
                      <table>
                        <thead>
                          <tr><th>فیلد</th><th>توضیح</th><th>مثال</th></tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td><strong>از وضعیت</strong></td>
                            <td>فرایند باید الان در این وضعیت باشد</td>
                            <td>بررسی کمیته پیشرفت</td>
                          </tr>
                          <tr>
                            <td><strong>به وضعیت</strong></td>
                            <td>فرایند بعد از انتقال به این وضعیت می‌رود</td>
                            <td>تایید شده</td>
                          </tr>
                          <tr>
                            <td><strong>رویداد محرک</strong></td>
                            <td>چه اتفاقی باعث این انتقال می‌شود</td>
                            <td><code>committee_approved</code></td>
                          </tr>
                          <tr>
                            <td><strong>نقش مورد نیاز</strong></td>
                            <td>فقط این نقش می‌تواند این انتقال را اجرا کند</td>
                            <td><code>progress_committee</code></td>
                          </tr>
                          <tr>
                            <td><strong>اولویت</strong></td>
                            <td>اگر چند انتقال با یک رویداد وجود دارد (عدد بزرگ‌تر = اولویت بالاتر)</td>
                            <td>0</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>

              <h3>نکات مهم درباره انتقال‌ها</h3>
              <div className="guide-tips-grid">
                <div className="guide-tip">
                  <strong>انشعاب:</strong> از یک وضعیت می‌توانید چند انتقال به وضعیت‌های مختلف داشته باشید.
                  مثلاً از «تصمیم‌گیری کمیته» هم می‌توان به «تایید» و هم به «رد» رفت.
                </div>
                <div className="guide-tip">
                  <strong>بازگشت:</strong> انتقال می‌تواند به عقب هم باشد. مثلاً اگر درمانگر درخواست را رد کند،
                  فرایند به مرحله «انتخاب درمانگر» برمی‌گردد.
                </div>
                <div className="guide-tip">
                  <strong>اولویت:</strong> اگر یک رویداد بتواند فرایند را به چند وضعیت مختلف ببرد
                  (بسته به شرایط)، از فیلد اولویت استفاده کنید تا سیستم بداند ابتدا کدام را بررسی کند.
                </div>
                <div className="guide-tip">
                  <strong>رویداد محرک:</strong> نام رویداد را به انگلیسی و با خط‌زیر بنویسید.
                  مثلاً: <code>student_submitted</code>، <code>committee_approved</code>، <code>payment_confirmed</code>
                </div>
              </div>

              <h3>مثال بصری: جریان یک فرایند ساده</h3>
              <div className="guide-flow-example">
                <div className="guide-flow-node initial">ثبت درخواست</div>
                <div className="guide-flow-arrow">
                  <span>student_submitted</span>
                  <span className="arrow-line">↓</span>
                </div>
                <div className="guide-flow-node intermediate">بررسی کمیته</div>
                <div className="guide-flow-branch">
                  <div className="guide-flow-branch-item">
                    <div className="guide-flow-arrow">
                      <span>committee_approved</span>
                      <span className="arrow-line">↙</span>
                    </div>
                    <div className="guide-flow-node terminal success">تایید شده</div>
                  </div>
                  <div className="guide-flow-branch-item">
                    <div className="guide-flow-arrow">
                      <span>committee_rejected</span>
                      <span className="arrow-line">↘</span>
                    </div>
                    <div className="guide-flow-node terminal danger">رد شده</div>
                  </div>
                </div>
              </div>
            </div>
          </section>
          )}

          {/* ────────────── گام ۵ ────────────── */}
          {sections.some((s) => s.id === 'step5') && (
          <section id="step5" className="guide-section">
            <div className="guide-section-header">
              <span className="guide-section-icon">📋</span>
              <h2>گام ۵: تعریف قوانین (Rules)</h2>
            </div>
            <div className="guide-card">
              <p>
                قوانین شرایطی هستند که سیستم قبل از اجرای هر انتقال بررسی می‌کند.
                با استفاده از قوانین می‌توانید مطمئن شوید که فقط در شرایط صحیح، فرایند جلو می‌رود.
              </p>

              <h3>نحوه تعریف قانون</h3>
              <div className="guide-steps">
                <div className="guide-step">
                  <div className="guide-step-number">1</div>
                  <div className="guide-step-content">
                    <h4>از منوی سمت راست «مدیریت قوانین» را بزنید</h4>
                  </div>
                </div>
                <div className="guide-step">
                  <div className="guide-step-number">2</div>
                  <div className="guide-step-content">
                    <h4>روی «+ قانون جدید» کلیک کنید</h4>
                  </div>
                </div>
                <div className="guide-step">
                  <div className="guide-step-number">3</div>
                  <div className="guide-step-content">
                    <h4>اطلاعات قانون را وارد کنید</h4>
                    <div className="guide-field-table">
                      <table>
                        <thead>
                          <tr><th>فیلد</th><th>توضیح</th><th>مثال</th></tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td><strong>کد</strong></td>
                            <td>کد یکتا قانون</td>
                            <td><code>student_eligible_for_therapy</code></td>
                          </tr>
                          <tr>
                            <td><strong>نام فارسی</strong></td>
                            <td>توضیح فارسی قانون</td>
                            <td>صلاحیت دانشجو برای شروع درمان</td>
                          </tr>
                          <tr>
                            <td><strong>عبارت شرط</strong></td>
                            <td>شرطی که باید بررسی شود (به فرمت JSON)</td>
                            <td>{'{">=": ["student.term_count", 3]}'}</td>
                          </tr>
                          <tr>
                            <td><strong>پیام خطا</strong></td>
                            <td>پیامی که در صورت عدم برقراری شرط نمایش داده شود</td>
                            <td>دانشجو حداقل ۳ ترم نگذرانده است</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>

              <h3>نمونه قوانین رایج</h3>
              <div className="guide-rules-examples">
                <div className="guide-rule-example">
                  <div className="guide-rule-title">بررسی تعداد ترم</div>
                  <div className="guide-rule-desc">دانشجو باید حداقل ۳ ترم گذرانده باشد</div>
                  <code className="guide-rule-code">{'{">=": ["student.term_count", 3]}'}</code>
                </div>
                <div className="guide-rule-example">
                  <div className="guide-rule-title">بررسی وضعیت انترنی</div>
                  <div className="guide-rule-desc">دانشجو باید انترن باشد</div>
                  <code className="guide-rule-code">{'{"==": ["student.is_intern", true]}'}</code>
                </div>
                <div className="guide-rule-example">
                  <div className="guide-rule-title">بررسی نوع دوره</div>
                  <div className="guide-rule-desc">دانشجو باید در دوره جامع باشد</div>
                  <code className="guide-rule-code">{'{"==": ["student.course_type", "comprehensive"]}'}</code>
                </div>
                <div className="guide-rule-example">
                  <div className="guide-rule-title">شرط ترکیبی</div>
                  <div className="guide-rule-desc">دانشجو انترن باشد و حداقل ۳ ترم گذرانده باشد</div>
                  <code className="guide-rule-code">{'{"AND": [{"==": ["student.is_intern", true]}, {">=": ["student.term_count", 3]}]}'}</code>
                </div>
              </div>

              <div className="guide-callout success">
                <div className="guide-callout-icon">✅</div>
                <div>
                  <strong>عملگرهای قابل استفاده:</strong>
                  <ul>
                    <li><code>{'=='}</code> : مساوی</li>
                    <li><code>{'!='}</code> : نامساوی</li>
                    <li><code>{'>'}</code> : بزرگ‌تر</li>
                    <li><code>{'>='}</code> : بزرگ‌تر یا مساوی</li>
                    <li><code>{'<'}</code> : کوچک‌تر</li>
                    <li><code>{'<='}</code> : کوچک‌تر یا مساوی</li>
                    <li><code>AND</code> : و (همه شرایط باید برقرار باشد)</li>
                    <li><code>OR</code> : یا (حداقل یکی از شرایط باید برقرار باشد)</li>
                    <li><code>NOT</code> : نقیض (شرط نباید برقرار باشد)</li>
                  </ul>
                </div>
              </div>
            </div>
          </section>
          )}

          {/* ────────────── گام ۶ ────────────── */}
          {sections.some((s) => s.id === 'step6') && (
          <section id="step6" className="guide-section">
            <div className="guide-section-header">
              <span className="guide-section-icon">🚀</span>
              <h2>گام ۶: آزمایش و اجرای فرایند</h2>
            </div>
            <div className="guide-card">
              <p>
                بعد از تعریف فرایند، وضعیت‌ها و انتقال‌ها، می‌توانید فرایند را آزمایش کنید.
              </p>

              <h3>بررسی بصری</h3>
              <div className="guide-steps">
                <div className="guide-step">
                  <div className="guide-step-number">1</div>
                  <div className="guide-step-content">
                    <h4>به صفحه ویرایش فرایند بروید و تب «نمای بصری» را بزنید</h4>
                    <p>
                      تمام وضعیت‌ها و انتقال‌ها به‌صورت بصری نمایش داده می‌شوند. بررسی کنید که:
                    </p>
                    <ul>
                      <li>تمام مراحل تعریف شده‌اند</li>
                      <li>وضعیت شروع (سبز) و پایانی (قرمز) مشخص هستند</li>
                      <li>بین همه وضعیت‌ها انتقال مناسب وجود دارد</li>
                      <li>هیچ وضعیتی بدون مسیر ورود یا خروج نیست (مگر شروع و پایان)</li>
                    </ul>
                  </div>
                </div>
              </div>

              <h3>اجرای فرایند برای یک دانشجو</h3>
              <div className="guide-steps">
                <div className="guide-step">
                  <div className="guide-step-number">1</div>
                  <div className="guide-step-content">
                    <h4>از API یا رابط کاربری، فرایند را برای یک دانشجو شروع کنید</h4>
                    <p>سیستم یک «نمونه فرایند» (Process Instance) ایجاد می‌کند و آن را در وضعیت شروع قرار می‌دهد.</p>
                  </div>
                </div>
                <div className="guide-step">
                  <div className="guide-step-number">2</div>
                  <div className="guide-step-content">
                    <h4>رویدادهای محرک را ارسال کنید</h4>
                    <p>
                      با ارسال هر رویداد (مثلاً <code>student_submitted</code>)، سیستم بررسی می‌کند:
                    </p>
                    <ul>
                      <li>آیا انتقالی با این رویداد از وضعیت فعلی وجود دارد؟</li>
                      <li>آیا قوانین مربوطه برقرار هستند؟</li>
                      <li>آیا کاربر نقش مورد نیاز را دارد؟</li>
                    </ul>
                    <p>اگر همه شرایط برقرار باشد، انتقال اجرا می‌شود.</p>
                  </div>
                </div>
                <div className="guide-step">
                  <div className="guide-step-number">3</div>
                  <div className="guide-step-content">
                    <h4>نتیجه را بررسی کنید</h4>
                    <p>
                      بعد از هر انتقال، وضعیت جدید فرایند و عملیات‌های انجام‌شده را مشاهده کنید.
                      در صفحه «ردیابی دانشجو» می‌توانید وضعیت فعلی هر دانشجو را ببینید.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </section>
          )}

          {/* ────────────── گام ۷ ────────────── */}
          {sections.some((s) => s.id === 'step7') && (
          <section id="step7" className="guide-section">
            <div className="guide-section-header">
              <span className="guide-section-icon">📊</span>
              <h2>گام ۷: ردیابی و گزارش‌گیری</h2>
            </div>
            <div className="guide-card">
              <h3>ردیابی دانشجویان</h3>
              <p>
                در صفحه «ردیابی دانشجو» می‌توانید وضعیت تمام دانشجویان را در تمام فرایندها ببینید.
              </p>
              <div className="guide-feature-list">
                <div className="guide-feature">
                  <span className="guide-feature-icon">🔍</span>
                  <div>
                    <strong>جستجوی دانشجو:</strong> با کد دانشجویی یا نام، دانشجوی مورد نظر را پیدا کنید.
                  </div>
                </div>
                <div className="guide-feature">
                  <span className="guide-feature-icon">📋</span>
                  <div>
                    <strong>مشاهده فرایندهای فعال:</strong> تمام فرایندهایی که دانشجو الان در آن‌ها درگیر است و وضعیت فعلی هر کدام.
                  </div>
                </div>
                <div className="guide-feature">
                  <span className="guide-feature-icon">📜</span>
                  <div>
                    <strong>تاریخچه فرایندها:</strong> فرایندهای تکمیل‌شده و لغوشده.
                  </div>
                </div>
              </div>

              <h3>گزارش حسابرسی (Audit)</h3>
              <p>
                در صفحه «گزارش حسابرسی» تاریخچه کامل تمام عملیات سیستم قابل مشاهده است:
              </p>
              <div className="guide-feature-list">
                <div className="guide-feature">
                  <span className="guide-feature-icon">🔄</span>
                  <div>
                    <strong>انتقال‌ها:</strong> چه کسی، چه زمانی، چه انتقالی را اجرا کرده.
                  </div>
                </div>
                <div className="guide-feature">
                  <span className="guide-feature-icon">📋</span>
                  <div>
                    <strong>تغییر قوانین:</strong> چه کسی قوانین را تغییر داده.
                  </div>
                </div>
                <div className="guide-feature">
                  <span className="guide-feature-icon">🔐</span>
                  <div>
                    <strong>ورود و خروج:</strong> تاریخچه ورود کاربران.
                  </div>
                </div>
              </div>

              <div className="guide-callout info">
                <div className="guide-callout-icon">💡</div>
                <div>
                  <strong>نکته:</strong> تمام اطلاعات حسابرسی غیرقابل تغییر و حذف هستند.
                  این یعنی هیچ عملیاتی در سیستم بدون ردپا نخواهد بود.
                </div>
              </div>
            </div>
          </section>
          )}

          {/* ────────────── مثال کامل ────────────── */}
          {sections.some((s) => s.id === 'example') && (
          <section id="example" className="guide-section">
            <div className="guide-section-header">
              <span className="guide-section-icon">🎯</span>
              <h2>مثال کامل: ثبت فرایند «مرخصی آموزشی»</h2>
            </div>
            <div className="guide-card">
              <p>
                بیایید با هم یک فرایند واقعی را قدم‌به‌قدم در سیستم ثبت کنیم.
                فرض کنید فرایند «مرخصی آموزشی موقت» را به‌صورت سنتی اینگونه اجرا می‌کنید:
              </p>

              <div className="guide-callout warning">
                <div className="guide-callout-icon">📝</div>
                <div>
                  <strong>فرایند سنتی:</strong>
                  <ol>
                    <li>دانشجو فرم درخواست مرخصی را پر می‌کند و تحویل می‌دهد</li>
                    <li>کمیته پیشرفت درخواست را بررسی می‌کند</li>
                    <li>کمیته جلسه‌ای تنظیم و برگزار می‌کند</li>
                    <li>در جلسه تصمیم‌گیری می‌شود: تایید یا رد</li>
                    <li>اگر تایید شد، ثبت‌نام کلاس‌ها معلق می‌شود</li>
                    <li>نزدیک پایان مرخصی، به دانشجو یادآوری بازگشت داده می‌شود</li>
                    <li>اگر دانشجو بازنگشت، تخلف ثبت می‌شود</li>
                  </ol>
                </div>
              </div>

              <h3>مرحله ۱: ایجاد فرایند</h3>
              <div className="guide-example-box">
                <div className="guide-example-row">
                  <span className="guide-example-label">کد فرایند:</span>
                  <code>educational_leave</code>
                </div>
                <div className="guide-example-row">
                  <span className="guide-example-label">نام فارسی:</span>
                  <span>مرخصی آموزشی موقت از ثبت‌نام در کلاس‌ها</span>
                </div>
                <div className="guide-example-row">
                  <span className="guide-example-label">توضیحات:</span>
                  <span>فرایند درخواست و مدیریت مرخصی آموزشی موقت دانشجویان</span>
                </div>
                <div className="guide-example-row">
                  <span className="guide-example-label">وضعیت شروع:</span>
                  <code>request_form</code>
                </div>
              </div>

              <h3>مرحله ۲: تعریف وضعیت‌ها</h3>
              <div className="guide-field-table">
                <table>
                  <thead>
                    <tr><th>کد</th><th>نام فارسی</th><th>نوع</th><th>نقش مسئول</th><th>SLA</th></tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td><code>request_form</code></td>
                      <td>ثبت درخواست اولیه</td>
                      <td><span className="badge badge-success">شروع</span></td>
                      <td>student</td>
                      <td>-</td>
                    </tr>
                    <tr>
                      <td><code>committee_review</code></td>
                      <td>بررسی کمیته پیشرفت</td>
                      <td><span className="badge badge-info">میانی</span></td>
                      <td>progress_committee</td>
                      <td>168 ساعت</td>
                    </tr>
                    <tr>
                      <td><code>session_scheduled</code></td>
                      <td>جلسه تنظیم شد</td>
                      <td><span className="badge badge-info">میانی</span></td>
                      <td>progress_committee</td>
                      <td>-</td>
                    </tr>
                    <tr>
                      <td><code>committee_decision</code></td>
                      <td>تصمیم‌گیری کمیته</td>
                      <td><span className="badge badge-info">میانی</span></td>
                      <td>progress_committee</td>
                      <td>-</td>
                    </tr>
                    <tr>
                      <td><code>on_leave</code></td>
                      <td>در وقفه تحصیلی</td>
                      <td><span className="badge badge-info">میانی</span></td>
                      <td>system</td>
                      <td>-</td>
                    </tr>
                    <tr>
                      <td><code>return_reminder_sent</code></td>
                      <td>یادآوری بازگشت ارسال شد</td>
                      <td><span className="badge badge-info">میانی</span></td>
                      <td>system</td>
                      <td>336 ساعت</td>
                    </tr>
                    <tr>
                      <td><code>rejected</code></td>
                      <td>رد درخواست</td>
                      <td><span className="badge badge-danger">پایانی</span></td>
                      <td>system</td>
                      <td>-</td>
                    </tr>
                    <tr>
                      <td><code>returned</code></td>
                      <td>بازگشت به تحصیل</td>
                      <td><span className="badge badge-danger">پایانی</span></td>
                      <td>system</td>
                      <td>-</td>
                    </tr>
                    <tr>
                      <td><code>violation_registered</code></td>
                      <td>ثبت تخلف عدم بازگشت</td>
                      <td><span className="badge badge-danger">پایانی</span></td>
                      <td>system</td>
                      <td>-</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <h3>مرحله ۳: تعریف انتقال‌ها</h3>
              <div className="guide-field-table">
                <table>
                  <thead>
                    <tr><th>از</th><th></th><th>به</th><th>رویداد</th><th>نقش</th></tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td><span className="badge badge-success">request_form</span></td>
                      <td>→</td>
                      <td><span className="badge badge-info">committee_review</span></td>
                      <td><code>student_submitted</code></td>
                      <td>student</td>
                    </tr>
                    <tr>
                      <td><span className="badge badge-info">committee_review</span></td>
                      <td>→</td>
                      <td><span className="badge badge-info">session_scheduled</span></td>
                      <td><code>committee_set_meeting</code></td>
                      <td>progress_committee</td>
                    </tr>
                    <tr>
                      <td><span className="badge badge-info">session_scheduled</span></td>
                      <td>→</td>
                      <td><span className="badge badge-info">committee_decision</span></td>
                      <td><code>meeting_held</code></td>
                      <td>progress_committee</td>
                    </tr>
                    <tr>
                      <td><span className="badge badge-info">committee_decision</span></td>
                      <td>→</td>
                      <td><span className="badge badge-danger">rejected</span></td>
                      <td><code>committee_rejected</code></td>
                      <td>progress_committee</td>
                    </tr>
                    <tr>
                      <td><span className="badge badge-info">committee_decision</span></td>
                      <td>→</td>
                      <td><span className="badge badge-info">on_leave</span></td>
                      <td><code>committee_approved</code></td>
                      <td>progress_committee</td>
                    </tr>
                    <tr>
                      <td><span className="badge badge-info">on_leave</span></td>
                      <td>→</td>
                      <td><span className="badge badge-info">return_reminder_sent</span></td>
                      <td><code>send_return_reminder</code></td>
                      <td>system</td>
                    </tr>
                    <tr>
                      <td><span className="badge badge-info">return_reminder_sent</span></td>
                      <td>→</td>
                      <td><span className="badge badge-danger">returned</span></td>
                      <td><code>student_returned</code></td>
                      <td>-</td>
                    </tr>
                    <tr>
                      <td><span className="badge badge-info">return_reminder_sent</span></td>
                      <td>→</td>
                      <td><span className="badge badge-danger">violation_registered</span></td>
                      <td><code>return_deadline_passed</code></td>
                      <td>system</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="guide-callout success">
                <div className="guide-callout-icon">🎉</div>
                <div>
                  <strong>تبریک!</strong> شما با موفقیت یک فرایند کامل را در سیستم تعریف کردید.
                  اکنون سیستم می‌تواند مرخصی آموزشی دانشجویان را به‌صورت خودکار مدیریت کند.
                </div>
              </div>
            </div>
          </section>
          )}

          {/* ────────────── واژه‌نامه ────────────── */}
          <section id="glossary" className="guide-section">
            <div className="guide-section-header">
              <span className="guide-section-icon">📚</span>
              <h2>واژه‌نامه</h2>
            </div>
            <div className="guide-card">
              <div className="guide-glossary">
                <div className="guide-glossary-item">
                  <dt>فرایند (Process)</dt>
                  <dd>مجموعه‌ای مرتب از مراحل برای انجام یک کار. مثلاً «آغاز درمان آموزشی».</dd>
                </div>
                <div className="guide-glossary-item">
                  <dt>وضعیت (State)</dt>
                  <dd>هر مرحله از فرایند. مثلاً «در انتظار بررسی» یا «تایید شده».</dd>
                </div>
                <div className="guide-glossary-item">
                  <dt>انتقال (Transition)</dt>
                  <dd>حرکت از یک وضعیت به وضعیت دیگر. با یک رویداد محرک فعال می‌شود.</dd>
                </div>
                <div className="guide-glossary-item">
                  <dt>رویداد محرک (Trigger Event)</dt>
                  <dd>عملی که باعث حرکت فرایند از یک وضعیت به وضعیت دیگر می‌شود. مثلاً «تایید کمیته».</dd>
                </div>
                <div className="guide-glossary-item">
                  <dt>قانون (Rule)</dt>
                  <dd>شرطی که قبل از اجرای انتقال بررسی می‌شود. مثلاً «دانشجو حداقل ۳ ترم گذرانده باشد».</dd>
                </div>
                <div className="guide-glossary-item">
                  <dt>نقش (Role)</dt>
                  <dd>سمت یا مسئولیت یک کاربر در سیستم. مثلاً student، therapist، admin.</dd>
                </div>
                <div className="guide-glossary-item">
                  <dt>عملیات (Action)</dt>
                  <dd>کاری که بعد از انتقال به‌صورت خودکار انجام می‌شود. مثلاً ارسال پیامک.</dd>
                </div>
                <div className="guide-glossary-item">
                  <dt>نمونه فرایند (Process Instance)</dt>
                  <dd>یک اجرای مشخص از فرایند برای یک دانشجوی خاص. مثلاً «مرخصی احمد رضایی».</dd>
                </div>
                <div className="guide-glossary-item">
                  <dt>SLA (سطح خدمت)</dt>
                  <dd>حداکثر زمان مجاز برای یک مرحله. اگر از این زمان بگذرد، سیستم هشدار می‌دهد.</dd>
                </div>
                <div className="guide-glossary-item">
                  <dt>متادیتا (Metadata)</dt>
                  <dd>اطلاعات ساختاری سیستم: تعریف فرایندها، وضعیت‌ها، انتقال‌ها و قوانین.</dd>
                </div>
                <div className="guide-glossary-item">
                  <dt>حسابرسی (Audit)</dt>
                  <dd>ثبت تاریخچه تمام عملیات سیستم به‌صورت غیرقابل تغییر برای بررسی و پاسخگویی.</dd>
                </div>
              </div>
            </div>
          </section>

          {/* ────────────── سوالات متداول ────────────── */}
          <section id="faq" className="guide-section">
            <div className="guide-section-header">
              <span className="guide-section-icon">❓</span>
              <h2>سوالات متداول</h2>
            </div>
            <div className="guide-card">
              <FaqItem
                question="آیا برای استفاده از سامانه باید برنامه‌نویسی بلد باشم؟"
                answer="خیر. سامانه طوری طراحی شده که فقط با دانستن فرایندهای کاری‌تان بتوانید آن‌ها را تعریف کنید. تنها بخشی که ممکن است کمی فنی به نظر برسد، تعریف قوانین (Rules) است که با کمی تمرین بسیار ساده می‌شود."
              />
              <FaqItem
                question="آیا می‌توانم فرایندی را بعد از ساخت ویرایش کنم؟"
                answer="بله! می‌توانید هر زمان وضعیت‌ها و انتقال‌های جدید اضافه کنید. سیستم نسخه‌گذاری (versioning) دارد، بنابراین تغییرات شما ثبت و قابل پیگیری هستند."
              />
              <FaqItem
                question="اگر فرایندی در حال اجرا باشد و تعریف فرایند را تغییر دهم چه می‌شود؟"
                answer="فرایندهایی که قبلاً شروع شده‌اند با نسخه قبلی تعریف ادامه پیدا می‌کنند. فقط فرایندهای جدید از نسخه جدید استفاده خواهند کرد."
              />
              <FaqItem
                question="آیا داده‌ها قابل حذف هستند؟"
                answer="اطلاعات حسابرسی (Audit) غیرقابل حذف هستند. سایر اطلاعات توسط مدیر سیستم قابل مدیریت هستند."
              />
              <FaqItem
                question="چند فرایند می‌توانم تعریف کنم؟"
                answer="محدودیتی وجود ندارد. هر تعداد فرایند که نیاز دارید می‌توانید تعریف کنید."
              />
              <FaqItem
                question="آیا یک دانشجو می‌تواند همزمان در چند فرایند باشد؟"
                answer="بله! یک دانشجو می‌تواند همزمان در فرایندهای مختلف (مثلاً آغاز درمان و حضور و غیاب) شرکت داشته باشد. در صفحه «ردیابی دانشجو» تمام فرایندهای فعال هر دانشجو قابل مشاهده است."
              />
              <FaqItem
                question="SLA چیست و چرا مهم است؟"
                answer="SLA (Service Level Agreement) یا سطح خدمت، حداکثر زمان مجاز برای یک مرحله است. مثلاً اگر SLA مرحله «بررسی کمیته» ۱۶۸ ساعت (یک هفته) باشد و کمیته در این مدت اقدام نکند، سیستم هشدار می‌دهد. این ابزار به شما کمک می‌کند تاخیرها را شناسایی و مدیریت کنید."
              />
              <FaqItem
                question="آیا سیستم پیامک ارسال می‌کند؟"
                answer="بله! می‌توانید در تعریف انتقال‌ها عملیات «ارسال پیامک» یا «ارسال ایمیل» تعریف کنید تا سیستم به‌صورت خودکار اطلاع‌رسانی کند."
              />
              <FaqItem
                question="ورود به سامانه چگونه است؟"
                answer="ورود عادی با شماره موبایل و کد یکبار مصرف پیامکی است. برای برخی کاربران پرسنلی، ورود با نام کاربری و رمز عبور و در صورت نیاز پاسخ به چالش امنیتی نیز فعال است."
              />
            </div>
          </section>

        </div>
      </div>
    </div>
  )
}

function FaqItem({ question, answer }) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="guide-faq-item" onClick={() => setIsOpen(!isOpen)}>
      <div className="guide-faq-question">
        <span>{question}</span>
        <span className="guide-faq-toggle">{isOpen ? '−' : '+'}</span>
      </div>
      {isOpen && (
        <div className="guide-faq-answer">{answer}</div>
      )}
    </div>
  )
}
