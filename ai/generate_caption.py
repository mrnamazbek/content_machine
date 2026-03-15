"""
Caption & Hashtag Generator — uses OpenAI or Anthropic Claude to create viral captions.
"""

import json
from typing import Dict, Optional
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

import openai
import anthropic

from config.settings import settings
from database.db import db


class CaptionGenerator:
    """Generates viral captions and hashtags using LLM APIs."""

    TONES = {
        "gym discipline": "confident masculine, disciplined, warrior mindset",
        "engineer life": "smart, nerdy-cool, productive hustle",
        "coding mindset": "focused developer, tech-savvy grind",
        "football motivation": "competitive athlete, never-give-up energy",
    }

    def __init__(self, provider: str = "openai"):
        """
        Args:
            provider: "openai" or "anthropic" (fallback)
        """
        self.provider = provider
        self.openai_client = openai.OpenAI(api_key=settings.openai_api_key)
        self.anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def _build_prompt(self, topic: str, niche: str) -> str:
        tone = self.TONES.get(niche, "confident masculine")
        return f"""Write a viral TikTok/Instagram Reels caption.

Topic: {topic}
Tone: {tone}
Max caption length: 12 words
Include exactly 5 trending hashtags relevant to the topic

Your response must be a JSON object with this exact structure:
{{
    "caption": "Your viral caption here",
    "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3", "#hashtag4", "#hashtag5"]
}}

Rules:
- Caption must be punchy, attention-grabbing, and motivational
- Use short, powerful sentences
- No generic phrases like "check this out"
- Hashtags should mix popular (1M+ posts) and niche-specific tags
- Return ONLY valid JSON, no extra text"""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=15))
    def _call_openai(self, prompt: str) -> dict:
        """Generate caption via OpenAI."""
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a viral social media copywriter. Always respond with valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
            max_tokens=256,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return json.loads(content)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=15))
    def _call_anthropic(self, prompt: str) -> dict:
        """Generate caption via Anthropic Claude (fallback)."""
        response = self.anthropic_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=256,
            messages=[
                {"role": "user", "content": prompt},
            ],
            system="You are a viral social media copywriter. Always respond with valid JSON only.",
        )
        content = response.content[0].text

        # Handle possible markdown wrapping
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]

        return json.loads(content)

    def generate(self, video_id: int, topic: str,
                 niche: str = "gym discipline") -> Optional[Dict]:
        """
        Generate caption for a video. Tries primary provider, falls back to secondary.
        Returns dict with caption, hashtags, and saves to DB.
        """
        prompt = self._build_prompt(topic, niche)
        provider_used = self.provider
        model_used = ""

        try:
            if self.provider == "openai":
                result = self._call_openai(prompt)
                model_used = "gpt-4o-mini"
            else:
                result = self._call_anthropic(prompt)
                model_used = "claude-3-5-haiku-20241022"
        except Exception as e:
            # Fallback to other provider
            logger.warning(f"{self.provider} failed, falling back: {e}")
            try:
                if self.provider == "openai":
                    result = self._call_anthropic(prompt)
                    provider_used = "anthropic"
                    model_used = "claude-3-5-haiku-20241022"
                else:
                    result = self._call_openai(prompt)
                    provider_used = "openai"
                    model_used = "gpt-4o-mini"
            except Exception as e2:
                logger.error(f"Both providers failed for video {video_id}: {e2}")
                return None

        caption = result.get("caption", "")
        hashtags = result.get("hashtags", [])

        # Save to DB
        caption_id = db.save_caption(
            video_id=video_id,
            caption=caption,
            hashtags=hashtags,
            tone=self.TONES.get(niche, "confident masculine"),
            provider=provider_used,
            model=model_used,
        )

        # Update video status
        db.update_video_status(video_id, "captioned")

        logger.info(f"Caption generated for video {video_id} via {provider_used}: "
                     f"'{caption}' {hashtags}")

        return {
            "caption_id": caption_id,
            "video_id": video_id,
            "caption": caption,
            "hashtags": hashtags,
            "provider": provider_used,
        }

    def generate_batch(self, limit: int = 5) -> list:
        """Generate captions for all videos in 'processed' status."""
        videos = db.get_videos_by_status("processed", limit=limit)
        results = []

        for video in videos:
            topic = video.get("title", "") or video.get("niche", "motivation")
            niche = video.get("niche", "gym discipline")
            result = self.generate(video["id"], topic, niche)
            if result:
                results.append(result)

        logger.info(f"Batch caption generation complete: {len(results)}/{len(videos)}")
        return results
