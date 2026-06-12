# Helios - Helio Ring/Strap Health Analytics Platform

A comprehensive health analytics platform for Amazfit Helio Ring/Strap with AI-driven coaching and stress calendar correlation.

## Features

- **Real-time Sensor Data**: Heart rate, HRV (SDNN/RMSSD), SpO₂, skin temperature, EDA, 3-axis accelerometer/gyroscope
- **Zepp OS Mini Program**: Official device app + side service for iOS/Android
- **Historical Backfill**: Huami REST API (OAuth 2.0) for months of historical data
- **Deep Analytics Dashboard**: KPI cards, interactive charts, sleep staging, activity detection
- **AI Coaching**: Daily readiness score, anomaly detection, 30/60/90-day projections, natural language Q&A
- **Stress Calendar Correlation**: Sync Google Calendar, iOS Calendar, Outlook/Graph (MDM/Intune) → stress leaderboard
- **Cross-platform**: Web (PWA), iOS, Android via Capacitor
- **Local-first**: SQLite database, optional encrypted backup, no required cloud

## Architecture

```
Helio Ring/Strap
    │
    ├── Zepp OS Mini Program (Device App + Side Service) ──► Backend API
    ├── Huami REST API (Historical) ───────────────────────► Backend API
    ├── Gadgetbridge (Android Fallback) ───────────────────► Backend API
    └── Web Bluetooth / Capacitor BLE (Direct) ────────────► Backend API
                          │
                    FastAPI + SQLite (Time-series)
                          │
                    React + Vite + Tailwind + Recharts
                          │
                    Capacitor iOS/Android
```

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker & Docker Compose (optional)
- Ollama (for local AI coaching)

### Using Docker Compose (Recommended)

```bash
# Start all services
docker-compose up -d

# Backend: http://localhost:8000
# Frontend: http://localhost:5173
# API Docs: http://localhost:8000/docs
```

### Manual Setup

#### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Configure your API keys
uvicorn main:app --reload
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

#### Ollama (Local LLM)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull model
ollama pull nemotron3-ultra:latest

# Start Ollama server
ollama serve
```

## Configuration

### Environment Variables (Backend)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | SQLite database path |
| `SECRET_KEY` | JWT secret |
| `HUAMI_APP_ID` / `HUAMI_APP_SECRET` | Zepp API credentials |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google Calendar OAuth |
| `MS_GRAPH_CLIENT_ID` / `MS_GRAPH_CLIENT_SECRET` | Microsoft Graph OAuth |
| `OLLAMA_BASE_URL` | Ollama server URL |
| `OLLAMA_MODEL` | Model name (e.g., nemotron3-ultra:latest) |
| `REDIS_URL` | Redis for Celery |

### Device Pairing

1. **Zepp OS Mini Program** (Recommended):
   - Install Zepp app on phone
   - Pair Helio Ring/Strap in Zepp app
   - Install Mini Program from Zepp store (or side-load via Zeus CLI)
   - Data streams automatically to backend

2. **Direct BLE** (Web/Android):
   - Open web app in Chrome/Edge
   - Click "Connect Device"
   - Select Helio from Bluetooth devices

3. **Gadgetbridge** (Android only):
   - Install Gadgetbridge from F-Droid
   - Pair as "Helio Strap"
   - Export database and import via web UI

## Calendar Integration

### Google Calendar
1. Go to Settings → Calendar
2. Click "Connect Google Calendar"
3. Authorize OAuth consent

### Microsoft Outlook/Graph (MDM/Intune)
1. Go to Settings → Calendar
2. Click "Connect Outlook"
3. For MDM-managed devices: Use device code flow (no browser required)

### iOS Calendar
1. Install iOS app via TestFlight
2. Grant Calendar permission in iOS Settings
3. Events sync automatically via Capacitor EventKit bridge

## API Endpoints

### Ingestion
- `POST /api/v1/ingest/telemetry` - Batch sensor readings

### Metrics
- `GET /api/v1/metrics/kpi` - KPI summary (resting HR, HRV trend, SpO₂, etc.)
- `GET /api/v1/metrics/timeseries` - Downsampled time-series for charts
- `GET /api/v1/metrics/correlation` - Cross-metric correlation

### Sleep & Activity
- `GET /api/v1/sleep/stages` - Hypnogram for date
- `GET /api/v1/activity/sessions` - Auto-detected workouts

### AI Coach
- `GET /api/v1/coach/readiness` - Daily readiness score
- `GET /api/v1/coach/insights` - Anomaly/trend insights
- `POST /api/v1/coach/chat` - Natural language Q&A
- `GET /api/v1/coach/projections` - 30/60/90-day forecasts

### Calendar & Stress
- `GET /api/v1/calendar/accounts` - Connected calendars
- `GET /api/v1/correlation/events` - Events with stress scores
- `GET /api/v1/leaderboard` - Full stress leaderboard
- `GET /api/v1/leaderboard/people` - Most stressful colleagues

### Export
- `GET /api/v1/export/` - CSV/JSON/SQLite export

## Development

### Project Structure

```
helios/
├── backend/
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Settings
│   ├── models/                 # SQLAlchemy models
│   ├── routers/                # API routers
│   ├── services/               # Business logic
│   └── scripts/                # Migration/utility scripts
├── frontend/
│   ├── src/
│   │   ├── pages/              # Route components
│   │   ├── components/         # Reusable components
│   │   ├── hooks/              # Custom hooks
│   │   └── context/            # React context providers
│   └── public/
├── mobile/                     # Capacitor config
├── mini-program/               # Zepp OS Mini Program
│   ├── device-app/
│   ├── side-service/
│   └── server/
├── docker-compose.yml
└── .github/workflows/
```

### Running Tests

```bash
# Backend
cd backend
pytest -v

# Frontend
cd frontend
npm run test
```

## Deployment

### Production Docker

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### GitHub Releases

Automated on tag push (`v*`):
- Docker images to ghcr.io
- iOS .ipa and Android .apk artifacts
- Changelog from commit messages

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a PR

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- [Zepp OS](https://docs.zepp.com/) for Mini Program framework
- [Gadgetbridge](https://gadgetbridge.org/) for Helio Ring protocol reference
- [Health Data Export Tools](https://github.com/Sarmkadan/healthdata-export-tools) for analytics reference
- [Ollama](https://ollama.com/) for local LLM inference