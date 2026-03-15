"""
AI Content Machine — FastAPI Server.
Exposes endpoints for n8n workflow triggers.
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
import asyncio
import os
from pydantic import BaseModel
from typing import Optional
from loguru import logger

from config.settings import settings
from database.db import db

os.makedirs("videos", exist_ok=True)

app = FastAPI(
    title="AI Content Machine",
    description="Automated content pipeline API for n8n integration",
    version="1.0.0",
)

app.mount("/videos", StaticFiles(directory="videos"), name="videos")


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


class RunPipelineRequest(BaseModel):
    limit: int = 3
    platform: str = "tiktok"


# ── State Machine (Idempotency) ───────────────────
_pipeline_running = False

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


@app.get("/api/content/ready")
def get_ready_content(limit: int = 15):
    """Get videos and their captions that are ready to be posted manually."""
    videos = db.get_ready_videos(limit=limit)
    return {"status": "success", "data": videos}


@app.get("/trigger/run-pipeline")
async def trigger_run_pipeline(limit: int = 3, platform: str = "tiktok"):
    """
    Run the full content pipeline end-to-end via Server-Sent Events (SSE).
    Idempotent: prevents concurrent runs.
    """
    global _pipeline_running
    
    if _pipeline_running:
        async def _conflict():
            yield {"data": "ERROR: Pipeline is already running! Please wait for it to finish."}
        return EventSourceResponse(_conflict())
        
    async def event_generator():
        global _pipeline_running
        _pipeline_running = True
        try:
            # Yield initial connect
            yield {"data": "=== AI Content Machine Pipeline Started ==="}
            await asyncio.sleep(0.5)

            # Deferred heavy imports to avoid blocking
            from scrapers.discover_trends import TrendDiscoverer
            from scrapers.find_videos import VideoFinder
            from scrapers.download import VideoDownloader
            from processing.edit_video import VideoProcessor
            from ai.generate_caption import CaptionGenerator

            # 1. Discover
            yield {"data": "[1/5] Discovering trends..."}
            discoverer = TrendDiscoverer()
            trends = discoverer.discover_all()
            yield {"data": f"  -> Found trends for {len(trends)} niches"}
            await asyncio.sleep(0.1)

            # 2. Find
            yield {"data": "[2/5] Finding viral videos..."}
            finder = VideoFinder()
            total_found = 0
            for trend in trends:
                for topic in trend.get("topic_ideas", [])[:2]:
                    ids = finder.discover_and_save(query=topic, niche=trend["niche"])
                    total_found += len(ids)
            yield {"data": f"  -> Found {total_found} new videos"}
            await asyncio.sleep(0.1)

            # 3. Download
            yield {"data": "[3/5] Downloading videos..."}
            downloader = VideoDownloader()
            downloaded = downloader.download_batch(limit=limit)
            yield {"data": f"  -> Downloaded {len(downloaded)} videos"}
            await asyncio.sleep(0.1)

            # 4. Process
            yield {"data": "[4/5] Processing videos with FFmpeg..."}
            processor = VideoProcessor()
            processed = processor.process_batch(limit=limit)
            yield {"data": f"  -> Processed {len(processed)} videos"}
            await asyncio.sleep(0.1)

            # 5. Captions
            yield {"data": "[5/5] Generating AI Captions..."}
            generator = CaptionGenerator()
            captions = generator.generate_batch(limit=limit)
            yield {"data": f"  -> Generated {len(captions)} captions"}
            await asyncio.sleep(0.1)

            yield {"data": f"=== PIPELINE COMPLETE! {len(captions)} videos ready ==="}
            
        except Exception as e:
            logger.error(f"Pipeline crashed: {e}")
            yield {"data": f"ERROR: Pipeline failed halfway: {str(e)}"}
        finally:
            _pipeline_running = False

    return EventSourceResponse(event_generator())
