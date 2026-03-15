"""
Analytics Collector — scrapes performance metrics from posted videos.
"""

import time
from typing import Dict, Optional, List
from loguru import logger

from playwright.sync_api import sync_playwright

from config.settings import settings
from database.db import db


class MetricsCollector:
    """Collects analytics data from posted videos via Playwright scraping."""

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._page = None

    def start_browser(self, headless: bool = True):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=headless)
        context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        self._page = context.new_page()

    def close_browser(self):
        if self._page:
            self._page.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def collect_tiktok_metrics(self, post_url: str) -> Optional[Dict]:
        """Scrape metrics from a TikTok video page."""
        try:
            self._page.goto(post_url, wait_until="networkidle", timeout=30000)
            time.sleep(3)

            metrics = {
                "views": self._parse_metric('[data-e2e="views-count"], '
                                            '[class*="video-count"]'),
                "likes": self._parse_metric('[data-e2e="like-count"], '
                                           '[class*="like-count"]'),
                "comments": self._parse_metric('[data-e2e="comment-count"], '
                                               '[class*="comment-count"]'),
                "shares": self._parse_metric('[data-e2e="share-count"], '
                                            '[class*="share-count"]'),
            }
            logger.info(f"TikTok metrics for {post_url}: {metrics}")
            return metrics

        except Exception as e:
            logger.error(f"Failed to collect TikTok metrics for {post_url}: {e}")
            return None

    def collect_instagram_metrics(self, post_url: str) -> Optional[Dict]:
        """Scrape metrics from an Instagram post page."""
        try:
            self._page.goto(post_url, wait_until="networkidle", timeout=30000)
            time.sleep(3)

            metrics = {
                "views": self._parse_metric('span[class*="view"], '
                                            'span:has-text("views")'),
                "likes": self._parse_metric('section span[class*="like"], '
                                           'button[class*="like"] span'),
                "comments": self._parse_metric('span[class*="comment"]'),
                "shares": 0,  # Instagram doesn't show share count publicly
            }
            logger.info(f"Instagram metrics for {post_url}: {metrics}")
            return metrics

        except Exception as e:
            logger.error(f"Failed to collect Instagram metrics for {post_url}: {e}")
            return None

    def _parse_metric(self, selector: str) -> int:
        """Extract numeric value from a page element."""
        try:
            el = self._page.query_selector(selector)
            if not el:
                return 0
            text = el.text_content().strip()
            return self._text_to_number(text)
        except Exception:
            return 0

    @staticmethod
    def _text_to_number(text: str) -> int:
        """Convert text like '1.2M', '45.3K' to integers."""
        text = text.replace(",", "").strip().upper()
        multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
        for suffix, mult in multipliers.items():
            if text.endswith(suffix):
                try:
                    return int(float(text[:-1]) * mult)
                except ValueError:
                    return 0
        try:
            return int(text)
        except ValueError:
            return 0

    def collect_all(self) -> List[Dict]:
        """Collect metrics for all posted uploads that have a post_url."""
        results = []

        try:
            self.start_browser()

            # Get all 'posted' uploads with URLs
            with db.get_cursor(commit=False) as cur:
                cur.execute(
                    """SELECT id, platform, post_url
                       FROM uploads
                       WHERE status = 'posted' AND post_url IS NOT NULL
                       ORDER BY posted_at DESC
                       LIMIT 50"""
                )
                uploads = [dict(row) for row in cur.fetchall()]

            for upload in uploads:
                if upload["platform"] == "tiktok":
                    metrics = self.collect_tiktok_metrics(upload["post_url"])
                elif upload["platform"] == "instagram":
                    metrics = self.collect_instagram_metrics(upload["post_url"])
                else:
                    continue

                if metrics:
                    db.save_analytics(
                        upload_id=upload["id"],
                        views=metrics["views"],
                        likes=metrics["likes"],
                        comments=metrics["comments"],
                        shares=metrics["shares"],
                    )
                    results.append({"upload_id": upload["id"], **metrics})

        finally:
            self.close_browser()

        logger.info(f"Collected metrics for {len(results)} uploads")
        return results
