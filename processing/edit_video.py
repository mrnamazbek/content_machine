"""
Video Processor — uses FFmpeg to modify videos to avoid duplicate detection.
"""

import subprocess
import hashlib
import random
from pathlib import Path
from typing import Optional
from loguru import logger

from config.settings import settings
from database.db import db


class VideoProcessor:
    """Processes videos with FFmpeg to make them unique."""

    def __init__(self):
        self.output_dir = Path(settings.video_processed_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def process(self, video_id: int, input_path: str,
                watermark_text: str = None) -> Optional[str]:
        """
        Apply modifications to make the video unique:
        - Scale to 1080x1920 (vertical)
        - Slight random zoom (1.01–1.04x)
        - Contrast adjustment (+1–3%)
        - Saturation adjustment (+5–15%)
        - Slight speed variation (±2%)
        - Optional watermark text overlay
        """
        input_file = Path(input_path)
        if not input_file.exists():
            logger.error(f"Input file not found: {input_path}")
            return None

        # Randomize parameters for uniqueness
        zoom = round(random.uniform(1.01, 1.04), 3)
        contrast = round(random.uniform(1.01, 1.03), 3)
        saturation = round(random.uniform(1.05, 1.15), 2)
        speed = round(random.uniform(0.98, 1.02), 3)

        # Build output filename with hash
        file_hash = hashlib.md5(f"{video_id}_{zoom}_{contrast}".encode()).hexdigest()[:8]
        output_file = self.output_dir / f"{video_id}_{file_hash}.mp4"

        # Build filter chain
        vfilters = [
            f"scale=1080:1920:force_original_aspect_ratio=decrease",
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
            f"zoompan=z={zoom}:d=1:s=1080x1920",
            f"eq=contrast={contrast}:saturation={saturation}",
            f"setpts={1/speed}*PTS",
        ]

        # Optional watermark
        if watermark_text:
            # Escape special characters for FFmpeg drawtext
            safe_text = watermark_text.replace("'", "\\'").replace(":", "\\:")
            vfilters.append(
                f"drawtext=text='{safe_text}'"
                f":fontsize=24:fontcolor=white@0.5"
                f":x=(w-text_w)/2:y=h-50"
            )

        filter_chain = ",".join(vfilters)
        audio_filter = f"atempo={speed}" if speed != 1.0 else None

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_file),
            "-vf", filter_chain,
        ]

        if audio_filter:
            cmd.extend(["-af", audio_filter])

        cmd.extend([
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(output_file),
        ])

        logger.info(f"Processing video {video_id}: zoom={zoom}, "
                     f"contrast={contrast}, saturation={saturation}, speed={speed}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
            )

            if result.returncode != 0:
                logger.error(f"FFmpeg failed for video {video_id}: {result.stderr[:500]}")
                db.update_video_status(video_id, "failed")
                return None

            db.update_video_status(
                video_id, "processed",
                local_path_processed=str(output_file),
            )
            logger.info(f"Processed video saved: {output_file}")
            return str(output_file)

        except subprocess.TimeoutExpired:
            logger.error(f"FFmpeg timed out for video {video_id}")
            db.update_video_status(video_id, "failed")
            return None
        except Exception as e:
            logger.error(f"Processing error for video {video_id}: {e}")
            db.update_video_status(video_id, "failed")
            return None

    def process_batch(self, limit: int = 5) -> list:
        """Process all videos in 'downloaded' status."""
        videos = db.get_videos_by_status("downloaded", limit=limit)
        results = []

        for video in videos:
            path = self.process(video["id"], video["local_path_raw"])
            if path:
                results.append({"video_id": video["id"], "path": path})

        logger.info(f"Batch processing complete: {len(results)}/{len(videos)} successful")
        return results
