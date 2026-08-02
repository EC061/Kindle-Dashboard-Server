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
    *   **Weekly Calendar**: A seven-day view combining selected Apple iCloud calendars with the UGA Microsoft 365 default calendar. Apple calendars can be masked as Busy by calendar name.
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
# Persist the Microsoft token cache across container updates.
mkdir -p kindle-dashboard-data
docker run -p 5000:5000 --env-file .env \
  -v "$PWD/kindle-dashboard-data:/data" \
  ghcr.io/ec061/kindle-dashboard-server:master
```

The ready-to-edit Scribe/UGA Compose example is in `docker-compose.scribe.yml`.

### 3. Calendar setup

Calendar data is refreshed every five minutes (`CACHE_TTL_CALENDAR=300`). A one-minute image refresh reuses the current calendar cache between provider refreshes.

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

   A blank `APPLE_CALENDAR_NAMES` includes every Apple calendar. Calendars named in `APPLE_PRIVATE_CALENDAR_NAMES` remain included, but their events display only as `Busy`/`忙碌`, with no title or location. The private list does not affect Microsoft events.

For the UGA Microsoft 365 default calendar:

1. In the [Microsoft Entra admin center](https://entra.microsoft.com/), open **App registrations → New registration** and create an application for the UGA organizational directory. If UGA blocks app registration, an administrator must create or approve it.
2. Open **Authentication → Advanced settings** for the application and set **Allow public client flows** to **Yes**. No client secret or redirect URI is needed for device-code login.
3. Open **API permissions → Add a permission → Microsoft Graph → Delegated permissions**, add `Calendars.Read`, and complete administrator consent if UGA requires it.
4. Copy the **Application (client) ID** and **Directory (tenant) ID** from the application's Overview page into `.env`:

   ```dotenv
   MICROSOFT_CALENDAR_ENABLED=true
   MICROSOFT_CLIENT_ID=00000000-0000-0000-0000-000000000000
   MICROSOFT_TENANT_ID=00000000-0000-0000-0000-000000000000
   ```

   `organizations` can be used instead of a tenant ID for a multi-tenant organizational app. The tenant ID is recommended for a UGA-only registration.
5. Complete the one-time device login while the persistent `/data` volume is mounted:

   ```bash
   docker compose -f docker-compose.scribe.yml run --rm kindle-dashboard-server \
     uv run python microsoft_auth.py
   ```

Follow the printed URL and code, then sign in with the UGA Microsoft 365 account. Only its **default calendar** is read. Microsoft event names, locations, times, and durations are shown in full.

The refreshable Microsoft token cache is stored with owner-only permissions at `/data/microsoft-token-cache.json`. The Compose file maps it to `./kindle-dashboard-data`, so it survives image updates. To change accounts or recover from a revoked login, stop the service, delete `kindle-dashboard-data/microsoft-token-cache.json`, and run the device-login command again.

After configuring either provider, start the service and check `http://localhost:5000/dashboard`. Provider failures reuse the last successful five-minute cache instead of clearing the week view.

### 4. Running Locally

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
