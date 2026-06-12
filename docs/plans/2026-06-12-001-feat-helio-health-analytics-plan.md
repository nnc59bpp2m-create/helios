---
title: "feat: Helio Ring/Strap Health Analytics Platform with AI Coaching"
type: feat
status: active
date: 2026-06-12
origin: ""
deepened: ""
---

# Summary

Build a fullstack web application (FastAPI + React/Vite + SQLite) that pairs with Amazfit Helio Ring/Strap via BLE through a Zepp OS Mini Program, syncs raw sensor data (heart rate, HRV, SpO2, skin temperature, EDA, accelerometer) to a local backend, provides deep analytics dashboards with charting, delivers AI-driven coaching insights, and correlates physiological stress markers with calendar events (Google, iOS, Outlook/Graph with MDM support) to produce a "Stress Leaderboard" ranking meetings and colleagues by stress impact. Includes a cross-platform mobile wrapper (Capacitor) for iOS/Android. Push to public GitHub repo for version tracking.

# Problem Frame

The Zepp app shows limited metrics and lacks skin temperature visualization despite the Helio sensor having a temperature sensor. No official public API exists for real-time or historical raw data export. Gadgetbridge supports Helio Ring but is Android-only and lacks analytics/coaching. User wants a stats-freak grade analytics platform with AI coaching that works across web/iOS/Android, owns their data locally, and extracts maximum value from the Helio hardware.

# Requirements

## Data Acquisition
- R1. Pair with Helio Ring/Strap via BLE using Zepp OS Mini Program (Device App + Side Service architecture)
- R2. Stream real-time sensor data: heart rate, HRV (SDNN/RMSSD), SpO2, skin temperature, EDA, 3-axis accelerometer, 3-axis gyroscope
- R3. Sync historical data from Zepp cloud via Huami REST API (OAuth 2.0 with Xiaomi token exchange)
- R4. Fallback: support Gadgetbridge protocol for local BLE sync on Android (reference implementation)
- R5. Store all raw sensor readings with timestamps in local SQLite (time-series optimized schema)

## Analytics & Visualization
- R6. Dashboard with KPI cards: resting HR, HRV trend, SpO2 avg, skin temp baseline, recovery score, sleep quality
- R7. Interactive time-series charts: heart rate (continuous), HRV (daily), SpO2 (nocturnal), skin temperature (circadian), EDA (stress events)
- R8. Sleep staging visualization: hypnogram, phase durations, efficiency, latency, consistency score
- R9. Activity detection: auto-detect workouts from accelerometer/HR fusion, classify type, estimate intensity
- R10. Correlation analysis: HRV vs sleep, temp vs cycle phase, stress vs recovery, training load vs readiness
- R11. Export data to CSV/JSON/SQLite for external analysis

## AI Coaching
- R12. Daily readiness score (0-100) with contributing factors breakdown
- R13. Personalized insights: "Your HRV dropped 15% vs baseline — consider active recovery"
- R14. 30/60/90-day trend projections with confidence intervals
- R15. Anomaly detection: flag unusual patterns (elevated nocturnal HR, temp spikes, SpO2 dips)
- R16. Natural language Q&A: "How did my recovery trend last week?" → generated summary

## Platform & UX
- R17. Web app (PWA) with offline-first sync, dark mode, responsive layout
- R18. iOS/Android apps via Capacitor wrapping same React codebase
- R19. Real-time BLE data view when device in range (Web Bluetooth API on web, native BLE on mobile)
- R20. Multi-device support (Ring + Strap simultaneous, auto-reconcile overlapping data)
- R21. Data privacy: all data local-first, optional encrypted cloud backup (user-controlled)

## Calendar Integration & Stress Correlation
- R22. Sync calendar events from Google Calendar (OAuth 2.0), iOS Calendar (EventKit via Capacitor), Microsoft Outlook/Graph (OAuth 2.0 with MDM/Intune conditional access support)
- R23. Parse event metadata: title, organizer, attendees, start/end, location, recurrence, categorization (1:1, team, all-hands, external, focus-time)
- R24. Correlate sensor stress markers (EDA spikes, HRV drops, HR elevation, skin temp rise) ±30 min window around each event
- R25. Compute per-event stress score (0-100) with physiological evidence breakdown
- R26. Aggregate by organizer, attendee list, meeting series, calendar, and time-of-day → "Stress Leaderboard" rankings
- R27. Natural language insights: "Your 1:1s with [Name] average 78 stress score — HRV drops 22%", "Monday 9am all-hands: consistent EDA spikes"
- R28. Export correlation dataset (event + stress metrics) for external analysis

# Key Technical Decisions

- KTD1: **Zepp OS Mini Program as primary data bridge** — Device App on Helio reads sensors → Side Service on phone relays to our backend via HTTPS. Rationale: Official supported path, works on iOS/Android, accesses all sensor APIs including skin temp/EDA which BLE GATT may not expose.
- KTD2: **Huami REST API (OAuth 2.0) for historical backfill** — Exchange Xiaomi token → Huami access token → pull /users/-/heartrates, /users/-/sleep, /users/-/activities, /users/-/sensor (raw). Rationale: Only way to get multi-month history without manual CSV export.
- KTD3: **FastAPI + SQLite (with sqlite-utils / apsw) for backend** — Time-series schema with partitioned tables by month, indexes on (device_id, metric_type, timestamp). Rationale: Zero-config, portable, handles millions of rows, matches existing project patterns (conversation-stats-app, bd-dashboard).
- KTD4: **React + Vite + Tailwind + TanStack Query + Recharts for frontend** — Module C (existing app) design patterns. Dark mode via Tailwind `dark:` on `<html>`. Rationale: Consistent with KPMG BD Dashboard, conversation-stats-app Horizon 2.
- KTD5: **Capacitor for iOS/Android** — Single React codebase, native BLE plugin (`@capacitor-community/bluetooth-le`) for direct device connection when Mini Program not running. Rationale: Avoids Expo/React Native complexity, shares 95% code with web.
- KTD6: **Local LLM (Ollama) for AI coaching** — Gemma 3 12B or Nemotron 3 Ultra via Nous proxy for readiness scoring, insight generation, anomaly detection. Rationale: Free tier, privacy-preserving, no API keys, matches user's model budget constraints.
- KTD7: **Web Bluetooth API for browser-based real-time view** — Chrome/Edge support GATT; fallback to Mini Program relay on Safari/iOS. Rationale: Zero-install live data preview on desktop.

