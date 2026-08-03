import os
import ast
from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name):
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


class Config:
    # --- Server Configuration ---
    # Note: Port/Host are often handled by the WSGI server or docker-compose, 
    # but good to have defaults here.
    PORT = int(os.environ.get("PORT", 5000))
    HOST = os.environ.get("HOST", "0.0.0.0")

    # --- Location Configuration ---
    LATITUDE = float(os.environ.get("LATITUDE", "1.27710"))
    LONGITUDE = float(os.environ.get("LONGITUDE", "103.84610"))
    CITY_NAME = os.environ.get("CITY_NAME", "Singapore") # Used for display if location lookup fails or is disabled
    TIMEZONE = os.environ.get("TIMEZONE", "Asia/Singapore")

    # --- Screen Configuration ---
    # Kindle Scribe landscape resolution
    SCREEN_WIDTH = int(os.environ.get("SCREEN_WIDTH", 2480))
    SCREEN_HEIGHT = int(os.environ.get("SCREEN_HEIGHT", 1860))
    
    # --- Renderer Configuration ---
    # Timeout for page loading in milliseconds
    RENDER_TIMEOUT = int(os.environ.get("RENDER_TIMEOUT", 60000))

    # --- Locale & Localization ---
    LANGUAGE = os.environ.get("LANGUAGE", "CN") # CN or EN
    HOLIDAY_COUNTRY = os.environ.get("HOLIDAY_COUNTRY", "SG") # Country code for `holidays` library
    
    # --- Cache Durations (in seconds) ---
    CACHE_TTL_WEATHER = int(os.environ.get("CACHE_TTL_WEATHER", 600))     # 10 minutes
    CACHE_TTL_FINANCE = int(os.environ.get("CACHE_TTL_FINANCE", 900))     # 15 minutes
    CACHE_TTL_NEWS = int(os.environ.get("CACHE_TTL_NEWS", 300))           # 5 minutes
    CACHE_TTL_RENDER = int(os.environ.get("CACHE_TTL_RENDER", 60))        # 1 minute
    CACHE_TTL_CALENDAR = int(os.environ.get("CACHE_TTL_CALENDAR", 300))   # 5 minutes

    # --- Week Calendar Configuration ---
    CALENDAR_WEEK_START = os.environ.get("CALENDAR_WEEK_START", "SUNDAY").upper()
    CALENDAR_MAX_EVENTS_PER_DAY = int(os.environ.get("CALENDAR_MAX_EVENTS_PER_DAY", 6))

    # Apple iCloud CalDAV. A blank APPLE_CALENDAR_NAMES selects every calendar.
    APPLE_CALENDAR_ENABLED = _env_bool("APPLE_CALENDAR_ENABLED", False)
    APPLE_CALDAV_URL = os.environ.get("APPLE_CALDAV_URL", "https://caldav.icloud.com")
    APPLE_ID = os.environ.get("APPLE_ID", "")
    APPLE_APP_PASSWORD = os.environ.get("APPLE_APP_PASSWORD", "")
    APPLE_CALENDAR_NAMES = _env_list("APPLE_CALENDAR_NAMES")
    APPLE_PRIVATE_CALENDAR_NAMES = _env_list("APPLE_PRIVATE_CALENDAR_NAMES")

    # --- Finance Configuration ---
    # Expected format: JSON list of dicts or just a comma-separated list of symbols for defaults
    # If using formatted string in env: '[{"symbol": "SGDCNY=X", "name": "SGD/CNY"}, ...]'
    # OR simple comma separated: "SGDCNY=X,BTC-USD" (will use symbol as name)
    FINANCE_TICKERS_RAW = os.environ.get(
        "FINANCE_TICKERS",
        '[{"symbol":"SPCX","name":"SpaceX"},{"symbol":"SQQQ","name":"SQQQ"},{"symbol":"SOXS","name":"SOXS"},{"symbol":"BTC-USD","name":"比特币"},{"symbol":"CNY=X","name":"美元/人民币"},{"symbol":"^VIX","name":"VIX"}]'
    )
    
    @staticmethod
    def get_finance_tickers():
        raw = Config.FINANCE_TICKERS_RAW
        try:
            # Try parsing as JSON first
            return ast.literal_eval(raw)
        except:
            # Fallback to comma-separated list
            return [{"symbol": s.strip(), "name": s.strip()} for s in raw.split(",") if s.strip()]

    # --- Work/Commute Logic ---
    WORK_START_HOUR = int(os.environ.get("WORK_START_HOUR", 10))
    WORK_END_HOUR = int(os.environ.get("WORK_END_HOUR", 18))

    # --- News Configuration ---
    # If set, fetches news from this URL instead of Hacker News
    # Expected JSON format: [{"title": "...", "meta": "..."}, ...]
    NEWS_EXTERNAL_URL = os.environ.get("NEWS_EXTERNAL_URL", "")
