// Helios Device App for Zepp OS
// Reads all Helio sensors and relays to Side Service via ZML

import { MessageBuilder } from './shared/message'
import { getPackageInfo } from '@zos/app'
import * as ble from '@zos/ble'
import { HeartRate } from '@zos/sensor'
import { BloodOxygen } from '@zos/sensor'
import { Temperature } from '@zos/sensor'
import { EDA } from '@zos/sensor'
import { Accelerometer } from '@zos/sensor'
import { Gyroscope } from '@zos/sensor'
import { Time } from '@zos/sensor'
import * as hmUI from '@zos/ui'
import { log } from '@zos/utils'

App({
  globalData: {
    messageBuilder: null,
    sensors: {},
    sensorInstances: {},
    lastUpload: 0,
    uploadInterval: 10000 // 10 seconds
  },

  onCreate(options) {
    console.log('Helios Device App onCreate')
    
    // Initialize ZML MessageBuilder for BLE communication with Side Service
    const { appId } = getPackageInfo()
    const messageBuilder = new MessageBuilder({ 
      appId, 
      appDevicePort: 20, 
      appSidePort: 0, 
      ble 
    })
    
    this.globalData.messageBuilder = messageBuilder
    messageBuilder.connect()
    
    // Initialize all sensors
    this._initSensors()
    
    // Start periodic upload
    this._startUploadTimer()
    
    // Listen for requests from Side Service
    messageBuilder.on('request', ({ payload: buf }) => {
      this._handleRequest(messageBuilder.buf2Json(buf))
    })
    
    // Listen for calls from Side Service
    messageBuilder.on('call', ({ payload: buf }) => {
      this._handleCall(messageBuilder.buf2Json(buf))
    })
  },

  onDestroy(options) {
    console.log('Helios Device App onDestroy')
    this._stopUploadTimer()
    this._destroySensors()
    
    if (this.globalData.messageBuilder) {
      this.globalData.messageBuilder.disConnect()
    }
  },

  _initSensors() {
    const logger = log.getLogger('helios-device')
    
    try {
      // Heart Rate (continuous)
      this.globalData.sensorInstances.hr = new HeartRate()
      this.globalData.sensorInstances.hr.startContinuousMeasurement()
      
      // HRV - derived from HR sensor
      this.globalData.sensorInstances.hrv = this.globalData.sensorInstances.hr
      
      // SpO2
      this.globalData.sensorInstances.spo2 = new BloodOxygen()
      this.globalData.sensorInstances.spo2.startContinuousMeasurement()
      
      // Skin Temperature
      this.globalData.sensorInstances.temp = new Temperature()
      this.globalData.sensorInstances.temp.startContinuousMeasurement()
      
      // EDA (Stress)
      this.globalData.sensorInstances.eda = new EDA()
      this.globalData.sensorInstances.eda.startContinuousMeasurement()
      
      // Accelerometer
      this.globalData.sensorInstances.accel = new Accelerometer()
      this.globalData.sensorInstances.accel.startContinuousMeasurement()
      
      // Gyroscope
      this.globalData.sensorInstances.gyro = new Gyroscope()
      this.globalData.sensorInstances.gyro.startContinuousMeasurement()
      
      // Time for timestamps
      this.globalData.sensorInstances.time = new Time()
      
      logger.log('All sensors initialized')
    } catch (e) {
      logger.error('Sensor init error:', e)
    }
  },

  _destroySensors() {
    const sensors = this.globalData.sensorInstances
    Object.keys(sensors).forEach(key => {
      if (sensors[key] && sensors[key].stopContinuousMeasurement) {
        try { sensors[key].stopContinuousMeasurement() } catch (e) {}
      }
    })
    this.globalData.sensorInstances = {}
  },

  _startUploadTimer() {
    this.globalData.uploadTimer = setInterval(() => {
      this._uploadSensorData()
    }, this.globalData.uploadInterval)
  },

  _stopUploadTimer() {
    if (this.globalData.uploadTimer) {
      clearInterval(this.globalData.uploadTimer)
      this.globalData.uploadTimer = null
    }
  },

  _uploadSensorData() {
    const now = this.globalData.sensorInstances.time?.getTime() || Date.now()
    const readings = []
    
    // Heart Rate
    try {
      const hr = this.globalData.sensorInstances.hr?.getCurrentHeartRate()
      if (hr !== undefined && hr !== null) {
        readings.push({
          metric_type: 'hr',
          value: hr,
          timestamp_ms: now
        })
      }
      
      // HRV (SDNN, RMSSD) - from HR sensor
      const hrvSdnn = this.globalData.sensorInstances.hr?.getHRVSDNN?.()
      const hrvRmssd = this.globalData.sensorInstances.hr?.getHRVRMSSD?.()
      if (hrvSdnn !== undefined) {
        readings.push({
          metric_type: 'hrv_sdnn',
          value: hrvSdnn,
          timestamp_ms: now
        })
      }
      if (hrvRmssd !== undefined) {
        readings.push({
          metric_type: 'hrv_rmssd',
          value: hrvRmssd,
          timestamp_ms: now
        })
      }
    } catch (e) {
      console.error('HR read error:', e)
    }
    
    // SpO2
    try {
      const spo2 = this.globalData.sensorInstances.spo2?.getCurrentSpO2?.()
      if (spo2 !== undefined && spo2 !== null) {
        readings.push({
          metric_type: 'spo2',
          value: spo2,
          timestamp_ms: now
        })
      }
    } catch (e) {
      console.error('SpO2 read error:', e)
    }
    
    // Skin Temperature
    try {
      const temp = this.globalData.sensorInstances.temp?.getCurrentTemperature?.()
      if (temp !== undefined && temp !== null) {
        readings.push({
          metric_type: 'skin_temp',
          value: temp,
          timestamp_ms: now
        })
      }
    } catch (e) {
      console.error('Temp read error:', e)
    }
    
    // EDA
    try {
      const eda = this.globalData.sensorInstances.eda?.getCurrentEDA?.()
      if (eda !== undefined && eda !== null) {
        readings.push({
          metric_type: 'eda',
          value: eda,
          timestamp_ms: now
        })
      }
    } catch (e) {
      console.error('EDA read error:', e)
    }
    
    // Accelerometer
    try {
      const accel = this.globalData.sensorInstances.accel?.getCurrentAcceleration?.()
      if (accel) {
        readings.push(
          { metric_type: 'accel_x', value: accel.x, timestamp_ms: now },
          { metric_type: 'accel_y', value: accel.y, timestamp_ms: now },
          { metric_type: 'accel_z', value: accel.z, timestamp_ms: now }
        )
      }
    } catch (e) {
      console.error('Accel read error:', e)
    }
    
    // Gyroscope
    try {
      const gyro = this.globalData.sensorInstances.gyro?.getCurrentGyroscope?.()
      if (gyro) {
        readings.push(
          { metric_type: 'gyro_x', value: gyro.x, timestamp_ms: now },
          { metric_type: 'gyro_y', value: gyro.y, timestamp_ms: now },
          { metric_type: 'gyro_z', value: gyro.z, timestamp_ms: now }
        )
      }
    } catch (e) {
      console.error('Gyro read error:', e)
    }
    
    if (readings.length > 0) {
      this.globalData.messageBuilder.request({
        type: 'UPLOAD',
        params: { readings, device_id: this._getDeviceId() }
      }).then(data => {
        console.log('Upload response:', data)
      }).catch(err => {
        console.error('Upload failed:', err)
      })
    }
  },

  _handleRequest(request) {
    const { type, params } = request
    
    switch (type) {
      case 'GET_STATUS':
        this.globalData.messageBuilder.call({
          type: 'STATUS',
          params: {
            device_id: this._getDeviceId(),
            sensors: Object.keys(this.globalData.sensorInstances),
            battery: this._getBatteryLevel(),
            timestamp: Date.now()
          }
        })
        break
        
      case 'START_STREAM':
        this._startRealtimeStream(params.interval || 1000)
        break
        
      case 'STOP_STREAM':
        this._stopRealtimeStream()
        break
    }
  },

  _handleCall(call) {
    // Handle calls from Side Service
    console.log('Received call:', call)
  },

  _getDeviceId() {
    // In production, get from device info
    return 'helios-' + this.globalData.messageBuilder.appId.slice(-8)
  },

  _getBatteryLevel() {
    // Would use @zos/battery
    return 85
  },

  _startRealtimeStream(interval) {
    if (this.globalData.streamTimer) return
    
    this.globalData.streamTimer = setInterval(() => {
      this._uploadSensorData()
    }, interval)
  },

  _stopRealtimeStream() {
    if (this.globalData.streamTimer) {
      clearInterval(this.globalData.streamTimer)
      this.globalData.streamTimer = null
    }
  }
})