- KTD8: **Multi-provider calendar sync with token abstraction layer** — Google (OAuth 2.0 + refresh tokens), Microsoft Graph (OAuth 2.0 + device code flow for MDM/Intune conditional access), iOS EventKit (native via Capacitor plugin). Unified `CalendarEvent` schema normalizes all sources. Rationale: MDM-locked Outlook requires device code flow or brokered auth; Google/iOS are standard OAuth. Abstraction enables adding CalDAV/Exchange later.
- KTD9: **Stress correlation engine: time-window join + physiological weighting** — For each event, query sensor_readings in [start-30min, end+30min]. Weight: EDA (40%), HRV drop from baseline (30%), HR elevation above resting (20%), skin temp rise (10%). Score = weighted z-score normalized 0-100. Rationale: EDA is most specific to sympathetic activation; HRV is gold standard for autonomic balance; HR/temp are secondary confirmers.
- KTD10: **Attendee/entity resolution for leaderboards** — Extract organizer email, attendee emails, domain patterns. Fuzzy-match against contacts (Google People, Microsoft Graph People, local address book). Aggregate at person-level (not event-level) for "most stressful colleague" ranking. Rationale: Same person across different meeting series → single leaderboard entry. Domain-based fallback for external attendees.

# High-Level Technical Design

```mermaid
flowchart TB
    subgraph Helio[Helio Ring/Strap]
        S1[BioTracker PPG\nHR/HRV/SpO2]
        S2[Temp Sensor\nSkin Temp]
        S3[EDA Sensor\nStress]
        S4[IMU\nAccel/Gyro]
    end

    subgraph MiniProgram[Zepp OS Mini Program]
        DA[Device App\n@zos/sensor APIs]
        SS[Side Service\nFetch API → Backend]
        DA -->|ZML BLE| SS
    end

    subgraph Calendar[Calendar Providers]
        GCAL[Google Calendar\nOAuth 2.0]
        ICAL[iOS Calendar\nEventKit/Capacitor]
        O365[Microsoft Graph\nOAuth 2.0 + Device Code\nMDM/Intune Support]
    end

    subgraph Backend[FastAPI Backend :8000]
        API[REST API\n/api/v1/*]
        DB[(SQLite\nTime-series)]
        AI[AI Coach\nOllama/Local LLM]
        HUAMI[Huami REST\nOAuth Client]
        SYNC[Sync Scheduler\nCron/Background]
        CALSYNC[Calendar Sync\nMulti-provider]
        CORR[Stress Correlation\nEngine]
        LEADER[Leaderboard\nAggregator]
        API --> DB
        API --> AI
        SYNC --> HUAMI
        SYNC --> DB
        CALSYNC --> GCAL
        CALSYNC --> ICAL
        CALSYNC --> O365
        CALSYNC --> DB
        CORR --> DB
        LEADER --> DB
        SS -->|HTTPS POST| API
    end

    subgraph Frontend[React/Vite PWA :5173]
        DASH[Dashboard\nKPI + Charts]
        LIVE[Live BLE View\nWeb Bluetooth]
        MOBILE[Capacitor iOS/Android]
        CHAT[AI Coach Chat\nNatural Language]
        STRESS[Stress Calendar\nLeaderboard View]
        DASH -->|TanStack Query| API
        LIVE -->|Web Bluetooth| Helio
        MOBILE -.->|@capacitor/bluetooth-le| Helio
        CHAT --> API
        STRESS --> API
    end

    Helio -.->|BLE GATT\n(Fallback)| Frontend
    Frontend -->|HTTPS| Backend
```

# Implementation Units

### U1. Project Scaffold & Dev Environment
**Goal**: Initialize monorepo with backend, frontend, mobile configs, CI/CD
**Requirements**: R17, R18
**Dependencies**: None
**Files**:
- `backend/` — FastAPI app, `main.py`, `routers/`, `models/`, `services/`, `scripts/`
- `frontend/` — Vite + React + Tailwind + TypeScript, `src/`, `vite.config.ts`
- `mobile/` — Capacitor config, `capacitor.config.ts`, iOS/Android native projects
- `.github/workflows/ci.yml` — lint, typecheck, test, build
- `docker-compose.yml` — local dev stack (backend, frontend, ollama)
- `README.md`, `CONTRIBUTING.md`
**Patterns**: Follow `fullstack-web-application` skill, `kpmg-bd-dashboard-implementation.md` structure
**Test Scenarios**:
- `backend` starts on `:8000`, serves `/health` → 200
- `frontend` builds, `npm run build` succeeds, assets in `dist/`
- `mobile` `npx cap sync` completes without errors
- Docker compose up brings all services healthy

