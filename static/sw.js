// sw.js - FIXED VERSION with Better Error Handling
const CACHE_NAME = 'opensell-v2.0.3';
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
                return Promise.all([
                    cache.add(new Request(OFFLINE_URL, { cache: 'reload' })),
                    cache.addAll(STATIC_CACHE_URLS.filter(u => u !== OFFLINE_URL)).catch(err => {
                        console.error('Failed to cache some URLs:', err);
                    })
                ]);
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
        '/notifications/',
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

    // Only static assets are cached. Anything else (JSON, counts, per-user data) must always
    // hit the network, otherwise stale or another user's responses could be served from cache.
    const isStaticAsset = url.pathname.startsWith('/static/') ||
        ['style', 'script', 'image', 'font'].includes(event.request.destination);
    if (!isStaticAsset) {
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

function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = atob(base64);
    return Uint8Array.from([...raw].map(c => c.charCodeAt(0)));
}

self.addEventListener('push', event => {
    // Never return without showing a notification: iOS (and Chrome) drop the subscription
    // when a push arrives and nothing visible is shown.
    let data = {};
    if (event.data) {
        try {
            data = event.data.json();
        } catch (error) {
            data = { body: event.data.text() };
        }
    }
    const options = {
        body:  data.body || data.message || 'You have a new notification',
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
});

self.addEventListener('notificationclick', event => {
    event.notification.close();

    const targetUrl = (event.notification.data && event.notification.data.url)
        ? event.notification.data.url
        : '/notifications/';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(async windowClients => {
            // If a tab/app window is already open, focus it and move it to the target page
            for (const client of windowClients) {
                if (new URL(client.url).origin === self.location.origin) {
                    try {
                        const focused = await client.focus();
                        if (focused && 'navigate' in focused) await focused.navigate(targetUrl);
                        return;
                    } catch (err) {
                        break; // fall back to opening a new window
                    }
                }
            }
            return clients.openWindow(targetUrl);
        })
    );
});

self.addEventListener('pushsubscriptionchange', event => {
    // Browser rotated the subscription — re-subscribe. If the server rejects this background
    // sync (e.g. CSRF), pwa.js re-syncs the subscription on the next visit.
    event.waitUntil((async () => {
        try {
            let key = event.oldSubscription && event.oldSubscription.options &&
                event.oldSubscription.options.applicationServerKey;
            if (!key) {
                const res = await fetch('/notifications/push/vapid-key/', { credentials: 'include' });
                const { publicKey } = await res.json();
                key = urlBase64ToUint8Array(publicKey);
            }
            const newSub = await self.registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: key,
            });
            await fetch('/notifications/push/subscribe/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ subscription: newSub.toJSON() }),
                credentials: 'include',
            });
        } catch (err) {
            console.error('pushsubscriptionchange failed:', err);
        }
    })());
});