"""
Video Downloader — downloads videos using yt-dlp.
"""

import subprocess
import os
from pathlib import Path
from typing import Optional
from loguru import logger

from config.settings import settings
from database.db import db


class VideoDownloader:
    """Downloads videos via yt-dlp and updates the database."""

    def __init__(self):
        self.output_dir = Path(settings.video_raw_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download(self, video_id: int, url: str) -> Optional[str]:
        """
        Download a single video by URL.
        Returns local file path on success, None on failure.
        """
        output_template = str(self.output_dir / f"{video_id}_%(id)s.%(ext)s")

        logger.info(f"Downloading video id={video_id}: {url}")

        try:
            result = subprocess.run(
                [
                    "yt-dlp",
                    "-f", "best[height<=1920]",
                    "--merge-output-format", "mp4",
                    "-o", output_template,
                    "--no-playlist",
                    "--socket-timeout", "30",
                    "--retries", "3",
                    url,
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                logger.error(f"yt-dlp failed for video {video_id}: {result.stderr[:500]}")
                db.update_video_status(video_id, "failed")
                return None

            # Find the downloaded file
            downloaded = self._find_downloaded_file(video_id)
            if downloaded:
                db.update_video_status(
                    video_id, "downloaded", local_path_raw=str(downloaded)
                )
                logger.info(f"Downloaded: {downloaded}")
                return str(downloaded)
            else:
                logger.error(f"Download completed but file not found for video {video_id}")
                db.update_video_status(video_id, "failed")
                return None

        except subprocess.TimeoutExpired:
            logger.error(f"Download timed out for video {video_id}")
            db.update_video_status(video_id, "failed")
            return None
        except Exception as e:
            logger.error(f"Download error for video {video_id}: {e}")
            db.update_video_status(video_id, "failed")
            return None

    def _find_downloaded_file(self, video_id: int) -> Optional[Path]:
        """Find the downloaded file by video_id prefix."""
        for f in self.output_dir.iterdir():
            if f.name.startswith(f"{video_id}_") and f.suffix == ".mp4":
                return f
        return None

    def download_batch(self, limit: int = 5) -> list:
        """Download all videos in 'discovered' status."""
        videos = db.get_videos_by_status("discovered", limit=limit)
        results = []

        for video in videos:
            path = self.download(video["id"], video["source_url"])
            if path:
                results.append({"video_id": video["id"], "path": path})

        logger.info(f"Batch download complete: {len(results)}/{len(videos)} successful")
        return results