### U2. Zepp OS Mini Program: Device App + Side Service
**Goal**: Build Mini Program that reads all Helio sensors and relays to backend
**Requirements**: R1, R2
**Dependencies**: U1
**Files**:
- `mini-program/device-app/` — `app.js`, `page/index/`, `shared/message.js`, `device-polyfill.js`
- `mini-program/side-service/` — `app-side-service.js`, `shared/message-side.js`
- `mini-program/server/` — Node.js reference receiver (for testing)
- `docs/miniprogram-deploy.md` — Zeus CLI build/upload steps
**Approach**: Use ZML MessageBuilder for BLE comms. Device App: `HeartRate`, `BloodOxygen`, `Temperature`, `EDA`, `Accelerometer`, `Gyroscope` sensor APIs. Side Service: `fetch` to `POST /api/v1/ingest/telemetry` with batched readings.
**Patterns**: `post-health-data` sample, `bluetooth-communication` guide
**Test Scenarios**:
- Device App connects to Side Service via ZML (`connect()` → success)
- Side Service receives `request` type `UPLOAD` with payload containing all 6 sensor types
- Side Service POSTs to backend, receives 200 OK with ingestion ID
- `onDestroy` calls `disConnect()` — no memory leak

### U3. Huami REST API Client & Historical Backfill
**Goal**: OAuth 2.0 flow to pull months of historical data from Zepp cloud
**Requirements**: R3
**Dependencies**: U1
**Files**:
- `backend/services/huami_client.py` — token exchange, verified requests, pagination
- `backend/services/backfill.py` — orchestrate full historical sync with checkpointing
- `backend/routers/sync.py` — `/api/v1/sync/historical`, `/api/v1/sync/status`
- `backend/models/sync_state.py` — cursor/token storage
**Approach**: Exchange Xiaomi `access_token` + `app_id`/`app_secret` → Huami `access_token` + `refresh_token`. Paginate `/users/-/heartrates`, `/users/-/sleep`, `/users/-/activities`, `/users/-/sensor` (raw). Store raw JSON + normalized rows. Resume from last cursor on retry.
**Patterns**: `zepp-health/rest-api` DeepWiki, `ce-work` idempotent importer pattern
**Test Scenarios**:
- Valid Xiaomi token → Huami token exchange succeeds
- Paginated fetch of 30 days heart rate data → correct row count, no duplicates
- Interrupted sync resumes from checkpoint (no data loss, no re-fetch)
- Rate limit handling: 429 → exponential backoff, retry succeeds

### U4. SQLite Time-Series Schema & Ingestion Pipeline
**Goal**: High-throughput ingestion, efficient queries for dashboard
**Requirements**: R5, R6-R11
**Dependencies**: U1, U2, U3
**Files**:
- `backend/models/schema.sql` — partitioned tables, indexes, views
- `backend/services/ingest.py` — batch insert, deduplication, normalization
- `backend/routers/ingest.py` — `/api/v1/ingest/telemetry`, `/api/v1/ingest/batch`
- `backend/services/aggregation.py` — precompute daily/hourly rollups
- `backend/scripts/migrate.py` — idempotent migration runner
**Schema**:
```sql
CREATE TABLE sensor_readings (
  id INTEGER PRIMARY KEY,
  device_id TEXT NOT NULL,
  metric_type TEXT NOT NULL,  -- 'hr', 'hrv_sdnn', 'hrv_rmssd', 'spo2', 'skin_temp', 'eda', 'accel_x', 'accel_y', 'accel_z', 'gyro_x', 'gyro_y', 'gyro_z'
  value REAL NOT NULL,
  timestamp_ms INTEGER NOT NULL,
  source TEXT NOT NULL,  -- 'miniprogram', 'huami', 'gadgetbridge', 'ble_direct'
  raw_json TEXT
);
CREATE INDEX idx_sensor_device_metric_time ON sensor_readings(device_id, metric_type, timestamp_ms);
-- Monthly partitions via triggers or application-level sharding
```
**Patterns**: `fullstack-web-application` sqlite patterns, `ce-work` time-series partitioning
**Test Scenarios**:
- Insert 100k readings → < 2s, query last 7 days HR → < 50ms
- Duplicate ingestion (same device/metric/timestamp) → upsert, no duplicate rows
- Aggregation job computes daily HRV avg, min, max correctly
- Partition pruning works: query single month doesn't scan full table

### U5. REST API: Query Endpoints for Dashboard
**Goal**: Fast, typed endpoints for all dashboard data needs
**Requirements**: R6-R11
**Dependencies**: U4
**Files**:
- `backend/routers/metrics.py` — `/api/v1/metrics/*`
- `backend/routers/sleep.py` — `/api/v1/sleep/*`
- `backend/routers/activity.py` — `/api/v1/activity/*`
- `backend/routers/export.py` — `/api/v1/export/*` (CSV/JSON/SQLite streaming)
- `backend/services/query.py` — reusable query builders, cache layer (TTL 30s)
**Endpoints**:
- `GET /metrics/kpi?days=30` → resting_hr, hrv_trend, spo2_avg, skin_temp_baseline, recovery_score, sleep_quality
- `GET /metrics/timeseries?metric=hr&start=&end=&interval=1h` → downsampled arrays for charts
- `GET /sleep/stages?date=` → hypnogram array, phase durations, efficiency
- `GET /activity/sessions?days=30` → detected workouts with type, intensity, strain
- `GET /correlations?x=hrv&y=sleep_score&days=90` → scatter + regression
- `GET /export?format=csv&metrics=hr,hrv,spo2,temp&start=&end=` → streaming CSV
**Patterns**: `conversation-stats-app` analytics endpoints, `fullstack-web-application` API contract validation
**Test Scenarios**:
- KPI endpoint returns all 6 metrics with correct types
- Timeseries downsampling: 1M raw points → 720 hourly buckets, max/avg/min preserved
- Export streams 500k rows without OOM (generator + StreamingResponse)
- Response shapes match frontend TypeScript interfaces exactly

