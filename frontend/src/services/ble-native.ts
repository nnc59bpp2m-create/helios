// Capacitor native BLE implementation using @capacitor-community/bluetooth-le

import { 
  BLEServiceInterface, 
  BLEDevice, 
  BLEReading, 
  parseHelioPacket, 
  parseHeartRate,
  HELIO_SERVICES,
  HR_CHARACTERISTICS
} from './ble'

// Types for @capacitor-community/bluetooth-le
interface BluetoothLePlugin {
  initialize(): Promise<{ initialized: boolean }>
  requestDevice(options: RequestDeviceOptions): Promise<{ device: CapacitorBLEDevice }>
  connect(deviceId: string): Promise<void>
  disconnect(deviceId: string): Promise<void>
  startNotifications(deviceId: string, service: string, characteristic: string): Promise<void>
  stopNotifications(deviceId: string, service: string, characteristic: string): Promise<void>
  read(deviceId: string, service: string, characteristic: string): Promise<{ value: string }> // base64
  getConnectedDevices(): Promise<{ devices: CapacitorBLEDevice[] }>
  addListener(eventName: 'onDeviceFound' | 'onDeviceConnected' | 'onDeviceDisconnected' | 'onCharacteristicChanged', listener: (data: any) => void): Promise<{ remove: () => void }>
}

interface CapacitorBLEDevice {
  deviceId: string
  name: string
  rssi?: number
  services?: string[]
}

interface RequestDeviceOptions {
  services?: string[]
  name?: string
  namePrefix?: string
  allowDuplicates?: boolean
}

let BluetoothLe: BluetoothLePlugin | null = null

async function loadBluetoothLe(): Promise<BluetoothLePlugin> {
  if (BluetoothLe) return BluetoothLe
  
  try {
    const mod = await import('@capacitor-community/bluetooth-le')
    BluetoothLe = mod.BluetoothLe
    await BluetoothLe.initialize()
    return BluetoothLe
  } catch (e) {
    console.error('Failed to load @capacitor-community/bluetooth-le:', e)
    throw new Error('Bluetooth LE plugin not available. Run: npm install @capacitor-community/bluetooth-le')
  }
}

export class NativeBluetoothService implements BLEServiceInterface {
  private deviceId: string | null = null
  private callbacks = new Map<string, (value: DataView) => void>()
  private notificationListeners = new Map<string, () => void>()
  private deviceFoundCallback: ((device: BLEDevice) => void) | null = null
  private deviceLostCallback: ((deviceId: string) => void) | null = null

  async requestDevice(filters?: any[]): Promise<BLEDevice> {
    const ble = await loadBluetoothLe()
    
    const result = await ble.requestDevice({
      services: [
        HELIO_SERVICES.HEART_RATE,
        HELIO_SERVICES.BATTERY,
        HELIO_SERVICES.DEVICE_INFO,
        HELIO_SERVICES.ZEPP_CUSTOM_1,
        HELIO_SERVICES.ZEPP_CUSTOM_2
      ],
      namePrefix: 'Helio',
      allowDuplicates: false
    })
    
    this.deviceId = result.device.deviceId
    
    // Set up listeners
    this.setupListeners()
    
    return {
      id: result.device.deviceId,
      name: result.device.name || 'Helio',
      rssi: result.device.rssi
    }
  }

  private setupListeners() {
    const ble = BluetoothLe
    if (!ble) return

    // Device found
    const removeFound = (await ble.addListener('onDeviceFound', (device: any) => {
      if (this.deviceFoundCallback) {
        this.deviceFoundCallback({
          id: device.deviceId,
          name: device.name,
          rssi: device.rssi
        })
      }
    })).remove
    this.notificationListeners.set('onDeviceFound', removeFound)

    // Device connected
    const removeConnected = (await ble.addListener('onDeviceConnected', (device: any) => {
      console.log('Device connected:', device.deviceId)
    })).remove
    this.notificationListeners.set('onDeviceConnected', removeConnected)

    // Device disconnected
    const removeDisconnected = (await ble.addListener('onDeviceDisconnected', (data: any) => {
      console.log('Device disconnected:', data.deviceId)
      if (this.deviceLostCallback && data.deviceId === this.deviceId) {
        this.deviceLostCallback(data.deviceId)
      }
    })).remove
    this.notificationListeners.set('onDeviceDisconnected', removeDisconnected)

    // Characteristic changed (notifications)
    const removeCharChanged = (await ble.addListener('onCharacteristicChanged', (data: any) => {
      const key = `${data.service}:${data.characteristic}`
      const callback = this.callbacks.get(key)
      if (callback && data.value) {
        // Value is base64 encoded
        const binary = atob(data.value)
        const bytes = new Uint8Array(binary.length)
        for (let i = 0; i < binary.length; i++) {
          bytes[i] = binary.charCodeAt(i)
        }
        callback(bytes.buffer)
      }
    })).remove
    this.notificationListeners.set('onCharacteristicChanged', removeCharChanged)
  }

