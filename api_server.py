"""
AI Content Machine — FastAPI Server.
Exposes endpoints for n8n workflow triggers.
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from loguru import logger

from config.settings import settings
from database.db import db

app = FastAPI(
    title="AI Content Machine",
    description="Automated content pipeline API for n8n integration",
    version="1.0.0",
)


# ── Startup / Shutdown ────────────────────────────

@app.on_event("startup")
def startup():
    db.connect()
    db.init_schema()
    logger.info("API server started, database connected, schema verified")


@app.on_event("shutdown")
def shutdown():
    db.close()
    logger.info("API server shut down")


# ── Health Check ──────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "content-machine"}


@app.get("/")
def serve_dashboard():
    """Serve the frontend glassmorphism dashboard."""
    return FileResponse("frontend/index.html")


# ── Request Models ────────────────────────────────

class DiscoverRequest(BaseModel):
    niche: Optional[str] = None  # None = all niches


class FindRequest(BaseModel):
    niche: Optional[str] = None
    limit: int = 10


class BatchRequest(BaseModel):
    limit: int = 5


class UploadRequest(BaseModel):
    platform: str = "tiktok"
    limit: int = 3


class AnalyzeRequest(BaseModel):
    days: int = 7
    provider: str = "openai"


# ── Pipeline Endpoints ────────────────────────────

@app.post("/trigger/discover")
def trigger_discover(req: DiscoverRequest, bg: BackgroundTasks):
    """Trigger trend discovery."""
    from scrapers.discover_trends import TrendDiscoverer

    discoverer = TrendDiscoverer()

    if req.niche:
        result = discoverer.discover(req.niche)
        return {"status": "completed", "data": result}
    else:
        bg.add_task(_discover_all, discoverer)
        return {"status": "started", "message": "Discovering trends for all niches"}


def _discover_all(discoverer):
    try:
        discoverer.discover_all()
    except Exception as e:
        logger.error(f"Background discover failed: {e}")


@app.post("/trigger/find")
def trigger_find(req: FindRequest, bg: BackgroundTasks):
    """Trigger video discovery."""
    from scrapers.find_videos import VideoFinder

    finder = VideoFinder()
    niches = [req.niche] if req.niche else settings.niche_list

    total = 0
    for n in niches:
        ids = finder.discover_and_save(query=n, niche=n, max_results=req.limit)
        total += len(ids)

    return {"status": "completed", "videos_found": total}


@app.post("/trigger/download")
def trigger_download(req: BatchRequest):
    """Download discovered videos."""
    from scrapers.download import VideoDownloader

    downloader = VideoDownloader()
    results = downloader.download_batch(limit=req.limit)
    return {"status": "completed", "downloaded": len(results)}


@app.post("/trigger/process")
def trigger_process(req: BatchRequest):
    """Process downloaded videos with FFmpeg."""
    from processing.edit_video import VideoProcessor

    processor = VideoProcessor()
    results = processor.process_batch(limit=req.limit)
    return {"status": "completed", "processed": len(results)}


@app.post("/trigger/generate")
def trigger_generate(req: BatchRequest):
    """Generate captions for processed videos."""
    from ai.generate_caption import CaptionGenerator

    generator = CaptionGenerator()
    results = generator.generate_batch(limit=req.limit)
    return {"status": "completed", "captions_generated": len(results)}


@app.post("/trigger/upload")
def trigger_upload(req: UploadRequest):
    """Upload captioned videos to platform."""
    from upload.upload_tiktok import TikTokUploader
    from upload.upload_instagram import InstagramUploader

    videos = db.get_videos_by_status("captioned", limit=req.limit)
    uploaded = 0

    for video in videos:
        with db.get_cursor(commit=False) as cur:
            cur.execute(
                "SELECT * FROM captions WHERE video_id = %s ORDER BY id DESC LIMIT 1",
                (video["id"],)
            )
            caption_row = cur.fetchone()

        if not caption_row:
            continue

        video_path = video.get("local_path_processed") or video.get("local_path_raw")
        if not video_path:
            continue

        upload_id = db.save_upload(
            video_id=video["id"],
            caption_id=caption_row["id"],
            platform=req.platform,
        )

        uploader = TikTokUploader() if req.platform == "tiktok" else InstagramUploader()
        result = uploader.safe_upload(
            video_path=video_path,
            caption=caption_row["caption"],
            hashtags=caption_row["hashtags"],
        )

        if result.get("success"):
            db.update_upload_status(upload_id, "posted", post_url=result.get("post_url"))
            db.update_video_status(video["id"], "posted")
            uploaded += 1
        else:
            db.update_upload_status(upload_id, "failed", error_message=result.get("error"))

    return {"status": "completed", "uploaded": uploaded}


@app.post("/trigger/analytics")
def trigger_analytics():
    """Collect analytics from posted videos."""
    from analytics.metrics import MetricsCollector

    collector = MetricsCollector()
    results = collector.collect_all()
    return {"status": "completed", "metrics_collected": len(results)}


@app.post("/trigger/optimize")
def trigger_optimize(req: AnalyzeRequest):
    """Run AI strategy optimization."""
    from ai.strategy import StrategyOptimizer

    optimizer = StrategyOptimizer(provider=req.provider)
    result = optimizer.analyze(days=req.days)

    if result:
        return {"status": "completed", "data": result}
    else:
        return {"status": "completed", "message": "No data available"}


@app.get("/status")
def pipeline_status():
    """Get current pipeline status — video counts by status."""
    statuses = {}
    for s in ["discovered", "downloaded", "processed", "captioned", "posted", "failed"]:
        videos = db.get_videos_by_status(s, limit=1000)
        statuses[s] = len(videos)

    return {
        "pipeline_status": statuses,
        "total_videos": sum(statuses.values()),
    }
