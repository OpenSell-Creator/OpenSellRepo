(function () {
  'use strict';

  // ── Config ────────────────────────────────────────────────────────────────
  const SUBSCRIBE_URL   = '/notifications/push/subscribe/';
  const UNSUBSCRIBE_URL = '/notifications/push/unsubscribe/';
  const VAPID_KEY_URL   = '/notifications/push/vapid-key/';
  const SW_PATH         = '/static/js/pwa.js';   // must be at root scope

  // ── Utility ───────────────────────────────────────────────────────────────

  function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64  = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw     = atob(base64);
    return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
  }

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content');
    const cookie = document.cookie.split(';').find((c) => c.trim().startsWith('csrftoken='));
    return cookie ? cookie.split('=')[1].trim() : '';
  }

  async function postJSON(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify(body),
      credentials: 'same-origin',
    });
  }

  // ── Core ──────────────────────────────────────────────────────────────────

  async function getVapidPublicKey() {
    const res  = await fetch(VAPID_KEY_URL, { credentials: 'same-origin' });
    const data = await res.json();
    return data.publicKey;
  }

  async function subscribeToPush(registration) {
    const vapidPublicKey  = await getVapidPublicKey();
    const applicationServerKey = urlBase64ToUint8Array(vapidPublicKey);

    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey,
    });

    await postJSON(SUBSCRIBE_URL, { subscription: subscription.toJSON() });
    console.log('[PushManager] Subscribed and synced with server.');
    return subscription;
  }

  async function unsubscribeFromPush(registration) {
    const subscription = await registration.pushManager.getSubscription();
    if (!subscription) return;

    await postJSON(UNSUBSCRIBE_URL, { endpoint: subscription.endpoint });
    await subscription.unsubscribe();
    console.log('[PushManager] Unsubscribed.');
  }

  // ── Init ──────────────────────────────────────────────────────────────────

  async function init() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      console.log('[PushManager] Push not supported in this browser.');
      return;
    }

    // Register (or reuse) the service worker
    const registration = await navigator.serviceWorker.register(SW_PATH, { scope: '/' });
    console.log('[PushManager] Service worker registered:', registration.scope);

    // Check current permission state
    const permission = Notification.permission;

    if (permission === 'granted') {
      // Already allowed — make sure we have a subscription on the server
      const existingSub = await registration.pushManager.getSubscription();
      if (!existingSub) {
        await subscribeToPush(registration);
      } else {
        // Sync the existing subscription endpoint in case it rotated
        await postJSON(SUBSCRIBE_URL, { subscription: existingSub.toJSON() });
      }

    } else if (permission === 'default') {
      // Only request permission in response to a user gesture (button click).
      // Wiring up the "Enable push" button in the preferences page.
      const enableBtn = document.getElementById('enablePushBtn');
      if (enableBtn) {
        enableBtn.addEventListener('click', async () => {
          const result = await Notification.requestPermission();
          if (result === 'granted') {
            await subscribeToPush(registration);
            enableBtn.textContent = 'Push notifications enabled ✓';
            enableBtn.disabled = true;
          }
        });
      }
    }

    // Wire up "Disable push" button if present
    const disableBtn = document.getElementById('disablePushBtn');
    if (disableBtn) {
      disableBtn.addEventListener('click', async () => {
        await unsubscribeFromPush(registration);
        disableBtn.textContent = 'Push notifications disabled';
        disableBtn.disabled = true;
      });
    }
  }

  // Run after DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();