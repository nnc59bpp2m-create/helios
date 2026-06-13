// Settings App for Helios Mini Program
// Runs on phone (Zepp App) - allows user to configure backend URL and view status

import { settingsStorage } from '@zos/storage'

Page({
  build() {
    const config = settingsStorage.getItem('helios_config')
    let backendUrl = 'http://192.168.1.100:8000'
    let deviceId = ''
    
    if (config) {
      try {
        const parsed = JSON.parse(config)
        backendUrl = parsed.backendUrl || backendUrl
        deviceId = parsed.deviceId || ''
      } catch (error) {
        console.error('Failed to parse config:', error)
      }
    }

    // Backend URL input
    const urlInput = new Input({
      x: 20,
      y: 80,
      w: 280,
      h: 50,
      hint: 'Backend URL',
      text: backendUrl,
      type: InputType.URL,
      onChange: (text) => {
        backendUrl = text
      }
    })

    // Device ID input (optional)
    const deviceInput = new Input({
      x: 20,
      y: 150,
      w: 280,
      h: 50,
      hint: 'Device ID (optional)',
      text: deviceId,
      type: InputType.TEXT,
      onChange: (text) => {
        deviceId = text
      }
    })

    // Save button
    const saveButton = new Button({
      x: 20,
      y: 230,
      w: 280,
      h: 50,
      text: 'Save Configuration',
      onClick: () => {
        const config = { backendUrl, deviceId }
        settingsStorage.setItem('helios_config', JSON.stringify(config))
        Toast({ content: 'Configuration saved!' })
      }
    })

    // Test connection button
    const testButton = new Button({
      x: 20,
      y: 300,
      w: 280,
      h: 50,
      text: 'Test Connection',
      color: 0x0ea5e9,
      onClick: () => {
        this._testConnection(backendUrl)
      }
    })

    // Status display
    const statusText = new Text({
      x: 20,
      y: 380,
      w: 280,
      h: 100,
      text: 'Status: Not tested',
      textSize: 16,
      color: 0x64748b
    })

    this.statusText = statusText
  },

  _testConnection(url) {
    this.statusText.setProperty(prop.TEXT, 'Status: Testing...')
    
    fetch({
      url: `${url}/health`,
      method: 'GET',
      success: (response) => {
        if (response.status === 200) {
          this.statusText.setProperty(prop.TEXT, 'Status: Connected!')
          Toast({ content: 'Backend connection successful!' })
        } else {
          this.statusText.setProperty(prop.TEXT, `Status: Error ${response.status}`)
        }
      },
      fail: (error) => {
        this.statusText.setProperty(prop.TEXT, 'Status: Connection failed')
        Toast({ content: 'Failed to connect to backend' })
      }
    })
  }
})