### U6. Frontend: Dashboard Core & KPI Cards
**Goal**: Main dashboard with real-time KPI cards, global date filter, responsive grid
**Requirements**: R6, R17
**Dependencies**: U1, U5
**Files**:
- `frontend/src/pages/Dashboard.tsx` — main layout, `GlobalFilterContext` (date range, device)
- `frontend/src/components/kpi/KPICard.tsx` — value, sparkline (MiniAreaChart), trend badge
- `frontend/src/components/charts/MiniAreaChart.tsx` — 120px inline trend, Recharts
- `frontend/src/hooks/useMetrics.ts` — TanStack Query wrappers for `/metrics/kpi`, `/metrics/timeseries`
- `frontend/src/context/GlobalFilterContext.tsx` — URL-synced filters (`replaceState`)
**Patterns**: `ce-frontend-design` Module D, `conversation-stats-dashboard-layout.md` Horizon 2
**Test Scenarios**:
- Dashboard loads, 6 KPI cards render with values + sparklines
- Date range picker updates URL, all charts refetch
- Mobile: stacks to single column, touch-friendly tap targets
- Dark mode: `.dark` on `<html>`, all CSS vars overridden, no white flash

### U7. Frontend: Interactive Time-Series Charts
**Goal**: Deep-dive chart pages for each metric with zoom, pan, cross-filtering
**Requirements**: R7, R10
**Dependencies**: U6
**Files**:
- `frontend/src/pages/HeartRate.tsx` — continuous HR, zones overlay, resting HR line
- `frontend/src/pages/HRV.tsx` — daily SDNN/RMSSD, baseline band, readiness correlation
- `frontend/src/src/pages/SpO2.tsx` — nocturnal SpO2, desaturation events, altitude overlay
- `frontend/src/pages/SkinTemperature.tsx` — circadian rhythm, cycle phase markers, baseline deviation
- `frontend/src/pages/EDA.tsx` — stress events timeline, recovery windows, sympathetic/parasympathetic balance
- `frontend/src/components/charts/TimeSeriesChart.tsx` — reusable: zoom, pan, brush, crosshair, legend
- `frontend/src/components/charts/CorrelationScatter.tsx` — R10 scatter with regression line
**Patterns**: `ce-frontend-design` data density, Recharts `Brush` + `Zoom` + `ReferenceArea`
**Test Scenarios**:
- HR chart: 30 days continuous data → smooth pan/zoom, zone bands render correctly
- HRV chart: baseline band (mean ± 1σ) visible, readiness score overlay toggles
- SpO2: desaturation events (<90%) marked, count matches backend
- Skin temp: 28-day cycle phase overlay aligns with user input
- Cross-filter: brushing date range on HR chart updates HRV chart range

### U8. Frontend: Sleep & Activity Pages
**Goal**: Sleep staging hypnogram, activity auto-detection, workout detail
**Requirements**: R8, R9
**Dependencies**: U5, U6
**Files**:
- `frontend/src/pages/Sleep.tsx` — hypnogram (REM/deep/light/awake), phase bars, consistency calendar
- `frontend/src/pages/Activity.tsx` — session list, type badges, strain score, route map (if GPS)
- `frontend/src/components/sleep/Hypnogram.tsx` — SVG/hypnogram with phase colors, 30-min epochs
- `frontend/src/components/activity/SessionCard.tsx` — type icon, duration, HR zones, strain
**Patterns**: `conversation-stats-horizon2-checklist.md` widget patterns, `ce-frontend-design` utility copy
**Test Scenarios**:
- Hypnogram: 8h sleep → 960 epochs render, phase colors match legend, total phase times sum to duration
- Activity list: auto-detected run/cycle/walk classified correctly from HR+accel fusion
- Session detail: HR zone distribution pie, strain calculation matches backend

### U9. Frontend: AI Coach Chat & Insights Panel
**Goal**: Natural language Q&A, daily readiness card, anomaly alerts, 30/60/90 projections
**Requirements**: R12-R16
**Dependencies**: U5, U6
**Files**:
- `frontend/src/pages/Coach.tsx` — chat interface, readiness header, insights feed
- `frontend/src/components/coach/ReadinessCard.tsx` — score 0-100, factor breakdown (HRV, sleep, temp, strain)
- `frontend/src/components/coach/InsightFeed.tsx` — scrollable cards: "HRV ↓15%", "Temp spike day 14"
- `frontend/src/components/coach/ProjectionChart.tsx` — 30/60/90 day forecast with CI bands
- `frontend/src/hooks/useCoach.ts` — streams `/api/v1/coach/chat`, `/api/v1/coach/readiness`, `/api/v1/coach/insights`
- `frontend/src/components/ui/ChatMessage.tsx` — user/assistant bubbles, markdown render, copy button
**Patterns**: `ce-frontend-design` conversational UI, `fullstack-web-application` SSE pattern for streaming
**Test Scenarios**:
- Readiness card: score computes from 4 factors, weights match backend config
- Chat: "How was my recovery last week?" → streams response, cites data (dates, values)
- Insights: anomaly detection flags nocturnal HR > baseline + 10bpm, temp > 37.5°C
- Projections: 30-day HRV forecast shows mean + 95% CI, updates weekly

