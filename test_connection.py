"""
Diagnostic verification script for WEEX API Connectivity
Run this before starting the bot to confirm API keys and market access.
"""

import sys
from config import config
from weex_client import WeexClient

def test_connection():
    print("=" * 60)
    print("           WEEX API CONNECTION DIAGNOSTIC")
    print("=" * 60)
    print(f"Base URL: {config.base_url}")
    print(f"Symbol:   {config.symbol}")
    print(f"Mode:     {'DRY RUN' if config.dry_run else 'LIVE'}")
    print("-" * 60)

    client = WeexClient(
        api_key=config.api_key,
        api_secret=config.api_secret,
        passphrase=config.passphrase,
        base_url=config.base_url
    )

    # 1. Public Exchange Info
    print("[1] Testing Public Exchange Info ... ", end="", flush=True)
    meta = client.get_exchange_info(config.symbol)
    if meta:
        print("OK")
        print(f"    Contract Val: {meta['contractVal']}")
        print(f"    Min Order Size: {meta['minOrderSize']} BTC")
        print(f"    Price Precision: {meta['pricePrecision']}")
        print(f"    Qty Precision: {meta['quantityPrecision']}")
    else:
        print("FAILED")
        print(f"    Could not load symbol metadata for {config.symbol}!")
        return

    # 2. Public Klines
    print("[2] Testing 1m Klines Endpoint ... ", end="", flush=True)
    klines = client.get_klines(config.symbol, interval="1m", limit=5)
    if klines and len(klines) > 0:
        print(f"OK ({len(klines)} bars received)")
        latest = klines[-1]
        print(f"    Latest 1m Bar: Close={latest['close']}, High={latest['high']}, Low={latest['low']}")
    else:
        print("FAILED")

    # 3. Mark Price
    print("[3] Testing Mark Price ... ", end="", flush=True)
    mp = client.get_mark_price(config.symbol)
    if mp:
        print(f"OK (${mp:,.1f})")
    else:
        print("FAILED")

    # 4. Private Account Authentication (if keys provided)
    if config.api_key and config.api_secret:
        print("[4] Testing Private Account Auth & Balance ... ", end="", flush=True)
        try:
            balance = client.get_available_margin()
            print(f"OK (${balance:.2f} USDT available)")
        except Exception as e:
            print(f"FAILED ({e})")

        print("[5] Checking Existing Positions ... ", end="", flush=True)
        try:
            positions = client.get_open_positions(config.symbol)
            print(f"OK ({len(positions)} active positions)")
            for p in positions:
                print(f"    {p['side']} {p['size']} {p['symbol']} @ {p['entry_price']}")
        except Exception as e:
            print(f"FAILED ({e})")
    else:
        print("[4] Private Auth: SKIPPED (No API keys provided in .env - running in public test mode)")

    print("=" * 60)
    print("Diagnostic complete!")

if __name__ == "__main__":
    test_connection()
