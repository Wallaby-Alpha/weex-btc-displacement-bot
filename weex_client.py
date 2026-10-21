import hmac
import hashlib
import base64
import time
import json
import logging
import requests
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger("weex_bot.client")

class WeexClient:
    def __init__(self, api_key: str, api_secret: str, passphrase: str, base_url: str = "https://api-contract.weex.com"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "WeexBTCDisplacementBot/1.0"
        })

    def _generate_signature(self, timestamp: str, method: str, path: str, body_str: str) -> str:
        message = timestamp + method.upper() + path + body_str
        sig = hmac.new(
            self.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).digest()
        return base64.b64encode(sig).decode("utf-8")

    def request(self, method: str, path: str, body: Optional[Dict[str, Any]] = None, is_public: bool = False, timeout: int = 10) -> Tuple[int, Any]:
        url = self.base_url + path
        timestamp = str(int(time.time() * 1000))
        body_str = json.dumps(body) if (method.upper() not in ["GET", "DELETE"] and body is not None) else ""

        headers = {}
        if not is_public:
            if not self.api_key or not self.api_secret:
                raise ValueError("API Key and Secret must be provided for private endpoints.")
            headers["ACCESS-KEY"] = self.api_key
            headers["ACCESS-SIGN"] = self._generate_signature(timestamp, method, path, body_str)
            headers["ACCESS-TIMESTAMP"] = timestamp
            headers["ACCESS-PASSPHRASE"] = self.passphrase

        try:
            resp = self.session.request(
                method=method.upper(),
                url=url,
                headers=headers,
                data=body_str if body_str else None,
                timeout=timeout
            )
            try:
                data = resp.json()
            except Exception:
                data = resp.text

            if resp.status_code >= 400:
                logger.warning(f"WEEX API non-2xx [{resp.status_code}] on {method} {path}: {data}")

            return resp.status_code, data
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error on {method} {path}: {e}")
            raise

    # ---------------- Public Market Endpoints ---------------- #

    def get_exchange_info(self, symbol: str = "BTCUSDT") -> Optional[Dict[str, Any]]:
        status, data = self.request("GET", "/capi/v3/market/exchangeInfo", is_public=True)
        if status != 200:
            return None
        symbols = data.get("symbols", []) or data.get("data", {}).get("symbols", [])
        for s in symbols:
            if s.get("symbol") == symbol or s.get("displaySymbol") == symbol:
                return {
                    "symbol": s.get("symbol"),
                    "contractVal": float(s.get("contractVal", 0.0001)),
                    "minOrderSize": float(s.get("minOrderSize", 0.0001)),
                    "pricePrecision": int(s.get("pricePrecision", 1)),
                    "quantityPrecision": int(s.get("quantityPrecision", 4)),
                    "minLeverage": int(s.get("minLeverage", 1)),
                    "maxLeverage": int(s.get("maxLeverage", 100))
                }
        return None

    def get_klines(self, symbol: str = "BTCUSDT", interval: str = "1m", limit: int = 50) -> List[Dict[str, Any]]:
        """
        Returns list of candles sorted chronologically (oldest to newest):
        [{'timestamp': ms, 'open': float, 'high': float, 'low': float, 'close': float, 'volume': float}, ...]
        """
        path = f"/capi/v3/market/klines?symbol={symbol}&interval={interval}&limit={limit}"
        status, data = self.request("GET", path, is_public=True)
        if status != 200 or not isinstance(data, list):
            logger.error(f"Failed to fetch klines for {symbol}: status {status}")
            return []

        candles = []
        # WEEX returns newest first or oldest first. Check timestamps to ensure chronological ascending order.
        for row in data:
            try:
                candles.append({
                    "timestamp": int(row[0]),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5])
                })
            except (ValueError, IndexError):
                continue

        # Sort ascending by timestamp
        candles.sort(key=lambda x: x["timestamp"])
        return candles

    def get_mark_price(self, symbol: str = "BTCUSDT") -> Optional[float]:
        status, data = self.request("GET", f"/capi/v3/market/premiumIndex?symbol={symbol}", is_public=True)
        if status == 200:
            if isinstance(data, list):
                for item in data:
                    if item.get("symbol") == symbol:
                        return float(item.get("markPrice", 0))
            elif isinstance(data, dict):
                return float(data.get("data", {}).get("markPrice") or data.get("markPrice", 0))
        return None

    # ---------------- Private Account & Trading ---------------- #

    def get_available_margin(self) -> float:
        status, data = self.request("GET", "/capi/v3/account/balance")
        if status != 200:
            return 0.0
        balances = data if isinstance(data, list) else (data.get("data", []) if isinstance(data, dict) else [])
        for asset in balances:
            if asset.get("asset") == "USDT":
                return float(asset.get("availableBalance") or asset.get("balance") or 0.0)
        return 0.0

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        payload = {
            "symbol": symbol,
            "isolatedLongLeverage": str(leverage),
            "isolatedShortLeverage": str(leverage)
        }
        status, data = self.request("POST", "/capi/v3/account/leverage", body=payload)
        return status == 200

    def get_open_positions(self, symbol: str = "BTCUSDT") -> List[Dict[str, Any]]:
        status, data = self.request("GET", "/capi/v3/account/position/allPosition")
        if status != 200:
            return []
        positions = data if isinstance(data, list) else (data.get("data", []) if isinstance(data, dict) else [])
        active = []
        for p in positions:
            size = float(p.get("size") or p.get("total") or 0)
            if size > 0 and (p.get("symbol") == symbol or not symbol):
                active.append({
                    "symbol": p.get("symbol"),
                    "side": p.get("side"),  # 'LONG' or 'SHORT'
                    "size": size,
                    "entry_price": float(p.get("openValue", 0)) / size if size > 0 else float(p.get("entryPrice", 0)),
                    "unrealized_pnl": float(p.get("unrealizePnl", 0)),
                    "margin": float(p.get("isolatedMargin") or p.get("marginSize") or 0)
                })
        return active

    def place_market_order_with_tpsl(
        self,
        symbol: str,
        side: str,  # 'BUY' or 'SELL'
        position_side: str,  # 'LONG' or 'SHORT'
        quantity: float,
        tp_price: float,
        sl_price: float,
        client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Submits market order with attached preset TP and SL.
        """
        cid = client_order_id or f"b-{int(time.time()*1000)}"
        if not cid.startswith("b-"):
            cid = f"b-{cid}"

        payload = {
            "symbol": symbol,
            "side": side,
            "positionSide": position_side,
            "type": "MARKET",
            "quantity": str(quantity),
            "newClientOrderId": cid,
            "tpTriggerPrice": str(tp_price),
            "tpWorkingType": "MARK_PRICE",
            "slTriggerPrice": str(sl_price),
            "slWorkingType": "MARK_PRICE"
        }

        logger.info(f"Submitting WEEX Market Order: {side} {quantity} {symbol} (TP: {tp_price}, SL: {sl_price})")
        status, data = self.request("POST", "/capi/v3/order", body=payload)
        
        if status == 200 and isinstance(data, dict) and (data.get("success") or data.get("orderId")):
            return {
                "success": True,
                "orderId": str(data.get("orderId")),
                "clientOrderId": cid,
                "data": data
            }
        
        err_msg = data.get("msg") if isinstance(data, dict) else str(data)
        logger.error(f"Failed to place WEEX order: status {status}, message: {err_msg}")
        return {
            "success": False,
            "error": err_msg,
            "status": status
        }

    def close_market_position(self, symbol: str, side: str, position_side: str, quantity: float) -> bool:
        """
        Closes position by submitting opposing market order.
        """
        cid = f"b-close-{int(time.time()*1000)}"
        payload = {
            "symbol": symbol,
            "side": side,  # 'SELL' to close LONG, 'BUY' to close SHORT
            "positionSide": position_side,
            "type": "MARKET",
            "quantity": str(quantity),
            "newClientOrderId": cid
        }
        logger.info(f"Submitting Market Close: {side} {quantity} {symbol} for {position_side} position")
        status, data = self.request("POST", "/capi/v3/order", body=payload)
        return status == 200

    def place_native_tpsl_plan_order(
        self,
        symbol: str,
        plan_type: str,  # 'TAKE_PROFIT' or 'STOP_LOSS'
        trigger_price: float,
        position_side: str,  # 'LONG' or 'SHORT'
        trigger_price_type: str = "CONTRACT_PRICE"
    ) -> bool:
        """
        Submits dedicated native exchange-level conditional plan order to WEEX matching engine.
        Using quantity: '0' creates native whole-position protection directly on the exchange.
        """
        cid = f"b-plan-{plan_type[:2].lower()}-{int(time.time()*1000)}"
        payload = {
            "symbol": symbol,
            "clientAlgoId": cid,
            "planType": plan_type,
            "triggerPrice": str(trigger_price),
            "positionSide": position_side,
            "executePrice": "0",  # Market execution upon trigger
            "quantity": "0",      # 0 = Dynamic whole-position protection on WEEX
            "triggerPriceType": trigger_price_type
        }
        logger.info(f"Submitting WEEX Native Plan Order: {plan_type} @ {trigger_price} ({position_side})")
        status, data = self.request("POST", "/capi/v3/placeTpSlOrder", body=payload)
        item = data[0] if isinstance(data, list) else data
        success = status == 200 and isinstance(item, dict) and bool(item.get("success") or item.get("orderId"))
        if success:
            logger.info(f"[+] Native exchange {plan_type} registered successfully on WEEX matching engine.")
        else:
            logger.warning(f"[!] Native {plan_type} plan order response: status {status}, data: {data}")
        return success
