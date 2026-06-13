// PWA Service Worker registration and offline-first sync

export interface SyncQueueItem {
  id: string
  type: 'ingest' | 'calendar_sync' | 'export'
  payload: any
  timestamp: number
  retries: number
}

export interface PWAConfig {
  swUrl: string
  syncInterval: number
  maxRetries: number
}

class PWAService {
  private registration: ServiceWorkerRegistration | null = null
  private syncQueue: SyncQueueItem[] = []
  private isOnline = navigator.onLine
  private config: PWAConfig
  private dbName = 'helios-offline-db'
  private dbVersion = 1

  constructor(config: Partial<PWAConfig> = {}) {
    this.config = {
      swUrl: '/sw.js',
      syncInterval: 30000, // 30 seconds
      maxRetries: 3,
      ...config
    }
  }

  async initialize(): Promise<boolean> {
    if (!('serviceWorker' in navigator)) {
      console.warn('Service Worker not supported')
      return false
    }

    try {
      this.registration = await navigator.serviceWorker.register(this.config.swUrl)
      console.log('Service Worker registered:', this.registration.scope)

      // Listen for online/offline events
      window.addEventListener('online', () => this.handleOnline())
      window.addEventListener('offline', () => this.handleOffline())

      // Initialize IndexedDB for offline queue
      await this.initOfflineDB()

      // Start periodic sync
      this.startPeriodicSync()

      return true
    } catch (error) {
      console.error('Service Worker registration failed:', error)
      return false
    }
  }

  private async initOfflineDB(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.dbVersion)
      
      request.onerror = () => reject(request.error)
      request.onsuccess = () => resolve()
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result
        
        if (!db.objectStoreNames.contains('syncQueue')) {
          db.createObjectStore('syncQueue', { keyPath: 'id' })
        }
        
