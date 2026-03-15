"""
AI Content Machine — CLI Orchestrator.
Run individual pipeline steps or the full pipeline.
"""

import sys
import click
from loguru import logger

from config.settings import settings
from database.db import db

# Configure logging
logger.remove()
logger.add(sys.stderr, level=settings.log_level)
logger.add("logs/content_machine.log", rotation="10 MB", retention="7 days",
           level="DEBUG")


def init_db():
    """Initialize database connection."""
    db.connect()


@click.group()
def cli():
    """AI Content Machine — Automated content pipeline."""
    pass


@cli.command()
def discover():
    """Discover trending topics via Perplexity API."""
    init_db()
    from scrapers.discover_trends import TrendDiscoverer

    discoverer = TrendDiscoverer()
    results = discoverer.discover_all()
    logger.info(f"Discovered trends for {len(results)} niches")
    for r in results:
        click.echo(f"  [{r['niche']}] {len(r['hashtags'])} hashtags, "
                    f"{len(r['topic_ideas'])} topics")


@cli.command()
@click.option("--niche", default=None, help="Specific niche to search")
@click.option("--limit", default=10, help="Max videos per search")
def find(niche, limit):
    """Find viral videos matching discovered trends."""
    init_db()
    from scrapers.find_videos import VideoFinder

    finder = VideoFinder()
    niches = [niche] if niche else settings.niche_list

    total = 0
    for n in niches:
        ids = finder.discover_and_save(query=n, niche=n, max_results=limit)
        total += len(ids)
        click.echo(f"  [{n}] Found {len(ids)} new videos")

    click.echo(f"Total: {total} videos saved")


@cli.command()
@click.option("--url", default=None, help="Specific URL to download")
@click.option("--limit", default=5, help="Max videos to download")
def download(url, limit):
    """Download discovered videos."""
    init_db()
    from scrapers.download import VideoDownloader

    downloader = VideoDownloader()

    if url:
        # Download single video by URL — create a temp record
        video_id = db.save_video(source_url=url, source_platform="manual",
                                 niche="manual")
        if video_id:
            path = downloader.download(video_id, url)
            click.echo(f"Downloaded: {path}" if path else "Download failed")
    else:
        results = downloader.download_batch(limit=limit)
        click.echo(f"Downloaded {len(results)} videos")


@cli.command()
@click.option("--input", "input_path", default=None, help="Specific video to process")
@click.option("--limit", default=5, help="Max videos to process")
def process(input_path, limit):
    """Process downloaded videos with FFmpeg."""
    init_db()
    from processing.edit_video import VideoProcessor

    processor = VideoProcessor()

    if input_path:
        output = processor.process(video_id=0, input_path=input_path)
        click.echo(f"Processed: {output}" if output else "Processing failed")
    else:
        results = processor.process_batch(limit=limit)
        click.echo(f"Processed {len(results)} videos")


@cli.command(name="generate-captions")
@click.option("--topic", default=None, help="Topic for caption generation")
@click.option("--niche", default="gym discipline", help="Content niche")
@click.option("--provider", default="openai", help="AI provider (openai/anthropic)")
@click.option("--limit", default=5, help="Max captions to generate")
def generate_captions(topic, niche, provider, limit):
    """Generate captions and hashtags using AI."""
    init_db()
    from ai.generate_caption import CaptionGenerator

    generator = CaptionGenerator(provider=provider)

    if topic:
        result = generator.generate(video_id=0, topic=topic, niche=niche)
        if result:
            click.echo(f"Caption: {result['caption']}")
            click.echo(f"Hashtags: {' '.join(result['hashtags'])}")
    else:
        results = generator.generate_batch(limit=limit)
        click.echo(f"Generated {len(results)} captions")
        for r in results:
            click.echo(f"  [{r['video_id']}] {r['caption']}")


