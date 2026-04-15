import React, { useState } from 'react'
import { Link } from 'react-router-dom'

const GUIDE_SECTIONS = [
  {
    title: 'ثبت‌نام در سامانه',
    icon: '📝',
    steps: [
      { title: 'ورود به صفحه ثبت‌نام', desc: 'از منوی بالای سایت گزینه «ثبت‌نام» را انتخاب کنید.' },
      { title: 'تکمیل فرم', desc: 'اطلاعات شخصی، تحصیلی و شماره تماس خود را وارد نمایید.' },
      { title: 'ارسال فرم', desc: 'پس از بررسی اطلاعات، دکمه ارسال را بزنید. کد پیگیری یا دانشجویی دریافت خواهید کرد.' },
      { title: 'انتظار بررسی', desc: 'کارشناسان انستیتو مدارک شما را بررسی و نتیجه را از طریق پیامک اطلاع‌رسانی می‌کنند.' },
    ],
  },
  {
    title: 'ورود به سامانه',
    icon: '🔐',
    steps: [
      { title: 'وارد صفحه ورود شوید', desc: 'از منوی سایت گزینه «ورود» را انتخاب کنید.' },
      { title: 'شماره موبایل', desc: 'شماره‌ای که در پرونده ثبت شده را وارد کنید (پیش‌فرض: ورود با کد یکبار مصرف پیامکی).' },
      { title: 'کد یکبار مصرف', desc: 'کد ۶ رقمی به موبایل شما ارسال می‌شود؛ آن را وارد و تأیید کنید.' },
      { title: 'ورود به پنل', desc: 'پس از تأیید، بسته به نقش شما به داشبورد یا پنل تخصصی (مثلاً دانشجو) هدایت می‌شوید.' },
    ],
  },
  {
    title: 'پیگیری فرآیندها',
    icon: '📊',
    steps: [
      { title: 'داشبورد و مسیر فعلی', desc: 'پس از ورود، کارت مسیر تحصیلی و وضعیت کلی پرونده را در پنل دانشجو ببینید.' },
      { title: 'تب فرآیندها', desc: 'فرآیندهای مجاز را شروع یا ادامه دهید؛ مرحله فعلی، فرم‌های مرحله‌ای و «راهنمای قدم بعد» نمایش داده می‌شود.' },
      { title: 'جلسات و تکالیف', desc: 'در تب‌های مربوطه می‌توانید جلسات درمان و تکالیف/ارجاع‌ها را پیگیری کنید.' },
      { title: 'مسیر آموزشی (گام‌افزاری)', desc: 'پیشرفت انگیزشی و امتیاز مسیر آموزشی در بخش اختصاصی پنل قابل مشاهده است.' },
      { title: 'اقدام لازم', desc: 'هر جا اقدامی از شما لازم باشد (مدرک، پرداخت، تأیید فرم) در همان پنل اعلام می‌شود.' },
    ],
  },
  {
    title: 'آشنایی با فرآیندها',
    icon: '📋',
    steps: [
      { title: 'صفحه «فرآیندها»', desc: 'از منوی سایت وارد صفحه «فرآیندها» شوید تا فهرست فرآیندهای فعال سامانه و مراحل هر کدام را ببینید.' },
      { title: 'هم‌راستایی با پنل', desc: 'همان فرآیندها پس از پذیرش در پنل دانشجو قابل شروع یا پیگیری هستند؛ قفل بودن برخی درخواست‌ها به مرحلهٔ مسیر شما بستگی دارد.' },
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
    a: 'بله، شرایط انصراف و استرداد شهریه بر اساس آیین‌نامه انستیتو و مرحله‌ای که در آن هستید متفاوت است.',
  },
  {
    q: 'اگر رمز عبور یا دسترسی خود را فراموش کنم چه کنم؟',
    a: 'برای اکثر کاربران ورود با شماره موبایل و کد یکبار مصرف پیامکی است؛ کد تازه درخواست کنید. کاربران پرسنلی که ورود با نام کاربری و رمز دارند، از مسیر «ورود با رمز عبور» و در صورت نیاز پشتیبانی انستیتو کمک بگیرند.',
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
        <p>
          آموزش گام‌به‌گام ورود با پیامک، پنل دانشجو و پیگیری فرآیندها.
          برای نمای کلی مراحل و نقش‌ها، صفحه{' '}
          <Link to="/student-lifecycle">مسیر تحصیلی و نقش‌ها</Link>
          {' '}را ببینید.
        </p>
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
          <p>با تکمیل فرم ثبت‌نام، اولین قدم را بردارید — یا پیش از آن نمای کلی مسیر را ببینید</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', justifyContent: 'center' }}>
            <Link to="/register" className="pub-cta-btn">
              شروع ثبت‌نام
            </Link>
            <Link to="/student-lifecycle" className="pub-cta-btn" style={{ background: 'transparent', border: '2px solid currentColor' }}>
              مسیر تحصیلی و نقش‌ها
            </Link>
          </div>
        </div>
      </section>
    </>
  )
}
