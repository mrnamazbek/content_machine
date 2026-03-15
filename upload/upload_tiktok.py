"""
TikTok Uploader — Playwright-based video upload to TikTok.

WARNING: TikTok actively fights automation. Selectors may change.
         This is designed for educational/personal use.
         Consider using the official TikTok Content Posting API if approved.
"""

import time
from pathlib import Path
from typing import Dict
from loguru import logger

from config.settings import settings
from upload.base_uploader import BaseUploader


class TikTokUploader(BaseUploader):
    """Uploads videos to TikTok via browser automation."""

    PLATFORM = "tiktok"
    AUTH_STATE_FILE = "tiktok_auth.json"

    UPLOAD_URL = "https://www.tiktok.com/creator#/upload?scene=creator_center"
    LOGIN_URL = "https://www.tiktok.com/login"

    def login(self, username: str = "", password: str = "") -> bool:
        """
        Login to TikTok.
        Due to TikTok's anti-bot measures, manual login + session save
        is the most reliable approach.
        """
        username = username or settings.tiktok_username
        password = password or settings.tiktok_password

        if not username or not password:
            logger.warning("TikTok credentials not configured. "
                           "Run with headless=False for manual login.")
            return False

        try:
            self._page.goto(self.LOGIN_URL, wait_until="networkidle", timeout=30000)
            time.sleep(3)

            # Click "Use phone / email / username"
            self._page.click('div[class*="channel-item"]', timeout=5000)
            time.sleep(1)

            # Click "Log in with email or username"
            self._page.click('a[href*="email"]', timeout=5000)
            time.sleep(1)

            # Fill credentials
            self._page.fill('input[name="username"]', username, timeout=5000)
            self._page.fill('input[type="password"]', password, timeout=5000)

            # Click login button
            self._page.click('button[type="submit"]', timeout=5000)

            # Wait for navigation
            time.sleep(5)

            # Check if login succeeded
            if "login" not in self._page.url.lower():
                self.save_auth_state()
                logger.info("TikTok login successful")
                return True
            else:
                logger.warning("TikTok login may have failed (CAPTCHA possible)")
                return False

        except Exception as e:
            logger.error(f"TikTok login failed: {e}")
            return False

    def upload_video(self, video_path: str, caption: str,
                     hashtags: list) -> Dict:
        """
        Upload a video to TikTok Creator Center.

        Steps:
        1. Navigate to upload page
        2. Upload video file via file input
        3. Wait for processing
        4. Enter caption and hashtags
        5. Click publish
        """
        if not Path(video_path).exists():
            return {"success": False, "error": f"Video not found: {video_path}"}

        full_caption = f"{caption} {' '.join(hashtags)}"

        try:
            logger.info(f"Uploading to TikTok: {video_path}")

            # Navigate to upload page
            self._page.goto(self.UPLOAD_URL, wait_until="networkidle", timeout=30000)
            time.sleep(3)

            # Upload video via file input
            file_input = self._page.query_selector('input[type="file"]')
            if not file_input:
                # Try alternative selector
                file_input = self._page.query_selector('input[accept="video/*"]')

            if file_input:
                file_input.set_input_files(video_path)
                logger.info("Video file selected")
            else:
                return {"success": False, "error": "Could not find file input element"}

            # Wait for video to process (up to 2 min)
            time.sleep(10)
            logger.info("Waiting for TikTok to process video...")

            # Try to wait for processing indicator to disappear
            try:
                self._page.wait_for_selector(
                    '[class*="upload-success"], [class*="info-progress"]',
                    timeout=120000,
                )
            except Exception:
                logger.warning("Upload progress indicator not found, continuing...")

            time.sleep(5)

            # Enter caption
            caption_editor = self._page.query_selector(
                'div[contenteditable="true"], '
                'div[data-placeholder*="caption"], '
                'div[class*="caption-editor"]'
            )
            if caption_editor:
                caption_editor.click()
                # Clear existing text
                self._page.keyboard.press("Control+A")
                self._page.keyboard.press("Backspace")
                time.sleep(0.5)
                self._page.keyboard.type(full_caption, delay=30)
                logger.info("Caption entered")
            else:
                logger.warning("Caption editor not found")

            time.sleep(2)

            # Click Post / Publish button
            publish_button = self._page.query_selector(
                'button:has-text("Post"), '
                'button:has-text("Publish"), '
                'div[class*="post-button"]'
            )
            if publish_button:
                publish_button.click()
                logger.info("Publish button clicked")
                time.sleep(10)

                return {
                    "success": True,
                    "platform": "tiktok",
                    "caption": full_caption,
                }
            else:
                return {"success": False, "error": "Publish button not found"}

        except Exception as e:
            logger.error(f"TikTok upload error: {e}")
            return {"success": False, "error": str(e)}

    def _do_login(self):
        self.login()

    def manual_login_flow(self):
        """
        Launch visible browser for manual login.
        Use this to create initial session state.
        """
        logger.info("Starting manual TikTok login flow...")
        self.start_browser(headless=False)
        self._page.goto(self.LOGIN_URL, wait_until="networkidle")

        logger.info("Please log in manually in the browser window.")
        logger.info("Press Enter in terminal when done...")
        input("Press Enter after logging in...")

        self.save_auth_state()
        self.close_browser()
        logger.info("TikTok session saved! Future uploads will use this session.")
