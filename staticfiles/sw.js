const CACHE_NAME = 'opensell-v1.0.0';
const OFFLINE_URL = '/offline/';

// Files to cache for offline functionality
const STATIC_CACHE_URLS = [
    '/',
    '/categories/',
    '/products/',
    '/static/css/main.css', // Adjust to your actual CSS files
    '/static/js/main.js',   // Adjust to your actual JS files
    '/static/images/logoicon.png',
    OFFLINE_URL
];

// Install event - cache essential files
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('Service Worker: Caching essential files');
                return cache.addAll(STATIC_CACHE_URLS);
            })
            .then(() => self.skipWaiting())
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('Service Worker: Deleting old cache', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// Fetch event - implement caching strategies
self.addEventListener('fetch', event => {
    // Skip cross-origin requests
    if (!event.request.url.startsWith(self.location.origin)) {
        return;
    }

    // Handle navigation requests
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request)
                .catch(() => {
                    return caches.open(CACHE_NAME)
                        .then(cache => cache.match(OFFLINE_URL));
                })
        );
        return;
    }

    // Handle other requests with cache-first strategy
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                if (response) {
                    // Update cache in background
                    fetch(event.request)
                        .then(fetchResponse => {
                            if (fetchResponse.ok) {
                                caches.open(CACHE_NAME)
                                    .then(cache => cache.put(event.request, fetchResponse.clone()));
                            }
                        })
                        .catch(() => {});
                    return response;
                }

                // Not in cache, fetch from network
                return fetch(event.request)
                    .then(fetchResponse => {
                        // Cache successful responses
                        if (fetchResponse.ok && fetchResponse.type === 'basic') {
                            const responseClone = fetchResponse.clone();
                            caches.open(CACHE_NAME)
                                .then(cache => cache.put(event.request, responseClone));
                        }
                        return fetchResponse;
                    });
            })
    );
});

// Background sync for when connection is restored
self.addEventListener('sync', event => {
    if (event.tag === 'background-sync') {
        event.waitUntil(
            // Handle any background sync operations
            console.log('Background sync triggered')
        );
    }
});

// Push notifications (if you plan to implement them)
self.addEventListener('push', event => {
    if (event.data) {
        const data = event.data.json();
        const options = {
            body: data.body,
            icon: '/static/images/logoicon.png',
            badge: '/static/images/logoicon-72.png',
            tag: 'opensell-notification',
            requireInteraction: true,
            actions: [
                {
                    action: 'view',
                    title: 'View',
                    icon: '/static/images/view-icon.png'
                },
                {
                    action: 'close',
                    title: 'Close',
                    icon: '/static/images/close-icon.png'
                }
            ]
        };

        event.waitUntil(
            self.registration.showNotification(data.title, options)
        );
    }
});