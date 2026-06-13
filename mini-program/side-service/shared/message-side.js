// ZML MessageBuilder for Side Service (Zepp OS / Phone)

class MessageBuilder {
  constructor() {
    this.connected = false
    this.eventHandlers = {}
    this.requestId = 0
    this.pendingRequests = new Map()
    this.messagePort = null
  }

  listen(callback) {
    // In Zepp OS Side Service, communication is via messaging API
    // This is a simplified version - real implementation uses @zos/message
    
    // Simulate connection
    setTimeout(() => {
      this.connected = true
      if (callback) callback()
    }, 100)
  }

  on(event, handler) {
    if (!this.eventHandlers[event]) {
      this.eventHandlers[event] = []
    }
    this.eventHandlers[event].push(handler)
  }

  call(message) {
    // Send message to Device App
    console.log('Side Service call:', message)
    // In real implementation: messagePort.postMessage(message)
  }

  response(data) {
    // Send response to Device App request
    console.log('Side Service response:', data)
  }
}

export { MessageBuilder }