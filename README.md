# WEEX BTC Intraday Displacement Trading Bot

Automated quantitative execution bot for **BTC/USDT** perpetual contracts on WEEX V3, designed to capture institutional continuation momentum off key market liquidity gates.

## Strategy Summary
* **Target Windows (UTC):**
  * `08:03 UTC` (London Cash Open + 8h Funding)
  * `13:33 UTC` (New York Cash Open / NYO)
  * `16:03 UTC` (European Close / US Midday + 8h Funding)
  * `00:03 UTC` (Daily 1D Open / Asia + 8h Funding)
* **Scan Window:** 30 minutes from each session start.
* **Trade Limit:** Max 1 trade per session window.
* **Displacement Rule:** 1-minute candle body $\ge 1.5 \times \text{ATR}(14)$ with body comprising $\ge 65\%$ of total candle range.
* **Fixed Dollar Risk:** Configured to risk **$1.00 USD** per trade by dynamically sizing the contract quantity:
  $$\text{Position Size (BTC)} = \frac{\text{Dollar Risk (\$1.00)}}{\text{Stop Loss Distance (\$)}} = \frac{1.00}{\text{ATR}_{14}}$$
* **Reward : Risk:** 1.5 : 1 (Take Profit = $\text{Entry} \pm 1.5 \times \text{Risk}$).
* **Max Hold Timeout:** 60 minutes.

---

## Project Structure

```
weex-btc-displacement-bot/
├── bot.py                  # Core trading engine & 1m event loop
├── weex_client.py          # WEEX V3 Contract API client (HMAC SHA-256)
├── strategy.py             # Math, ATR, displacement detection & $1 sizing
├── config.py               # Environment configuration loader
├── test_connection.py      # Diagnostic script to verify API keys & market feeds
├── weex-bot.service        # systemd unit file for 24/7 background running
├── deploy.sh               # One-click Ubuntu / DigitalOcean droplet installer
├── Dockerfile              # Containerized deployment
├── docker-compose.yml      # Docker compose configuration
├── requirements.txt        # Lightweight dependencies (requests, python-dotenv)
├── .env.example            # Environment template
└── .gitignore
```

---

## Step 1: Push to Your GitHub Repository

In your terminal (inside the bot directory):

```bash
cd weex-btc-displacement-bot
git init
git add .
git commit -m "Initial commit of WEEX BTC Displacement Bot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

*(Note: `.env` is included in `.gitignore`, ensuring your API keys are never exposed on GitHub).*

---

## Step 2: Set Up DigitalOcean Droplet

1. Go to [DigitalOcean](https://cloud.digitalocean.com/) and create a new **Droplet**:
   * **OS:** Ubuntu 22.04 LTS or 24.04 LTS
   * **Plan:** Basic ($4 - $6/month is plenty)
   * **Region:** Any low-latency region (e.g. New York, Frankfurt, or Singapore)
   * **Authentication:** SSH Key or Password
2. SSH into your droplet:
   ```bash
   ssh root@YOUR_DROPLET_IP
   ```

---

## Step 3: Clone & Deploy on the Droplet

On your droplet, run:

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git weex-btc-displacement-bot
cd weex-btc-displacement-bot
chmod +x deploy.sh
./deploy.sh
```

---

## Step 4: Configure Your WEEX API Keys

Edit the newly created `.env` file on your droplet:

```bash
nano .env
```

Fill in your WEEX contract API credentials:

```ini
WEEX_API_KEY=your_actual_api_key
WEEX_API_SECRET=your_actual_api_secret
WEEX_PASSPHRASE=your_actual_passphrase
WEEX_BASE_URL=https://api-contract.weex.com

SYMBOL=BTCUSDT
DOLLAR_RISK=1.00
REWARD_RISK_RATIO=1.5
LEVERAGE=20

# Start in DRY_RUN=true first to observe live simulated logs!
DRY_RUN=true
```

Press `Ctrl + O` then `Enter` to save, and `Ctrl + X` to exit.

---

## Step 5: Test Connection

Verify that your droplet can communicate with WEEX and authenticate your keys:

```bash
python3 test_connection.py
```

You should see:
```
[1] Testing Public Exchange Info ... OK
[2] Testing 1m Klines Endpoint ... OK
[3] Testing Mark Price ... OK
[4] Testing Private Account Auth & Balance ... OK ($XX.XX USDT available)
```

---

## Step 6: Start the Bot 24/7 (systemd)

Start the bot as a background service:

```bash
# Start service
sudo systemctl start weex-bot

# Check service status
sudo systemctl status weex-bot

# Monitor live output logs
sudo journalctl -u weex-bot -f
```

To stop or restart:
```bash
sudo systemctl restart weex-bot
sudo systemctl stop weex-bot
```

---

## Alternative: Run via Docker

If you prefer Docker:

```bash
docker compose up -d
docker compose logs -f
```
