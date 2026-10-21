import os
from dataclasses import dataclass
from typing import List
from dotenv import load_dotenv

load_dotenv()

@dataclass
class BotConfig:
    # WEEX API Credentials
    api_key: str = os.getenv("WEEX_API_KEY", "")
    api_secret: str = os.getenv("WEEX_API_SECRET", "")
    passphrase: str = os.getenv("WEEX_PASSPHRASE", "")
    base_url: str = os.getenv("WEEX_BASE_URL", "https://api-contract.weex.com")

    # Contract Specifications
    symbol: str = os.getenv("SYMBOL", "BTCUSDT")
    leverage: int = int(os.getenv("LEVERAGE", "20"))
    position_mode: str = os.getenv("POSITION_MODE", "LONG").upper()  # WEEX V3 requires 'LONG' or 'SHORT'
    
    # Risk & Strategy Parameters
    dollar_risk: float = float(os.getenv("DOLLAR_RISK", "1.00"))  # $1 fixed risk per trade
    reward_risk_ratio: float = float(os.getenv("REWARD_RISK_RATIO", "1.5"))  # 1.5:1 TP
    atr_period: int = int(os.getenv("ATR_PERIOD", "14"))
    k_atr: float = float(os.getenv("K_ATR", "1.5"))  # Candle body >= 1.5x ATR
    min_body_ratio: float = float(os.getenv("MIN_BODY_RATIO", "0.65"))  # Body >= 65% of Range
    
    # Timing & Execution Schedule (UTC)
    target_sessions: List[str] = None
    window_minutes: int = int(os.getenv("WINDOW_MINUTES", "30"))
    max_hold_minutes: int = int(os.getenv("MAX_HOLD_MINUTES", "60"))
    max_trades_per_window: int = int(os.getenv("MAX_TRADES_PER_WINDOW", "1"))
    
    # Operational Modes
    dry_run: bool = os.getenv("DRY_RUN", "true").lower() in ("true", "1", "yes")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    def __post_init__(self):
        raw_sessions = os.getenv("SESSIONS", "08:03,13:33,16:03,00:03")
        self.target_sessions = [s.strip() for s in raw_sessions.split(",") if s.strip()]

config = BotConfig()
