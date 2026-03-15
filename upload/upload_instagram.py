"""
Instagram Reels Uploader — Playwright-based video upload.

WARNING: Instagram actively fights automation.
         Selectors may change. For production use, consider the
         Instagram Graph API (requires Facebook App Review).
"""

import time
from pathlib import Path
from typing import Dict
from loguru import logger

from config.settings import settings
from upload.base_uploader import BaseUploader


class InstagramUploader(BaseUploader):
    """Uploads videos as Instagram Reels via browser automation."""

    PLATFORM = "instagram"
    AUTH_STATE_FILE = "instagram_auth.json"

    LOGIN_URL = "https://www.instagram.com/accounts/login/"
    UPLOAD_URL = "https://www.instagram.com/"

    def login(self, username: str = "", password: str = "") -> bool:
        """Login to Instagram."""
        username = username or settings.instagram_username
        password = password or settings.instagram_password

        if not username or not password:
            logger.warning("Instagram credentials not configured.")
            return False

        try:
            self._page.goto(self.LOGIN_URL, wait_until="networkidle", timeout=30000)
            time.sleep(3)

            # Accept cookies if dialog appears
            try:
                self._page.click('button:has-text("Allow"), button:has-text("Accept")',
                                 timeout=3000)
                time.sleep(1)
            except Exception:
                pass

            # Fill login form
            self._page.fill('input[name="username"]', username, timeout=5000)
            self._page.fill('input[name="password"]', password, timeout=5000)

            # Submit
            self._page.click('button[type="submit"]', timeout=5000)
            time.sleep(5)

            # Handle "Save Login Info" and notification popups
            try:
                self._page.click('button:has-text("Not Now")', timeout=5000)
                time.sleep(1)
            except Exception:
                pass
            try:
                self._page.click('button:has-text("Not Now")', timeout=3000)
            except Exception:
                pass

            if "login" not in self._page.url.lower():
                self.save_auth_state()
                logger.info("Instagram login successful")
                return True
            else:
                logger.warning("Instagram login may have failed")
                return False

        except Exception as e:
            logger.error(f"Instagram login failed: {e}")
            return False

    def upload_video(self, video_path: str, caption: str,
                     hashtags: list) -> Dict:
        """
        Upload a video as Instagram Reel.

        Steps:
        1. Navigate to Instagram
        2. Click create (+ icon)
        3. Select file
        4. Configure as Reel
        5. Enter caption
        6. Share
        """
        if not Path(video_path).exists():
            return {"success": False, "error": f"Video not found: {video_path}"}

        full_caption = f"{caption}\n\n{' '.join(hashtags)}"

        try:
            logger.info(f"Uploading to Instagram Reels: {video_path}")

            self._page.goto(self.UPLOAD_URL, wait_until="networkidle", timeout=30000)
            time.sleep(3)

            # Click the "Create" / "New post" button (+ icon in nav)
            create_btn = self._page.query_selector(
                'svg[aria-label="New post"], '
                'a[href*="create"], '
                '[class*="create"]'
            )
            if create_btn:
                create_btn.click()
                time.sleep(2)
            else:
                # Try alternative: direct URL approach
                self._page.goto("https://www.instagram.com/create/style/",
                                wait_until="networkidle", timeout=15000)
                time.sleep(2)

            # Select file via input
            file_input = self._page.query_selector('input[type="file"]')
            if file_input:
                file_input.set_input_files(video_path)
                logger.info("Video file selected")
            else:
                return {"success": False, "error": "Could not find file input"}

            time.sleep(5)

            # Click through the steps (crop, filters, etc.)
            for step_label in ["Next", "Next"]:
                try:
                    self._page.click(f'button:has-text("{step_label}")', timeout=10000)
                    time.sleep(2)
                except Exception:
                    logger.debug(f"'{step_label}' button not found, continuing...")

            # Enter caption on the final screen
            caption_area = self._page.query_selector(
                'textarea[aria-label*="caption"], '
                'div[role="textbox"][contenteditable="true"], '
                'textarea[placeholder*="Write a caption"]'
            )
            if caption_area:
                caption_area.click()
                self._page.keyboard.type(full_caption, delay=20)
                logger.info("Caption entered")
            else:
                logger.warning("Caption area not found")

            time.sleep(2)

            # Click Share / Post
            share_btn = self._page.query_selector(
                'button:has-text("Share"), '
                'button:has-text("Post"), '
                'div[role="button"]:has-text("Share")'
            )
            if share_btn:
                share_btn.click()
                logger.info("Share button clicked")
                time.sleep(10)

                return {
                    "success": True,
                    "platform": "instagram",
                    "caption": full_caption,
                }
            else:
                return {"success": False, "error": "Share button not found"}

        except Exception as e:
            logger.error(f"Instagram upload error: {e}")
            return {"success": False, "error": str(e)}

    def _do_login(self):
        self.login()

    def manual_login_flow(self):
        """Launch visible browser for manual login."""
        logger.info("Starting manual Instagram login flow...")
        self.start_browser(headless=False)
        self._page.goto(self.LOGIN_URL, wait_until="networkidle")

        logger.info("Please log in manually in the browser window.")
        input("Press Enter after logging in...")

        self.save_auth_state()
        self.close_browser()
        logger.info("Instagram session saved!")
