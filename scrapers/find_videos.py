"""
Video Discovery — finds viral short-form videos matching discovered trends.
Uses yt-dlp search functionality to find videos on various platforms.
"""

import subprocess
import json
from typing import List, Dict, Optional
from loguru import logger

from config.settings import settings
from database.db import db


class VideoFinder:
    """Finds viral short-form videos based on trending topics."""

    def __init__(self):
        self.min_views = settings.min_views
        self.max_duration = settings.max_duration

    def search_videos(self, query: str, platform: str = "tiktok",
                      max_results: int = 10) -> List[Dict]:
        """
        Search for videos using yt-dlp.
        Supported platforms: tiktok, instagram, youtube.
        """
        search_prefix = {
            "tiktok": "ytsearch",       # yt-dlp can search YouTube; for TikTok use direct URLs
            "youtube": "ytsearch",
        }

        prefix = search_prefix.get(platform, "ytsearch")
        # Enhance query to heavily bias towards YouTube Shorts
        search_query = f"{prefix}{max_results * 2}:\"{query}\" #shorts"

        logger.info(f"Searching videos: platform={platform}, query='{search_query}'")

        try:
            result = subprocess.run(
                [
                    "yt-dlp",
                    "--dump-json",
                    "--flat-playlist",
                    "--no-download",
                    search_query,
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                logger.warning(f"yt-dlp search returned code {result.returncode}: {result.stderr[:300]}")
                return []

            videos = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    videos.append(self._parse_video_data(data, platform))
                except json.JSONDecodeError:
                    continue

            return videos

        except subprocess.TimeoutExpired:
            logger.error("yt-dlp search timed out")
            return []
        except Exception as e:
            logger.error(f"Video search failed: {e}")
            return []

    def _parse_video_data(self, data: dict, platform: str) -> dict:
        """Extract relevant fields from yt-dlp JSON output."""
        return {
            "source_url": data.get("webpage_url") or data.get("url", ""),
            "source_platform": platform,
            "title": data.get("title", ""),
            "original_views": data.get("view_count", 0) or 0,
            "original_likes": data.get("like_count", 0) or 0,
            "duration": data.get("duration", 0) or 0,
            "hashtags": data.get("tags", []) or [],
        }

    def filter_videos(self, videos: List[Dict]) -> List[Dict]:
        """Filter videos by views, duration, and deduplication."""
        filtered = []
        for v in videos:
            # 1. Check max duration
            # yt-dlp sometimes fails to get duration (returns 0). We should only skip if it's explicitly strictly greater.
            if v["duration"] > 0 and v["duration"] > self.max_duration:
                logger.debug(f"Skipping (too long={v['duration']}s): {v['title'][:50]}")
                continue

            # 2. Check minimum views
            # yt-dlp flat-playlist often misses view_count (returns 0 or very small numbers like '5' for live streams).
            # We relax the strict filter if the view count wasn't successfully scraped to avoid dropping viral shorts.
            if v["original_views"] > 0 and v["original_views"] < self.min_views:
                 # Soft fallback: if it's a short, we might still accept it if view parsing failed
                 if v["original_views"] > 1000: # If it actually parsed a real number > 1000 but < min_views
                     logger.debug(f"Skipping (low views={v['original_views']}): {v['title'][:50]}")
                     continue

            # Prevent extremely long titles that might be compilations
            if len(v["title"]) > 150:
                 continue

            filtered.append(v)

        # Sort by views (descending) to get the best ones, treating 0 as unknown (potentially high)
        filtered.sort(key=lambda x: x["original_views"] if x["original_views"] > 1000 else float('inf'), reverse=True)
        
        # Limit to the actual requested amount, since we doubled the yt-dlp search scope
        filtered = filtered[:10]

        logger.info(f"Filtered {len(filtered)}/{len(videos)} videos passed criteria")
        return filtered

    def discover_and_save(self, query: str, niche: str,
                          platform: str = "tiktok") -> List[int]:
        """Full pipeline: search → filter → deduplicate → save to DB."""
        videos = self.search_videos(query, platform)
        filtered = self.filter_videos(videos)

        saved_ids = []
        for v in filtered:
            video_id = db.save_video(
                source_url=v["source_url"],
                source_platform=v["source_platform"],
                title=v["title"],
                original_views=v["original_views"],
                original_likes=v["original_likes"],
                duration=v["duration"],
                hashtags=v["hashtags"],
                niche=niche,
            )
            if video_id:
                saved_ids.append(video_id)
                logger.info(f"Saved video id={video_id}: {v['title'][:60]}")
            else:
                logger.debug(f"Duplicate skipped: {v['source_url']}")

        logger.info(f"Saved {len(saved_ids)} new videos for query '{query}'")
        return saved_ids
