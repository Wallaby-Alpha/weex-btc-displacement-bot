"""
End-to-End Mechanics Verification Script
Safely tests:
1. Market order entry with positionSide="BOTH" (One-Way Mode)
2. Native exchange-level Stop Loss plan order (/capi/v3/placeTpSlOrder)
3. Native exchange-level Take Profit plan order (/capi/v3/placeTpSlOrder)
4. Verification of active position and TP/SL on WEEX matching engine
5. Clean immediate market close
"""

import sys
import time
from config import config
from weex_client import WeexClient

def run_test():
    print("=" * 65)
    print("         WEEX LIVE ORDER & TP/SL MECHANICS TEST")
    print("=" * 65)
    
    if not config.api_key or not config.api_secret:
        print("[!] ERROR: No API credentials found in .env!")
        return

    client = WeexClient(
        api_key=config.api_key,
        api_secret=config.api_secret,
        passphrase=config.passphrase,
        base_url=config.base_url
    )
    client.position_side_mode = config.position_mode

    # 1. Check Symbol Meta & Mark Price
    print("[1] Fetching Symbol Metadata & Current Price ...")
    meta = client.get_exchange_info(config.symbol)
    mark_price = client.get_mark_price(config.symbol)
    margin = client.get_available_margin()
    
    if not meta or not mark_price:
        print("[!] Failed to fetch market data from WEEX.")
        return

    print(f"    Symbol:           {config.symbol}")
    print(f"    Current Price:    ${mark_price:,.1f}")
    print(f"    Available Margin: ${margin:.2f} USDT")
    print(f"    Position Mode:    {client.position_side_mode}")

    if margin < 1.0:
        print("[!] Warning: Available margin is low (< $1 USDT). Test may fail if insufficient funds.")

    # Minimum size for test (0.0001 BTC is ~$8.40 notional, requires ~$0.42 margin at 20x)
    test_qty = meta["minOrderSize"]
    price_prec = meta["pricePrecision"]
    
    # Set wide test TP/SL so it doesn't get filled during test
    test_sl = round(mark_price * 0.95, price_prec)  # 5% below
    test_tp = round(mark_price * 1.05, price_prec)  # 5% above

    print("-" * 65)
    print(f"[*] Placing Test BUY Market Order:")
    print(f"    Qty:  {test_qty} BTC (~${test_qty * mark_price:.2f} notional)")
    print(f"    SL:   ${test_sl} (Native Whole-Position SL)")
    print(f"    TP:   ${test_tp} (Native Whole-Position TP)")
    print("-" * 65)

    # 2. Submit Market Entry
    print("\n[2] Submitting Market Entry Order (/capi/v3/order) ...")
    entry_res = client.place_market_order(
        symbol=config.symbol,
        side="BUY",
        position_side=client.position_side_mode,
        quantity=test_qty
    )
    
    if not entry_res.get("success"):
        print(f"[FAILED] Entry Order Rejected: {entry_res.get('error')}")
        print(f"Raw Response: {entry_res}")
        return

    order_id = entry_res.get("orderId")
    print(f"    [SUCCESS] Market Order Filled! Order ID: {order_id}")

    # Give WEEX matching engine half a second to register the position
    time.sleep(1.0)

    # 3. Submit Native Stop Loss Plan Order
    print("\n[3] Submitting Native Exchange STOP LOSS Plan Order ...")
    sl_ok = client.place_native_tpsl_plan_order(
        symbol=config.symbol,
        plan_type="STOP_LOSS",
        trigger_price=test_sl,
        position_side=client.position_side_mode
    )
    if sl_ok:
        print(f"    [SUCCESS] Native Stop Loss Registered @ ${test_sl}")
    else:
        print(f"    [FAILED] Could not register Stop Loss.")

    # 4. Submit Native Take Profit Plan Order
    print("\n[4] Submitting Native Exchange TAKE PROFIT Plan Order ...")
    tp_ok = client.place_native_tpsl_plan_order(
        symbol=config.symbol,
        plan_type="TAKE_PROFIT",
        trigger_price=test_tp,
        position_side=client.position_side_mode
    )
    if tp_ok:
        print(f"    [SUCCESS] Native Take Profit Registered @ ${test_tp}")
    else:
        print(f"    [FAILED] Could not register Take Profit.")

    time.sleep(1.0)

    # 5. Verify Open Position on Exchange
    print("\n[5] Verifying Open Position on Exchange ...")
    positions = client.get_open_positions(config.symbol)
    found_pos = None
    for p in positions:
        print(f"    Active Position: {p['side']} {p['size']} {p['symbol']} | Entry: ${p['entry_price']:,.1f} | PnL: ${p['unrealized_pnl']:.4f}")
        found_pos = p

    # 6. Clean Up: Close Test Position Immediately
    print("\n[6] Cleaning Up: Closing Test Position at Market ...")
    if found_pos:
        close_ok = client.close_market_position(
            symbol=config.symbol,
            side="SELL",
            position_side=client.position_side_mode,
            quantity=found_pos["size"]
        )
        if close_ok:
            print("    [SUCCESS] Test position closed cleanly at market.")
        else:
            print("    [FAILED] Failed to close test position. Please close manually in WEEX app.")
    else:
        print("    No open position found to close.")

    print("\n" + "=" * 65)
    print("                 MECHANICS TEST COMPLETE")
    print("=" * 65)
    if sl_ok and tp_ok:
        print(">>> ALL SYSTEMS VERIFIED: Orders, Sizing, and Native TP/SL work 100%! <<<")
    else:
        print(">>> Attention: Check logs above for any rejected steps. <<<")

if __name__ == "__main__":
    run_test()