@cli.command()
@click.option("--platform", default="tiktok", help="Platform (tiktok/instagram)")
@click.option("--limit", default=3, help="Max videos to upload")
def upload(platform, limit):
    """Upload processed videos to social media."""
    init_db()
    from upload.upload_tiktok import TikTokUploader
    from upload.upload_instagram import InstagramUploader

    # Get videos ready to upload (status = captioned)
    videos = db.get_videos_by_status("captioned", limit=limit)

    if not videos:
        click.echo("No videos ready for upload")
        return

    for video in videos:
        # Get the latest caption for this video
        with db.get_cursor(commit=False) as cur:
            cur.execute(
                "SELECT * FROM captions WHERE video_id = %s ORDER BY id DESC LIMIT 1",
                (video["id"],)
            )
            caption_row = cur.fetchone()

        if not caption_row:
            logger.warning(f"No caption found for video {video['id']}")
            continue

        video_path = video.get("local_path_processed") or video.get("local_path_raw")
        if not video_path:
            logger.warning(f"No video file for video {video['id']}")
            continue

        # Create upload record
        upload_id = db.save_upload(
            video_id=video["id"],
            caption_id=caption_row["id"],
            platform=platform,
        )

        # Upload
        if platform == "tiktok":
            uploader = TikTokUploader()
        else:
            uploader = InstagramUploader()

        result = uploader.safe_upload(
            video_path=video_path,
            caption=caption_row["caption"],
            hashtags=caption_row["hashtags"],
        )

        if result.get("success"):
            db.update_upload_status(upload_id, "posted",
                                    post_url=result.get("post_url"))
            db.update_video_status(video["id"], "posted")
            click.echo(f"  Uploaded video {video['id']} to {platform}")
        else:
            db.update_upload_status(upload_id, "failed",
                                    error_message=result.get("error"))
            click.echo(f"  Failed video {video['id']}: {result.get('error')}")


@cli.command(name="collect-analytics")
def collect_analytics():
    """Collect analytics from posted videos."""
    init_db()
    from analytics.metrics import MetricsCollector

    collector = MetricsCollector()
    results = collector.collect_all()
    click.echo(f"Collected metrics for {len(results)} uploads")


@cli.command()
@click.option("--days", default=7, help="Days of data to analyze")
@click.option("--provider", default="openai", help="AI provider")
def optimize(days, provider):
    """Run AI strategy optimization."""
    init_db()
    from ai.strategy import StrategyOptimizer

    optimizer = StrategyOptimizer(provider=provider)
    result = optimizer.analyze(days=days)

    if result:
        click.echo(f"\nStrategy Report:")
        click.echo(f"  Best topics: {result.get('best_topics', [])}")
        click.echo(f"  Best times: {result.get('best_posting_times', [])}")
        click.echo(f"  Best styles: {result.get('best_caption_styles', [])}")
        click.echo(f"\n  {result.get('report', '')}")
    else:
        click.echo("No data available for analysis")


@cli.command(name="run-pipeline")
@click.option("--limit", default=3, help="Videos per batch")
@click.option("--platform", default="tiktok", help="Upload platform")
def run_pipeline(limit, platform):
    """Run the full content pipeline end-to-end."""
    init_db()
    from scrapers.discover_trends import TrendDiscoverer
    from scrapers.find_videos import VideoFinder
    from scrapers.download import VideoDownloader
    from processing.edit_video import VideoProcessor
    from ai.generate_caption import CaptionGenerator

    click.echo("=" * 50)
    click.echo("AI Content Machine — Full Pipeline")
    click.echo("=" * 50)

    # Step 1: Discover trends
    click.echo("\n[1/5] Discovering trends...")
    discoverer = TrendDiscoverer()
    trends = discoverer.discover_all()
    click.echo(f"  Found trends for {len(trends)} niches")

    # Step 2: Find videos
    click.echo("\n[2/5] Finding viral videos...")
    finder = VideoFinder()
    total_found = 0
    for trend in trends:
        for topic in trend.get("topic_ideas", [])[:2]:
            ids = finder.discover_and_save(query=topic, niche=trend["niche"])
            total_found += len(ids)
    click.echo(f"  Found {total_found} new videos")

    # Step 3: Download
    click.echo("\n[3/5] Downloading videos...")
    downloader = VideoDownloader()
    downloaded = downloader.download_batch(limit=limit)
    click.echo(f"  Downloaded {len(downloaded)} videos")

    # Step 4: Process
    click.echo("\n[4/5] Processing videos...")
    processor = VideoProcessor()
    processed = processor.process_batch(limit=limit)
    click.echo(f"  Processed {len(processed)} videos")

    # Step 5: Generate captions
    click.echo("\n[5/5] Generating captions...")
    generator = CaptionGenerator()
    captions = generator.generate_batch(limit=limit)
    click.echo(f"  Generated {len(captions)} captions")

    click.echo(f"\nPipeline complete! {len(captions)} videos ready for upload.")
    click.echo(f"Run: python main.py upload --platform {platform}")


@cli.command(name="login-tiktok")
def login_tiktok():
    """Manual TikTok login to save session."""
    from upload.upload_tiktok import TikTokUploader
    uploader = TikTokUploader()
    uploader.manual_login_flow()


@cli.command(name="login-instagram")
def login_instagram():
    """Manual Instagram login to save session."""
    from upload.upload_instagram import InstagramUploader
    uploader = InstagramUploader()
    uploader.manual_login_flow()


if __name__ == "__main__":
    cli()
