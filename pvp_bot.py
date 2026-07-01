import asyncio
import argparse
from collections import defaultdict
import sys
import os
import logging
import random
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

    STRATEGY_HANDLERS = {
        "balanced_skills": "_strategy_balanced_skills",
        "custom": "_strategy_custom",
    }

    def __init__(self, headless=False, autoplay=False, strategy="balanced_skills", allowed_buttons=None):
        self.headless = headless
        self.autoplay = autoplay
        self.strategy = strategy
        self.allowed_buttons = set(allowed_buttons or [])
        self.browser = None
        self.page = None
        self.dashboard_url = "https://demonicscans.org/game_dash.php"
        self.pvp_url = "https://demonicscans.org/pvp.php"
        self.last_response_status = None
        self.next_state_dict = {
            'pvp_page_wait_for_tokens': 'pvp_page_find_match',
            'pvp_page_find_match': 'match_page_autoplay',
            'match_page_autoplay': 'match_in_progress',
            'match_fast_enemy': 'match_in_progress',
            'match_in_progress': 'match_finished',  # or match_finished based on result
            'match_finished': 'pvp_page'
        }

        self.state_dict = {
            'pvp_page_wait_for_tokens':self.wait_for_tokens,
            'pvp_page_find_match':self.find_and_click_match,
            'match_page_autoplay':self.click_autoplay,
            'match_fast_enemy':self.click_fastenemy,
            'match_in_progress':self.match_in_progress,
            'match_finished':self.back_to_pvp
        }

        handler_name = self.STRATEGY_HANDLERS.get(self.strategy, self.STRATEGY_HANDLERS["balanced_skills"])
        self.strategy_handler = getattr(self, handler_name)
        self.available_buttons=[]
        self.buttons_info=None
        self.win_loss_counter=defaultdict(int)

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

            autoplay_btn = soup.select_one('#autoPlayBtn')
            quick_enemy_btn = soup.select_one('#fastEnemyBtn')
            status_badge = soup.select_one('#matchStatusBadge')

            # here depends if we are in autoplay mode or bot mode, if bot mode, we will not click autoplay, but if autoplay is off, we will click it
            if not self.autoplay and quick_enemy_btn and not quick_enemy_btn.text.lower().endswith("on"):
                return 'match_fast_enemy'

            # match page always autoplay button, if already on autoplay, skip it
            if self.autoplay and autoplay_btn and not autoplay_btn.text.lower().endswith("on"):
                # May need to check autoplay text
                return 'match_page_autoplay'

            #TODO: probably good to go back to in_progress_loop instead of comming here on every decision

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

    async def click_fastenemy(self):
        """Click autoplay button on match page"""

        return await self.safe_click('#fastEnemyBtn', max_attempts=3)

    async def get_buttons_info(self):
        self.available_buttons = await self.get_available_skill_buttons()
        allowed_buttons = [btn for btn in self.available_buttons if self._button_allowed(await btn.inner_text())]
        buttons_info = []
        for btn in allowed_buttons:
            buttons_info.append(await self._get_button_info(btn))
        self.buttons_info = buttons_info  # Store for later use in bot_play

    async def back_to_pvp(self):
        """Click back button to return to PVP page"""

        has_continue_btn = await self.page.query_selector('#continueRewardsBtn')

        # need to check the visibility of the continue button, if visible, click it first
        if has_continue_btn and await has_continue_btn.is_visible():
            logger.info(f"{GOLD}{'='*20} MATCH WON {'='*20}{RESET}")
            self.win_loss_counter['wins'] += 1
            await self.safe_click('#continueRewardsBtn', max_attempts=3)
        else:
            logger.info(f"{RED}{'='*20} MATCH LOST {'='*20}{RESET}")
            self.win_loss_counter['loss'] += 1
        return await self.safe_click('a.back-btn', max_attempts=3)


    async def match_in_progress(self, max_wait_seconds=600):
        """Wait for match to finish by monitoring matchStatusBadge"""
        if self.autoplay:
            logger.info("Waiting for match to finish...")
            return await asyncio.sleep(random.randint(5,10))

        return await self.bot_play()



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

                logger.info(f"{GREEN}Iteration {iteration} completed{RESET} - {GOLD}Wins: {self.win_loss_counter['wins']} - {RED} Losses: {self.win_loss_counter['loss']}{RESET}")

        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)

        finally:
            await self.close_browser()

    @staticmethod
    def _normalize_button_name(value):
        return " ".join((value or "").strip().lower().split())

    def _button_allowed(self, button_name):
        if self._normalize_button_name(button_name) == "slash":
            return True
        if not self.allowed_buttons:
            return True
        normalized_allowed = {self._normalize_button_name(btn) for btn in self.allowed_buttons}
        return self._normalize_button_name(button_name) in normalized_allowed

    async def _get_button_info(self, btn):
        text = (await btn.inner_text() or "").strip()
        skill_name = text.splitlines()[0].strip() if text else ""

        skill_id_raw = await btn.get_attribute('data-skill-id')
        if skill_id_raw is None:
            skill_id_raw = await btn.get_attribute('data-skill')

        skill_id = None
        if skill_id_raw is not None:
            try:
                skill_id = int(skill_id_raw)
            except ValueError:
                skill_id = skill_id_raw

        cost_raw = await btn.get_attribute('data-cost')
        resource_cost_raw = await btn.get_attribute('data-resource-cost')
        requires_full_resource_raw = await btn.get_attribute('data-requires-full-resource')

        cost = int(cost_raw) if cost_raw and cost_raw.isdigit() else 0
        resource_cost = int(resource_cost_raw) if resource_cost_raw and resource_cost_raw.isdigit() else 0
        requires_full_resource = requires_full_resource_raw == "1"

        return {
            "button": btn,
            "skill_name": skill_name,
            "skill_id": skill_id,
            "cost": cost,
            "resource_cost": resource_cost,
            "requires_full_resource": requires_full_resource,
        }


    async def _strategy_balanced_skills(self, buttons_info, available_tokens, resource=0):
        # adds dinamic attrs, for balanced strategy only
        if not hasattr(self, "_last_used_skill_index"):
            self._last_used_skill_index = -1
            self.skills_counter = defaultdict(int)

        #skills goes from 1 to n, 0 is always slash, which is free and always allowed

        btns = buttons_info[1:] if buttons_info else buttons_info # Exclude Slash (index 0)
        current_index = (self._last_used_skill_index + 1) % len(btns)   
        #Check cost for current index
        if btns[current_index]["cost"] >= available_tokens:
            # if not enough.. use slash which is free
            logger.info(f"Not enough tokens for '{btns[current_index]['skill_name']}'skill with cost {btns[current_index]['cost']}, using 'Slash' instead")
            return buttons_info[0]

        # if enough, use the skill and update last used index
        self._last_used_skill_index = current_index
        # logger.info(f"Choosing skill '{btns[current_index]['skill_name']}' with cost {btns[current_index]['cost']}")
        self.skills_counter[btns[current_index]['skill_name']] += 1
        return btns[current_index]

    async def _strategy_custom(self, buttons_info, available_tokens, resource=0):
        # Placeholder behavior until custom strategy rules are implemented.
        logger.info("Strategy 'custom' is a placeholder and currently redirects to 'balanced_skills'")
        return await self._strategy_balanced_skills(buttons_info, available_tokens, resource)

    async def get_resources(self):
        """Get current tokens and resource values"""
        tokens_element = await self.page.query_selector('#myTokens')
        resource_element = await self.page.query_selector('#myResource')

        available_tokens = 0
        if tokens_element:
            try:
                available_tokens = int((await tokens_element.text_content() or "0").strip())
            except ValueError:
                logger.warning("Could not parse token count from #myTokens")

        resource = 0
        if resource_element:
            resource_text = (await resource_element.text_content() or "").strip()
            digits_only = "".join(ch for ch in resource_text if ch.isdigit())
            if digits_only:
                resource = int(digits_only)

        return available_tokens, resource

    async def get_turn_side(self):
        """Get current turn side (player or enemy)"""
        turn_side_element = await self.page.query_selector('#turnMeta')
        side,slot= None, None
        if turn_side_element:
            text = (await turn_side_element.text_content() or "").strip().lower()
            side, *rest, slot = text.split(' ')
        return side, slot

    async def get_available_skill_buttons(self):
        """Get all available skill buttons on the match page"""
        skill_buttons = await self.page.query_selector_all('button.skillCard')
        available_buttons = []
        for btn in skill_buttons:
            available_buttons.append(btn)
        return available_buttons

    async def bot_play(self):
        """This will run live match! pressing the attack button when ready, and waiting for the match to finish"""

        available_tokens, available_resources = await self.get_resources()
        turn, side = await self.get_turn_side()
        attack_btn = await self.page.query_selector('#attackBtn')

        if not self.buttons_info:
            await self.get_buttons_info()

        if 'allied' in (turn or '').lower() and not await attack_btn.is_enabled():
            logger.info("Waiting for turn to be 'Allied' and attack button to be enabled...")
            await asyncio.sleep(1)
            return False

        if not attack_btn or not await attack_btn.is_enabled():
            logger.info("Attack button is not enabled, waiting for next turn...")
            await asyncio.sleep(0.5)
            return False

        #turn should be 'Allied'
        logger.info("Attack button is enabled, clicking it...")
        await self.safe_click('#attackBtn', max_attempts=3)
        await self.page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(0.5)  # Wait a bit for any redirects or page loads



        selected_button = await self.strategy_handler(self.buttons_info, available_tokens, available_resources)

        if selected_button is None:
            logger.error("No skill buttons available to click, skipping turn")
            return False

        # use button data-skill-id or data-skill attribute to click the button
        await self.safe_click(f"button[data-skill-id='{selected_button['skill_id']}']", max_attempts=3)
        logger.info(f"Clicked skill button '{selected_button['skill_name']}' with cost {selected_button['cost']} and resource cost {selected_button['resource_cost']}")
        await self.page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(0.5)  # Wait a bit for any redirects or page loads
        return True

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
    parser.add_argument(
        "--autoplay",
        action="store_true",
        help="Use autoplay while match is in progress. By default, bot-play is used"
    )
    parser.add_argument(
        "--strategy",
        default="balanced_skills",
        choices=sorted(PVPAutomation.STRATEGY_HANDLERS.keys()),
        help="Button selection strategy for bot-play mode (default). balanced_skills tries to use all skills over time (helpful for achievements). custom is a placeholder that currently redirects to balanced_skills"
    )
    parser.add_argument(
        "--allowed-buttons",
        nargs="*",
        default=[],
        help="Allowed skill buttons (space or comma separated). Slash is always allowed"
    )
    args = parser.parse_args(sys.argv[1:])

    allowed_buttons = set()
    for value in args.allowed_buttons:
        allowed_buttons.update(part.strip() for part in value.split(',') if part.strip())

    automation = PVPAutomation(
        headless=args.headless,
        autoplay=args.autoplay,
        strategy=args.strategy,
        allowed_buttons=allowed_buttons,
    )

    logger.info(
        "Configuration: autoplay=%s strategy=%s allowed_buttons=%s",
        args.autoplay,
        args.strategy,
        sorted(allowed_buttons) if allowed_buttons else "ALL (Slash always allowed)",
    )

    # Run for max 100 iterations, or indefinitely if None
    await automation.run_loop(max_iterations=None)


if __name__ == "__main__":
    asyncio.run(main())