  async connect(deviceId: string): Promise<void> {
    const ble = await loadBluetoothLe()
    this.deviceId = deviceId
    await ble.connect(deviceId)
    console.log('Connected to Helio via native BLE')
  }

  async disconnect(deviceId: string): Promise<void> {
    const ble = await loadBluetoothLe()
    if (this.deviceId === deviceId) {
      await ble.disconnect(deviceId)
      this.deviceId = null
    }
  }

  async startNotifications(
    deviceId: string,
    serviceUuid: string,
    characteristicUuid: string,
    callback: (value: DataView) => void
  ): Promise<void> {
    const ble = await loadBluetoothLe()
    const key = `${serviceUuid}:${characteristicUuid}`
    this.callbacks.set(key, callback)
    await ble.startNotifications(deviceId, serviceUuid, characteristicUuid)
  }

  async stopNotifications(
    deviceId: string,
    serviceUuid: string,
    characteristicUuid: string
  ): Promise<void> {
    const ble = await loadBluetoothLe()
    const key = `${serviceUuid}:${characteristicUuid}`
    this.callbacks.delete(key)
    await ble.stopNotifications(deviceId, serviceUuid, characteristicUuid)
  }

  async readCharacteristic(
    deviceId: string,
    serviceUuid: string,
    characteristicUuid: string
  ): Promise<DataView> {
    const ble = await loadBluetoothLe()
    const result = await ble.read(deviceId, serviceUuid, characteristicUuid)
    // Value is base64
    const binary = atob(result.value)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i)
    }
    return bytes.buffer
  }

  async getConnectedDevices(): Promise<BLEDevice[]> {
    const ble = await loadBluetoothLe()
    const result = await ble.getConnectedDevices()
    return result.devices.map(d => ({
      id: d.deviceId,
      name: d.name,
      rssi: d.rssi
    }))
  }

  onDeviceFound(callback: (device: BLEDevice) => void): void {
    this.deviceFoundCallback = callback
  }

  onDeviceLost(callback: (deviceId: string) => void): void {
    this.deviceLostCallback = callback
  }

  async cleanup() {
    // Remove all listeners
    for (const remove of this.notificationListeners.values()) {
      remove()
    }
    this.notificationListeners.clear()
    this.callbacks.clear()
  }
}

// Auto-detect Helio and start standard sensors
export async function connectAndStreamHelioNative(
  deviceId: string,
  onReading: (readings: BLEReading[]) => void
): Promise<NativeBluetoothService> {
  const service = new NativeBluetoothService()
  
  await service.connect(deviceId)
  
  // Start HR notifications (standard)
  try {
    await service.startNotifications(
      deviceId,
      HELIO_SERVICES.HEART_RATE,
      HR_CHARACTERISTICS.MEASUREMENT,
      (value) => {
        const hr = parseHeartRate(new DataView(value))
        if (hr !== null) {
          onReading([{ metric_type: 'hr', value: hr, timestamp_ms: Date.now() }])
        }
      }
    )
    console.log('Native HR notifications started')
  } catch (e) {
    console.warn('Native HR notifications failed:', e)
  }

  // Try Zepp custom service
  try {
    await service.startNotifications(
      deviceId,
      HELIO_SERVICES.ZEPP_CUSTOM_1,
      '0000fff2-0000-1000-8000-00805f9b34fb',
      (value) => {
        const readings = parseHelioPacket(new DataView(value))
        if (readings.length > 0) {
          onReading(readings)
        }
      }
    )
    console.log('Native Zepp custom notifications started')
  } catch (e) {
    console.warn('Native Zepp custom notifications failed:', e)
  }

  return service
}