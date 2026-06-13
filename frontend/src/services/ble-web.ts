// Web Bluetooth API implementation

import { BLEServiceInterface, BLEDevice, BLEReading, parseHelioPacket, parseHeartRate, HELIO_SERVICES, HR_CHARACTERISTICS } from './ble'

declare global {
  interface Navigator {
    bluetooth: Bluetooth
  }
}

interface Bluetooth {
  requestDevice(options: RequestDeviceOptions): Promise<BluetoothDevice>
  getDevices(): Promise<BluetoothDevice[]>
}

interface RequestDeviceOptions {
  filters?: BluetoothLEScanFilter[]
  optionalServices?: string[]
}

interface BluetoothLEScanFilter {
  services?: string[]
  name?: string
  namePrefix?: string
  manufacturerId?: number
}

interface BluetoothDevice {
  id: string
  name?: string
  gatt: BluetoothRemoteGATTServer
  addEventListener(type: 'gattserverdisconnected', listener: (event: Event) => void): void
  removeEventListener(type: 'gattserverdisconnected', listener: (event: Event) => void): void
}

interface BluetoothRemoteGATTServer {
  connected: boolean
  connect(): Promise<BluetoothRemoteGATTServer>
  disconnect(): void
  getPrimaryService(service: string | number): Promise<BluetoothRemoteGATTService>
  getPrimaryServices(): Promise<BluetoothRemoteGATTService[]>
}

interface BluetoothRemoteGATTService {
  device: BluetoothDevice
  uuid: string
  getCharacteristic(characteristic: string | number): Promise<BluetoothRemoteGATTCharacteristic>
  getCharacteristics(): Promise<BluetoothRemoteGATTCharacteristic[]>
}

interface BluetoothRemoteGATTCharacteristic {
  service: BluetoothRemoteGATTService
  uuid: string
  properties: {
    broadcast: boolean
    read: boolean
    writeWithoutResponse: boolean
    write: boolean
    notify: boolean
    indicate: boolean
    authenticatedSignedWrites: boolean
    reliableWrite: boolean
    writableAuxiliaries: boolean
  }
  readValue(): Promise<DataView>
  writeValue(value: BufferSource): Promise<void>
  startNotifications(): Promise<void>
  stopNotifications(): Promise<void>
  addEventListener(type: 'characteristicvaluechanged', listener: (event: Event & { target: BluetoothRemoteGATTCharacteristic }) => void): void
  removeEventListener(type: 'characteristicvaluechanged', listener: (event: Event & { target: BluetoothRemoteGATTCharacteristic }) => void): void
}

export class WebBluetoothService implements BLEServiceInterface {
  private device: BluetoothDevice | null = null
  private gatt: BluetoothRemoteGATTServer | null = null
  private callbacks = new Map<string, (value: DataView) => void>()
  private deviceFoundCallback: ((device: BLEDevice) => void) | null = null
  private deviceLostCallback: ((deviceId: string) => void) | null = null

  async requestDevice(filters?: any[]): Promise<BLEDevice> {
    if (!navigator.bluetooth) {
      throw new Error('Web Bluetooth API not supported. Use Chrome/Edge.')
    }

    const options: RequestDeviceOptions = {
      optionalServices: [
        HELIO_SERVICES.HEART_RATE,
        HELIO_SERVICES.BATTERY,
        HELIO_SERVICES.DEVICE_INFO,
        HELIO_SERVICES.ZEPP_CUSTOM_1,
        HELIO_SERVICES.ZEPP_CUSTOM_2
      ],
      filters: filters || [
        { namePrefix: 'Helio' },
        { namePrefix: 'Amazfit' }
      ]
    }

    const btDevice = await navigator.bluetooth.requestDevice(options)
    
    this.device = btDevice
    
    btDevice.addEventListener('gattserverdisconnected', this.handleDisconnect.bind(this))
    
    return {
      id: btDevice.id,
      name: btDevice.name || 'Unknown'
    }
  }

