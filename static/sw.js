// sw.js - FIXED VERSION with Better Error Handling
const CACHE_NAME = 'opensell-v1.0.2';
const OFFLINE_URL = '/offline/';

const STATIC_CACHE_URLS = [
    '/',
    '/categories/',
    '/products/',
    '/static/css/styles.css',
    '/static/css/pwa.css',
    '/static/js/pwa.js',
    '/static/images/logoicon.png',
    OFFLINE_URL
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('Service Worker: Caching essential files');
                return cache.addAll(STATIC_CACHE_URLS).catch(err => {
                    console.error('Failed to cache some URLs:', err);
                });
            })
            .then(() => self.skipWaiting())
    );
});

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

self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);
    
    // CRITICAL: Skip caching for these patterns
    const skipCachePatterns = [
        '/api/',
        '/admin/',
        '/dashboard/',
        '/deposit/',
        '/accounts/',
        '/check-payment',
        '/create-permanent',
        '/generate-quick'
    ];
    
    // Check if URL matches any skip pattern
    const shouldSkipCache = skipCachePatterns.some(pattern => 
        url.pathname.includes(pattern)
    );
    
    // Skip external requests
    if (url.origin !== self.location.origin) {
        return;
    }

    if (event.request.method !== 'GET') {
        return;
    }

    // Skip caching for API/admin patterns — let browser handle directly
    if (shouldSkipCache) {
        return;
    }

    // Handle navigation requests (page loads)
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

    // Cache static assets (CSS, JS, images, etc.)
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                if (response) {
                    // Return cached version and update in background
                    fetch(event.request)
                        .then(fetchResponse => {
                            if (fetchResponse && fetchResponse.ok) {
                                caches.open(CACHE_NAME)
                                    .then(cache => cache.put(event.request, fetchResponse.clone()))
                                    .catch(err => console.error('Cache update failed:', err));
                            }
                        })
                        .catch(() => {}); // Silently fail background updates
                    return response;
                }

                // Not in cache, fetch it
                return fetch(event.request)
                    .then(fetchResponse => {
                        // Only cache successful GET requests for basic content
                        if (fetchResponse && fetchResponse.ok && 
                            fetchResponse.type === 'basic' &&
                            event.request.method === 'GET') {
                            const responseClone = fetchResponse.clone();
                            caches.open(CACHE_NAME)
                                .then(cache => cache.put(event.request, responseClone))
                                .catch(err => console.error('Failed to cache response:', err));
                        }
                        return fetchResponse;
                    })
                    .catch(error => {
                        console.error('Fetch failed:', url.pathname, error);
                        // Return offline page for navigation requests
                        if (event.request.mode === 'navigate') {
                            return caches.match(OFFLINE_URL);
                        }
                        throw error;
                    });
            })
    );
});

self.addEventListener('push', event => {
    if (!event.data) return;
    try {
        const data = event.data.json();
        const options = {
            body:  data.body || data.message || '',
            icon:  data.icon  || '/static/images/logoicon.png',
            badge: data.badge || '/static/images/logoicon.png',
            tag:   data.tag   || 'opensell-notification',
            renotify: true,
            requireInteraction: false,
            // Passed to notificationclick so it knows where to navigate
            data: { url: data.url || '/notifications/' },
        };
        event.waitUntil(
            self.registration.showNotification(data.title || 'OpenSell', options)
        );
    } catch (error) {
        console.error('Error processing push notification:', error);
    }
});
self.addEventListener('notificationclick', event => {
    event.notification.close();

    const targetUrl = (event.notification.data && event.notification.data.url)
        ? event.notification.data.url
        : '/notifications/';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
            // If a tab with the site is already open, navigate it and focus
            for (const client of windowClients) {
                if (new URL(client.url).origin === self.location.origin) {
                    client.navigate(targetUrl);
                    return client.focus();
                }
            }
            // No open tab — open a new one
            return clients.openWindow(targetUrl);
        })
    );
});

self.addEventListener('pushsubscriptionchange', event => {
    // Browser rotated the subscription keys — re-subscribe and sync with server
    event.waitUntil(
        self.registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: event.oldSubscription
                ? event.oldSubscription.options.applicationServerKey
                : null,
        }).then(newSub => {
            return fetch('/notifications/push/subscribe/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ subscription: newSub.toJSON() }),
                credentials: 'include',
            });
        })
    );
});