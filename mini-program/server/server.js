// Reference Node.js server for Helios Mini Program testing
// Simulates the backend ingestion endpoint

const express = require('express')
const cors = require('cors')
const WebSocket = require('ws')
const http = require('http')

const app = express()
const PORT = process.env.PORT || 4080

app.use(cors())
app.use(express.json())

// Store for connected device apps
const deviceConnections = new Map()

// Ingestion endpoint (matches backend /api/v1/ingest/telemetry)
app.post('/api/v1/ingest/telemetry', (req, res) => {
  const { readings } = req.body
  
  if (!readings || !Array.isArray(readings)) {
    return res.status(400).json({ error: 'readings array required' })
  }

  console.log(`Received ${readings.length} readings from device`)
  
  // Log sample readings
  readings.slice(0, 3).forEach(r => {
    console.log(`  ${r.metric_type}: ${r.value} at ${new Date(r.timestamp_ms).toISOString()}`)
  })

  // In real implementation, this would forward to FastAPI backend
  // For testing, just acknowledge
  res.json({
    ingested: readings.length,
    duplicates: 0,
    errors: [],
    ingestion_id: Math.random().toString(36).slice(2, 10)
  })
})

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'helios-miniprogram-server' })
})

// Create HTTP server and attach WebSocket
const server = http.createServer(app)
const wss = new WebSocket.Server({ server })

// WebSocket for real-time data streaming
wss.on('connection', (ws, req) => {
  const deviceId = req.url.slice(1) || 'unknown'
  console.log(`Device connected: ${deviceId}`)
  
  deviceConnections.set(deviceId, ws)
  
  ws.on('message', (data) => {
    try {
      const msg = JSON.parse(data)
      console.log(`WS [${deviceId}]:`, msg.type || 'data')
      
      // Echo back for testing
      ws.send(JSON.stringify({ type: 'ack', original: msg }))
    } catch (e) {
      console.error('WS parse error:', e)
    }
  })
  
  ws.on('close', () => {
    console.log(`Device disconnected: ${deviceId}`)
    deviceConnections.delete(deviceId)
  })
})

// Simulate periodic status broadcast
setInterval(() => {
  deviceConnections.forEach((ws, deviceId) => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'status',
        timestamp: Date.now(),
        connected_devices: deviceConnections.size
      }))
    }
  })
}, 30000)

server.listen(PORT, () => {
  console.log(`Helios Mini Program server running on http://localhost:${PORT}`)
  console.log(`Ingestion endpoint: http://localhost:${PORT}/api/v1/ingest/telemetry`)
})