### U10. Backend: AI Coach Service (Local LLM)
**Goal**: Readiness scoring, insight generation, anomaly detection, NL Q&A via Ollama
**Requirements**: R12-R16
**Dependencies**: U4, U5
**Files**:
- `backend/services/coach/readiness.py` — weighted formula: HRV (40%), sleep (30%), temp (15%), strain (15%)
- `backend/services/coach/insights.py` — rule-based + LLM: trend deltas, threshold breaches, pattern matches
- `backend/services/coach/anomaly.py` — statistical (z-score > 2.5) + isolation forest on multivariate
- `backend/services/coach/chat.py` — RAG over user's time-series: embed recent windows, retrieve, prompt LLM
- `backend/routers/coach.py` — `/api/v1/coach/readiness`, `/api/v1/coach/insights`, `/api/v1/coach/chat` (SSE)
- `backend/services/llm.py` — Ollama client, model management, prompt templates, streaming
**Approach**: Daily readiness computed at 06:00 local via cron. Insights generated on new data ingest. Chat: retrieve last 30 days relevant metrics → inject into system prompt → stream Gemma/Nemotron response. No external API calls.
**Patterns**: `fullstack-web-application` SSE, `llm-provider-routing` local-first, `ce-frontend-design` streaming chat
**Test Scenarios**:
- Readiness: HRV baseline 50ms, current 42ms → factor score ~60, total ~72
- Insights: generates "HRV dropped 16% vs 7-day avg" when true
- Anomaly: flags SpO2 dip to 88% at 03:00, HR spike to 120bpm during sleep
- Chat: "Why am I tired?" → references low HRV, high nocturnal temp, poor sleep efficiency

### U11. Capacitor iOS/Android Build & Native BLE
**Goal**: Mobile apps with native BLE direct connection (fallback when Mini Program unavailable)
**Requirements**: R18, R19
**Dependencies**: U1, U6
**Files**:
- `mobile/ios/App/App/` — Xcode project, `Info.plist` (NSBluetoothAlwaysUsageDescription)
- `mobile/android/app/src/main/` — `AndroidManifest.xml` (BLUETOOTH_CONNECT, BLUETOOTH_SCAN)
- `frontend/src/services/ble.ts` — abstract BLE interface (Web Bluetooth / Capacitor plugin)
- `frontend/src/services/ble-web.ts` — `navigator.bluetooth` implementation
- `frontend/src/services/ble-native.ts` — `@capacitor-community/bluetooth-le` implementation
- `capacitor.config.ts` — plugins: `BluetoothLe`, `LocalNotifications`, `BackgroundTask`
**Approach**: Detect platform at runtime → use Web Bluetooth on Chrome/Edge/WebView, Capacitor plugin on iOS/Safari/Android native. Parse Helio GATT: Heart Rate (0x180D), Battery (0x180F), Device Info (0x180A), Zepp custom service for temp/EDA/IMU. Stream to backend via same `/ingest/telemetry`.
**Patterns**: `ce-frontend-design` Module C, `fullstack-web-application` mobile patterns
**Test Scenarios**:
- iOS build: `npx cap open ios` → Xcode builds, app launches, requests Bluetooth permission
- Android build: `npx cap open android` → Gradle builds, app installs, scans for Helio
- BLE connect: discovers Helio, reads HR notify characteristic, parses BPM correctly
- Background: iOS background task processes queued readings when app backgrounded

### U12. Gadgetbridge Protocol Support (Android Fallback)
**Goal**: Optional local sync via Gadgetbridge DB for Android users without Mini Program
**Requirements**: R4
**Dependencies**: U4
**Files**:
- `backend/services/gadgetbridge.py` — read `Gadgetbridge` SQLite, parse `MI_BAND_ACTIVITY_SAMPLE`, `HEART_RATE`, `HRV`, `SPO2`, `TEMPERATURE` tables
- `backend/routers/sync.py` — add `/api/v1/sync/gadgetbridge` endpoint
- `docs/gadgetbridge-import.md` — user guide: export GB DB, upload, import
**Approach**: User copies `Gadgetbridge` DB from phone → upload via web UI → backend parses known tables → normalizes to `sensor_readings`. Reference: Gadgetbridge commit `33c012e1b` for Helio Ring schema.
**Patterns**: `healthdata-export-tools` multi-source parsing, idempotent import
**Test Scenarios**:
- Sample GB DB with Helio data → imports HR, HRV, sleep, SpO2, temp without errors
- Duplicate import → upsert, no duplicate rows
- Missing tables (old GB version) → graceful skip, log warning

### U13. PWA Configuration & Offline-First Sync
**Goal**: Installable web app, background sync, offline chart viewing
**Requirements**: R17
**Dependencies**: U6, U7, U8, U9
**Files**:
- `frontend/public/manifest.webmanifest` — name, icons, display: standalone
- `frontend/vite.config.ts` — `vite-plugin-pwa` config, runtime caching
- `frontend/src/sw.ts` — Workbox: precache shell, runtime cache API (stale-while-revalidate)
- `frontend/src/services/sync.ts` — IndexedDB queue for offline mutations, Background Sync API
- `frontend/src/hooks/useOnline.ts` — navigator.onLine listener, toast on reconnect
**Patterns**: `fullstack-web-application` PWA patterns, `ce-frontend-design` offline UX
**Test Scenarios**:
- Lighthouse PWA score > 90
- Offline: open cached dashboard, view last-synced charts, no console errors
- Online: background sync flushes queued ingest, toast "Synced 47 readings"

