import time
import unittest
from unittest.mock import patch

import requests

from cache_utils import SimpleCache
from config import Config
from data_services import (
    get_empty_weather,
    get_weather,
    weather_cache,
    weather_icon_symbol,
)


class SimpleCacheTests(unittest.TestCase):
    def test_expired_value_remains_available_as_stale_fallback(self):
        cache = SimpleCache(ttl_seconds=1)
        cache.cache["key"] = ("last-good-value", time.time() - 2)

        self.assertIsNone(cache.get("key"))
        self.assertEqual(cache.get_stale("key"), "last-good-value")


class WeatherFallbackTests(unittest.TestCase):
    def test_weather_icons_are_local_monochrome_symbols(self):
        self.assertEqual(weather_icon_symbol("01d"), "☀")
        self.assertEqual(weather_icon_symbol("10d"), "☂")

    def setUp(self):
        self.cache_key = f"weather_data_{Config.LATITUDE}_{Config.LONGITUDE}"
        self.previous = weather_cache.cache.get(self.cache_key)

        self.last_good = get_empty_weather()
        self.last_good["current"]["temp"] = 25
        self.last_good["current"]["desc"] = "毛毛雨"
        weather_cache.cache[self.cache_key] = (
            self.last_good,
            time.time() - Config.CACHE_TTL_WEATHER - 1,
        )

    def tearDown(self):
        if self.previous is None:
            weather_cache.cache.pop(self.cache_key, None)
        else:
            weather_cache.cache[self.cache_key] = self.previous

    @patch("data_services.requests.get", side_effect=requests.Timeout("temporary outage"))
    def test_refresh_failure_returns_last_good_weather(self, _mock_get):
        result = get_weather()

        self.assertEqual(result["current"]["temp"], 25)
        self.assertEqual(result["current"]["desc"], "毛毛雨")


if __name__ == "__main__":
    unittest.main()
