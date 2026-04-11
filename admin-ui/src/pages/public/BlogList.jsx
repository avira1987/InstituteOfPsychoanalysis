import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { blogApi } from '../../services/api'

const CATEGORY_LABELS = {
  news: 'اخبار',
  article: 'مقاله',
  tutorial: 'آموزشی',
  announcement: 'اطلاعیه',
}

const CATEGORY_ICONS = {
  news: '📰',
  article: '📖',
  tutorial: '🎓',
  announcement: '📢',
}

export default function BlogList() {
  const [posts, setPosts] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [category, setCategory] = useState('')

  useEffect(() => {
    setLoading(true)
    blogApi.list({ page, limit: 9, category: category || undefined })
      .then(r => {
        setPosts(r.data.posts || [])
        setTotalPages(r.data.pages || 1)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [page, category])

  const formatDate = (iso) => {
    if (!iso) return ''
    try {
      return new Date(iso).toLocaleDateString('fa-IR')
    } catch {
      return iso.split('T')[0]
    }
  }

  return (
    <>
      <div className="pub-page-header">
        <h1>مقالات و اخبار</h1>
        <p>آخرین مقالات، اخبار و اطلاعیه‌های انستیتو روانکاوی تهران</p>
      </div>

      <section className="pub-section">
        {/* Category Filter */}
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '2rem', flexWrap: 'wrap', justifyContent: 'center' }}>
          <button
            className={`pub-navbar-link ${!category ? 'active' : ''}`}
            onClick={() => { setCategory(''); setPage(1) }}
          >
            همه
          </button>
          {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
            <button
              key={key}
              className={`pub-navbar-link ${category === key ? 'active' : ''}`}
              onClick={() => { setCategory(key); setPage(1) }}
            >
              {CATEGORY_ICONS[key]} {label}
            </button>
          ))}
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '3rem' }}>
            <div className="loading-spinner" style={{ margin: '0 auto' }} />
          </div>
        ) : posts.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-secondary)' }}>
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📄</div>
            <p>هنوز مقاله‌ای منتشر نشده است.</p>
          </div>
        ) : (
          <>
            <div className="pub-blog-grid">
              {posts.map(post => (
                <Link to={`/blog/${post.slug}`} key={post.id} className="pub-blog-card">
                  <div className="pub-blog-thumb">
                    {CATEGORY_ICONS[post.category] || '📄'}
                  </div>
                  <div className="pub-blog-body">
                    <div className="pub-blog-meta">
                      {post.category && (
                        <span className="pub-blog-category">
                          {CATEGORY_LABELS[post.category] || post.category}
                        </span>
                      )}
                      <span>{formatDate(post.published_at)}</span>
                      {post.views > 0 && <span>{post.views} بازدید</span>}
                    </div>
                    <h3>{post.title}</h3>
                    {post.summary && <p>{post.summary}</p>}
                    <span className="pub-blog-read">
                      ادامه مطلب ←
                    </span>
                  </div>
                </Link>
              ))}
            </div>

            {totalPages > 1 && (
              <div className="pagination" style={{ marginTop: '2rem' }}>
                <button
                  className="btn btn-outline btn-sm"
                  disabled={page <= 1}
                  onClick={() => setPage(p => p - 1)}
                >
                  قبلی
                </button>
                <span className="pagination-info">
                  صفحه {page} از {totalPages}
                </span>
                <button
                  className="btn btn-outline btn-sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage(p => p + 1)}
                >
                  بعدی
                </button>
              </div>
            )}
          </>
        )}
      </section>
    </>
  )
}
