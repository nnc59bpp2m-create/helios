// Abstract BLE interface for cross-platform (Web + Capacitor)

export interface BLEDevice {
  id: string
  name: string
  rssi?: number
  services?: string[]
}

export interface BLEReading {
  metric_type: string
  value: number
  timestamp_ms: number
}

export interface BLEServiceInterface {
  requestDevice(filters?: BluetoothLEScanFilter[]): Promise<BLEDevice>
  connect(deviceId: string): Promise<void>
  disconnect(deviceId: string): Promise<void>
  startNotifications(deviceId: string, serviceUuid: string, characteristicUuid: string, callback: (value: DataView) => void): Promise<void>
  stopNotifications(deviceId: string, serviceUuid: string, characteristicUuid: string): Promise<void>
  readCharacteristic(deviceId: string, serviceUuid: string, characteristicUuid: string): Promise<DataView>
  getConnectedDevices(): Promise<BLEDevice[]>
  onDeviceFound(callback: (device: BLEDevice) => void): void
  onDeviceLost(callback: (deviceId: string) => void): void
}

export interface BluetoothLEScanFilter {
  services?: string[]
  name?: string
  namePrefix?: string
  manufacturerId?: number
}

// Helio GATT Service UUIDs (standard + custom)
export const HELIO_SERVICES = {
  // Standard Bluetooth SIG services
  HEART_RATE: '0000180d-0000-1000-8000-00805f9b34fb',
  BATTERY: '0000180f-0000-1000-8000-00805f9b34fb',
  DEVICE_INFO: '0000180a-0000-1000-8000-00805f9b34fb',
  
  // Zepp/Huami custom services (based on Gadgetbridge research)
  ZEPP_CUSTOM_1: '0000fff0-0000-1000-8000-00805f9b34fb',
  ZEPP_CUSTOM_2: '0000ffe0-0000-1000-8000-00805f9b34fb',
}

// Heart Rate characteristics
export const HR_CHARACTERISTICS = {
  MEASUREMENT: '00002a37-0000-1000-8000-00805f9b34fb',
  BODY_SENSOR_LOCATION: '00002a38-0000-1000-8000-00805f9b34fb',
  CONTROL_POINT: '00002a39-0000-1000-8000-00805f9b34fb'
}

// Battery
export const BATTERY_CHARACTERISTICS = {
  LEVEL: '00002a19-0000-1000-8000-00805f9b34fb'
}

// Zepp custom characteristics (from Gadgetbridge)
export const ZEPP_CHARACTERISTICS = {
  DATA_NOTIFY: '0000fff2-0000-1000-8000-00805f9b34fb',
  DATA_WRITE: '0000fff1-0000-1000-8000-00805f9b34fb',
  CONFIG_NOTIFY: '0000ffe2-0000-1000-8000-00805f9b34fb',
  CONFIG_WRITE: '0000ffe1-0000-1000-8000-00805f9b34fb'
}

// Parse Helio data packets
export function parseHelioPacket(data: DataView): BLEReading[] {
  const readings: BLEReading[] = []
  const timestamp = Date.now()
  
  try {
    const packetType = data.getUint8(0)
    
    switch (packetType) {
      case 0x01: // Heart rate
        if (data.byteLength >= 2) {
          const hr = data.getUint8(1)
          readings.push({
            metric_type: 'hr',
            value: hr,
            timestamp_ms: timestamp
          })
        }
        break
        
      case 0x02: // HRV
        if (data.byteLength >= 5) {
          const sdnn = data.getUint16(1, true)
          const rmssd = data.getUint16(3, true)
          readings.push(
            { metric_type: 'hrv_sdnn', value: sdnn, timestamp_ms: timestamp },
            { metric_type: 'hrv_rmssd', value: rmssd, timestamp_ms: timestamp }
          )
        }
        break
        
      case 0x03: // SpO2
        if (data.byteLength >= 2) {
          const spo2 = data.getUint8(1)
          readings.push({ metric_type: 'spo2', value: spo2, timestamp_ms: timestamp })
        }
        break
        
      case 0x04: // Temperature
        if (data.byteLength >= 3) {
          const tempRaw = data.getInt16(1, true)
          const temp = tempRaw / 100
          readings.push({ metric_type: 'skin_temp', value: temp, timestamp_ms: timestamp })
        }
        break
        
      case 0x05: // EDA
        if (data.byteLength >= 3) {
          const edaRaw = data.getUint16(1, true)
          const eda = edaRaw / 100
          readings.push({ metric_type: 'eda', value: eda, timestamp_ms: timestamp })
        }
        break
        
      case 0x10: // Accelerometer (3-axis)
        if (data.byteLength >= 7) {
          const x = data.getInt16(1, true) / 1000
          const y = data.getInt16(3, true) / 1000
          const z = data.getInt16(5, true) / 1000
          readings.push(
            { metric_type: 'accel_x', value: x, timestamp_ms: timestamp },
            { metric_type: 'accel_y', value: y, timestamp_ms: timestamp },
            { metric_type: 'accel_z', value: z, timestamp_ms: timestamp }
          )
        }
        break
        
      case 0x11: // Gyroscope
        if (data.byteLength >= 7) {
          const x = data.getInt16(1, true) / 100
          const y = data.getInt16(3, true) / 100
          const z = data.getInt16(5, true) / 100
          readings.push(
            { metric_type: 'gyro_x', value: x, timestamp_ms: timestamp },
            { metric_type: 'gyro_y', value: y, timestamp_ms: timestamp },
            { metric_type: 'gyro_z', value: z, timestamp_ms: timestamp }
          )
        }
        break
    }
  } catch (e) {
    console.error('Helio packet parse error:', e)
  }
  
  return readings
}

// Parse standard Heart Rate measurement
export function parseHeartRate(data: DataView): number | null {
  try {
    const flags = data.getUint8(0)
    const hrFormat = flags & 0x01
    
    if (hrFormat === 0) {
      return data.getUint8(1)
    } else {
      return data.getUint16(1, true)
    }
  } catch (e) {
    console.error('HR parse error:', e)
    return null
  }
}