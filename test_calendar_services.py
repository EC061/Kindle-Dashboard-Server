import contextlib
import datetime
import io
import json
import time
import unittest
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from caldav.lib.error import AuthorizationError

import calendar_services
from cache_utils import SimpleCache
from calendar_services import (
    CalendarAuthRequired,
    _normalize_event,
    _provider_events,
    build_week_agenda,
    fetch_ics_events,
    get_week_agenda,
)
from config import Config


class CalendarNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.timezone = ZoneInfo(Config.TIMEZONE)
        self.week_start = datetime.datetime(2026, 8, 2, tzinfo=self.timezone)
        self.week_end = self.week_start + datetime.timedelta(days=7)

    def test_private_apple_calendar_masks_title_location_and_notes(self):
        event = _normalize_event(
            source="apple",
            event_id="private-1",
            calendar_name="Private",
            title="Sensitive appointment",
            location="Private office",
            notes="Private details",
            start=self.week_start + datetime.timedelta(days=1, hours=10),
            end=self.week_start + datetime.timedelta(days=1, hours=11),
            private=True,
        )

        self.assertIn(event["title"], {"Busy", "忙碌"})
        self.assertEqual(event["location"], "")
        self.assertEqual(event["notes"], "")

    def test_public_apple_event_keeps_name_location_and_time_range(self):
        event = _normalize_event(
            source="apple",
            event_id="apple-1",
            calendar_name="UGA Classes",
            title="CSCI 8000",
            location="Boyd 328",
            notes="Geography 0155",
            start=self.week_start + datetime.timedelta(days=2, hours=9, minutes=55),
            end=self.week_start + datetime.timedelta(days=2, hours=11, minutes=15),
            private=False,
        )

        agenda = build_week_agenda([event], self.week_start, self.week_end)
        rendered = agenda["days"][2]["events"][0]
        self.assertEqual(rendered["title"], "CSCI 8000")
        self.assertEqual(rendered["location"], "Boyd 328")
        self.assertEqual(rendered["notes"], "Geography 0155")
        self.assertEqual(rendered["time"], "09:55–11:15")
        self.assertEqual(rendered["duration"], "1h20m")

    def test_week_can_show_six_events_and_reports_the_remainder(self):
        events = []
        for index in range(7):
            start = self.week_start + datetime.timedelta(days=2, hours=8 + index)
            events.append(_normalize_event(
                source="apple",
                event_id=f"apple-{index}",
                calendar_name="UGA Classes",
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

    def test_timed_events_use_proportional_8_to_18_positions(self):
        event = _normalize_event(
            source="apple",
            event_id="positioned",
            calendar_name="UGA Classes",
            title="Cloud Computing",
            location="Boyd 328",
            start=self.week_start + datetime.timedelta(days=2, hours=9),
            end=self.week_start + datetime.timedelta(days=2, hours=10, minutes=30),
        )

        with (
            patch.object(Config, "CALENDAR_DAY_START_HOUR", 8),
            patch.object(Config, "CALENDAR_DAY_END_HOUR", 18),
        ):
            agenda = build_week_agenda([event], self.week_start, self.week_end)

        rendered = agenda["days"][2]["timed_events"][0]
        self.assertEqual(rendered["top_pct"], 10.0)
        self.assertEqual(rendered["height_pct"], 15.0)
        self.assertEqual(rendered["left_pct"], 0.0)
        self.assertEqual(rendered["width_pct"], 100.0)

    def test_overlapping_events_share_the_day_column(self):
        starts = [(9, 0, 60), (9, 30, 90), (12, 0, 60)]
        events = []
        for index, (hour, minute, duration) in enumerate(starts):
            start = self.week_start + datetime.timedelta(
                days=2, hours=hour, minutes=minute
            )
            events.append(_normalize_event(
                source="apple",
                event_id=f"overlap-{index}",
                calendar_name="UGA Classes",
                title=f"Event {index}",
                location="Boyd",
                start=start,
                end=start + datetime.timedelta(minutes=duration),
            ))

        agenda = build_week_agenda(events, self.week_start, self.week_end)
        rendered = agenda["days"][2]["timed_events"]

        self.assertEqual([event["width_pct"] for event in rendered], [50.0, 50.0, 100.0])
        self.assertEqual([event["left_pct"] for event in rendered], [0.0, 50.0, 0.0])

    def test_events_are_clipped_to_grid_but_keep_real_time_label(self):
        early = _normalize_event(
            source="apple",
            event_id="early",
            calendar_name="UGA Classes",
            title="Early meeting",
            location="Boyd",
            start=self.week_start + datetime.timedelta(days=2, hours=7, minutes=30),
            end=self.week_start + datetime.timedelta(days=2, hours=8, minutes=30),
        )
        evening = _normalize_event(
            source="apple",
            event_id="evening",
            calendar_name="UGA Classes",
            title="Evening meeting",
            location="Boyd",
            start=self.week_start + datetime.timedelta(days=2, hours=18, minutes=30),
            end=self.week_start + datetime.timedelta(days=2, hours=19, minutes=30),
        )

        agenda = build_week_agenda([early, evening], self.week_start, self.week_end)
        day = agenda["days"][2]

        self.assertEqual(len(day["timed_events"]), 1)
        self.assertEqual(day["timed_events"][0]["top_pct"], 0.0)
        self.assertEqual(day["timed_events"][0]["height_pct"], 5.0)
        self.assertEqual(day["timed_events"][0]["time"], "07:30–08:30")
        self.assertEqual(day["outside_count"], 1)

    def test_current_time_position_uses_grid_hours(self):
        now = self.week_start + datetime.timedelta(days=2, hours=13)
        agenda = build_week_agenda([], self.week_start, self.week_end, now=now)

        self.assertTrue(agenda["days"][2]["is_today"])
        self.assertEqual(agenda["days"][2]["current_time_pct"], 50.0)


class IcsCalendarTests(unittest.TestCase):
    def setUp(self):
        self.timezone = ZoneInfo(Config.TIMEZONE)
        self.week_start = datetime.datetime(2026, 8, 2, tzinfo=self.timezone)
        self.week_end = self.week_start + datetime.timedelta(days=7)

    def test_multiple_ics_feeds_are_parsed_from_json(self):
        configured = [
            {"name": "UGA Events", "url": "https://example.com/uga.ics"},
            {"name": "Private", "url": "webcal://example.com/private.ics", "private": True},
        ]
        with patch.object(Config, "ICS_CALENDARS_RAW", json.dumps(configured)):
            feeds = Config.get_ics_calendars()

        self.assertEqual([feed["name"] for feed in feeds], ["UGA Events", "Private"])
        self.assertFalse(feeds[0]["private"])
        self.assertTrue(feeds[1]["private"])
        self.assertEqual(feeds[1]["url"], "https://example.com/private.ics")

    def test_invalid_ics_feed_does_not_remove_valid_feeds(self):
        configured = [
            {"name": "UGA Events", "url": "https://example.com/uga.ics"},
            {"name": "Missing URL"},
        ]
        with patch.object(Config, "ICS_CALENDARS_RAW", json.dumps(configured)):
            feeds = Config.get_ics_calendars()

        self.assertEqual(len(feeds), 1)
        self.assertEqual(feeds[0]["name"], "UGA Events")

    def test_failed_ics_feed_does_not_hide_another_feed(self):
        feeds = [
            {"name": "Unavailable", "url": "https://example.com/down.ics", "private": False},
            {"name": "UGA Events", "url": "https://example.com/uga.ics", "private": False},
        ]

        def fetch_feed(feed, _start, _end):
            if feed["name"] == "Unavailable":
                raise RuntimeError("temporary outage")
            return [_normalize_event(
                source="ics",
                event_id="uga-event",
                calendar_name=feed["name"],
                title="TALENT Project",
                location="Boyd GRSC",
                start=self.week_start + datetime.timedelta(days=5, hours=10),
                end=self.week_start + datetime.timedelta(days=5, hours=11),
            )]

        with (
            patch.object(Config, "get_ics_calendars", return_value=feeds),
            patch("calendar_services.fetch_apple_events", return_value=[]),
            patch("calendar_services.fetch_ics_events", side_effect=fetch_feed),
            patch.object(calendar_services, "apple_cache", SimpleCache(300)),
            patch.object(calendar_services, "ics_cache", SimpleCache(300)),
            patch.object(calendar_services, "agenda_cache", SimpleCache(300)),
        ):
            agenda = get_week_agenda(self.week_start)

        friday_events = agenda["days"][5]["events"]
        self.assertEqual(len(friday_events), 1)
        self.assertEqual(friday_events[0]["title"], "TALENT Project")

    @patch("calendar_services.requests.get")
    def test_ics_feed_expands_recurring_events_within_week(self, mock_get):
        response = Mock()
        response.content = b"""BEGIN:VCALENDAR\r
VERSION:2.0\r
PRODID:-//Kindle Dashboard Tests//EN\r
BEGIN:VEVENT\r
UID:talent-project\r
DTSTART:20260731T140000Z\r
DTEND:20260731T150000Z\r
RRULE:FREQ=WEEKLY;COUNT=3\r
SUMMARY:TALENT Project\r
LOCATION:Boyd GRSC\r
DESCRIPTION:Weekly project sync\r
END:VEVENT\r
END:VCALENDAR\r
"""
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        events = fetch_ics_events(
            {"name": "UGA Events", "url": "https://example.com/uga.ics", "private": False},
            self.week_start,
            self.week_end,
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["title"], "TALENT Project")
        self.assertEqual(events[0]["location"], "Boyd GRSC")
        self.assertEqual(events[0]["notes"], "Weekly project sync")
        self.assertEqual(events[0]["start"].date(), datetime.date(2026, 8, 7))
        mock_get.assert_called_once_with(
            "https://example.com/uga.ics",
            headers={"User-Agent": "Kindle-Dashboard-Server/0.1"},
            timeout=15,
        )

    @patch("calendar_services.requests.get")
    def test_private_ics_feed_masks_event_details(self, mock_get):
        response = Mock()
        response.content = b"""BEGIN:VCALENDAR\r
VERSION:2.0\r
BEGIN:VEVENT\r
UID:private-event\r
DTSTART:20260805T140000Z\r
DTEND:20260805T150000Z\r
SUMMARY:Sensitive event\r
LOCATION:Private office\r
DESCRIPTION:Private details\r
END:VEVENT\r
END:VCALENDAR\r
"""
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        events = fetch_ics_events(
            {"name": "Private feed", "url": "https://example.com/private.ics", "private": True},
            self.week_start,
            self.week_end,
        )

        self.assertEqual(len(events), 1)
        self.assertIn(events[0]["title"], {"Busy", "忙碌"})
        self.assertEqual(events[0]["location"], "")
        self.assertEqual(events[0]["notes"], "")


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

    def _run_failing_provider(self, error):
        def failing_fetcher(_start, _end):
            raise error

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = _provider_events(
                SimpleCache(ttl_seconds=1),
                "week",
                failing_fetcher,
                datetime.datetime.now(datetime.UTC),
                datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=7),
                "iCloud",
            )
        return result, output.getvalue()

    def test_rejected_caldav_credentials_are_reported_on_stdout(self):
        result, logged = self._run_failing_provider(
            AuthorizationError(url="https://caldav.icloud.com", reason="Unauthorized")
        )

        self.assertEqual(result, [])
        self.assertIn("AUTHENTICATION FAILED", logged)
        self.assertIn("iCloud", logged)
        self.assertIn("APPLE_ID", logged)

    def test_missing_caldav_credentials_are_reported_on_stdout(self):
        _, logged = self._run_failing_provider(
            CalendarAuthRequired("APPLE_ID and APPLE_APP_PASSWORD are required")
        )

        self.assertIn("AUTHENTICATION FAILED", logged)

    def test_non_auth_failure_keeps_the_plain_error_message(self):
        _, logged = self._run_failing_provider(RuntimeError("temporary outage"))

        self.assertNotIn("AUTHENTICATION FAILED", logged)
        self.assertIn("temporary outage", logged)


if __name__ == "__main__":
    unittest.main()