  async connect(deviceId: string): Promise<void> {
    if (!this.device || this.device.id !== deviceId) {
      // Try to get already paired device
      const devices = await navigator.bluetooth.getDevices()
      this.device = devices.find(d => d.id === deviceId) || null
    }

    if (!this.device) {
      throw new Error('Device not found. Call requestDevice first.')
    }

    if (!this.device.gatt) {
      throw new Error('Device has no GATT server')
    }

    this.gatt = await this.device.gatt.connect()
    console.log('Connected to Helio device')
  }

  async disconnect(deviceId: string): Promise<void> {
    if (this.gatt && this.gatt.connected) {
      this.gatt.disconnect()
    }
    this.gatt = null
    this.device = null
  }

  async startNotifications(
    deviceId: string,
    serviceUuid: string,
    characteristicUuid: string,
    callback: (value: DataView) => void
  ): Promise<void> {
    if (!this.gatt) throw new Error('Not connected')

    const service = await this.gatt.getPrimaryService(serviceUuid)
    const characteristic = await service.getCharacteristic(characteristicUuid)

    const key = `${serviceUuid}:${characteristicUuid}`
    this.callbacks.set(key, callback)

    await characteristic.startNotifications()

    characteristic.addEventListener('characteristicvaluechanged', this.handleNotification.bind(this, key))
  }

  async stopNotifications(
    deviceId: string,
    serviceUuid: string,
    characteristicUuid: string
  ): Promise<void> {
    if (!this.gatt) return

    const key = `${serviceUuid}:${characteristicUuid}`
    this.callbacks.delete(key)

    try {
      const service = await this.gatt.getPrimaryService(serviceUuid)
      const characteristic = await service.getCharacteristic(characteristicUuid)
      await characteristic.stopNotifications()
    } catch (e) {
      console.warn('Stop notifications failed:', e)
    }
  }

  async readCharacteristic(
    deviceId: string,
    serviceUuid: string,
    characteristicUuid: string
  ): Promise<DataView> {
    if (!this.gatt) throw new Error('Not connected')

    const service = await this.gatt.getPrimaryService(serviceUuid)
    const characteristic = await service.getCharacteristic(characteristicUuid)
    return characteristic.readValue()
  }

  async getConnectedDevices(): Promise<BLEDevice[]> {
    if (!this.gatt || !this.gatt.connected) return []
    return [{ id: this.device!.id, name: this.device!.name || 'Helio' }]
  }

  onDeviceFound(callback: (device: BLEDevice) => void): void {
    this.deviceFoundCallback = callback
  }

  onDeviceLost(callback: (deviceId: string) => void): void {
    this.deviceLostCallback = callback
  }

  private handleNotification(key: string, event: Event) {
    const target = event.target as any
    const value = target.value
    const callback = this.callbacks.get(key)
    if (callback && value) {
      callback(value)
    }
  }

  private handleDisconnect() {
    console.log('Helio device disconnected')
    this.gatt = null
  }
}

// Auto-detect Helio and start standard sensors
export async function connectAndStreamHelio(
  deviceId: string,
  onReading: (readings: BLEReading[]) => void
): Promise<WebBluetoothService> {
  const service = new WebBluetoothService()
  
  await service.connect(deviceId)
  
  // Start HR notifications (standard)
  try {
    await service.startNotifications(
      deviceId,
      HELIO_SERVICES.HEART_RATE,
      HR_CHARACTERISTICS.MEASUREMENT,
      (value) => {
        const hr = parseHeartRate(value)
        if (hr !== null) {
          onReading([{ metric_type: 'hr', value: hr, timestamp_ms: Date.now() }])
        }
      }
    )
    console.log('HR notifications started')
  } catch (e) {
    console.warn('HR notifications failed:', e)
  }

  // Try Zepp custom service for more sensors
  try {
    await service.startNotifications(
      deviceId,
      HELIO_SERVICES.ZEPP_CUSTOM_1,
      '0000fff2-0000-1000-8000-00805f9b34fb', // Notify characteristic
      (value) => {
        const readings = parseHelioPacket(value)
        if (readings.length > 0) {
          onReading(readings)
        }
      }
    )
    console.log('Zepp custom notifications started')
  } catch (e) {
    console.warn('Zepp custom notifications failed:', e)
  }

  return service
}