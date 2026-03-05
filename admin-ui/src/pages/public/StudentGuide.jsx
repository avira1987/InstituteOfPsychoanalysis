import React, { useState } from 'react'
import { Link } from 'react-router-dom'

const GUIDE_SECTIONS = [
  {
    title: 'ثبت‌نام در سامانه',
    icon: '📝',
    steps: [
      { title: 'ورود به صفحه ثبت‌نام', desc: 'از منوی بالای سایت گزینه "ثبت‌نام" را انتخاب کنید.' },
      { title: 'تکمیل فرم', desc: 'اطلاعات شخصی، تحصیلی و شماره تماس خود را وارد نمایید.' },
      { title: 'ارسال فرم', desc: 'پس از بررسی اطلاعات، دکمه ارسال را بزنید. کد دانشجویی دریافت خواهید کرد.' },
      { title: 'انتظار بررسی', desc: 'کارشناسان انیستیتو مدارک شما را بررسی و نتیجه را از طریق پیامک اطلاع‌رسانی می‌کنند.' },
    ],
  },
  {
    title: 'ورود به سامانه',
    icon: '🔐',
    steps: [
      { title: 'وارد صفحه ورود شوید', desc: 'از منوی سایت گزینه "ورود" را انتخاب کنید.' },
      { title: 'شماره موبایل خود را وارد کنید', desc: 'شماره‌ای که هنگام ثبت‌نام وارد کرده‌اید.' },
      { title: 'کد یکبار مصرف', desc: 'یک کد ۶ رقمی به موبایل شما ارسال می‌شود. آن را وارد کنید.' },
      { title: 'ورود به پنل', desc: 'پس از تأیید کد، به پنل دانشجویی خود هدایت خواهید شد.' },
    ],
  },
  {
    title: 'پیگیری فرآیندها',
    icon: '📊',
    steps: [
      { title: 'داشبورد دانشجو', desc: 'پس از ورود، در داشبورد وضعیت کلی پرونده خود را ببینید.' },
      { title: 'مشاهده فرآیندهای فعال', desc: 'فرآیندهای در حال اجرا و مرحله فعلی هر کدام نمایش داده می‌شود.' },
      { title: 'تاریخچه', desc: 'تمام تغییرات و مراحل طی شده به صورت تاریخچه قابل مشاهده است.' },
      { title: 'اقدامات مورد نیاز', desc: 'اگر اقدامی از شما نیاز باشد (ارسال مدرک، پرداخت و ...) در پنل نمایش داده می‌شود.' },
    ],
  },
]

const FAQ_ITEMS = [
  {
    q: 'آیا ثبت‌نام آنلاین کافی است یا حضوری هم لازم است؟',
    a: 'ثبت‌نام اولیه به صورت آنلاین انجام می‌شود. پس از بررسی مدارک، در صورت تأیید اولیه، برای مصاحبه حضوری دعوت خواهید شد.',
  },
  {
    q: 'چگونه از وضعیت ثبت‌نام خود مطلع شوم؟',
    a: 'پس از بررسی مدارک، نتیجه از طریق پیامک به شماره موبایل ثبت شده اطلاع‌رسانی می‌شود. همچنین می‌توانید با ورود به سامانه، وضعیت پرونده خود را پیگیری کنید.',
  },
  {
    q: 'هزینه ثبت‌نام و شهریه چقدر است؟',
    a: 'هزینه‌ها بسته به نوع دوره (مقدماتی یا جامع) متفاوت است. اطلاعات دقیق هزینه‌ها پس از تأیید پذیرش ارائه خواهد شد.',
  },
  {
    q: 'آیا امکان انصراف پس از ثبت‌نام وجود دارد؟',
    a: 'بله، شرایط انصراف و استرداد شهریه بر اساس آیین‌نامه انیستیتو و مرحله‌ای که در آن هستید متفاوت است.',
  },
  {
    q: 'اگر رمز عبور یا دسترسی خود را فراموش کنم چه کنم؟',
    a: 'سامانه از سیستم ورود با کد یکبار مصرف پیامکی استفاده می‌کند. کافی است شماره موبایل خود را وارد کنید تا کد جدید دریافت نمایید.',
  },
  {
    q: 'آیا امکان تغییر نوع دوره پس از ثبت‌نام وجود دارد؟',
    a: 'بله، تغییر نوع دوره با تأیید کمیته آموزشی امکان‌پذیر است. درخواست خود را از طریق پنل دانشجویی ثبت کنید.',
  },
]

export default function StudentGuide() {
  const [openFaq, setOpenFaq] = useState(null)

  return (
    <>
      <div className="pub-page-header">
        <h1>راهنمای استفاده از سامانه</h1>
        <p>آموزش گام‌به‌گام نحوه استفاده از سامانه اتوماسیون آموزشی</p>
      </div>

      {/* ─── Guide Sections ─── */}
      {GUIDE_SECTIONS.map((section, sIdx) => (
        <section key={sIdx} className="pub-section" style={{ paddingBottom: sIdx < GUIDE_SECTIONS.length - 1 ? '1rem' : undefined }}>
          <div className="pub-section-header">
            <div className="pub-section-badge">{section.icon} {section.title}</div>
            <h2>{section.title}</h2>
          </div>

          <div className="pub-steps">
            {section.steps.map((step, idx) => (
              <div key={idx} className="pub-step">
                <div className="pub-step-num">{idx + 1}</div>
                <div className="pub-step-content">
                  <h3>{step.title}</h3>
                  <p>{step.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}

      {/* ─── FAQ ─── */}
      <section className="pub-section" style={{ paddingTop: '1rem' }}>
        <div className="pub-section-header">
          <div className="pub-section-badge">سوالات متداول</div>
          <h2>پرسش‌های رایج</h2>
          <p>پاسخ سوالات متداول دانشجویان</p>
        </div>

        <div className="pub-faq-list">
          {FAQ_ITEMS.map((item, idx) => (
            <div
              key={idx}
              className={`pub-faq-item ${openFaq === idx ? 'open' : ''}`}
            >
              <button
                className="pub-faq-q"
                onClick={() => setOpenFaq(openFaq === idx ? null : idx)}
              >
                {item.q}
                <span className="pub-faq-icon">+</span>
              </button>
              {openFaq === idx && (
                <div className="pub-faq-a">{item.a}</div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ─── CTA ─── */}
      <section className="pub-section" style={{ paddingTop: 0 }}>
        <div className="pub-cta">
          <h2>آماده ثبت‌نام هستید؟</h2>
          <p>با تکمیل فرم ثبت‌نام، اولین قدم را بردارید</p>
          <Link to="/register" className="pub-cta-btn">
            شروع ثبت‌نام
          </Link>
        </div>
      </section>
    </>
  )
}
