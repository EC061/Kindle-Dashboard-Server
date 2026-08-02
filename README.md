# Kindle Scribe Dashboard Server

[English](README-en.md)

这是一个默认针对横屏 **Kindle Scribe** (2480x1860) 优化的 E-ink 仪表盘服务端程序，同时也可适配其他设备。

它旨在配合 Kindle 上的 KUAL 扩展（或其他浏览器/截图工具）使用，提供一个高对比度、低刷新率、信息丰富且美观的 "Always-on" 桌面副屏。

![Real Shot](demo_shot.avif)

*   **全球化支持**: 
    *   **多语言界面**: 原生支持中文 (CN) 和英文 (EN) 切换，自动调整排版以防止溢出（如长单词排版）。
    *   **自定义地理位置**: 可配置全球任何城市的经纬度，自动获取当地天气及空气质量 (AQI)。
    *   **多国节假日**: 集成 `holidays` 库，支持配置不同国家/地区的法定节假日。
*   **丰富的数据展示**:
    *   **天气预报**: 紧凑显示当前天气、今日/明日高低温和降雨概率、下次降雨时间，以及未来三小时预报。
    *   **七日日历**: 合并指定的 Apple iCloud 日历与 UGA Microsoft 365 默认日历；可按 Apple 日历名称将活动隐藏为“忙碌”。
    *   **金融市场**: 实时追踪汇率、股票及加密货币走势，生成迷你趋势图 (Sparklines)。
    *   **Hacker News**: 自动抓取热门科技新闻，支持自定义外部新闻源。
*   **服务端自动化渲染**:
    *   **高度可配置**: 通过 `.env` 文件配置分辨率、语言、位置、数据源和缓存时间。
    *   **高质量抖动算法**: 渲染 16 级灰度图像并应用 **Floyd-Steinberg 抖动**，为 E-ink 屏提供最佳观感。
    *   **适配多设备**: Dashboard 使用 1680x1264 横屏设计画布保证排版，`/render` 接口会自动缩放并裁切到配置的屏幕分辨率（Kindle Scribe 默认为 2480x1860）。
    *   **Docker & CI/CD**: 支持 Docker 部署，集成 GitHub Actions。

## 🛠 技术栈

*   **后端**: Python 3.12, Flask, uv
*   **前端**: HTML5, 本地编译的 Tailwind CSS
*   **渲染**: Playwright (Chromium)
*   **图像处理**: Pillow (Floyd-Steinberg Dithering)
*   **数据源**:
    *   `yfinance`: 股票与汇率数据
    *   `lunardate`: 农历转换
    *   `holidays`: 节假日数据
    *   `matplotlib`: 生成趋势图

### 1. 配置文件

项目使用 `.env` 文件进行配置。请先复制模版并根据需要修改：

```bash
cp .env_example .env
nano .env # 修改经纬度、语言、分辨率等
```

### 2. 使用 Docker (推荐)

```bash
docker pull ghcr.io/ec061/kindle-dashboard-server:master
# 持久保存 Microsoft 登录令牌，容器更新后无需重新登录
mkdir -p kindle-dashboard-data
docker run -p 5000:5000 --env-file .env \
  -v "$PWD/kindle-dashboard-data:/data" \
  ghcr.io/ec061/kindle-dashboard-server:master
```

项目内的 `docker-compose.scribe.yml` 是已经按 Scribe 与 UGA 设置好的可编辑示例。

### 3. 日历设置

日历数据每五分钟更新一次（`CACHE_TTL_CALENDAR=300`）。图片即使每分钟刷新，也会在两次日历更新之间复用缓存。

Apple iCloud CalDAV：