### U14. Multi-Device Reconciliation & Data Privacy
**Goal**: Merge Ring + Strap streams, encrypt local DB, optional encrypted cloud backup
**Requirements**: R20, R21
**Dependencies**: U4, U5
**Files**:
- `backend/services/reconcile.py` — time-window merge (5-min), prefer higher fidelity (Ring HRV > Strap), gap fill
- `backend/services/encryption.py` — SQLCipher if available, else application-level AES-GCM per row
- `backend/routers/backup.py` — `/api/v1/backup/create`, `/api/v1/backup/restore` (user password → PBKDF2 → encrypt SQLite → upload to S3/R2/Drive)
- `frontend/src/pages/Settings.tsx` — device management, encryption toggle, backup config
**Approach**: Each device gets `device_id` (MAC-based hash). Reconciliation runs hourly cron. Encryption opt-in: derive key from user passphrase, encrypt `value` + `raw_json` columns. Backup: stream encrypted DB to presigned URL.
**Patterns**: `ce-frontend-design` settings UX, `fullstack-web-application` cron patterns
**Test Scenarios**:
- Ring + Strap overlapping 1hr → merged timeline, no duplicates, Ring HRV preferred
- Encryption on → `value` column unreadable without key, query via API works
- Backup create → encrypted file, restore → identical row count, values match

### U15. CI/CD, GitHub Release, Documentation
**Goal**: Automated testing, public repo, release artifacts, user docs
**Requirements**: All
**Dependencies**: U1-U14
**Files**:
- `.github/workflows/ci.yml` — matrix: backend (pytest), frontend (vitest, playwright), mobile (gradle, xcodebuild)
- `.github/workflows/release.yml` — tag push → build, sign, upload APK/IPA/Web bundle
- `docs/architecture.md` — system diagram, data flow, schema
- `docs/api.md` — OpenAPI spec (auto-generated from FastAPI)
- `docs/user-guide.md` — pairing, Mini Program install, mobile app install, features
- `docs/developer-guide.md` — extending sensors, adding metrics, custom AI prompts
**Patterns**: `github-repo-management`, `fullstack-web-application` verification gates
**Test Scenarios**:
- CI passes on main branch
- Release workflow publishes GitHub Release with `helios-web.tar.gz`, `helios-android.apk`, `helios-ios.ipa`
- `docs/api.md` matches live `/openapi.json`
- User guide: fresh user can pair Helio → see data in < 10 min

### U16. Calendar Sync: Multi-Provider OAuth & Event Ingestion
**Goal**: Unified calendar sync across Google, iOS, Outlook/Graph with MDM support
**Requirements**: R22, R23
**Dependencies**: U1, U4, U5
**Files**:
- `backend/services/calendar/base.py` — abstract `CalendarProvider` interface, `CalendarEvent` schema
- `backend/services/calendar/google.py` — Google Calendar API v3, OAuth 2.0, refresh token rotation, incremental sync (`syncToken`)
- `backend/services/calendar/outlook.py` — Microsoft Graph API, OAuth 2.0 + device code flow for MDM/Intune, delta query (`$delta`), brokered auth detection
- `backend/services/calendar/ios.py` — Capacitor EventKit plugin bridge, local calendar access on device
- `backend/services/calendar/sync_orchestrator.py` — scheduled sync (15-min), conflict resolution, deduplication by `ical_uid`
- `backend/routers/calendar.py` — `/api/v1/calendar/connect/{provider}`, `/api/v1/calendar/sync`, `/api/v1/calendar/events`, `/api/v1/calendar/categorize`
- `backend/models/calendar.py` — `calendar_accounts`, `calendar_events`, `calendar_sync_state` tables
**Approach**: Each provider implements `list_events(since)`, `get_event(uid)`, `watch_changes()`. Normalize to `CalendarEvent`: `uid`, `provider`, `account_id`, `title`, `organizer_email`, `attendee_emails[]`, `start_ms`, `end_ms`, `location`, `recurrence_rule`, `category` (1:1, team, all-hands, external, focus, personal). Categorization: heuristic (attendee count, organizer domain, keywords) + user overrides stored in DB.
**Patterns**: `fullstack-web-application` sync patterns, `google-workspace` skill for Google API, `outlook-graph-api` skill for Microsoft Graph
**Test Scenarios**:
- Google OAuth flow → tokens stored encrypted, incremental sync fetches only changes
- Outlook device code flow → works without browser on headless/server, handles Conditional Access MFA
- iOS EventKit → reads local calendars on device, syncs via Capacitor bridge
- Categorization: 1 attendee + same org domain → "1:1"; >5 attendees + "all-hands" in title → "all-hands"
- Deduplication: same `ical_uid` across providers → single merged event

### U17. Stress Correlation Engine & Per-Event Scoring
**Goal**: Join sensor windows with calendar events, compute physiological stress scores
**Requirements**: R24, R25
**Dependencies**: U4, U5, U16
**Files**:
- `backend/services/correlation/engine.py` — time-window join, sensor aggregation, z-score normalization
- `backend/services/correlation/scoring.py` — weighted stress score (EDA 40%, HRV 30%, HR 20%, Temp 10%), baseline computation
- `backend/services/correlation/baselines.py` — rolling 28-day baselines per metric, circadian adjustment
- `backend/routers/correlation.py` — `/api/v1/correlation/events`, `/api/v1/correlation/event/{uid}`, `/api/v1/correlation/recompute`
- `backend/models/correlation.py` — `event_stress_scores`, `stress_baselines` tables
**Approach**: For each event, query `sensor_readings` in `[start_ms - 1800000, end_ms + 1800000]` (±30 min). Compute: EDA mean/peak/area-under-curve, HRV (SDNN/RMSSD) min/mean vs baseline, HR max/mean vs resting baseline, skin temp max/mean vs circadian baseline. Weighted z-score → 0-100. Store per-event breakdown + aggregate daily/weekly. Recompute on baseline updates (nightly cron).
**Patterns**: `fullstack-web-application` analytics endpoints, `ce-work` time-series join patterns
**Test Scenarios**:
- Event with known EDA spike → score > 70, EDA component > 60
- Baseline computation: 28 days data → rolling mean/std per hour-of-day
- Recompute after new baseline → scores shift correctly, audit trail preserved
- No sensor data in window → score = null, flagged for review