        if (!db.objectStoreNames.contains('cachedData')) {
          db.createObjectStore('cachedData', { keyPath: 'key' })
        }
      }
    })
  }

  private startPeriodicSync(): void {
    setInterval(() => {
      if (this.isOnline && this.syncQueue.length > 0) {
        this.processSyncQueue()
      }
    }, this.config.syncInterval)
  }

  private handleOnline(): void {
    this.isOnline = true
    console.log('App online - processing sync queue')
    this.processSyncQueue()
    
    // Notify user
    this.showToast('Back online - syncing data...')
  }

  private handleOffline(): void {
    this.isOnline = false
    console.log('App offline - queueing operations')
    this.showToast('Offline - changes will sync when online')
  }

  private showToast(message: string): void {
    // Dispatch custom event for toast UI
    window.dispatchEvent(new CustomEvent('helios-toast', { 
      detail: { message, type: this.isOnline ? 'success' : 'warning' }
    }))
  }

  // Queue an operation for sync
  async queueSync(item: Omit<SyncQueueItem, 'id' | 'timestamp' | 'retries'>): Promise<string> {
    const syncItem: SyncQueueItem = {
      ...item,
      id: crypto.randomUUID(),
      timestamp: Date.now(),
      retries: 0
    }

    this.syncQueue.push(syncItem)
    await this.saveToOfflineDB('syncQueue', syncItem)
    
    // Try immediate sync if online
    if (this.isOnline) {
      this.processSyncQueue()
    }
    
    return syncItem.id
  }

  // Ingest sensor readings with offline support
  async ingestReadings(readings: any[], source: string = 'web'): Promise<{ success: boolean; queued: number }> {
    if (this.isOnline) {
      try {
        const response = await fetch('/api/v1/ingest/telemetry', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ readings, source })
        })
        
        if (response.ok) {
          const result = await response.json()
          return { success: true, queued: 0 }
        }
      } catch (error) {
        console.warn('Online ingest failed, queueing:', error)
      }
    }

    // Queue for later
    const id = await this.queueSync({
      type: 'ingest',
      payload: { readings, source }
    })
    
    return { success: true, queued: 1 }
  }

  // Process sync queue
  async processSyncQueue(): Promise<void> {
    if (this.syncQueue.length === 0) return

    const toProcess = [...this.syncQueue]
    const failed: SyncQueueItem[] = []

    for (const item of toProcess) {
      try {
        let success = false
        
        switch (item.type) {
          case 'ingest':
            success = await this.syncIngest(item.payload)
            break
          case 'calendar_sync':
            success = await this.syncCalendar(item.payload)
            break
          case 'export':
            success = await this.syncExport(item.payload)
            break
        }
        
        if (success) {
          // Remove from queue
          this.syncQueue = this.syncQueue.filter(i => i.id !== item.id)
          await this.removeFromOfflineDB('syncQueue', item.id)
        } else {
          // Increment retries
          item.retries++
          if (item.retries >= this.config.maxRetries) {
            console.error('Max retries reached for:', item.id)
            failed.push(item)
          }
          failed.push(item)
        }
      } catch (error) {
        console.error('Sync failed for item:', item.id, error)
        item.retries++
        if (item.retries >= this.config.maxRetries) {
          console.error('Max retries reached for:', item.id)
        }
        failed.push(item)
      }
    }

    // Update queue with failed items
    this.syncQueue = failed
    await this.saveOfflineQueue()
  }

  private async syncIngest(payload: any): Promise<boolean> {
    try {
      const response = await fetch('/api/v1/ingest/telemetry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      return response.ok
    } catch {
      return false
    }
  }

  private async syncCalendar(payload: any): Promise<boolean> {
    try {
      const response = await fetch('/api/v1/calendar/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      return response.ok
    } catch {
      return false
    }
  }

  private async syncExport(payload: any): Promise<boolean> {
    try {
      const response = await fetch('/api/v1/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      return response.ok
    } catch {
      return false
    }
  }

  // Offline DB operations
  private async saveToOfflineDB(storeName: string, data: any): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.dbVersion)
      request.onsuccess = () => {
        const db = request.result
        const transaction = db.transaction(storeName, 'readwrite')
        const store = transaction.objectStore(storeName)
        store.put(data)
        transaction.oncomplete = () => resolve()
        transaction.onerror = () => reject(transaction.error)
      }
      request.onerror = () => reject(request.error)
    })
  }

  private async removeFromOfflineDB(storeName: string, key: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.dbVersion)
      request.onsuccess = () => {
        const db = request.result
        const transaction = db.transaction(storeName, 'readwrite')
        const store = transaction.objectStore(storeName)
        store.delete(key)
        transaction.oncomplete = () => resolve()
        transaction.onerror = () => reject(transaction.error)
      }
      request.onerror = () => reject(request.error)
    })
  }

  private async saveOfflineQueue(): Promise<void> {
    // Clear and rewrite entire queue
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.dbVersion)
      request.onsuccess = () => {
        const db = request.result
        const transaction = db.transaction('syncQueue', 'readwrite')
        const store = transaction.objectStore('syncQueue')
        store.clear()
        this.syncQueue.forEach(item => store.put(item))
        transaction.oncomplete = () => resolve()
        transaction.onerror = () => reject(transaction.error)
      }
      request.onerror = () => reject(request.error)
    })
  }

  // Cache API responses for offline viewing
  async cacheData(key: string, data: any): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.dbVersion)
      request.onsuccess = () => {
        const db = request.result
        const transaction = db.transaction('cachedData', 'readwrite')
        const store = transaction.objectStore('cachedData')
        store.put({ key, data, timestamp: Date.now() })
        transaction.oncomplete = () => resolve()
        transaction.onerror = () => reject(transaction.error)
      }
      request.onerror = () => reject(request.error)
    })
  }

  async getCachedData(key: string): Promise<any | null> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.dbVersion)
      request.onsuccess = () => {
        const db = request.result
        const transaction = db.transaction('cachedData', 'readonly')
        const store = transaction.objectStore('cachedData')
        const getRequest = store.get(key)
        getRequest.onsuccess = () => resolve(getRequest.result?.data || null)
        getRequest.onerror = () => reject(getRequest.error)
      }
      request.onerror = () => reject(request.error)
    })
  }

  // Get sync status
  getSyncStatus(): { queueLength: number; isOnline: boolean; lastSync: number | null } {
    return {
      queueLength: this.syncQueue.length,
      isOnline: this.isOnline,
      lastSync: this.syncQueue.length > 0 ? this.syncQueue[0].timestamp : null
    }
  }

  // Force sync now
  async forceSync(): Promise<void> {
    if (this.isOnline) {
      await this.processSyncQueue()
    } else {
      throw new Error('Cannot sync while offline')
    }
  }
}

// Singleton instance
let pwaServiceInstance: PWAService | null = null

export function getPWAService(config?: Partial<PWAConfig>): PWAService {
  if (!pwaServiceInstance) {
    pwaServiceInstance = new PWAService(config)
  }
  return pwaServiceInstance
}

// Auto-initialize on load
if (typeof window !== 'undefined') {
  window.addEventListener('load', () => {
    getPWAService().initialize()
  })
}