// sw.js - OpenSell service worker (v2.0.5)
const CACHE_NAME = 'opensell-v2.0.5';
const OFFLINE_URL = '/offline/';

const STATIC_CACHE_URLS = [
    '/static/css/pwa.css',
    '/static/js/pwa.js',
    '/static/images/logoicon.png',
    '/static/css/pages/navbar.css'
];

// Dynamic / authenticated paths that must never be cached or intercepted.
const SKIP_CACHE_PATTERNS = [
    '/api/',
    '/admin/',
    '/controlroom/',
    '/dashboard/',
    '/deposit/',
    '/accounts/',
    '/check-payment',
    '/create-permanent',
    '/generate-quick',
    '/notifications/',
    '/messages/',
    '/detail/',
    '/inbox/',
    '/ajax/',
    '/send/'
];

// ── Install ────────────────────────────────────────────────────────────────
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                // Each add is isolated: one failing URL must NEVER block the worker
                // from installing, otherwise push can never be delivered.
                const jobs = [OFFLINE_URL, ...STATIC_CACHE_URLS].map(url =>
                    cache.add(new Request(url, { cache: 'reload' })).catch(err => {
                        console.warn('SW: could not pre-cache', url, err);
                    })
                );
                return Promise.all(jobs);
            })
            .then(() => self.skipWaiting())
    );
});

// ── Activate ───────────────────────────────────────────────────────────────
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys()
            .then(names => Promise.all(
                names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n))
            ))
            .then(() => self.clients.claim())
    );
});

// ── Fetch ──────────────────────────────────────────────────────────────────
self.addEventListener('fetch', event => {
    const request = event.request;
    const url = new URL(request.url);

    if (url.origin !== self.location.origin) return;
    if (request.method !== 'GET') return;
    if (SKIP_CACHE_PATTERNS.some(p => url.pathname.includes(p))) return;
    if (url.pathname === '/sw.js') return;

    // Page loads: network first, offline page as fallback
    if (request.mode === 'navigate') {
        event.respondWith(
            fetch(request).catch(() =>
                caches.open(CACHE_NAME).then(cache => cache.match(OFFLINE_URL))
            )
        );
        return;
    }

    // Static assets: cache first, refresh in background
    event.respondWith(
        caches.match(request).then(cached => {
            if (cached) {
                fetch(request)
                    .then(res => {
                        if (isCacheable(res)) {
                            const copy = res.clone();
                            caches.open(CACHE_NAME).then(c => c.put(request, copy)).catch(() => {});
                        }
                    })
                    .catch(() => {});
                return cached;
            }

            return fetch(request).then(res => {
                if (isCacheable(res)) {
                    const copy = res.clone();
                    caches.open(CACHE_NAME).then(c => c.put(request, copy)).catch(() => {});
                }
                return res;
            });
        })
    );
});

// Only cache successful same-origin responses that are NOT html
// (an html body here is almost always a login redirect or error page).
function isCacheable(res) {
    if (!res || !res.ok || res.type !== 'basic') return false;
    const type = res.headers.get('content-type') || '';
    return !type.includes('text/html');
}

// ── Push ───────────────────────────────────────────────────────────────────
self.addEventListener('push', event => {
    let data = {};
    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            data = { body: event.data.text() };
        }
    }

    const title = data.title || 'OpenSell';
    const options = {
        body: data.body || data.message || '',
        icon: data.icon || '/static/images/logoicon.png',
        badge: data.badge || '/static/images/logoicon.png',
        tag: data.tag || 'opensell-notification',
        renotify: true,
        requireInteraction: false,
        data: { url: data.url || '/notifications/' }
    };

    // Always show a notification: browsers revoke push if a push event shows nothing.
    event.waitUntil(self.registration.showNotification(title, options));
});

// ── Notification click ─────────────────────────────────────────────────────
self.addEventListener('notificationclick', event => {
    event.notification.close();

    const rawUrl = (event.notification.data && event.notification.data.url) || '/notifications/';
    const targetUrl = new URL(rawUrl, self.location.origin).href;

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
            for (const client of windowClients) {
                if (new URL(client.url).origin === self.location.origin) {
                    return client.focus().then(c => (c && 'navigate' in c) ? c.navigate(targetUrl) : null);
                }
            }
            return clients.openWindow(targetUrl);
        })
    );
});

// ── Subscription rotated by the browser ────────────────────────────────────
// A service worker cannot read the CSRF cookie, so it cannot POST to Django safely.
// Instead, tell any open page to re-sync; pwa.js also re-syncs on every page load.
self.addEventListener('pushsubscriptionchange', event => {
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
            windowClients.forEach(c => c.postMessage({ type: 'PUSH_SUBSCRIPTION_CHANGED' }));
        })
    );
});