### U18. Leaderboard Aggregation & Stress Calendar UI
**Goal**: Aggregate by person/meeting series/time → leaderboard rankings + calendar view
**Requirements**: R26, R27
**Dependencies**: U17, U6, U9
**Files**:
- `backend/services/leaderboard/aggregator.py` — person-level (attendee email fuzzy-match), meeting-series (recurrence UID), time-of-day, calendar, category rollups
- `backend/services/leaderboard/contacts.py` — contact resolution: Google People API, Microsoft Graph People, local vCard/CSV import
- `backend/routers/leaderboard.py` — `/api/v1/leaderboard/people`, `/api/v1/leaderboard/series`, `/api/v1/leaderboard/time-of-day`, `/api/v1/leaderboard/export`
- `frontend/src/pages/StressCalendar.tsx` — calendar heatmap (month view), event color by stress score, click → detail drawer
- `frontend/src/pages/StressLeaderboard.tsx` — ranked tables: People (avg score, count, trend), Series, Time-slots, Categories
- `frontend/src/components/stress/EventDetailDrawer.tsx` — physiological breakdown, sensor mini-chart, attendee list, AI insight
- `frontend/src/components/stress/StressHeatmap.tsx` — React-Calendar or custom, color scale 0-100, tooltip with score
- `frontend/src/hooks/useStressCorrelation.ts` — TanStack Query for leaderboard + calendar endpoints
**Approach**: People leaderboard: fuzzy-match attendee emails → resolve to person (name, avatar, org). Aggregate: mean score, event count, 30-day trend (slope). Meeting series: group by `recurrence_uid` or title similarity. Time-of-day: bucket by hour, show avg stress by hour. Calendar view: month grid, each day shows max/avg stress, click expands to event list.
**Patterns**: `ce-frontend-design` Module D (data dashboards), `conversation-stats-dashboard-layout.md` heatmap patterns
**Test Scenarios**:
- People leaderboard: "John Doe" (john@company.com, j.doe@partner.com) → single entry, avg 72, 15 events, trend ↓
- Calendar heatmap: June 2026 → each day colored, hover shows top 3 events
- Event drawer: shows HRV drop -18%, EDA peak 2.3µS, HR +22bpm, AI insight: "Highest EDA spike this month"
- Export: CSV with event_uid, title, organizer, attendees[], start, end, stress_score, component_scores

### U19. Calendar Privacy Controls & MDM Hardening
**Goal**: Granular privacy, token security, MDM/Intune compliance for Outlook
**Requirements**: R21, R22, R28
**Dependencies**: U14, U16
**Files**:
- `backend/services/calendar/token_vault.py` — encrypted token storage (per-account AES-GCM, key from user passphrase + device fingerprint)
- `backend/services/calendar/mdm.py` — Intune MAM SDK integration detection, conditional access token validation, app protection policy awareness
- `backend/routers/calendar_privacy.py` — `/api/v1/calendar/privacy`, `/api/v1/calendar/accounts/{id}/scope`, `/api/v1/calendar/export-correlation`
- `frontend/src/pages/CalendarSettings.tsx` — per-account toggle, category filters (exclude "personal", "focus-time"), data retention, delete account + purge events
- `docs/mdm-outlook-setup.md` — admin guide: Intune app protection policy, conditional access exclusion, device compliance
**Approach**: Tokens never in logs, encrypted at rest. Per-account sync scope: "all calendars" vs "selected calendars". Category exclusions: events matching "personal", "doctor", "therapy", "focus" → skip correlation. Retention: raw events 90 days, aggregated scores 1 year. Export: correlation dataset (event + stress) → CSV/JSON, no raw sensor data. MDM: detect `IntuneMAMEnrollment` env, use Graph `deviceCode` flow, respect `ManagedBrowser` requirement.
**Patterns**: `fullstack-web-application` encryption patterns, `outlook-graph-api` MDM patterns
**Test Scenarios**:
- Token vault: encrypt/decrypt round-trip, wrong passphrase → failure
- Category exclusion: "Personal: Doctor" event → not in leaderboard, not correlated
- Retention purge: events > 90 days → deleted, aggregates preserved
- Export: correlation CSV has event_uid, stress_score, components, no HR/EDA raw values
- MDM: device code flow completes on enrolled device, fails on unmanaged (configurable)

# Scope Boundaries

## Deferred for Later
- Watch face / complication for Zepp OS showing readiness score
- Social features: share insights, compare with friends (opt-in)
- Integration with Apple Health / Google Fit / Health Connect
- Advanced ML: custom models per user (fine-tune on local data)
- Voice coaching via TTS during workouts
- CalDAV / Exchange on-prem calendar support (beyond Graph/Google/iOS)
- Real-time stress alert during meetings (requires continuous BLE + low latency)

