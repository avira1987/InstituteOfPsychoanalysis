import React, { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { blogApi } from '../../services/api'

const CATEGORY_LABELS = {
  news: 'اخبار',
  article: 'مقاله',
  tutorial: 'آموزشی',
  announcement: 'اطلاعیه',
}

export default function BlogPost() {
  const { slug } = useParams()
  const [post, setPost] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    setLoading(true)
    blogApi.get(slug)
      .then(r => setPost(r.data))
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [slug])

  const formatDate = (iso) => {
    if (!iso) return ''
    try {
      return new Date(iso).toLocaleDateString('fa-IR', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    } catch {
      return iso.split('T')[0]
    }
  }

  if (loading) {
    return (
      <>
        <div className="pub-page-header">
          <h1>در حال بارگذاری...</h1>
        </div>
        <div style={{ textAlign: 'center', padding: '3rem' }}>
          <div className="loading-spinner" style={{ margin: '0 auto' }} />
        </div>
      </>
    )
  }

  if (error || !post) {
    return (
      <>
        <div className="pub-page-header">
          <h1>مقاله یافت نشد</h1>
          <p>متأسفانه مقاله مورد نظر پیدا نشد.</p>
        </div>
        <div style={{ textAlign: 'center', padding: '3rem' }}>
          <Link to="/blog" className="btn btn-primary">
            بازگشت به لیست مقالات
          </Link>
        </div>
      </>
    )
  }

  return (
    <>
      <div className="pub-page-header">
        <div style={{ marginBottom: '0.75rem' }}>
          {post.category && (
            <span className="pub-blog-category" style={{ fontSize: '0.82rem' }}>
              {CATEGORY_LABELS[post.category] || post.category}
            </span>
          )}
        </div>
        <h1>{post.title}</h1>
        <p style={{ marginTop: '0.75rem' }}>
          {post.author && <span>{post.author} &bull; </span>}
          {formatDate(post.published_at)}
          {post.views > 0 && <span> &bull; {post.views} بازدید</span>}
        </p>
      </div>

      <div className="pub-post-content">
        {post.summary && (
          <div style={{
            background: 'var(--primary-light)',
            padding: '1.25rem',
            borderRadius: 'var(--radius-lg)',
            marginBottom: '2rem',
            fontWeight: 500,
            lineHeight: '1.9'
          }}>
            {post.summary}
          </div>
        )}

        <div
          dangerouslySetInnerHTML={{ __html: post.content }}
          style={{ whiteSpace: 'pre-wrap' }}
        />

        {post.tags && (
          <div style={{ marginTop: '2rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border)' }}>
            <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>برچسب‌ها: </span>
            {post.tags.split(',').map((tag, i) => (
              <span key={i} className="badge badge-info" style={{ marginLeft: '0.5rem' }}>
                {tag.trim()}
              </span>
            ))}
          </div>
        )}

        <div style={{ marginTop: '2rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border)', textAlign: 'center' }}>
          <Link to="/blog" className="btn btn-outline">
            ← بازگشت به لیست مقالات
          </Link>
        </div>
      </div>
    </>
  )
}
