import copy
import datetime
import hashlib
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from zoneinfo import ZoneInfo

import caldav
import recurring_ical_events
import requests
from icalendar import Calendar

from cache_utils import SimpleCache
from config import Config


apple_cache = SimpleCache(Config.CACHE_TTL_CALENDAR)
ics_cache = SimpleCache(Config.CACHE_TTL_CALENDAR)
agenda_cache = SimpleCache(Config.CACHE_TTL_CALENDAR)


class CalendarAuthRequired(RuntimeError):
    pass


def _week_bounds(now=None):
    timezone = ZoneInfo(Config.TIMEZONE)
    now = now or datetime.datetime.now(timezone)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone)
    else:
        now = now.astimezone(timezone)

    if Config.CALENDAR_WEEK_START == "MONDAY":
        days_since_start = now.weekday()
    else:
        days_since_start = (now.weekday() + 1) % 7

    start_date = now.date() - datetime.timedelta(days=days_since_start)
    start = datetime.datetime.combine(start_date, datetime.time.min, timezone)
    return start, start + datetime.timedelta(days=7)


def _as_datetime(value, timezone, *, end=False):
    if isinstance(value, datetime.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone)
        return value.astimezone(timezone)
    if isinstance(value, datetime.date):
        return datetime.datetime.combine(value, datetime.time.min, timezone)
    if value is None:
        return None
    parsed = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone)


def _normalize_event(
    *, source, event_id, calendar_name, title, location, start, end,
    all_day=False, private=False
):
    timezone = ZoneInfo(Config.TIMEZONE)
    start_dt = _as_datetime(start, timezone)
    end_dt = _as_datetime(end, timezone, end=True)
    if start_dt is None:
        return None
    if end_dt is None or end_dt <= start_dt:
        end_dt = start_dt + (
            datetime.timedelta(days=1) if all_day else datetime.timedelta(hours=1)
        )

    display_title = "忙碌" if private and Config.LANGUAGE != "EN" else (
        "Busy" if private else (title or "(Untitled)")
    )
    return {
        "source": source,
        "id": event_id,
        "calendar_name": calendar_name,
        "title": display_title,
        "location": "" if private else (location or ""),
        "start": start_dt,
        "end": end_dt,
        "all_day": bool(all_day),
        "private": bool(private),
    }


def _calendar_name(calendar):
    value = getattr(calendar, "name", None)
    if callable(value):
        value = value()
    return str(value or getattr(calendar, "url", "iCloud"))


def _ical_components(resource):
    component = getattr(resource, "component", None)
    if component is None:
        component = getattr(resource, "icalendar_instance", None)
    if component is None:
        return []
    if getattr(component, "name", "") == "VEVENT":
        return [component]
    return list(component.walk("VEVENT"))


def fetch_apple_events(start, end):
    if not Config.APPLE_CALENDAR_ENABLED:
        return []
    if not Config.APPLE_ID or not Config.APPLE_APP_PASSWORD:
        raise CalendarAuthRequired("APPLE_ID and APPLE_APP_PASSWORD are required")

    selected_names = {name.casefold() for name in Config.APPLE_CALENDAR_NAMES}
    private_names = {name.casefold() for name in Config.APPLE_PRIVATE_CALENDAR_NAMES}

    client = caldav.DAVClient(
        url=Config.APPLE_CALDAV_URL,
        username=Config.APPLE_ID,
        password=Config.APPLE_APP_PASSWORD,
        timeout=15,
    )
    calendars = client.principal().calendars()
    events = []

    for calendar in calendars:
        calendar_name = _calendar_name(calendar)
        if selected_names and calendar_name.casefold() not in selected_names:
            continue
        is_private_calendar = calendar_name.casefold() in private_names
        resources = calendar.search(
            start=start,
            end=end,
            event=True,
            expand=True,
        )
        for resource in resources:
            for component in _ical_components(resource):
                if str(component.get("status", "")).upper() == "CANCELLED":
                    continue
                dtstart = component.get("dtstart")
                dtend = component.get("dtend")
                start_value = getattr(dtstart, "dt", None)
                end_value = getattr(dtend, "dt", None)
                all_day = isinstance(start_value, datetime.date) and not isinstance(
                    start_value, datetime.datetime
                )
                normalized = _normalize_event(
                    source="apple",
                    event_id=str(component.get("uid", getattr(resource, "url", ""))),
                    calendar_name=calendar_name,
                    title=str(component.get("summary", "")),
                    location=str(component.get("location", "")),
                    start=start_value,
                    end=end_value,
                    all_day=all_day,
                    private=is_private_calendar,
                )
                if normalized:
                    events.append(normalized)

    return events


