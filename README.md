PVP Automation Script
Automated PVP farming for online games using Playwright and BeautifulSoup.

Setup
Install dependencies:

pip install -r requirements.txt
playwright install chromium
Set environment variables for login (if needed):

# Windows PowerShell:

$env:GAME_USERNAME = "your_username"
$env:GAME_PASSWORD = "your_password"
If you omit these, the script assumes you're already logged in via an active session/cookies.

Usage
python ==pvp_bot==.py
The script will:

Open a browser and navigate to the PVP page
Loop indefinitely through PVP matches
Check tokens before each match
Wait 5 minutes if tokens are depleted
Automatically play matches and return to start
What You Need to Customize

1. Token Selector (IMPORTANT)
   The script tries to find tokens with this selector:

token_element = soup.select_one('[class*="token"]')
You need to inspect the PVP page and find the actual token element:

Open https://demonicscans.org/pvp.php in your browser
Press F12 (Developer Tools)
Find the token display element (right-click → Inspect)
Update the selector in the script
Example: If the token element has id="tokens", change to:

token_element = soup.select_one('#tokens')
2. Button Selectors
The script looks for buttons by text:

"Find Solo Match"
"Autoplay"
"Back"
If these exact button texts don't exist, update them in the script. You can use:

button:has-text("exact button text") - for text match
#button_id - for ID
.button_class - for class
[data-action="match"] - for data attributes
3. matchStatusBadge Selector
The script currently looks for:

status_badge = soup.select_one('[class*="matchStatusBadge"], #matchStatusBadge')
Verify this element exists and update if needed. The script expects statuses like:

"In progress"
"Allies victory" / "Enemy victory"
Or any text containing "victory"
4. Login (if needed)
The script already handles login via game dashboard:

Navigates to https://demonicscans.org/game_dash.php first
If credentials are in ENV vars, logs in automatically
Then navigates to the PVP page
If the login form selectors are different, update these in the login() method:

await self.page.fill('input[name="username"]', username)
await self.page.fill('input[name="password"]', password)
await self.page.click('button[type="submit"]')
Look for the actual input and button names on the dashboard page and update them accordingly.

Debugging Tips
See what's happening: Set headless=False in the script to watch the browser
Inspect elements: Use the --debug flag or take screenshots:
await self.page.screenshot(path="debug.png")
Check logs: The script logs everything. Look for "Match status" and error messages
Example Output
2026-06-28 10:30:45 - INFO - Browser initialized
2026-06-28 10:30:50 - INFO - Navigated to PVP page
2026-06-28 10:30:51 - INFO - ==================================================
2026-06-28 10:30:51 - INFO - Starting iteration 1
2026-06-28 10:30:51 - INFO - ==================================================
2026-06-28 10:30:52 - INFO - Tokens available: 42
2026-06-28 10:30:52 - INFO - Clicked 'Find Solo Match'
2026-06-28 10:30:53 - INFO - Clicked autoplay
2026-06-28 10:30:53 - INFO - Waiting for match to finish...
2026-06-28 10:30:58 - DEBUG - Match in progress, waiting...
2026-06-28 10:31:03 - DEBUG - Match in progress, waiting...
2026-06-28 10:31:08 - INFO - Match finished! Result: allies victory
2026-06-28 10:31:08 - INFO - Clicked back button
Troubleshooting
Issue	Solution
"Failed to find/click 'Find Solo Match'"	Update the button selector in the script
Script hangs at token check	Verify the token selector is correct
Match never finishes	Check if matchStatusBadge exists; verify status text values
Browser keeps opening/closing	Set headless=True to run in background
Next Steps
Inspect the PVP page to find the exact selectors for tokens and buttons
Update the relevant selectors in the script
Run with headless=False first to debug and watch behavior
Once working, set headless=True to run it in the background