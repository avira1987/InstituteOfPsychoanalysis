import React, { useMemo } from 'react'

const XP_PER_LEVEL = 100
const MAX_LEVEL = 99

const RANK_BY_LEVEL = [
  [50, 'افسانهٔ مسیر آموزشی'],
  [35, 'استاد مسیر انیستیتو'],
  [20, 'ستارهٔ پیشرفت'],
  [12, 'پیشرو'],
  [6, 'کاوشگر مسیر'],
  [2, 'رهرو تازه‌کار'],
  [1, 'دانشجوی تازه‌کار'],
]

function rankTitleForLevel(level) {
  for (const [minLv, title] of RANK_BY_LEVEL) {
    if (level >= minLv) return title
  }
  return RANK_BY_LEVEL[RANK_BY_LEVEL.length - 1][1]
}

const BADGE_DEFS = [
  { id: 'first_spark', title_fa: 'اولین جرقه', description_fa: 'اولین قدم را در مسیر فرایند برداشتید.', emoji: '✨', check: 'xp15' },
  { id: 'bronze_trail', title_fa: 'مسیر برنزی', description_fa: 'به ۱۰۰ امتیاز تجربه رسیدید.', emoji: '🥉', check: 'xp100' },
  { id: 'silver_trail', title_fa: 'مسیر نقره‌ای', description_fa: 'به ۳۰۰ امتیاز تجربه رسیدید.', emoji: '🥈', check: 'xp300' },
  { id: 'gold_trail', title_fa: 'مسیر طلایی', description_fa: 'به ۸۰۰ امتیاز تجربه رسیدید.', emoji: '🥇', check: 'xp800' },
  { id: 'dual_path', title_fa: 'دو مسیر', description_fa: 'حداقل دو فرایند فعال یا گذشته در کارنامهٔ شما ثبت شده است.', emoji: '🔀', check: 'instances2' },
  { id: 'polyglot_process', title_fa: 'چندفراینده', description_fa: 'حداقل سه نوع فرایند مختلف را تجربه کرده‌اید.', emoji: '🎯', check: 'process3' },
  { id: 'marathon', title_fa: 'استقامت', description_fa: 'به ۱۵۰۰ امتیاز تجربه رسیدید.', emoji: '🏃', check: 'xp1500' },
]

function checkCondition(check, totalXp, instances) {
  const codes = new Set(
    Object.values(instances || {})
      .map(v => v?.process_code)
      .filter(Boolean)
  )
  const nInst = Object.keys(instances || {}).length
  switch (check) {
    case 'xp15': return totalXp >= 15
    case 'xp100': return totalXp >= 100
    case 'xp300': return totalXp >= 300
    case 'xp800': return totalXp >= 800
    case 'xp1500': return totalXp >= 1500
    case 'instances2': return nInst >= 2
    case 'process3': return codes.size >= 3
    default: return false
  }
}

/** اگر سرور هنوز gamification نفرستاده، از hidden_progress همان منطق بک‌اند را تکرار می‌کنیم. */
function computeClientSnapshot(extra) {
  const hp = extra?.hidden_progress || {}
  const totalXp = Number(hp.total_xp || 0)
  const instances = hp.instances || {}
  const level = Math.min(MAX_LEVEL, Math.max(1, 1 + Math.floor(totalXp / XP_PER_LEVEL)))
  const xpInLevel = totalXp % XP_PER_LEVEL
  const xpToNext = level < MAX_LEVEL ? XP_PER_LEVEL - xpInLevel : 0
  const rankTitle = rankTitleForLevel(level)
  const badges = BADGE_DEFS.map(bd => ({
    id: bd.id,
    title_fa: bd.title_fa,
    description_fa: bd.description_fa,
    emoji: bd.emoji,
    earned: checkCondition(bd.check, totalXp, instances),
    earned_at: null,
  }))
  const earnedCount = badges.filter(b => b.earned).length
  return {
    version: 1,
    level,
    total_xp: totalXp,
    xp_in_current_level: xpInLevel,
    xp_to_next_level: xpToNext,
    xp_per_level: XP_PER_LEVEL,
    rank_title_fa: rankTitle,
    badges,
    stats: { badges_earned: earnedCount, badges_total: badges.length },
  }
}

function resolveGamification(extra) {
  const g = extra?.gamification
  if (g && typeof g.level === 'number' && Array.isArray(g.badges)) return g
  return computeClientSnapshot(extra || {})
}

