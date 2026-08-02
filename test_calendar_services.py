import datetime
import time
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from cache_utils import SimpleCache
from calendar_services import (
    _normalize_event,
    _provider_events,
    build_week_agenda,
)
from config import Config


class CalendarNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.timezone = ZoneInfo(Config.TIMEZONE)
        self.week_start = datetime.datetime(2026, 8, 2, tzinfo=self.timezone)
        self.week_end = self.week_start + datetime.timedelta(days=7)

    def test_private_apple_calendar_masks_title_and_location(self):
        event = _normalize_event(
            source="apple",
            event_id="private-1",
            calendar_name="Private",
            title="Sensitive appointment",
            location="Private office",
            start=self.week_start + datetime.timedelta(days=1, hours=10),
            end=self.week_start + datetime.timedelta(days=1, hours=11),
            private=True,
        )

        self.assertIn(event["title"], {"Busy", "忙碌"})
        self.assertEqual(event["location"], "")

    def test_microsoft_event_keeps_name_location_and_time_range(self):
        event = _normalize_event(
            source="microsoft",
            event_id="ms-1",
            calendar_name="Microsoft 365",
            title="CSCI 8000",
            location="Boyd 328",
            start=self.week_start + datetime.timedelta(days=2, hours=9, minutes=55),
            end=self.week_start + datetime.timedelta(days=2, hours=11, minutes=15),
            private=False,
        )

        agenda = build_week_agenda([event], self.week_start, self.week_end)
        rendered = agenda["days"][2]["events"][0]
        self.assertEqual(rendered["title"], "CSCI 8000")
        self.assertEqual(rendered["location"], "Boyd 328")
        self.assertEqual(rendered["time"], "09:55–11:15")
        self.assertEqual(rendered["duration"], "1h20m")

    def test_week_can_show_six_events_and_reports_the_remainder(self):
        events = []
        for index in range(7):
            start = self.week_start + datetime.timedelta(days=2, hours=8 + index)
            events.append(_normalize_event(
                source="microsoft",
                event_id=f"ms-{index}",
                calendar_name="Microsoft 365",
                title=f"Event {index}",
                location="Boyd",
                start=start,
                end=start + datetime.timedelta(minutes=45),
                private=False,
            ))

        with patch.object(Config, "CALENDAR_MAX_EVENTS_PER_DAY", 6):
            agenda = build_week_agenda(events, self.week_start, self.week_end)

        self.assertEqual(len(agenda["days"][2]["events"]), 6)
        self.assertEqual(agenda["days"][2]["hidden_count"], 1)


class CalendarCacheTests(unittest.TestCase):
    def test_provider_failure_uses_expired_calendar_data(self):
        cache = SimpleCache(ttl_seconds=1)
        cached = [{"title": "Last good event"}]
        cache.cache["week"] = (cached, time.time() - 2)

        def failing_fetcher(_start, _end):
            raise RuntimeError("temporary provider outage")

        result = _provider_events(
            cache,
            "week",
            failing_fetcher,
            datetime.datetime.now(datetime.UTC),
            datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=7),
        )
        self.assertEqual(result, cached)


if __name__ == "__main__":
    unittest.main()
