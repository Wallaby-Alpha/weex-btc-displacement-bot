from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

class DisplacementStrategy:
    @staticmethod
    def calculate_atr(candles: List[Dict[str, Any]], period: int = 14) -> Optional[float]:
        if len(candles) < period + 1:
            return None

        tr_list = []
        for i in range(1, len(candles)):
            c_curr = candles[i]
            c_prev = candles[i - 1]
            h = c_curr["high"]
            l = c_curr["low"]
            prev_close = c_prev["close"]
            tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
            tr_list.append(tr)

        # Wilder's exponential smoothing
        if len(tr_list) < period:
            return None

        atr = sum(tr_list[:period]) / period
        for tr in tr_list[period:]:
            atr = (atr * (period - 1) + tr) / period

        return atr

    @staticmethod
    def evaluate_displacement(
        candle: Dict[str, Any],
        atr: float,
        k_atr: float = 1.5,
        min_body_ratio: float = 0.65,
        wick_tol: float = 0.25
    ) -> Optional[str]:
        """
        Returns 'BULLISH', 'BEARISH', or None
        """
        o = candle["open"]
        h = candle["high"]
        l = candle["low"]
        c = candle["close"]

        rng = h - l
        if rng <= 0 or atr <= 0:
            return None

        body = abs(c - o)
        body_ratio = body / rng

        # Size and conviction filters
        if body < (k_atr * atr):
            return None
        if body_ratio < min_body_ratio:
            return None

        # Bullish continuation check
        if c > o and c >= (h - wick_tol * rng):
            return "BULLISH"

        # Bearish continuation check
        if c < o and c <= (l + wick_tol * rng):
            return "BEARISH"

        return None

    @staticmethod
    def check_session_active(
        target_sessions: List[str],
        window_minutes: int = 30,
        now_dt: Optional[datetime] = None
    ) -> Tuple[bool, Optional[str], int]:
        """
        Evaluates if the current UTC time is inside any configured session window.
        Returns: (is_active, session_identifier, minutes_into_session)
        """
        now = now_dt or datetime.now(timezone.utc)
        current_minute_of_day = now.hour * 60 + now.minute

        for s_str in target_sessions:
            try:
                hh, mm = map(int, s_str.split(":"))
                start_minute = hh * 60 + mm
                end_minute = start_minute + window_minutes

                if start_minute <= current_minute_of_day < end_minute:
                    elapsed = current_minute_of_day - start_minute
                    sess_id = f"{now.strftime('%Y-%m-%d')}_{s_str}"
                    return True, sess_id, elapsed
            except ValueError:
                continue

        return False, None, -1

    @staticmethod
    def calculate_order_parameters(
        direction: str,
        entry_price: float,
        atr: float,
        dollar_risk: float,
        reward_risk_ratio: float,
        symbol_meta: Dict[str, Any],
        available_margin: Optional[float] = None,
        leverage: int = 20
    ) -> Dict[str, Any]:
        """
        Calculates exact quantity for fixed $1 dollar risk, and rounds TP/SL to exchange precision.
        Caps quantity safely within available margin to prevent order rejections.
        """
        risk_points = round(atr, symbol_meta.get("pricePrecision", 1))
        if risk_points <= 0:
            risk_points = 50.0  # fallback minimum

        # Calculate exact position size for the desired dollar risk
        # Dollar Risk = Position Size (BTC) * Risk Points ($)
        # Position Size = Dollar Risk / Risk Points
        raw_quantity = dollar_risk / risk_points
        qty_prec = symbol_meta.get("quantityPrecision", 4)
        min_qty = symbol_meta.get("minOrderSize", 0.0001)

        # Cap by available margin if provided (use 85% of margin as safe buffer)
        if available_margin is not None and available_margin > 0 and entry_price > 0:
            max_allowed_qty = (available_margin * leverage * 0.85) / entry_price
            if raw_quantity > max_allowed_qty:
                raw_quantity = max(max_allowed_qty, min_qty)

        quantity = round(raw_quantity, qty_prec)
        if quantity < min_qty:
            quantity = min_qty

        price_prec = symbol_meta.get("pricePrecision", 1)

        if direction == "BULLISH":
            side = "BUY"
            position_side = "LONG"
            sl_price = round(entry_price - risk_points, price_prec)
            tp_price = round(entry_price + (reward_risk_ratio * risk_points), price_prec)
        else:
            side = "SELL"
            position_side = "SHORT"
            sl_price = round(entry_price + risk_points, price_prec)
            tp_price = round(entry_price - (reward_risk_ratio * risk_points), price_prec)

        actual_risk_dollars = quantity * risk_points

        return {
            "direction": direction,
            "side": side,
            "position_side": position_side,
            "entry_price": entry_price,
            "quantity": quantity,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "risk_points": risk_points,
            "target_points": round(reward_risk_ratio * risk_points, price_prec),
            "estimated_dollar_risk": round(actual_risk_dollars, 4)
        }
