"""
Base uploader — abstract class with common upload logic.
"""

import abc
from pathlib import Path
from typing import Optional, Dict
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed

from playwright.sync_api import sync_playwright, Browser, Page

from config.settings import settings


class BaseUploader(abc.ABC):
    """Abstract base class for platform uploaders."""

    PLATFORM: str = ""
    AUTH_STATE_FILE: str = ""

    def __init__(self):
        self.auth_dir = Path(settings.auth_dir)
        self.auth_dir.mkdir(parents=True, exist_ok=True)
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._playwright = None

    @property
    def auth_state_path(self) -> Path:
        return self.auth_dir / self.AUTH_STATE_FILE

    def start_browser(self, headless: bool = True):
        """Launch Playwright browser with saved auth state if available."""
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

        context_kwargs = {
            "viewport": {"width": 1080, "height": 1920},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        # Load saved session if exists
        if self.auth_state_path.exists():
            context_kwargs["storage_state"] = str(self.auth_state_path)
            logger.info(f"Loading saved auth state for {self.PLATFORM}")

        context = self._browser.new_context(**context_kwargs)
        self._page = context.new_page()

    def save_auth_state(self):
        """Save browser auth state for future sessions."""
        if self._page:
            self._page.context.storage_state(path=str(self.auth_state_path))
            logger.info(f"Auth state saved for {self.PLATFORM}")

    def close_browser(self):
        """Close browser and cleanup."""
        if self._page:
            self.save_auth_state()
            self._page.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    @abc.abstractmethod
    def login(self, username: str, password: str) -> bool:
        """Platform-specific login logic."""
        pass

    @abc.abstractmethod
    def upload_video(self, video_path: str, caption: str,
                     hashtags: list) -> Dict:
        """Platform-specific upload logic."""
        pass

    def safe_upload(self, video_path: str, caption: str,
                    hashtags: list, headless: bool = True) -> Dict:
        """Upload with browser lifecycle management."""
        try:
            self.start_browser(headless=headless)

            # Check if we need to login
            if not self.auth_state_path.exists():
                logger.info(f"No saved session for {self.PLATFORM}, logging in...")
                self._do_login()

            result = self.upload_video(video_path, caption, hashtags)
            return result

        except Exception as e:
            logger.error(f"Upload failed on {self.PLATFORM}: {e}")
            return {"success": False, "error": str(e)}
        finally:
            self.close_browser()

    def _do_login(self):
        """Attempt login with configured credentials."""
        raise NotImplementedError("Override _do_login in subclass")

    def _wait_and_click(self, selector: str, timeout: int = 10000):
        """Wait for element and click it."""
        self._page.wait_for_selector(selector, timeout=timeout)
        self._page.click(selector)

    def _wait_and_fill(self, selector: str, text: str, timeout: int = 10000):
        """Wait for element and fill it with text."""
        self._page.wait_for_selector(selector, timeout=timeout)
        self._page.fill(selector, text)