## Outside This Product's Identity
- Firmware modification or flashing
- Reverse-engineering proprietary Zepp protocols beyond public APIs
- Cloud-hosted multi-tenant SaaS (this is local-first, single-user)
- Medical diagnosis or FDA-cleared claims
- Calendar management (create/edit/delete events) — read-only correlation only

# Risks & Dependencies

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Zepp OS Mini Program API changes | Medium | High | Pin API_LEVEL, monitor zepp-health/discussions, fallback to Gadgetbridge/BLE |
| Huami REST API rate limits / deprecation | Medium | High | Cache aggressively, respect Retry-After, local-first design works without cloud |
| iOS Web Bluetooth not supported | High | Medium | Capacitor native BLE plugin covers iOS; Mini Program works on iOS via Zepp app |
| Helio GATT custom service undocumented | Medium | High | Reference Gadgetbridge implementation, Mini Program uses official sensor APIs |
| Local LLM quality insufficient for coaching | Low | Medium | Rule-based insights as fallback, prompt engineering, upgrade model when available |
| SQLite write throughput at scale | Low | Low | Partitioned tables, batch inserts, WAL mode, consider TimescaleDB if needed |
| Google Calendar API quota / breaking changes | Low | Medium | Incremental syncToken, exponential backoff, monitor workspace dev blog |
| Microsoft Graph MDM/Intune conditional access blocks device code flow | Medium | High | Document admin config (Intune app protection policy, CA exclusion), fallback to brokered auth via Authenticator app, test on enrolled device |
| iOS EventKit permission denied / background access limited | Medium | Medium | Request full access at setup, guide user to Settings > Privacy > Calendars, Capacitor plugin handles runtime permissions |
| Attendee email fuzzy-match false positives (common names) | Medium | Low | Require domain match + frequency threshold, manual merge/split UI, confidence score in leaderboard |
| Calendar token rotation / revocation breaks sync | Low | High | Encrypted vault with rotation handling, webhook/notification for revocation (Graph `changeNotifications`, Google `watch`), graceful re-auth flow |

# Sources & Research

- Zepp OS Mini Program architecture: `zepp-health/zeppos-samples/post-health-data` (Device App + Side Service + ZML)
- Huami REST API: `zepp-health/rest-api` (OAuth 2.0, `/users/-/heartrates`, `/users/-/sleep`, `/users/-/sensor`)
- Gadgetbridge Helio Ring support: `Freeyourgadget/Gadgetbridge#5127` (commits `33c012e1b`, `064782422`)
- Health data export parsing: `Sarmkadan/healthdata-export-tools` (multi-format, analytics engine)
- Fullstack patterns: `conversation-stats-app` (Horizon 2), `bd-dashboard` (KPMG), `fullstack-web-application` skill
- Frontend design: `ce-frontend-design` Module D (data dashboards), dark mode fix, animation verification
- Capacitor BLE: `@capacitor-community/bluetooth-le` (cross-platform GATT)
- Local LLM: Ollama + Gemma 3 12B / Nemotron 3 Ultra via Nous free tier
- Google Calendar API: v3 incremental sync (`syncToken`), watch notifications, People API for contact resolution
- Microsoft Graph API: delta query (`$delta`), device code flow (MDM/Intune), change notifications, People API, Conditional Access / Intune MAM SDK docs
- iOS EventKit: Capacitor `@capacitor-community/eventkit` or custom plugin, full calendar access entitlement
- Stress physiology: EDA/HRV/HR correlation literature (sympathetic activation markers), circadian baseline methods

# Implementation Sequence

```
U1 (scaffold) → U2 (Mini Program) → U3 (Huami backfill) → U4 (DB/ingest) → U5 (API)
    ↓
U6 (Dashboard core) → U7 (Charts) → U8 (Sleep/Activity) → U9 (Coach UI)
    ↓
U10 (Coach backend) ← U11 (Mobile) ← U12 (Gadgetbridge) ← U13 (PWA) ← U14 (Multi-device/Privacy)
    ↓
U16 (Calendar sync) → U17 (Correlation engine) → U18 (Leaderboard UI) → U19 (Privacy/MDM)
    ↓
U15 (CI/CD, Release, Docs)
```

Parallelizable after U5: U6-U9 (frontend), U10 (backend AI), U11-U14 (platform features).
Parallelizable after U16: U17 (correlation), U18 (leaderboard frontend) can start with mock data.

# Verification Gates

1. **U2**: Mini Program builds with Zeus CLI, installs on Helio via Zepp app, streams live HR to backend
2. **U3**: Historical backfill pulls 90 days of data for test account, row counts match Zepp app
3. **U4+U5**: Dashboard loads in < 2s with 1M readings, timeseries queries < 100ms
4. **U6-U9**: Lighthouse Performance > 90, Accessibility > 95, PWA > 90
5. **U10**: Coach readiness matches manual calculation, chat streams coherent responses
6. **U11**: iOS TestFlight build installs, BLE connects to Helio, background sync works
7. **U16**: Google OAuth + Outlook device code + iOS EventKit all connect, incremental sync fetches only changes, categorization accuracy > 90% on labeled set
8. **U17**: Known high-stress event (public speaking, difficult 1:1) → score > 75, component breakdown matches physiological expectation
9. **U18**: Leaderboard ranks top 5 people by avg stress, calendar heatmap renders month view, event drawer shows sensor evidence + AI insight
10. **U19**: Token vault encrypt/decrypt works, category exclusion filters events, MDM device code flow completes on enrolled test device, export CSV has correct schema
11. **U15**: GitHub Release publishes all three artifacts, docs render on GitHub Pages