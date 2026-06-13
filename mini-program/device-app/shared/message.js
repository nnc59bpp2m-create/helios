// ZML MessageBuilder for Device App (Zepp OS)
// Based on official ZML library

class MessageBuilder {
  constructor({ appId, appDevicePort, appSidePort, ble }) {
    this.appId = appId
    this.appDevicePort = appDevicePort
    this.appSidePort = appSidePort
    this.ble = ble
    this.connected = false
    this.eventHandlers = {}
    this.requestId = 0
    this.pendingRequests = new Map()
    this.connectionCallback = null
  }

  connect() {
    if (this.connected) return Promise.resolve()
    
    return new Promise((resolve, reject) => {
      this.connectionCallback = { resolve, reject }
      
      this.ble.connect({
        serviceUuid: '0000fff0-0000-1000-8000-00805f9b34fb',
        writeUuid: '0000fff1-0000-1000-8000-00805f9b34fb',
        notifyUuid: '0000fff2-0000-1000-8000-00805f9b34fb',
        onConnect: () => {
          this.connected = true
          this._setupNotifications()
          if (this.connectionCallback) {
            this.connectionCallback.resolve()
            this.connectionCallback = null
          }
        },
        onDisconnect: () => {
          this.connected = false
          if (this.connectionCallback) {
            this.connectionCallback.reject(new Error('Disconnected'))
            this.connectionCallback = null
          }
        }
      })
    })
  }

  disConnect() {
    this.ble.disconnect()
    this.connected = false
  }

  _setupNotifications() {
    this.ble.notify({
      serviceUuid: '0000fff0-0000-1000-8000-00805f9b34fb',
      notifyUuid: '0000fff2-0000-1000-8000-00805f9b34fb',
      onNotify: (buffer) => {
        this._handleIncoming(buffer)
      }
    })
  }

  request(message) {
    return new Promise((resolve, reject) => {
      const id = ++this.requestId
      this.pendingRequests.set(id, { resolve, reject, timeout: setTimeout(() => {
        this.pendingRequests.delete(id)
        reject(new Error('Request timeout'))
      }, 10000) })

      this._send({
        ...message,
        id,
        type: 'request'
      })
    })
  }

  call(message) {
    return this._send({
      ...message,
      type: 'call'
    })
  }

  on(event, handler) {
    if (!this.eventHandlers[event]) {
      this.eventHandlers[event] = []
    }
    this.eventHandlers[event].push(handler)
  }

  off(event, handler) {
    if (!this.eventHandlers[event]) return
    const idx = this.eventHandlers[event].indexOf(handler)
    if (idx > -1) this.eventHandlers[event].splice(idx, 1)
  }

  _send(message) {
    if (!this.connected) {
      return Promise.reject(new Error('Not connected'))
    }

    const buffer = this.json2Buf(message)
    return this.ble.write({
      serviceUuid: '0000fff0-0000-1000-8000-00805f9b34fb',
      writeUuid: '0000fff1-0000-1000-8000-00805f9b34fb',
      data: buffer
    })
  }

  _handleIncoming(buffer) {
    const message = this.buf2Json(buffer)
    
    if (message.type === 'response' && message.id) {
      const pending = this.pendingRequests.get(message.id)
      if (pending) {
        clearTimeout(pending.timeout)
        this.pendingRequests.delete(message.id)
        if (message.error) {
          pending.reject(new Error(message.error))
        } else {
          pending.resolve(message.data)
        }
      }
      return
    }

    // Emit event
    const handlers = this.eventHandlers[message.type] || []
    handlers.forEach(handler => {
      try {
        handler({ payload: buffer })
      } catch (e) {
        console.error('Event handler error:', e)
      }
    })
  }

  json2Buf(json) {
    const str = JSON.stringify(json)
    const encoder = new TextEncoder()
    return encoder.encode(str)
  }

  buf2Json(buffer) {
    const decoder = new TextDecoder()
    const str = decoder.decode(buffer)
    return JSON.parse(str)
  }
}

export { MessageBuilder }