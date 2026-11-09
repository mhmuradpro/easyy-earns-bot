# Easyy Earns Telegram Mini App starter

## Included
- Green/dark Mini App dashboard
- Telegram bot `/start` with a Web App button
- Telegram `initData` signature verification on the server
- SQLite user records, referral links, balance display, withdrawal requests
- Admin `/addbalance USER_ID AMOUNT` command
- Safe placeholder for rewarded ads

## Important ad-policy notes
- Adsterra Popunder is not a rewarded-ad format. Never credit users for viewing/clicking it or force popunders.
- Only add AdsGram rewards after your account is approved for the relevant product and you have the current official integration instructions and reward callback verification.
- The starter intentionally does not fake ad views or automatically grant ad rewards.

## Setup
1. Create a Telegram bot with @BotFather.
2. Host this project on a Python web service with HTTPS.
3. Set environment variables:
   - `BOT_TOKEN`: secret token from BotFather
   - `BOT_USERNAME`: Easyy_Earns_bot (without @)
   - `WEBAPP_URL`: public HTTPS URL of this app
   - `ADMIN_ID`: your numeric Telegram user ID
4. Install dependencies: `pip install -r requirements.txt`
5. Run: `python app.py`
6. In @BotFather, use `/setdomain` and set the domain of your HTTPS app URL (domain only, as prompted).
7. Open your bot and press Start, then tap Open Easyy Earns.

## Admin
Send `/addbalance USER_ID AMOUNT` from the Telegram account whose numeric ID is in `ADMIN_ID`.
This is a manual admin credit for testing/legitimate funded rewards, not ad verification.

## Production checklist
- Use a persistent disk/managed database; ephemeral hosting can erase SQLite data.
- Add withdrawal review/approval tooling before real payouts.
- Add rate limits, audit logs, privacy policy, terms, and abuse prevention.
- Never share BOT_TOKEN or put it in frontend HTML/JavaScript.
- Use a verified provider callback with signature/transaction checks before issuing any ad reward.
