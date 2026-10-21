import time
import signal
import sys
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from config import config
from weex_client import WeexClient
from strategy import DisplacementStrategy

# Configure Logging
logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("weex_bot.engine")

class WEEXDisplacementBot:
    def __init__(self):
        self.client = WeexClient(
            api_key=config.api_key,
            api_secret=config.api_secret,
            passphrase=config.passphrase,
            base_url=config.base_url
        )
        self.symbol = config.symbol
        self.symbol_meta: Optional[Dict[str, Any]] = None
        
        # State tracking
        self.running = True
        self.current_session_id: Optional[str] = None
        self.trades_in_current_session: int = 0
        self.active_trade: Optional[Dict[str, Any]] = None
        self.last_evaluated_timestamp: int = 0

        # Handle system shutdown signals (for systemd / docker)
        signal.signal(signal.SIGINT, self._handle_exit)
        signal.signal(signal.SIGTERM, self._handle_exit)

    def _handle_exit(self, signum, frame):
        logger.info("[*] Shutdown signal received. Exiting gracefully...")
        self.running = False

    def initialize(self) -> bool:
        logger.info("=" * 60)
        logger.info(f"[*] Starting WEEX 1m Displacement Bot [{self.symbol}]")
        logger.info(f"[*] Mode: {'DRY RUN (Simulated)' if config.dry_run else 'LIVE TRADING ($1 Risk)'}")
        logger.info(f"[*] Target Sessions (UTC): {config.target_sessions}")
        logger.info(f"[*] Risk per Trade: ${config.dollar_risk:.2f} | R:R Target: {config.reward_risk_ratio}:1")
        logger.info(f"[*] Displacement Filter: Body >= {config.k_atr}x ATR(14), Conviction >= {config.min_body_ratio*100:.0f}%")
        logger.info("=" * 60)

        # 1. Fetch Symbol Metadata
        self.symbol_meta = self.client.get_exchange_info(self.symbol)
        if not self.symbol_meta:
            logger.error(f"[!] Unable to load exchange specifications for {self.symbol}. Halting.")
            return False

        logger.info(f"[+] Loaded {self.symbol} metadata: minOrderSize={self.symbol_meta['minOrderSize']}, pricePrecision={self.symbol_meta['pricePrecision']}, qtyPrecision={self.symbol_meta['quantityPrecision']}")

        # 2. If Live Mode, verify account connectivity and set leverage
        if not config.dry_run:
            margin = self.client.get_available_margin()
            logger.info(f"[+] Available USDT Balance: ${margin:.2f}")
            if margin <= 0:
                logger.warning("[!] Available margin is 0 USDT. Ensure account is funded.")
            
            # Set leverage
            self.client.set_leverage(self.symbol, config.leverage)
            logger.info(f"[+] Leverage set to {config.leverage}x isolated.")

            # Check existing positions
            positions = self.client.get_open_positions(self.symbol)
            if positions:
                logger.warning(f"[!] Found existing active position on {self.symbol}: {positions[0]}")
                self.active_trade = {
                    "side": positions[0]["side"],
                    "entry_time": time.time(),
                    "quantity": positions[0]["size"],
                    "entry_price": positions[0]["entry_price"]
                }

        return True

    def check_position_status(self):
        """
        Monitors open position and enforces max hold timeout.
        """
        if not self.active_trade:
            return

        trade = self.active_trade
        elapsed_minutes = (time.time() - trade["entry_time"]) / 60.0

        if config.dry_run:
            # In dry-run, check latest mark price vs simulated TP/SL
            mark_price = self.client.get_mark_price(self.symbol)
            if mark_price:
                hit_tp = mark_price >= trade["tp_price"] if trade["side"] == "BUY" else mark_price <= trade["tp_price"]
                hit_sl = mark_price <= trade["sl_price"] if trade["side"] == "BUY" else mark_price >= trade["sl_price"]
                
                if hit_tp:
                    logger.info(f"[SIMULATED EXIT] Position hit TAKE PROFIT at {mark_price}! PnL: +${config.dollar_risk * config.reward_risk_ratio:.2f}")
                    self.active_trade = None
                    return
                elif hit_sl:
                    logger.info(f"[SIMULATED EXIT] Position hit STOP LOSS at {mark_price}! PnL: -${config.dollar_risk:.2f}")
                    self.active_trade = None
                    return

            if elapsed_minutes >= config.max_hold_minutes:
                logger.info(f"[SIMULATED EXIT] Max hold duration ({config.max_hold_minutes}m) reached. Position closed.")
                self.active_trade = None
            return

        # In live mode: Query exchange positions
        open_positions = self.client.get_open_positions(self.symbol)
        if not open_positions:
            logger.info("[+] Active position has closed on exchange (TP or SL was filled).")
            self.active_trade = None
            return

        # Check for timeout exit
        if elapsed_minutes >= config.max_hold_minutes:
            pos = open_positions[0]
            logger.info(f"[!] Max hold timeout ({config.max_hold_minutes}m) exceeded. Closing position at market...")
            close_side = "SELL" if pos["side"] == "LONG" else "BUY"
            success = self.client.close_market_position(
                symbol=self.symbol,
                side=close_side,
                position_side=pos["side"],
                quantity=pos["size"]
            )
            if success:
                logger.info("[+] Market close order executed successfully.")
                self.active_trade = None
            else:
                logger.error("[!] Failed to execute timeout market close.")

    def evaluate_new_bar(self):
        """
        Executed immediately after a 1-minute candle closes.
        """
        # Fetch last 40 closed candles
        candles = self.client.get_klines(self.symbol, interval="1m", limit=40)
        if len(candles) < 20:
            logger.warning("[!] Insufficient klines returned from WEEX.")
            return

        # The last candle in list is current forming bar, second to last is latest CLOSED bar
        closed_candle = candles[-2]
        c_time = closed_candle["timestamp"]

        # Prevent duplicate evaluation of the same closed bar
        if c_time <= self.last_evaluated_timestamp:
            return
        self.last_evaluated_timestamp = c_time

        # Compute ATR(14) on closed bars
        atr = DisplacementStrategy.calculate_atr(candles[:-1], period=config.atr_period)
        if not atr:
            return

        # Check active session window
        now_utc = datetime.now(timezone.utc)
        is_active, sess_id, minutes_in = DisplacementStrategy.check_session_active(
            target_sessions=config.target_sessions,
            window_minutes=config.window_minutes,
            now_dt=now_utc
        )

        # Reset session counter if session changed
        if sess_id != self.current_session_id:
            self.current_session_id = sess_id
            self.trades_in_current_session = 0

        bar_dt = datetime.fromtimestamp(c_time / 1000, tz=timezone.utc).strftime("%H:%M")
        status_msg = f"Closed Bar {bar_dt} UTC | C: {closed_candle['close']} | ATR(14): {atr:.1f}"

        if not is_active:
            logger.debug(f"{status_msg} | Outside active session window.")
            return

        logger.info(f"{status_msg} | In Window [{sess_id}] (+{minutes_in}m) | Trades taken: {self.trades_in_current_session}/{config.max_trades_per_window}")

        # Check trade limits
        if self.trades_in_current_session >= config.max_trades_per_window:
            return

        if self.active_trade is not None:
            logger.info("[-] Trade setup skipped: A position is already active.")
            return

        # Check for displacement pattern
        direction = DisplacementStrategy.evaluate_displacement(
            candle=closed_candle,
            atr=atr,
            k_atr=config.k_atr,
            min_body_ratio=config.min_body_ratio
        )

        if not direction:
            return

        # Valid displacement candle confirmed!
        entry_price = closed_candle["close"]
        logger.info(f"*** [{direction} DISPLACEMENT CONFIRMED] *** at {entry_price} (ATR: {atr:.1f})")

        order_params = DisplacementStrategy.calculate_order_parameters(
            direction=direction,
            entry_price=entry_price,
            atr=atr,
            dollar_risk=config.dollar_risk,
            reward_risk_ratio=config.reward_risk_ratio,
            symbol_meta=self.symbol_meta
        )

        logger.info(
            f"[*] Sizing for ${config.dollar_risk:.2f} Risk: "
            f"Side: {order_params['side']} | Qty: {order_params['quantity']} BTC | "
            f"SL: {order_params['sl_price']} (-${order_params['risk_points']}) | "
            f"TP: {order_params['tp_price']} (+${order_params['target_points']})"
        )

        if config.dry_run:
            logger.info(f"[SIMULATED ENTRY] Executed {order_params['side']} {order_params['quantity']} {self.symbol} at {entry_price}")
            self.active_trade = {
                "side": order_params["side"],
                "position_side": order_params["position_side"],
                "entry_time": time.time(),
                "entry_price": entry_price,
                "quantity": order_params["quantity"],
                "sl_price": order_params["sl_price"],
                "tp_price": order_params["tp_price"]
            }
            self.trades_in_current_session += 1
            return

        # Live Order Submission
        res = self.client.place_market_order_with_tpsl(
            symbol=self.symbol,
            side=order_params["side"],
            position_side=order_params["position_side"],
            quantity=order_params["quantity"],
            tp_price=order_params["tp_price"],
            sl_price=order_params["sl_price"]
        )

        if res.get("success"):
            logger.info(f"[+] Live Order Placed Successfully! OrderId: {res.get('orderId')}")
            self.active_trade = {
                "order_id": res.get("orderId"),
                "side": order_params["side"],
                "position_side": order_params["position_side"],
                "entry_time": time.time(),
                "entry_price": entry_price,
                "quantity": order_params["quantity"],
                "sl_price": order_params["sl_price"],
                "tp_price": order_params["tp_price"]
            }
            self.trades_in_current_session += 1
        else:
            logger.error(f"[!] Order placement failed: {res.get('error')}")

    def run(self):
        if not self.initialize():
            return

        logger.info("[*] Bot loop running. Synchronizing with 1m candle intervals...")

        while self.running:
            try:
                # 1. Check open position status & timeouts
                self.check_position_status()

                # 2. Check for new closed bar
                self.evaluate_new_bar()

                # 3. Precise clock alignment: Sleep until 1 second after the next minute
                now = datetime.now(timezone.utc)
                sleep_seconds = 61 - now.second - (now.microsecond / 1_000_000.0)
                if sleep_seconds < 1:
                    sleep_seconds += 60
                
                time.sleep(sleep_seconds)

            except Exception as e:
                logger.error(f"[!] Unhandled loop exception: {e}", exc_info=True)
                time.sleep(5)

        logger.info("[*] Bot stopped cleanly.")

if __name__ == "__main__":
    bot = WEEXDisplacementBot()
    bot.run()
