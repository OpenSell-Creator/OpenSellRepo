const CACHE_NAME = 'opensell-v1.0.0';
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
                return cache.addAll(STATIC_CACHE_URLS);
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
    if (!event.request.url.startsWith(self.location.origin)) {
        return;
    }

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

    event.respondWith(
        caches.match(event.request)
            .then(response => {
                if (response) {
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

                return fetch(event.request)
                    .then(fetchResponse => {
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

self.addEventListener('push', event => {
    if (event.data) {
        const data = event.data.json();
        const options = {
            body: data.body,
            icon: '/static/images/logoicon.png',
            badge: '/static/images/logoicon.png',
            tag: 'opensell-notification',
            requireInteraction: true
        };

        event.waitUntil(
            self.registration.showNotification(data.title, options)
        );
    }
});