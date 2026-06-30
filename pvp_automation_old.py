import asyncio
import os
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import re

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PVPAutomation:
    def __init__(self, headless=False):
        self.headless = headless
        self.browser = None
        self.page = None
        self.dashboard_url = "https://demonicscans.org/game_dash.php"
        self.pvp_url = "https://demonicscans.org/pvp.php"
        self.last_response_status = None

    async def init_browser(self):
        """Initialize Playwright browser"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=self.headless)
        self.page = await self.browser.new_page()

        # Track response status codes
        async def on_response(response):
            self.last_response_status = response.status
            if response.status >= 400:
                logger.warning(f"HTTP {response.status}: {response.url}")

        self.page.on("response", on_response)

        logger.info("Browser initialized")

    async def close_browser(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()
            logger.info("Browser closed")

    async def login(self):
        """Navigate to dashboard first, then PVP page"""
        logger.info("Navigating to game dashboard...")
        await self.page.goto(self.dashboard_url)
        await self.page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        logger.info("Dashboard loaded, checking if login required...")

        # Check if we're still on login page (adjust selector as needed)
        html = await self.get_page_html()

        # If you need to log in, credentials should come from ENV
        username = os.getenv("GAME_USERNAME")
        password = os.getenv("GAME_PASSWORD")

        if username and password:
            try:
                # Try to find and fill login form (adjust selectors as needed)
                await self.page.fill('input[name="email"]', username, timeout=5000)
                await self.page.fill('input[name="password"]', password, timeout=5000)
                await self.page.click('input[name="submit"]')
                await self.page.wait_for_load_state("networkidle")
                await asyncio.sleep(2)  # Give time for any redirects
                logger.info("Login completed")
            except Exception as e:
                logger.info(f"Could not find login form (might already be logged in): {e}")
        else:
            logger.info("No credentials in ENV, assuming already logged in or session active")

        # Now navigate to PVP page
        logger.info("Navigating to PVP page...")
        await self.page.goto(self.pvp_url)
        await self.page.wait_for_load_state("networkidle")
        await asyncio.sleep(1)  # Give time for any redirects

        logger.info("Navigated to PVP page")

    async def get_page_html(self):
        """Get current page HTML"""
        return await self.page.content()

    async def check_for_error(self):
        """Check if page has HTTP error or error content"""
        html = await self.get_page_html()

        # Check for common error indicators
        error_indicators = [
            '404',
            'page not found',
            # 'error',
            'cloudflare',
            'cf_clearance'
        ]

        # Check last HTTP status
        if self.last_response_status and self.last_response_status < 400:
            return False
        
        logger.warning(f"Got HTTP {self.last_response_status}")
        return True

        # html_lower = html.lower()
        # for indicator in error_indicators:
        #     if indicator in html_lower:
        #         logger.warning(f"Error page detected: {indicator}")
        #         return True

        # return False

    async def safe_click(self, selector, retry_count=3, delay=2):
        """Click with retry logic for transient errors"""
        for attempt in range(retry_count):
            try:
                self.last_response_status = None
                await self.page.click(selector)

                # Wait for page to stabilize before checking for errors
                try:
                    await self.page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    # If networkidle times out, try domcontentloaded
                    await self.page.wait_for_load_state("domcontentloaded", timeout=5000)

                await asyncio.sleep(2)

                # Check if we got an error
                if await self.check_for_error():
                    logger.warning(f"Error detected (4xx/5xx), reloading page... (attempt {attempt + 1}/{retry_count})")
                    # Reload the page instead of just retrying the click
                    await self.page.wait_for_load_state("networkidle", timeout=10000)
                    await self.page.reload()
                    await self.page.wait_for_load_state("networkidle", timeout=10000)
                    await asyncio.sleep(delay)
                    # Check if reload fixed the error

                    if await self.check_for_error():
                        logger.info("Page reload unsuccessful")
                        continue

                logger.info(f"Click successful: {selector}")
                return True

            except Exception as e:
                logger.warning(f"Click failed: {e}, reloading page and retrying... (attempt {attempt + 1}/{retry_count})")
                try:
                    await self.page.reload()
                    await self.page.wait_for_load_state("networkidle", timeout=10000)
                except Exception as reload_error:
                    logger.warning(f"Reload failed: {reload_error}")
                await asyncio.sleep(delay)

        logger.error(f"Failed to click {selector} after {retry_count} attempts")
        return False

    async def check_tokens(self):
        """Check if tokens > 0, wait 5 minutes if not"""

        html = await self.get_page_html()
        soup = BeautifulSoup(html, 'html.parser')

        # Find the info-pill that contains "Tokens:" and get its span
        info_pills = soup.find_all('div', class_='info-pill')
        token_element = None

        for pill in info_pills:
            if 'Tokens:' in pill.text:
                token_element = pill.find('span')
                break
        tokens=0
        if token_element:
            try:
                tokens = int(token_element.text.strip())
            except ValueError:
                logger.error(f"Could not parse token value: {token_element.text}")
        else:
            logger.error("Could not find tokens element")

        return tokens

    async def find_and_click_match(self):
        """Click on 'Find Solo Match' button"""
        if not await self.safe_click('button.js-matchmake[data-ladder="solo"]', retry_count=3):
            return False
        try:
            logger.info("Clicked 'Find Solo Match'")
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(.5)  # Give page time to load match
            return True
        except Exception as e:
            logger.error(f"Wait after match click failed: {e}")
            return False

    async def click_autoplay(self):
        """Click autoplay button on match page"""
        return await self.safe_click('#autoPlayBtn', retry_count=3)

    async def wait_for_match_finish(self, max_wait_seconds=600):
        """Wait for match to finish by monitoring matchStatusBadge"""
        logger.info("Waiting for match to finish...")
        start_time = datetime.now()

        while True:
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > max_wait_seconds:
                raise asyncio.TimeoutError(f"Match took too long (>{max_wait_seconds}s), timing out")

            html = await self.get_page_html()
            soup = BeautifulSoup(html, 'html.parser')

            # Look for matchStatusBadge by ID
            status_badge = soup.select_one('#matchStatusBadge')

            if status_badge:
                status_text = status_badge.text.strip().lower()
                logger.info(f"Match status: {status_text}")

                # Check if match is finished (contains "victory")
                if 'victory' in status_text:
                    logger.info(f"Match finished! Result: {status_text}")
                    return True if "allied" in status_text.lower() else False
                elif 'in progress' in status_text or status_text == '':
                    logger.debug("Match in progress, waiting...")
                else:
                    logger.debug(f"Unknown status: {status_text}")

            # Wait before next check. Create a random int between 5 and 10 seconds to avoid detection
            await asyncio.sleep(5 + (elapsed % 5))  # Sleep 5-10 seconds

    async def click_on_continue_button(self):
        """Process victory by clicking continue button"""
        return await self.safe_click('#continueRewardsBtn', retry_count=3)

    async def click_back_button(self):
        """Click back button to return to PVP page"""
        if not await self.safe_click('a.back-btn', retry_count=3):
            return False
        try:
            logger.info("Clicked back button")
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)
            return True
        except Exception as e:
            logger.error(f"Wait after back click failed: {e}")
            return False

    async def run_loop(self, max_iterations=None):
        """Main automation loop"""
        iteration = 0

        try:
            await self.init_browser()
            await self.login()

            while max_iterations is None or iteration < max_iterations:
                iteration += 1
                logger.info(f"\n{'='*50}")
                logger.info(f"Starting iteration {iteration}")
                logger.info(f"{'='*50}")

                # Check tokens
                tokens = await self.check_tokens()
                if tokens <= 0:
                    logger.warning("No tokens available, waiting 5 minutes...")
                    await asyncio.sleep(300)  # Wait 5 minutes
                    continue


                # Find and click match
                if not await self.find_and_click_match():
                    logger.error("Failed to find match, retrying...")
                    continue

                # Click autoplay
                if not await self.click_autoplay():
                    logger.error("Failed to click autoplay, retrying...")
                    continue

                # Wait for match to finishUnable to retrieve content because 
                winner=False
                try:
                    winner = await self.wait_for_match_finish()
                except asyncio.TimeoutError:
                    logger.warning("Match wait timed out")

                if winner:
                    await self.click_on_continue_button()

                # Click back
                if not await self.click_back_button():
                    logger.error("Failed to click back, but continuing...")

                logger.info(f"Iteration {iteration} completed")

        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)

        finally:
            await self.close_browser()


async def main():
    """Main entry point"""
    # Get credentials from ENV (for future login if needed)
    # username = os.getenv("GAME_USERNAME")
    # password = os.getenv("GAME_PASSWORD")

    automation = PVPAutomation(headless=False)  # Set to True for headless mode

    # Run for max 100 iterations, or indefinitely if None
    await automation.run_loop(max_iterations=None)


if __name__ == "__main__":
    asyncio.run(main())