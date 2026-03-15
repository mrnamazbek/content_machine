"""
PostgreSQL database helper — connection pool and CRUD operations.
"""

import psycopg2
import psycopg2.pool
import psycopg2.extras
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
from loguru import logger

from config.settings import settings


class Database:
    """Manages a PostgreSQL connection pool and provides CRUD helpers."""

    def __init__(self):
        self._pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None

    def connect(self):
        """Initialize the connection pool."""
        try:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=10,
                dsn=settings.database_url,
            )
            logger.info("Database connection pool created")
        except psycopg2.Error as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise

    def close(self):
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()
            logger.info("Database connection pool closed")

    @contextmanager
    def get_cursor(self, commit: bool = True):
        """Context manager yielding a cursor with auto-commit/rollback."""
        conn = self._pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            yield cursor
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            self._pool.putconn(conn)

    # ── Trends ────────────────────────────────────

    def save_trend(self, niche: str, hashtags: list, topic_ideas: list,
                   viral_hooks: list, source: str = "perplexity") -> int:
        with self.get_cursor() as cur:
            cur.execute(
                """INSERT INTO trends (niche, hashtags, topic_ideas, viral_hooks, source)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (niche, hashtags, topic_ideas, viral_hooks, source),
            )
            return cur.fetchone()["id"]

    # ── Videos ────────────────────────────────────

    def save_video(self, source_url: str, source_platform: str,
                   title: str = "", original_views: int = 0,
                   original_likes: int = 0, duration: float = 0,
                   hashtags: list = None, niche: str = "") -> Optional[int]:
        """Insert a discovered video. Returns None if duplicate."""
        try:
            with self.get_cursor() as cur:
                cur.execute(
                    """INSERT INTO videos
                       (source_url, source_platform, title, original_views,
                        original_likes, duration, hashtags, niche, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'discovered')
                       ON CONFLICT (source_url) DO NOTHING
                       RETURNING id""",
                    (source_url, source_platform, title, original_views,
                     original_likes, duration, hashtags or [], niche),
                )
                row = cur.fetchone()
                return row["id"] if row else None
        except psycopg2.Error as e:
            logger.error(f"Error saving video: {e}")
            return None

    def update_video_status(self, video_id: int, status: str, **kwargs):
        """Update video status and optional fields."""
        set_clauses = ["status = %s"]
        values = [status]
        for key, val in kwargs.items():
            set_clauses.append(f"{key} = %s")
            values.append(val)
        values.append(video_id)

        with self.get_cursor() as cur:
            cur.execute(
                f"UPDATE videos SET {', '.join(set_clauses)} WHERE id = %s",
                values,
            )

    def get_videos_by_status(self, status: str, limit: int = 10) -> List[Dict]:
        with self.get_cursor(commit=False) as cur:
            cur.execute(
                "SELECT * FROM videos WHERE status = %s ORDER BY created_at LIMIT %s",
                (status, limit),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_video_by_id(self, video_id: int) -> Optional[Dict]:
        with self.get_cursor(commit=False) as cur:
            cur.execute("SELECT * FROM videos WHERE id = %s", (video_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    # ── Captions ──────────────────────────────────

    def save_caption(self, video_id: int, caption: str, hashtags: list,
                     tone: str = "confident masculine",
                     provider: str = "openai", model: str = "") -> int:
        with self.get_cursor() as cur:
            cur.execute(
                """INSERT INTO captions (video_id, caption, hashtags, tone, provider, model)
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                (video_id, caption, hashtags, tone, provider, model),
            )
            return cur.fetchone()["id"]

    # ── Uploads ───────────────────────────────────

    def save_upload(self, video_id: int, caption_id: int, platform: str,
                    method: str = "playwright") -> int:
        with self.get_cursor() as cur:
            cur.execute(
                """INSERT INTO uploads (video_id, caption_id, platform, method, status)
                   VALUES (%s, %s, %s, %s, 'pending') RETURNING id""",
                (video_id, caption_id, platform, method),
            )
            return cur.fetchone()["id"]

    def update_upload_status(self, upload_id: int, status: str,
                             post_url: str = None, error_message: str = None):
        with self.get_cursor() as cur:
            cur.execute(
                """UPDATE uploads
                   SET status = %s, post_url = %s, error_message = %s,
                       posted_at = CASE WHEN %s = 'posted' THEN NOW() ELSE posted_at END
                   WHERE id = %s""",
                (status, post_url, error_message, status, upload_id),
            )

    # ── Analytics ─────────────────────────────────

    def save_analytics(self, upload_id: int, views: int = 0, likes: int = 0,
                       comments: int = 0, shares: int = 0) -> int:
        with self.get_cursor() as cur:
            cur.execute(
                """INSERT INTO analytics (upload_id, views, likes, comments, shares)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (upload_id, views, likes, comments, shares),
            )
            return cur.fetchone()["id"]

    def get_top_performing(self, days: int = 7, limit: int = 20) -> List[Dict]:
        """Get top performing posts from recent analytics data."""
        with self.get_cursor(commit=False) as cur:
            cur.execute(
                """SELECT u.id as upload_id, u.platform, u.post_url,
                          v.niche, v.source_url,
                          c.caption, c.hashtags as caption_hashtags,
                          a.views, a.likes, a.comments, a.shares,
                          a.collected_at
                   FROM analytics a
                   JOIN uploads u ON a.upload_id = u.id
                   JOIN videos v ON u.video_id = v.id
                   LEFT JOIN captions c ON u.caption_id = c.id
                   WHERE a.collected_at > NOW() - INTERVAL '%s days'
                   ORDER BY a.views DESC
                   LIMIT %s""",
                (days, limit),
            )
            return [dict(row) for row in cur.fetchall()]

    # ── Strategy Reports ──────────────────────────

    def save_strategy_report(self, report_text: str, best_topics: list,
                             best_times: list, best_styles: list,
                             provider: str = "openai", model: str = "") -> int:
        with self.get_cursor() as cur:
            cur.execute(
                """INSERT INTO strategy_reports
                   (report_text, best_topics, best_times, best_styles, provider, model)
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                (report_text, best_topics, best_times, best_styles, provider, model),
            )
            return cur.fetchone()["id"]


# Global database instance
db = Database()