def fetch_ics_events(feed, start, end):
    try:
        response = requests.get(
            feed["url"],
            headers={"User-Agent": "Kindle-Dashboard-Server/0.1"},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        # Published ICS URLs are bearer secrets; never include them in logs.
        raise RuntimeError(
            f"ICS request failed ({error.__class__.__name__})"
        ) from error
    calendar = Calendar.from_ical(response.content)
    components = recurring_ical_events.of(
        calendar,
        skip_bad_series=True,
    ).between(start, end)

    events = []
    for component in components:
        if str(component.get("status", "")).upper() == "CANCELLED":
            continue
        dtstart = component.get("dtstart")
        dtend = component.get("dtend")
        start_value = getattr(dtstart, "dt", None)
        end_value = getattr(dtend, "dt", None)
        all_day = isinstance(start_value, datetime.date) and not isinstance(
            start_value, datetime.datetime
        )
        event_id = str(component.get("uid", ""))
        recurrence_id = component.get("recurrence-id")
        if recurrence_id is not None:
            event_id = f"{event_id}:{getattr(recurrence_id, 'dt', recurrence_id)}"
        normalized = _normalize_event(
            source="ics",
            event_id=event_id,
            calendar_name=feed["name"],
            title=str(component.get("summary", "")),
            location=str(component.get("location", "")),
            start=start_value,
            end=end_value,
            all_day=all_day,
            private=feed["private"],
        )
        if normalized and normalized["start"] < end and normalized["end"] > start:
            events.append(normalized)
    return events


def _provider_events(cache, key, fetcher, start, end, provider_name=None):
    cached = cache.get(key)
    if cached is not None:
        return copy.deepcopy(cached)
    try:
        events = fetcher(start, end)
        cache.set(key, events)
        return events
    except Exception as error:
        print(f"Calendar provider error ({provider_name or key}): {error}")
        stale = cache.get_stale(key)
        return copy.deepcopy(stale) if stale is not None else []


def _duration_label(start, end):
    minutes = max(0, int((end - start).total_seconds() // 60))
    hours, minutes = divmod(minutes, 60)
    if hours and minutes:
        return f"{hours}h{minutes:02d}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def _event_for_day(event, day_start, day_end):
    if event["all_day"]:
        time_label = "全天" if Config.LANGUAGE != "EN" else "All day"
        duration = ""
    else:
        shown_start = max(event["start"], day_start)
        shown_end = min(event["end"], day_end)
        time_label = f"{shown_start:%H:%M}–{shown_end:%H:%M}"
        duration = _duration_label(shown_start, shown_end)
    return {
        "title": event["title"],
        "location": event["location"],
        "time": time_label,
        "duration": duration,
        "all_day": event["all_day"],
        "source": event["source"],
        "private": event["private"],
    }


def build_week_agenda(events, start, end):
    weekday_cn = ["一", "二", "三", "四", "五", "六", "日"]
    weekday_en = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    days = []
    now = datetime.datetime.now(ZoneInfo(Config.TIMEZONE))

    for offset in range(7):
        day_start = start + datetime.timedelta(days=offset)
        day_end = day_start + datetime.timedelta(days=1)
        day_events = [
            event for event in events
            if event["start"] < day_end and event["end"] > day_start
        ]
        day_events.sort(key=lambda event: (not event["all_day"], event["start"], event["title"]))
        visible = day_events[:Config.CALENDAR_MAX_EVENTS_PER_DAY]
        days.append({
            "weekday": (
                weekday_en[day_start.weekday()]
                if Config.LANGUAGE == "EN"
                else weekday_cn[day_start.weekday()]
            ),
            "date": str(day_start.day),
            "is_today": day_start.date() == now.date(),
            "events": [_event_for_day(event, day_start, day_end) for event in visible],
            "hidden_count": max(0, len(day_events) - len(visible)),
        })

    return {
        "label": f"{start:%m/%d}–{(end - datetime.timedelta(days=1)):%m/%d}",
        "days": days,
        "has_events": bool(events),
    }


def get_week_agenda(now=None):
    start, end = _week_bounds(now)
    cache_key = f"week_{start.isoformat()}"
    cached = agenda_cache.get(cache_key)
    if cached is not None:
        return copy.deepcopy(cached)

    providers = [(
        apple_cache,
        cache_key,
        fetch_apple_events,
        "iCloud",
    )]
    for index, feed in enumerate(Config.get_ics_calendars()):
        url_digest = hashlib.sha256(feed["url"].encode("utf-8")).hexdigest()[:16]
        feed_key = f"{cache_key}_ics_{index}_{url_digest}"
        providers.append((
            ics_cache,
            feed_key,
            partial(fetch_ics_events, feed),
            f"ICS {feed['name']}",
        ))

    with ThreadPoolExecutor(max_workers=len(providers)) as executor:
        futures = [
            executor.submit(
                _provider_events,
                cache,
                key,
                fetcher,
                start,
                end,
                provider_name,
            )
            for cache, key, fetcher, provider_name in providers
        ]
        events = [event for future in futures for event in future.result()]

    events.sort(key=lambda event: (event["start"], event["end"], event["title"]))
    agenda = build_week_agenda(events, start, end)
    agenda_cache.set(cache_key, agenda)
    return agenda


def get_cached_week_agenda(now=None):
    start, _ = _week_bounds(now)
    cached = agenda_cache.get_stale(f"week_{start.isoformat()}")
    return copy.deepcopy(cached) if cached is not None else None


def get_empty_week_agenda(now=None):
    start, end = _week_bounds(now)
    return build_week_agenda([], start, end)
