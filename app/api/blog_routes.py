"""Blog/Articles API routes."""

import uuid
import re
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.operational_models import BlogPost, User
from app.api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/blog", tags=["Blog"])


class BlogPostCreate(BaseModel):
    title: str
    summary: Optional[str] = None
    content: str
    category: Optional[str] = "article"
    tags: Optional[str] = None
    featured_image: Optional[str] = None
    is_published: bool = False


class BlogPostUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    featured_image: Optional[str] = None
    is_published: Optional[bool] = None


def _slugify(text: str) -> str:
    slug = re.sub(r'[^\w\s\u0600-\u06FF-]', '', text)
    slug = re.sub(r'[\s_]+', '-', slug).strip('-')
    return slug[:200] or str(uuid.uuid4())[:8]


# ─── Public endpoints ───────────────────────────────────────────

@router.get("/posts")
async def list_posts(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List published blog posts (public)."""
    query = select(BlogPost).where(BlogPost.is_published == True)
    if category:
        query = query.where(BlogPost.category == category)
    query = query.order_by(BlogPost.published_at.desc())

    count_q = select(func.count(BlogPost.id)).where(BlogPost.is_published == True)
    if category:
        count_q = count_q.where(BlogPost.category == category)
    total = (await db.execute(count_q)).scalar() or 0

    offset = (page - 1) * limit
    result = await db.execute(query.offset(offset).limit(limit))
    posts = result.scalars().all()

    return {
        "posts": [
            {
                "id": str(p.id),
                "title": p.title,
                "slug": p.slug,
                "summary": p.summary,
                "category": p.category,
                "tags": p.tags,
                "featured_image": p.featured_image,
                "views": p.views,
                "published_at": p.published_at.isoformat() if p.published_at else None,
            }
            for p in posts
        ],
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit if total else 1,
    }


@router.get("/posts/{slug}")
async def get_post(slug: str, db: AsyncSession = Depends(get_db)):
    """Get a single published blog post by slug (public)."""
    result = await db.execute(
        select(BlogPost).where(and_(BlogPost.slug == slug, BlogPost.is_published == True))
    )
    post = result.scalars().first()
    if not post:
        raise HTTPException(status_code=404, detail="مقاله یافت نشد")

    post.views = (post.views or 0) + 1
    await db.commit()

    author_name = None
    if post.author_id:
        ar = await db.execute(select(User.full_name_fa).where(User.id == post.author_id))
        author_name = ar.scalar()

    return {
        "id": str(post.id),
        "title": post.title,
        "slug": post.slug,
        "summary": post.summary,
        "content": post.content,
        "category": post.category,
        "tags": post.tags,
        "featured_image": post.featured_image,
        "author": author_name,
        "views": post.views,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "created_at": post.created_at.isoformat() if post.created_at else None,
    }


# ─── Admin endpoints ────────────────────────────────────────────

@router.get("/admin/posts")
async def admin_list_posts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """List all posts including drafts (admin)."""
    total = (await db.execute(select(func.count(BlogPost.id)))).scalar() or 0
    offset = (page - 1) * limit
    result = await db.execute(
        select(BlogPost).order_by(BlogPost.created_at.desc()).offset(offset).limit(limit)
    )
    posts = result.scalars().all()

    return {
        "posts": [
            {
                "id": str(p.id),
                "title": p.title,
                "slug": p.slug,
                "summary": p.summary,
                "category": p.category,
                "is_published": p.is_published,
                "views": p.views,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "published_at": p.published_at.isoformat() if p.published_at else None,
            }
            for p in posts
        ],
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit if total else 1,
    }


@router.post("/admin/posts")
async def create_post(
    data: BlogPostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """Create a new blog post (admin)."""
    slug = _slugify(data.title) + "-" + str(uuid.uuid4())[:6]
    now = datetime.now(timezone.utc)
    post = BlogPost(
        id=uuid.uuid4(),
        title=data.title,
        slug=slug,
        summary=data.summary,
        content=data.content,
        category=data.category or "article",
        tags=data.tags,
        featured_image=data.featured_image,
        author_id=current_user.id,
        is_published=data.is_published,
        published_at=now if data.is_published else None,
    )
    db.add(post)
    await db.commit()
    return {"id": str(post.id), "slug": post.slug, "message": "مقاله ایجاد شد."}


@router.patch("/admin/posts/{post_id}")
async def update_post(
    post_id: str,
    data: BlogPostUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """Update a blog post (admin)."""
    result = await db.execute(select(BlogPost).where(BlogPost.id == uuid.UUID(post_id)))
    post = result.scalars().first()
    if not post:
        raise HTTPException(status_code=404, detail="مقاله یافت نشد")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(post, field, value)

    if data.is_published and not post.published_at:
        post.published_at = datetime.now(timezone.utc)

    await db.commit()
    return {"message": "مقاله به‌روزرسانی شد."}


@router.delete("/admin/posts/{post_id}")
async def delete_post(
    post_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Delete a blog post (admin only)."""
    result = await db.execute(select(BlogPost).where(BlogPost.id == uuid.UUID(post_id)))
    post = result.scalars().first()
    if not post:
        raise HTTPException(status_code=404, detail="مقاله یافت نشد")
    await db.delete(post)
    await db.commit()
    return {"message": "مقاله حذف شد."}
