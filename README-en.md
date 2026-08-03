# Kindle Scribe Dashboard Server

[中文](README.md)

This is a highly configurable **E-ink dashboard server** application, optimized by default for the Kindle Scribe in landscape orientation but adaptable to other devices.

It is intended to be used with a KUAL extension (or other tools) on the Kindle to provide a high-contrast, multi-language supported, and aesthetically pleasing "Always-on" second screen. With the new decoupled configuration, it can be easily adjusted for different screen resolutions and regions.

![Real Shot](demo_shot.avif)

*   **E-ink & Layout Optimization**:
    *   Bento Grid layout provides modular information blocks.
    *   Pure B&W high-contrast design with Floyd-Steinberg dithering for sharp E-ink display.
*   **Global Support**:
    *   **Localization**: Native support for Chinese (CN) and English (EN) with layout adjustments for long strings.
    *   **Configurable Location**: Set any Latitude/Longitude to get local weather, Air Quality (AQI), and UV index.
    *   **Regional Holidays**: Supports public holiday data for various countries via the `holidays` library.
*   **Rich Data Display**:
    *   **Weather**: Compact current conditions, today/tomorrow high and low, rain probability, next rain, and the next three hourly forecasts.
    *   **Weekly Calendar**: An 08:00–18:00 proportional time grid with side-by-side overlapping events, combining selected Apple iCloud calendars and multiple read-only ICS feeds. Calendars can be masked as Busy.
    *   **Financials**: Real-time tracking of currency, stocks, and crypto with sparklines.
    *   **News**: Top 5 stories from Hacker News, or from a custom external JSON source.
*   **Automated Rendering**:
    *   **Fully Configurable**: Manage resolution, language, location, and data sources via `.env`.
    *   **Multi-Device Adaptation**: The dashboard uses a 1680x1264 landscape design canvas, while the `/render` API scales and crops the output to the configured screen resolution (2480x1860 by default for Kindle Scribe).
    *   **Docker & CI/CD**: Easy deployment with Docker and automated builds via GitHub Actions.

## 🛠 Tech Stack

*   **Backend**: Python 3.12, Flask, uv
*   **Frontend**: HTML5, locally compiled Tailwind CSS
*   **Rendering**: Playwright (Chromium)
*   **Image Processing**: Pillow (Floyd-Steinberg Dithering)
*   **Data Sources**:
    *   `yfinance`: Stock and exchange rate data
    *   `lunardate`: Lunar date conversion
    *   `holidays`: Public holiday data
    *   `matplotlib`: Trend chart generation

### 1. Configuration

The project uses a `.env` file for configuration. Copy the template and edit as needed:

```bash
cp .env_example .env
nano .env # Configure location, language, resolution, tickers, etc.
```

### 2. Using Docker (Recommended)

```bash
docker pull ghcr.io/ec061/kindle-dashboard-server:master
docker run -p 5000:5000 --env-file .env \
  ghcr.io/ec061/kindle-dashboard-server:master
```

The ready-to-edit Scribe/UGA Compose example is in `docker-compose.scribe.yml`.

### 3. Calendar setup

Calendar data is refreshed every five minutes (`CACHE_TTL_CALENDAR=300`). A one-minute image refresh reuses the current calendar cache between provider refreshes.
The week view positions events on a proportional 08:00–18:00 grid by default. Change the visible range with `CALENDAR_DAY_START_HOUR` and `CALENDAR_DAY_END_HOUR`. Overlapping events share the day column, and the current-time line advances with each one-minute render.

For Apple iCloud CalDAV:

1. At [Apple Account → Sign-In and Security](https://account.apple.com/account/manage), create an **app-specific password**. Do not put your normal Apple password in `.env`.
2. Open Apple Calendar and note the exact display names of the calendars you want. Matching is case-insensitive; names are separated with commas.
3. Add the following values to the `.env` file next to `docker-compose.scribe.yml`:

   ```dotenv
   APPLE_CALENDAR_ENABLED=true
   APPLE_ID=your-apple-account@example.com
   APPLE_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
   APPLE_CALENDAR_NAMES=Work,Family,Personal
   APPLE_PRIVATE_CALENDAR_NAMES=Personal
   ```

   A blank `APPLE_CALENDAR_NAMES` includes every CalDAV calendar. Calendars named in `APPLE_PRIVATE_CALENDAR_NAMES` remain included, but their events display only as `Busy`/`忙碌`, with no title or location.

For published or subscribed ICS calendars, configure `ICS_CALENDARS` as a JSON array. Direct fetching is required because subscription calendars shown by Apple Calendar are not always exposed to third-party CalDAV clients:

```dotenv
ICS_CALENDARS='[{"name":"UGA Events","url":"https://example.com/private-feed.ics"},{"name":"Travel","url":"https://example.com/travel.ics","private":true}]'
```

Each entry accepts:

* `name`: the name displayed by the dashboard; omitted names become `ICS 1`, `ICS 2`, and so on.
* `url`: the private HTTPS address of the published ICS feed.
* `private`: optional; when `true`, event titles and locations are shown only as `Busy`/`忙碌`.

An array of URL strings is also accepted when custom names are not needed:

```dotenv
ICS_CALENDARS='["https://example.com/one.ics","https://example.com/two.ics"]'
```

For a QNAP Compose application, the same setting can be entered directly in the local YAML:

```yaml
ICS_CALENDARS: >-
  [{"name":"UGA Events","url":"https://example.com/private-feed.ics"}]
```

Treat every ICS URL as a password: keep it only in the NAS configuration, never commit it or paste it into public logs. A direct ICS feed does not need to be listed in `APPLE_CALENDAR_NAMES`.

After configuring iCloud or ICS feeds, start the service and check `http://localhost:5000/dashboard`. All sources refresh every five minutes. Each source has an independent stale cache, so a temporary failure in one feed does not clear the other calendars.

### 4. Kindle Scribe local overlays

The server leaves dedicated blank regions for FBInk to draw the clock and battery percentage locally. For the native 2480x1860 landscape layout, use:

```bash
ENABLE_LOCAL_CLOCK=1
CLOCK_X=60
CLOCK_Y=180
CLOCK_SIZE=118
CLOCK_FONT="${BASE_DIR}/IBMPlexMono-SemiBold.ttf"

BATT_X=2300
BATT_Y=62
BATT_SIZE=48
BATT_FONT="${BASE_DIR}/IBMPlexMono-SemiBold.ttf"
```

The battery box occupies approximately `x=2273–2456`, `y=31–152` in native Scribe pixels. Small adjustments may be needed if a different FBInk font is used.

### 5. Running Locally

1.  **Install uv**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2.  **Setup**:
    ```bash
    uv sync
    uv run playwright install chromium --with-deps
    ```
3.  **Run**: `uv run app.py`

## 🔌 API Endpoints

*   `GET /dashboard`: Returns the responsive web version of the dashboard.
*   `GET /render`: Returns the **Kindle-optimized (config-based resolution, 16-level grayscale, dithered)** PNG image.

## 📱 Companion Client

If you have a jailbroken Kindle, use this companion project to automate image fetching and power management:

*   **[Kindle-Dashboard](https://github.com/t0saki/Kindle-Dashboard)**: A KUAL extension script that handles automated networking, image downloading, and high-quality rendering using FBInk.

## 📄 License

MIT License
