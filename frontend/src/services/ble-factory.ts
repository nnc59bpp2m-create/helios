// BLE Service Factory - picks Web Bluetooth or Capacitor Native based on platform

import { BLEServiceInterface } from './ble'
import { WebBluetoothService, connectAndStreamHelio as connectWeb } from './ble-web'
import { NativeBluetoothService, connectAndStreamHelioNative } from './ble-native'
import { Capacitor } from '@capacitor/core'

let bleServiceInstance: { service: BLEServiceInterface; cleanup: () => Promise<void> } | null = null

export async function getBLEService(): Promise<BLEServiceInterface> {
  if (bleServiceInstance) {
    return bleServiceInstance.service
  }

  const isNative = Capacitor.isNativePlatform()
  
  if (isNative) {
    const nativeService = new NativeBluetoothService()
    bleServiceInstance = {
      service: nativeService,
      cleanup: async () => {
        await nativeService.cleanup()
        bleServiceInstance = null
      }
    }
    return nativeService
  } else {
    const webService = new WebBluetoothService()
    bleServiceInstance = {
      service: webService,
      cleanup: async () => {
        bleServiceInstance = null
      }
    }
    return webService
  }
}

export async function connectAndStreamHelio(
  deviceId: string,
  onReading: (readings: any[]) => void
): Promise<{ service: BLEServiceInterface; cleanup: () => Promise<void> }> {
  const isNative = Capacitor.isNativePlatform()
  
  if (isNative) {
    const service = await connectAndStreamHelioNative(deviceId, onReading)
    return {
      service,
      cleanup: async () => { await service.cleanup() }
    }
  } else {
    const service = await connectWeb(deviceId, onReading)
    return {
      service,
      cleanup: async () => {}
    }
  }
}

export function isWebBluetoothSupported(): boolean {
  return !Capacitor.isNativePlatform() && 'bluetooth' in navigator
}

export function isNativeBLESupported(): boolean {
  return Capacitor.isNativePlatform()
}