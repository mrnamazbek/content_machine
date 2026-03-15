"""
AI Strategy Optimizer — analyzes top-performing posts and generates recommendations.
"""

import json
from typing import Dict, Optional
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

import openai
import anthropic

from config.settings import settings
from database.db import db


class StrategyOptimizer:
    """Analyzes performance data and generates content strategy recommendations."""

    def __init__(self, provider: str = "openai"):
        self.provider = provider
        self.openai_client = openai.OpenAI(api_key=settings.openai_api_key)
        self.anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def _build_analysis_prompt(self, posts_data: list) -> str:
        posts_summary = json.dumps(posts_data, indent=2, default=str)
        return f"""Analyze these TikTok/Instagram Reels posts and identify patterns for viral content.

Post data:
{posts_summary}

Return a JSON object with this structure:
{{
    "best_topics": ["topic1", "topic2", "topic3"],
    "best_caption_styles": ["style description 1", "style description 2"],
    "best_posting_times": ["time recommendation 1", "time recommendation 2"],
    "content_recommendations": ["actionable recommendation 1", "actionable recommendation 2"],
    "report": "Brief 3-5 sentence analysis of what works best and why"
}}

Focus on:
- Which niches get the most engagement
- Caption length and tone patterns
- Hashtag effectiveness
- Timing patterns (if available)
- Content types that perform best

Return ONLY valid JSON."""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def _call_openai(self, prompt: str) -> dict:
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a data-driven social media strategist. Always respond with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def _call_anthropic(self, prompt: str) -> dict:
        response = self.anthropic_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
            system="You are a data-driven social media strategist. Always respond with valid JSON.",
        )
        content = response.content[0].text.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(content)

    def analyze(self, days: int = 7) -> Optional[Dict]:
        """
        Analyze top-performing posts from the last N days.
        Generates strategy report and saves to DB.
        """
        logger.info(f"Running strategy analysis for the last {days} days")

        # Get performance data
        top_posts = db.get_top_performing(days=days, limit=20)

        if not top_posts:
            logger.warning("No analytics data available for strategy analysis")
            return None

        prompt = self._build_analysis_prompt(top_posts)
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
                logger.error(f"Strategy analysis failed with both providers: {e2}")
                return None

        # Save strategy report
        report_id = db.save_strategy_report(
            report_text=result.get("report", ""),
            best_topics=result.get("best_topics", []),
            best_times=result.get("best_posting_times", []),
            best_styles=result.get("best_caption_styles", []),
            provider=provider_used,
            model=model_used,
        )

        logger.info(f"Strategy report saved (id={report_id})")

        return {
            "report_id": report_id,
            **result,
        }
