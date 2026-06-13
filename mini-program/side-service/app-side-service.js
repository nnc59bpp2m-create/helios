// Helios Side Service for Zepp OS
// Runs on phone (Zepp App), relays data to backend via HTTPS

import { MessageBuilder } from '../shared/message-side'
import { settingsStorage } from '@zos/settings'

const BACKEND_URL = 'https://your-helios-backend.com/api/v1/ingest/telemetry'
// For local dev, use: 'http://192.168.x.x:8000/api/v1/ingest/telemetry'

const messageBuilder = new MessageBuilder()

AppSideService({
  onInit() {
    console.log('Helios Side Service onInit')
    messageBuilder.listen(() => {
      console.log('Side Service connected to Device App')
    })

    // Handle requests from Device App
    messageBuilder.on('request', async (ctx) => {
      const { type, params } = ctx.request.payload
      
      if (type === 'UPLOAD') {
        await this._handleUpload(ctx, params)
      } else if (type === 'GET_STATUS') {
        ctx.response({ data: { status: 'ok', backend: BACKEND_URL } })
      }
    })

    // Handle calls from Device App
    messageBuilder.on('call', (ctx) => {
      console.log('Received call from device:', ctx.request.payload)
    })
  },

  async _handleUpload(ctx, params) {
    const { readings, device_id } = params
    
    console.log(`Uploading ${readings.length} readings for ${device_id}`)
    
    try {
      const response = await fetch(BACKEND_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          readings: readings.map(r => ({
            device_id: device_id,
            metric_type: r.metric_type,
            value: r.value,
            timestamp_ms: r.timestamp_ms,
            source: 'miniprogram'
          }))
        })
      })

      if (response.ok) {
        const result = await response.json()
        ctx.response({ 
          data: { 
            message: `Uploaded ${result.ingested} readings`,
            ingestion_id: result.ingestion_id
          }
        })
        
        // Store last sync time
        settingsStorage.setItem('lastSync', Date.now().toString())
      } else {
        const error = await response.text()
        throw new Error(`Upload failed: ${response.status} ${error}`)
      }
    } catch (e) {
      console.error('Upload error:', e)
      ctx.response({ 
        error: e.message 
      })
    }
  }
})

// Periodic sync from settings storage
settingsStorage.addListener('change', (key) => {
  if (key === 'forceSync') {
    // Trigger manual sync
    console.log('Manual sync requested')
  }
})