/**
 * @param {{ extraData: object | null, compact?: boolean, onOpenDetails?: () => void }} props
 */
export default function GamificationPanel({ extraData, compact = false, onOpenDetails }) {
  const snap = useMemo(() => resolveGamification(extraData), [extraData])
  const pct = snap.xp_per_level
    ? Math.min(100, Math.round((snap.xp_in_current_level / snap.xp_per_level) * 100))
    : 0

  if (compact) {
    return (
      <div className="gam-compact">
        <div className="gam-compact-main">
          <div className="gam-level-pill" aria-hidden="true">
            <span className="gam-level-num">{snap.level}</span>
            <span className="gam-level-label">سطح</span>
          </div>
          <div className="gam-compact-text">
            <div className="gam-rank-title">{snap.rank_title_fa}</div>
            <div className="gam-xp-line">
              <span>{snap.total_xp} XP</span>
              {snap.level < MAX_LEVEL && (
                <span className="gam-xp-sub">تا سطح بعد: {snap.xp_to_next_level} XP</span>
              )}
            </div>
            <div className="gam-xp-bar gam-xp-bar--sm" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
              <div className="gam-xp-bar-fill" style={{ width: `${pct}%` }} />
            </div>
          </div>
        </div>
        {onOpenDetails && (
          <button type="button" className="btn btn-secondary gam-compact-btn" onClick={onOpenDetails}>
            مدال‌ها و جزئیات
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="gam-full">
      <div className="gam-hero">
        <div className="gam-hero-glow" aria-hidden="true" />
        <div className="gam-hero-inner">
          <div className="gam-ring-wrap">
            <div
              className="gam-donut"
              style={{ background: `conic-gradient(var(--primary) ${pct}%, var(--border) 0)` }}
              aria-hidden="true"
            >
              <div className="gam-donut-hole">
                <span className="gam-ring-level">{snap.level}</span>
                <span className="gam-ring-sub">سطح</span>
              </div>
            </div>
          </div>
          <div className="gam-hero-copy">
            <h2 className="gam-hero-title">{snap.rank_title_fa}</h2>
            <p className="gam-hero-xp">
              مجموع تجربه: <strong>{snap.total_xp}</strong> XP
            </p>
            <div className="gam-xp-bar" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
              <div className="gam-xp-bar-fill" style={{ width: `${pct}%` }} />
            </div>
            <p className="gam-hero-hint">
              {snap.level >= MAX_LEVEL
                ? 'به سقف سطح رسیده‌اید — همچنان با فعالیت، مدال‌ها را کامل کنید.'
                : `پیشرفت در این سطح: ${snap.xp_in_current_level} / ${snap.xp_per_level} XP — ${snap.xp_to_next_level} XP تا سطح ${snap.level + 1}`}
            </p>
          </div>
        </div>
      </div>

      <div className="gam-stats-row">
        <div className="gam-stat-chip">
          <span className="gam-stat-val">{snap.stats?.badges_earned ?? snap.badges.filter(b => b.earned).length}</span>
          <span className="gam-stat-key">مدال بازشده</span>
        </div>
        <div className="gam-stat-chip">
          <span className="gam-stat-val">{snap.stats?.badges_total ?? snap.badges.length}</span>
          <span className="gam-stat-key">کل مدال‌ها</span>
        </div>
      </div>

      <h3 className="gam-section-title">ویترین مدال‌ها</h3>
      <p className="gam-section-desc">
        با پیشروی در فرایندها امتیاز تجربه (XP) می‌گیرید. مدال‌ها با رسیدن به آستانه‌های مشخص باز می‌شوند.
      </p>
      <div className="gam-badge-grid">
        {snap.badges.map(b => (
          <div
            key={b.id}
            className={`gam-badge-card ${b.earned ? 'gam-badge-card--earned' : 'gam-badge-card--locked'}`}
          >
            <div className="gam-badge-emoji" aria-hidden="true">{b.emoji || '⭐'}</div>
            <div className="gam-badge-title">{b.title_fa}</div>
            <div className="gam-badge-desc">{b.description_fa}</div>
            {b.earned ? (
              <span className="gam-badge-status gam-badge-status--ok">باز شده</span>
            ) : (
              <span className="gam-badge-status gam-badge-status--lock">قفل</span>
            )}
            {b.earned && b.earned_at && (
              <div className="gam-badge-date">
                {new Date(b.earned_at).toLocaleDateString('fa-IR')}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
