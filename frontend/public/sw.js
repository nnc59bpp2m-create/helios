// Helios Service Worker - Offline-first PWA

const CACHE_NAME = 'helios-v1'
const STATIC_CACHE = 'helios-static-v1'
const API_CACHE = 'helios-api-v1'

const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/favicon.svg'
]

// Install event - cache static assets
self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(function(cache) {
      console.log('[SW] Caching static assets')
      return cache.addAll(STATIC_ASSETS)
    }).then(function() { self.skipWaiting() })
  )
})

// Activate event - clean old caches
self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(cacheNames) {
      return Promise.all(
        cacheNames
          .filter(function(name) { return name !== STATIC_CACHE && name !== API_CACHE })
          .map(function(name) { return caches.delete(name) })
      )
    }).then(function() { self.clients.claim() })
  )
})

// Fetch event - implement caching strategies
self.addEventListener('fetch', function(event) {
  var request = event.request
  var url = new URL(request.url)

  // Skip non-GET requests
  if (request.method !== 'GET') return

  // Skip chrome-extension, data:, etc.
  if (!url.protocol.startsWith('http')) return

  // API calls - Network First
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(request, API_CACHE))
    return
  }

  // Static assets - Cache First
  if (
    url.pathname.startsWith('/assets/') ||
    url.pathname.endsWith('.js') ||
    url.pathname.endsWith('.css') ||
    url.pathname.endsWith('.png') ||
    url.pathname.endsWith('.jpg') ||
    url.pathname.endsWith('.svg') ||
    url.pathname.endsWith('.ico') ||
    url.pathname.endsWith('.woff2')
  ) {
    event.respondWith(cacheFirst(request, STATIC_CACHE))
    return
  }

  // HTML pages - Network First (for SPA updates)
  if (request.headers.get('accept') && request.headers.get('accept').includes('text/html')) {
    event.respondWith(networkFirst(request, STATIC_CACHE))
    return
  }

  // Default: Network First
  event.respondWith(networkFirst(request, STATIC_CACHE))
})

// Cache First strategy
async function cacheFirst(request, cacheName) {
  var cache = await caches.open(cacheName)
  var cached = await cache.match(request)

  if (cached) {
    // Serve from cache, update in background
    fetch(request).then(function(response) {
      if (response.ok) cache.put(request, response.clone())
    }).catch(function() {})
    return cached
  }

  // Not in cache, fetch and cache
  try {
    var response = await fetch(request)
    if (response.ok) {
      cache.put(request, response.clone())
    }
    return response
  } catch (error) {
    return new Response('Offline', { status: 503, statusText: 'Service Unavailable' })
  }
}

// Network First strategy
async function networkFirst(request, cacheName) {
  var cache = await caches.open(cacheName)

  try {
    var response = await fetch(request)
    
    if (response.ok) {
      // Cache successful responses
      cache.put(request, response.clone())
    }
    
    return response
  } catch (error) {
    // Network failed, try cache
    var cached = await cache.match(request)
    
    if (cached) {
      return cached
    }
    
    // No cache, return offline response
    return new Response(
      JSON.stringify({ error: 'Offline', message: 'No cached data available' }),
      {
        status: 503,
        headers: { 'Content-Type': 'application/json' }
      }
    )
  }
}

// Background Sync for queued operations
self.addEventListener('sync', function(event) {
  if (event.tag === 'helios-sync') {
    event.waitUntil(doBackgroundSync())
  }
})

async function doBackgroundSync() {
  // Process queued operations from IndexedDB
  // Notify clients
  var clients = await self.clients.matchAll()
  clients.forEach(function(client) {
    client.postMessage({ type: 'SYNC_COMPLETE' })
  })
}

// Push notifications
self.addEventListener('push', function(event) {
  if (!event.data) return

  var data = event.data.json()
  
  var options = {
    body: data.body || 'New notification',
    icon: '/pwa-192x192.png',
    badge: '/badge-72x72.png',
    vibrate: [200, 100, 200],
    data: data.data || {},
    actions: data.actions || [],
    requireInteraction: data.requireInteraction || false
  }

  event.waitUntil(
    self.registration.showNotification(data.title || 'Helios', options)
  )
})

// Notification click
self.addEventListener('notificationclick', function(event) {
  event.notification.close()

  // Open or focus the app
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
      for (var i = 0; i < clientList.length; i++) {
        var client = clientList[i]
        if (client.url.includes('/') && 'focus' in client) {
          return client.focus()
        }
      }
      return self.clients.openWindow('/')
    })
  )
})

// Periodic background sync (if supported)
self.addEventListener('periodicsync', function(event) {
  if (event.tag === 'helios-periodic-sync') {
    event.waitUntil(doPeriodicSync())
  }
})

async function doPeriodicSync() {
  console.log('[SW] Periodic sync triggered')
  
  var clients = await self.clients.matchAll()
  clients.forEach(function(client) {
    client.postMessage({ type: 'PERIODIC_SYNC' })
  })
}

// Message handling from main thread
self.addEventListener('message', function(event) {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
  
  if (event.data && event.data.type === 'CACHE_API_RESPONSE') {
    var url = event.data.url
    var response = event.data.response
    caches.open(API_CACHE).then(function(cache) {
      cache.put(url, new Response(JSON.stringify(response), {
        headers: { 'Content-Type': 'application/json' }
      }))
    })
  }
})

console.log('[SW] Helios Service Worker loaded')