1. 在 [Apple 账户 → 登录与安全](https://account.apple.com/account/manage) 中创建 **App 专用密码**。不要把正常的 Apple 密码写进 `.env`。
2. 在 Apple 日历中确认要同步的日历显示名称。名称匹配不区分大小写，多个名称用逗号分隔。
3. 在 `docker-compose.scribe.yml` 同目录的 `.env` 中加入：

   ```dotenv
   APPLE_CALENDAR_ENABLED=true
   APPLE_ID=your-apple-account@example.com
   APPLE_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
   APPLE_CALENDAR_NAMES=Work,Family,Personal
   APPLE_PRIVATE_CALENDAR_NAMES=Personal
   ```

   `APPLE_CALENDAR_NAMES` 留空表示全部 Apple 日历。`APPLE_PRIVATE_CALENDAR_NAMES` 中的日历仍会显示，但活动只显示“忙碌”，隐藏标题和地点。该隐私列表不影响 Microsoft 活动。

UGA Microsoft 365 默认日历：

1. 在 [Microsoft Entra 管理中心](https://entra.microsoft.com/) 中打开 **应用注册 → 新注册**，为 UGA 组织目录创建应用。如果 UGA 禁止用户注册应用，需要管理员创建或批准。
2. 打开应用的 **身份验证 → 高级设置**，将 **允许公共客户端流** 设为 **是**。设备代码登录不需要客户端密钥或重定向 URI。
3. 打开 **API 权限 → 添加权限 → Microsoft Graph → 委托的权限**，添加 `Calendars.Read`；如 UGA 要求，还需完成管理员同意。
4. 从应用“概述”页复制 **应用程序（客户端）ID** 和 **目录（租户）ID** 到 `.env`：

   ```dotenv
   MICROSOFT_CALENDAR_ENABLED=true
   MICROSOFT_CLIENT_ID=00000000-0000-0000-0000-000000000000
   MICROSOFT_TENANT_ID=00000000-0000-0000-0000-000000000000
   ```

   多租户组织应用可以用 `organizations` 代替租户 ID；UGA 专用注册建议使用实际租户 ID。
5. 挂载持久化 `/data` 卷后，执行一次设备登录：

   ```bash
   docker compose -f docker-compose.scribe.yml run --rm kindle-dashboard-server \
     uv run python microsoft_auth.py
   ```

按终端中显示的网址和代码操作，然后使用 UGA Microsoft 365 账户登录。程序只读取该账户的 **默认日历**，Microsoft 活动的名称、地点、时间和时长会完整显示。

Microsoft 可刷新令牌会以仅文件所有者可读的权限保存在 `/data/microsoft-token-cache.json`。Compose 文件将其映射到 `./kindle-dashboard-data`，因此更新镜像不会丢失登录。如需更换账户或修复已撤销的登录，先停止服务，删除 `kindle-dashboard-data/microsoft-token-cache.json`，再重新执行设备登录命令。

配置任一提供商后，启动服务并访问 `http://localhost:5000/dashboard` 检查。如果提供商暂时失败，界面会继续使用上次成功的五分钟缓存，不会清空周视图。

### 4. Kindle Scribe 本地叠加信息

服务端为 FBInk 在 Kindle 上本地绘制时钟和电池百分比保留了空白区域。原生 2480x1860 横屏布局可使用：

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

电池框在 Scribe 原生像素中约为 `x=2273–2456`、`y=31–152`。如果使用不同的 FBInk 字体，可能需要小幅调整。

### 5. 本地运行

1.  **安装 uv**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2.  **准备环境**:
    ```bash
    uv sync
    uv run playwright install chromium --with-deps
    ```
3.  **运行**: `uv run app.py`

## 🔌 API 接口

*   `GET /dashboard`: 返回响应式网页版的仪表盘。
*   `GET /render`: 返回 **Kindle 优化版 (根据配置的分辨率, 16级灰度, 抖动处理)** 的 PNG 图片。这是 Kindle 客户端最常用的接口。

## 📱 配套客户端

如果你拥有越狱后的 Kindle，可以配合以下客户端项目使用，实现自动化刷新与休眠管理：

*   **[Kindle-Dashboard](https://github.com/t0saki/Kindle-Dashboard)**: 运行在 Kindle 上的 KUAL 插件脚本，负责自动联网、下载图片并使用 FBInk 高质量渲染。

## 📄 许可证

MIT License
