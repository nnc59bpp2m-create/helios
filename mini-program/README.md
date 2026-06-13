# Helios Zepp OS Mini Program

## Overview

This Mini Program enables direct sensor data streaming from Amazfit Helio Ring/Strap to the Helios backend via the Zepp OS ecosystem.

### Architecture

```
┌─────────────────┐     BLE (ZML)      ┌──────────────────┐     HTTPS      ┌────────────┐
│  Device App     │ ◄─────────────────► │  Side Service    │ ──────────────► │  Backend   │
│  (on Helio)     │                     │  (on Phone)      │                 │  (FastAPI) │
└─────────────────┘                     └──────────────────┘                 └────────────┘
        │                                        │
        │ @zos/sensor APIs                       │ @zos/network fetch
        ▼                                        ▼
   Heart Rate                          Settings Storage
   HRV (SDNN/RMSSD)                    (backend URL)
   SpO2
   Skin Temperature
   EDA
   Accelerometer (3-axis)
   Gyroscope (3-axis)
```

## Components

### 1. Device App (`device-app/`)
Runs on the Helio Ring/Strap. Collects sensor data using Zepp OS `@zos/sensor` APIs and sends to Side Service via ZML MessageBuilder over BLE.

**Sensors accessed:**
- `HeartRate` - Continuous HR, resting HR
- `BloodOxygen` - SpO2
- `Temperature` - Skin temperature
- `EDA` - Electrodermal activity (stress)
- `Accelerometer` - 3-axis motion
- `Gyroscope` - 3-axis rotation
- `Sleep` - Sleep staging (when available)

**Features:**
- Batch uploads (50 readings or 5 seconds)
- Automatic reconnection
- Sensor lifecycle management
- Command handling (START/STOP/STATUS)

### 2. Side Service (`side-service/`)
Runs on the paired phone within the Zepp App. Receives sensor data from Device App and forwards to Helios backend via HTTPS.

**Features:**
- Receives batched sensor data from Device App
- POSTs to `/api/v1/ingest/telemetry`
- Stores backend URL in Settings Storage
- Handles Device App commands

### 3. Settings App (`settings-app/`)
UI within Zepp App for configuring backend URL and testing connection.

## Building

### Prerequisites
- Node.js 18+
- Zeus CLI: `npm install -g @zeppos/zeus`
- Zepp OS development environment

### Build Commands

```bash
cd mini-program

# Install dependencies
npm install

# Build Device App
zeus build device-app

# Build Side Service
zeus build side-service

# Build Settings App
zeus build settings-app

# Upload to Zepp store (requires developer account)
zeus upload
```

### Configuration

The Mini Program targets these Zepp OS devices:
- Amazfit Helio Ring
- Amazfit Helio Strap
- Any Zepp OS 3.0+ device with BioTracker PPG

API Level: 200 (minimum), 420 (target)

Required Permissions:
- `sensor:heart_rate`
- `sensor:blood_oxygen`
- `sensor:temperature`
- `sensor:eda`
- `sensor:accelerometer`
- `sensor:gyroscope`
- `sensor:sleep`
- `ble:central`
- `network:fetch`
- `storage:settings`

## Data Format

### Sensor Reading (sent from Device App to Side Service)
```json
{
  "readings": [
    {
      "metric_type": "hr",
      "value": 72,
      "timestamp_ms": 1700000000000,
      "source": "miniprogram"
    },
    {
      "metric_type": "hrv_sdnn",
      "value": 45.2,
      "timestamp_ms": 1700000000000,
      "source": "miniprogram"
    }
  ]
}
```

### Backend Ingestion (sent from Side Service to Backend)
```json
POST /api/v1/ingest/telemetry
{
  "readings": [
    {
      "device_id": "helios-ring-abc123",
      "metric_type": "hr",
      "value": 72,
      "timestamp_ms": 1700000000000,
      "source": "miniprogram"
    }
  ]
}
```

## Development Notes

### Testing Locally

1. Start backend: `docker-compose up -d backend`
2. Note your machine's LAN IP (e.g., 192.168.1.100)
3. In Zepp App, open Settings App and set backend URL to `http://192.168.1.100:8000`
4. Pair Helio Ring/Strap in Zepp App
5. Open Helios Mini Program on watch
6. Data should start flowing to backend

### Debugging

- Use `console.log` in Device App - view in Zeus CLI device log
- Side Service logs visible in Zeus CLI phone log
- Settings App shows connection status

### Common Issues

1. **BLE connection fails**: Ensure Zepp App is running, Helio is paired, Bluetooth enabled
2. **Backend unreachable**: Use LAN IP (not localhost), ensure phone and backend on same network
3. **Sensors not reading**: Check permissions in `project.json`, ensure Helio firmware supports sensors
4. **Upload fails**: Check backend `/health` endpoint, verify CORS settings

## Zeus CLI Project Structure

```
mini-program/
├── project.json                 # Project configuration
├── package.json                 # Build scripts
├── device-app/
│   ├── app.js                   # Main entry
│   ├── app.json                 # Device app config
│   └── shared/
│       ├── device-polyfill.js   # Environment polyfills
│       └── message.js           # ZML MessageBuilder (device side)
├── side-service/
│   ├── app-side-service.js      # Main entry
│   └── shared/
│       └── message-side.js      # ZML MessageBuilder (phone side)
├── settings-app/
│   └── app.js                   # Settings UI
└── server/
    └── index.js                 # Local test server
```

## References

- [Zepp OS Documentation](https://docs.zepp.com/)
- [Zepp OS Mini Program Architecture](https://docs.zepp.com/docs/guides/framework/)
- [Bluetooth Communication Guide](https://docs.zepp.com/docs/guides/best-practice/bluetooth-communication/)
- [post-health-data Sample](https://github.com/zepp-health/zeppos-samples/tree/main/application/2.0/post-health-data)
- [Device Sensor APIs](https://docs.zepp.com/docs/reference/device-app-api/newAPI/sensor/)