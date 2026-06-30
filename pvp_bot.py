import asyncio
import argparse
import sys
import os
import logging
import random
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BLUE  = "\033[94m"
GREEN = "\033[92m"
RESET = "\033[0m"
GOLD  = "\033[38;5;220m"
RED   = "\033[91m"
class PVPAutomation:
    def __init__(self, headless=False):
        self.headless = headless
        self.browser = None
        self.page = None
        self.dashboard_url = "https://demonicscans.org/game_dash.php"
        self.pvp_url = "https://demonicscans.org/pvp.php"
        self.last_response_status = None

        self.next_state_dict = {
            'pvp_page_wait_for_tokens': 'pvp_page_find_match',
            'pvp_page_find_match': 'match_page_autoplay',
            'match_page_autoplay': 'match_in_progress',
            'match_in_progress': 'match_finished',  # or match_finished based on result
            'match_finished': 'pvp_page'
        }

        self.state_dict = {
            'pvp_page_wait_for_tokens':self.wait_for_tokens,
            'pvp_page_find_match':self.find_and_click_match,
            'match_page_autoplay':self.click_autoplay,
            'match_in_progress':self.wait_for_match_finish,
            'match_finished':self.back_to_pvp
        }


    async def init_browser(self):
        """Initialize Playwright browser"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=self.headless)
        self.page = await self.browser.new_page()

        # Track response status codes
        async def on_response(response):
            if response.status >= 400:
                logger.warning(f"HTTP {response.status}: {response.url}")
                self.last_response_status = response.status

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
                logger.info("Login completed")
            except Exception as e:
                logger.info(f"Could not find login form (might already be logged in): {e}")
        else:
            logger.info("No credentials in ENV, assuming already logged in or session active")
        await asyncio.sleep(2)  # Wait a bit for any redirects or page loads
        # Now navigate to PVP page
        logger.info("Navigating to PVP page...")
        await self.page.goto(self.pvp_url)
        await self.page.wait_for_load_state("networkidle")
        await asyncio.sleep(1)  # Wait a bit for any redirects or page loads
        logger.info("Navigated to PVP page")

    async def get_page_html(self):
        """Get current page HTML"""
        return await self.page.content()

    async def get_page_state(self):
        """Determine current page state by checking what elements are available"""
        try:
            html = await self.get_page_html()
            soup = BeautifulSoup(html, 'html.parser')

            # Check what's on the page
            has_tokens = soup.select_one('div.info-pill:-soup-contains("Tokens")')
            # Find the info-pill that contains "Tokens:" and get its span
            has_find_match = soup.select_one('button.js-matchmake[data-ladder="solo"]')
            has_continue_match = soup.find('a', string="Continue Solo Match")
            # If on pvp page, check tokens and find match button
            if has_tokens and (has_find_match or has_continue_match):
                # check tokens
                if (tokens:= int(has_tokens.find('span').text.strip())) <= 0:
                    return 'pvp_page_wait_for_tokens'
                else:
                    logging.info("%s Tokens available, ready to find match", tokens)
                    return 'pvp_page_find_match'

            # If not above case, then im on match page, check for autoplay button or back button

            has_autoplay = soup.select_one('#autoPlayBtn')
            status_badge = soup.select_one('#matchStatusBadge')

            # match page always autoplay button, if already on autoplay, skip it
            if has_autoplay and has_autoplay.text!="Auto Play On":
                # May need to check autoplay text
                return 'match_page_autoplay'

            if status_badge:
                status = status_badge.text.strip().lower()

                if 'in progress' in status:
                    return 'match_in_progress'

                if 'victory' in status:
                    return 'match_finished'

            return 'unknown_state'

        except Exception as e:
            logger.error(f"Error determining page state: {e}")
            return 'error_state'

    async def safe_click(self, selector, max_attempts=3):
        """Click and reload on 5XX errors"""
        for attempt in range(max_attempts):
            try:
                self.last_response_status = None
                await self.page.click(selector)
                await self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                logger.info(f"Click successful: {selector}")
                return True

            except Exception as e:
                logger.warning(f"Click failed: {e}")
                if self.last_response_status and self.last_response_status >= 500:
                    logger.warning(f"Got HTTP {self.last_response_status}, reloading...")
                    try:
                        await self.page.reload()
                        await self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                        await asyncio.sleep(2)
                    except Exception as reload_error:
                        logger.warning(f"Reload failed: {reload_error}")

                if attempt < max_attempts - 1:
                    await asyncio.sleep(2)
                    continue

        logger.error(f"Failed to click {selector} after {max_attempts} attempts")
        return False

    async def wait_for_tokens(self):
        """Check if tokens > 0, wait 5 minutes if not"""
        await asyncio.sleep(1*60)  # Wait a bit before checking

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

        if token_element:
            try:
                tokens = int(token_element.text.strip())
                return tokens
            except ValueError as ex:
                logger.error(f"Could not parse token value: {token_element.text}")
                raise ex

        raise Exception("Token element not found on page")

    async def find_and_click_match(self):
        """Click on 'Find Solo Match' button"""
        #find in self.page
        has_continue_match = await self.page.query_selector('a:has-text("Continue Solo Match")')
        if has_continue_match:
            logger.info("Continue Solo Match button found, clicking it...")
            if not await self.safe_click('a:has-text("Continue Solo Match")', max_attempts=3):
                return False
        else:
            if not await self.safe_click('button.js-matchmake[data-ladder="solo"]', max_attempts=3):
                return False

        try:
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)  # Give page time to load match
            return True
        except Exception as e:
            logger.error(f"Wait after match click failed: {e}")
            return False

    async def click_autoplay(self):
        """Click autoplay button on match page"""
        return await self.safe_click('#autoPlayBtn', max_attempts=3)

    async def back_to_pvp(self):
        """Click back button to return to PVP page"""

        has_continue_btn = await self.page.query_selector('#continueRewardsBtn')

        # need to check the visibility of the continue button, if visible, click it first
        if has_continue_btn and await has_continue_btn.is_visible():
            logger.info(f"{GOLD}{'='*20} MATCH WON {'='*20}{RESET}")
            await self.safe_click('#continueRewardsBtn', max_attempts=3)
        else:
            logger.info(f"{RED}{'='*20} MATCH LOST {'='*20}{RESET}")
        return await self.safe_click('a.back-btn', max_attempts=3)


    async def wait_for_match_finish(self, max_wait_seconds=600):
        """Wait for match to finish by monitoring matchStatusBadge"""
        logger.info("Waiting for match to finish...")
        # Wait before next check
        await asyncio.sleep(random.randint(5,10))  # Increase wait time gradually

    async def run_loop(self, max_iterations=None):
        """Main automation loop"""
        iteration = 0

        try:
            await self.init_browser()
            await self.login()

            while max_iterations is None or iteration < max_iterations:
                iteration += 1
                logger.info(f"{BLUE}{'='*50}{RESET}")
                logger.info(f"{BLUE}Starting iteration {iteration}{RESET}")
                logger.info(f"{BLUE}{'='*50}{RESET}")

                # Determine current state
                last_state=None
                while True:
                    state = await self.get_page_state()
                    if state!= last_state:
                        last_state=state
                        logger.info(f"Current state: {state}")
                    action = self.state_dict.get(state, None)
                    if action is None:
                        logger.warning(f"No action defined for state: {state}, reloading page...")
                        await self.page.reload()
                        await self.page.wait_for_load_state("domcontentloaded")
                        continue
                    _ = await action()
                    await self.page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(1)  # Wait a bit for any redirects or page loads

                    next_state = self.next_state_dict.get(state, None)
                    if next_state is None:
                        logger.warning(f"No next state defined for state: {state}, breaking loop...")
                        break
                    if next_state == 'pvp_page':
                        break

                logger.info(f"{GREEN}Iteration {iteration} completed{RESET}")

        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)

        finally:
            await self.close_browser()

    def live_match(self):
        """This will run live match! pressing the attack button when ready, and waiting for the match to finish"""
        # Get buttons
        
        # Get available tokens
        
        # Get 
        return False

async def main():
    """Main entry point"""
    # Get credentials from ENV (for future login if needed)
    # username = os.getenv("GAME_USERNAME")
    # password = os.getenv("GAME_PASSWORD")
    parser = argparse.ArgumentParser(description="Run the PVP automation bot")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode"
    )
    args = parser.parse_args(sys.argv[1:])

    automation = PVPAutomation(headless=args.headless)

    # Run for max 100 iterations, or indefinitely if None
    await automation.run_loop(max_iterations=None)


if __name__ == "__main__":
    asyncio.run(main())
