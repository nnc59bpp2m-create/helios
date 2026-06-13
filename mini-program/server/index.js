// Local test server for Mini Program development
// Receives data from Side Service and logs it

const http = require('http')
const url = require('url')

const PORT = process.env.PORT || 4080

const server = http.createServer((req, res) => {
  const parsedUrl = url.parse(req.url, true)
  
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type')
  
  if (req.method === 'OPTIONS') {
    res.writeHead(204)
    res.end()
    return
  }

  if (parsedUrl.pathname === '/sleep' && req.method === 'POST') {
    let body = ''
    req.on('data', chunk => body += chunk)
    req.on('end', () => {
      try {
        const data = JSON.parse(body)
        console.log('[TestServer] Received sleep data:', JSON.stringify(data, null, 2))
        res.writeHead(200, { 'Content-Type': 'application/json' })
        res.end(JSON.stringify({ message: 'ok', received: true }))
      } catch (error) {
        console.error('[TestServer] Parse error:', error)
        res.writeHead(400, { 'Content-Type': 'application/json' })
        res.end(JSON.stringify({ error: 'Invalid JSON' }))
      }
    })
    return
  }

  if (parsedUrl.pathname === '/api/v1/ingest/telemetry' && req.method === 'POST') {
    let body = ''
    req.on('data', chunk => body += chunk)
    req.on('end', () => {
      try {
        const data = JSON.parse(body)
        console.log('[TestServer] Received telemetry:', JSON.stringify(data, null, 2))
        res.writeHead(200, { 'Content-Type': 'application/json' })
        res.end(JSON.stringify({ 
          message: 'ok', 
          received: data.readings?.length || 0,
          ingestion_id: 'test-' + Date.now()
        }))
      } catch (error) {
        console.error('[TestServer] Parse error:', error)
        res.writeHead(400, { 'Content-Type': 'application/json' })
        res.end(JSON.stringify({ error: 'Invalid JSON' }))
      }
    })
    return
  }

  if (parsedUrl.pathname === '/health' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ 
      status: 'healthy', 
      service: 'helios-test-server',
      timestamp: new Date().toISOString()
    }))
    return
  }

  res.writeHead(404, { 'Content-Type': 'application/json' })
  res.end(JSON.stringify({ error: 'Not found' }))
})

server.listen(PORT, () => {
  console.log('[TestServer] Running on http://localhost:' + PORT)
  console.log('[TestServer] Endpoints:')
  console.log('  GET  /health')
  console.log('  POST /api/v1/ingest/telemetry')
  console.log('  POST /sleep (legacy)')
})
