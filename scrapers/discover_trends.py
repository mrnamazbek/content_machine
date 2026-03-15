"""
Trend Discovery — uses Perplexity API to find trending topics and hashtags.
"""

import json
import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings
from database.db import db


class TrendDiscoverer:
    """Discovers trending content using Perplexity API."""

    PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

    def __init__(self):
        self.api_key = settings.perplexity_api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_prompt(self, niche: str) -> str:
        return f"""Find currently trending TikTok and Instagram Reels topics, hashtags, and viral hooks for the niche: "{niche}".

Return a JSON object with this exact structure:
{{
    "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3", "#hashtag4", "#hashtag5"],
    "topic_ideas": ["topic idea 1", "topic idea 2", "topic idea 3"],
    "viral_hooks": ["hook phrase 1", "hook phrase 2", "hook phrase 3"]
}}

Focus on:
- Hashtags with high engagement rates
- Topics that are currently viral in the last 48 hours
- Short, punchy hook phrases that grab attention in the first 2 seconds
- Content that targets young male audience (18-30)

Return ONLY valid JSON, no extra text."""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def _call_perplexity(self, prompt: str) -> dict:
        """Call Perplexity API with retry logic."""
        payload = {
            "model": "sonar",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a social media trend analyst. Always respond with valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 1024,
        }

        with httpx.Client(timeout=60) as client:
            response = client.post(
                self.PERPLEXITY_URL,
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        # Extract JSON from response (handle markdown code blocks)
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]

        return json.loads(content)

    def discover(self, niche: str) -> dict:
        """Discover trends for a specific niche. Returns parsed data and saves to DB."""
        logger.info(f"Discovering trends for niche: {niche}")
        try:
            result = self._call_perplexity(self._build_prompt(niche))

            hashtags = result.get("hashtags", [])
            topic_ideas = result.get("topic_ideas", [])
            viral_hooks = result.get("viral_hooks", [])

            # Save to database
            trend_id = db.save_trend(
                niche=niche,
                hashtags=hashtags,
                topic_ideas=topic_ideas,
                viral_hooks=viral_hooks,
                source="perplexity",
            )
            logger.info(f"Trend saved (id={trend_id}): {len(hashtags)} hashtags, "
                        f"{len(topic_ideas)} topics, {len(viral_hooks)} hooks")

            return {
                "trend_id": trend_id,
                "niche": niche,
                "hashtags": hashtags,
                "topic_ideas": topic_ideas,
                "viral_hooks": viral_hooks,
            }

        except Exception as e:
            logger.error(f"Trend discovery failed for '{niche}': {e}")
            raise

    def discover_all(self) -> list:
        """Discover trends for all configured niches."""
        results = []
        for niche in settings.niche_list:
            try:
                result = self.discover(niche)
                results.append(result)
            except Exception as e:
                logger.warning(f"Skipping niche '{niche}': {e}")
        return results
