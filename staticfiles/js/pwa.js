class PWAManager {
    constructor() {
        this.deferredPrompt = null;
        this.isInstalled = false;
        this.installInstructions = null;
        this.init();
    }

    /**
     * Detects whether the current device is running iOS (iPhone/iPad/iPod).
     * iOS Safari does not support `beforeinstallprompt` and cannot trigger
     * programmatic installs, so any code path that calls updateInstallButton()
     * must skip iOS to avoid the "updateInstallButton called for iOS - button
     * should be hidden" warning.
     */
    isIOS() {
        return /iphone|ipad|ipod/i.test(navigator.userAgent) ||
            // iPadOS 13+ reports itself as MacOS with touch support
            (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    }

    async init() {
        // Don't initialize if running in PWA mode
        if (window.matchMedia('(display-mode: standalone)').matches ||
            window.navigator.standalone === true) {
            this.isInstalled = true;
            return;
        }

        await this.registerServiceWorker();
        this.setupInstallPrompt();
        this.checkInstallStatus();
        this.setupUIUpdates();
        this.setupInstallInstructionsIntegration();

        // Push notifications — only for authenticated users
        if (document.body.dataset.userAuthenticated === 'true') {
            this.initPushNotifications();
        }
    }

    async registerServiceWorker() {
        if ('serviceWorker' in navigator) {
            try {
                const registration = await navigator.serviceWorker.register('/sw.js');
                console.log('Service Worker registered successfully:', registration.scope);

                registration.addEventListener('updatefound', () => {
                    const newWorker = registration.installing;
                    newWorker.addEventListener('statechange', () => {
                        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                            this.showUpdateAvailable();
                        }
                    });
                });
            } catch (error) {
                console.error('Service Worker registration failed:', error);
            }
        }
    }

    setupInstallPrompt() {
        // `beforeinstallprompt` never fires on iOS — this block is safe as-is,
        // but the updateInstallButton() call inside is guarded anyway for clarity.
        window.addEventListener('beforeinstallprompt', (e) => {
            console.log('Install prompt available');
            e.preventDefault();
            this.deferredPrompt = e;
            this.showInstallButton();

            // Share the prompt with the install instructions modal.
            // Guard against iOS even though this event won't fire there —
            // belt-and-suspenders in case of future UA spoofing or emulation.
            if (window.pwaInstallInstructions && !this.isIOS()) {
                window.pwaInstallInstructions.deferredPrompt = e;
                this.safeUpdateInstallButton(window.pwaInstallInstructions);
            }
        });

        window.addEventListener('appinstalled', () => {
            console.log('PWA was installed');
            this.deferredPrompt = null;
            this.isInstalled = true;
            this.hideInstallButton();
            this.showInstallSuccess();

            // Mark installation time in localStorage
            localStorage.setItem('pwa_install_time', Date.now().toString());

            // Notify install instructions modal
            if (window.pwaInstallInstructions) {
                window.pwaInstallInstructions.isInstalled = true;
                window.pwaInstallInstructions.hideModal();
                window.pwaInstallInstructions.clearScheduledDisplays();
            }
        });
    }

    checkInstallStatus() {
        if (window.matchMedia('(display-mode: standalone)').matches ||
            window.navigator.standalone === true) {
            this.isInstalled = true;
            this.hideInstallButton();
        } else {
            // Check if PWA was previously installed (but running in browser now)
            const installTime = localStorage.getItem('pwa_install_time');
            if (installTime && (Date.now() - parseInt(installTime)) < (30 * 24 * 60 * 60 * 1000)) {
                // Consider recently installed (within 30 days)
                if (window.pwaInstallInstructions) {
                    window.pwaInstallInstructions.isPWAInstalledInBrowser = true;
                }
            }
        }
    }

    setupInstallInstructionsIntegration() {
        if (window.pwaInstallInstructions) {
            this.installInstructions = window.pwaInstallInstructions;
            this.sharePromptWithInstructions();
        } else {
            // Wait for pwaInstallInstructions to load
            setTimeout(() => {
                if (window.pwaInstallInstructions) {
                    this.installInstructions = window.pwaInstallInstructions;
                    this.sharePromptWithInstructions();
                }
            }, 1000);
        }
    }

    sharePromptWithInstructions() {
        // Only share the deferred prompt (and trigger a button update) when:
        //   1. The instructions object exists
        //   2. A real deferred prompt is available (non-null = Chromium-based browser)
        //   3. The platform is NOT iOS (iOS never receives a deferredPrompt anyway,
        //      but calling updateInstallButton() on it triggers the console warning)
        if (this.installInstructions && this.deferredPrompt && !this.isIOS()) {
            this.installInstructions.deferredPrompt = this.deferredPrompt;
            this.safeUpdateInstallButton(this.installInstructions);
        }
    }

    /**
     * Calls updateInstallButton() on the given instructions instance only when
     * the platform is not iOS. Centralising the guard here means every future
     * call site just uses this helper instead of repeating the check inline.
     *
     * @param {object} instructions - A pwaInstallInstructions instance
     */
    safeUpdateInstallButton(instructions) {
        if (!instructions || typeof instructions.updateInstallButton !== 'function') return;
        if (this.isIOS()) return; // iOS install button must stay hidden — skip silently
        instructions.updateInstallButton();
    }

    async promptInstall() {
        if (!this.deferredPrompt) {
            // No browser prompt available — show the guided instructions modal instead
            if (this.installInstructions) {
                this.installInstructions.show();
            } else {
                this.showInstallInstructions();
            }
            return;
        }

        this.deferredPrompt.prompt();
        const { outcome } = await this.deferredPrompt.userChoice;
        console.log(`User response to install prompt: ${outcome}`);

        if (outcome === 'accepted') {
            this.isInstalled = true;
            localStorage.setItem('pwa_install_time', Date.now().toString());
        }

        this.deferredPrompt = null;
        this.hideInstallButton();

        // Track analytics
        if (typeof gtag !== 'undefined') {
            gtag('event', 'pwa_install_attempted', {
                method: 'footer_button',
                outcome: outcome
            });
        }
    }

    showInstallButton() {
        const installBtn = document.getElementById('pwa-install-btn');
        const footerInstallBtn = document.getElementById('footer-install-btn');

        if (installBtn) {
            installBtn.style.display = 'block';
            installBtn.addEventListener('click', () => this.promptInstall());
        }

        if (footerInstallBtn) {
            footerInstallBtn.style.display = 'flex';
            footerInstallBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.promptInstall();
            });
        }
    }

    hideInstallButton() {
        const installBtn = document.getElementById('pwa-install-btn');
        const footerInstallBtn = document.getElementById('footer-install-btn');
        const pwaInstallSection = document.getElementById('pwaInstallSection');

        if (installBtn) installBtn.style.display = 'none';
        if (footerInstallBtn) footerInstallBtn.style.display = 'none';
        if (pwaInstallSection) pwaInstallSection.style.display = 'none';
    }

    showInstallInstructions() {
        const userAgent = navigator.userAgent.toLowerCase();
        let instructions = '';

        if (/iphone|ipad|ipod/.test(userAgent)) {
            instructions = 'To install: Tap the share button <i class="bi bi-share"></i> and select "Add to Home Screen"';
        } else if (/android/.test(userAgent)) {
            instructions = 'To install: Tap the menu button <i class="bi bi-three-dots-vertical"></i> and select "Add to Home Screen" or "Install App"';
        } else {
            instructions = 'To install: Look for the install button <i class="bi bi-download"></i> in your browser\'s address bar';
        }

        this.showToast(instructions, 'info', 5000);
    }

    showInstallSuccess() {
        this.showToast('OpenSell has been installed successfully! 🎉', 'success');
    }

    showUpdateAvailable() {
        this.showToast('A new version is available. Refresh to update.', 'info', 0, () => {
            window.location.reload();
        });
    }

    showToast(message, type = 'info', duration = 3000, action = null) {
        // Use the existing alert system if available
        if (typeof showSystemAlert !== 'undefined') {
            showSystemAlert(message, type, duration);
            return;
        }

        // Fallback to custom toast
        const toast = document.createElement('div');
        toast.className = `pwa-toast pwa-toast-${type}`;
        toast.innerHTML = `
            <div class="pwa-toast-content">
                <span>${message}</span>
                ${action ? '<button class="pwa-toast-action">Update</button>' : ''}
                <button class="pwa-toast-close">&times;</button>
            </div>
        `;

        document.body.appendChild(toast);
        setTimeout(() => toast.classList.add('pwa-toast-show'), 100);

        if (duration > 0) {
            setTimeout(() => this.hideToast(toast), duration);
        }

        toast.querySelector('.pwa-toast-close').addEventListener('click', () => {
            this.hideToast(toast);
        });

        if (action) {
            toast.querySelector('.pwa-toast-action').addEventListener('click', () => {
                action();
                this.hideToast(toast);
            });
        }
    }

    hideToast(toast) {
        toast.classList.remove('pwa-toast-show');
        setTimeout(() => toast.remove(), 300);
    }

    setupUIUpdates() {
        window.addEventListener('online', () => {
            this.showToast('You are back online!', 'success');
        });

        window.addEventListener('offline', () => {
            this.showToast('You are currently offline. Some features may be limited.', 'warning', 5000);
        });
    }

    // Public methods for manual control
    showInstallModal() {
        if (this.installInstructions) {
            this.installInstructions.show();
        }
    }

    hideInstallModal() {
        if (this.installInstructions) {
            this.installInstructions.hide();
        }
    }
    // ── Push Notification Methods ──────────────────────────────────────────

    _urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
        const base64  = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
        const raw     = atob(base64);
        return Uint8Array.from([...raw].map(c => c.charCodeAt(0)));
    }

    _getCsrfToken() {
        // Already present in base.html as <meta name="csrf-token">
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.getAttribute('content');
        const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
        return cookie ? cookie.split('=')[1].trim() : '';
    }

    async _postJSON(url, body) {
        return fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this._getCsrfToken(),
            },
            body: JSON.stringify(body),
            credentials: 'same-origin',
        });
    }

    async initPushNotifications() {
        if (!('PushManager' in window) || !('Notification' in window)) return;

        try {
            // SW is already registered by registerServiceWorker() — just get the registration
            const registration = await navigator.serviceWorker.ready;

            if (Notification.permission === 'granted') {
                // Already allowed — sync existing subscription with server
                await this._syncPushSubscription(registration);
            }

            // Wire up enable/disable buttons that may exist on the preferences page
            const enableBtn  = document.getElementById('enablePushBtn');
            const disableBtn = document.getElementById('disablePushBtn');

            if (enableBtn) {
                enableBtn.addEventListener('click', async () => {
                    const result = await Notification.requestPermission();
                    if (result === 'granted') {
                        const ok = await this._syncPushSubscription(registration);
                        if (ok) {
                            enableBtn.textContent = 'Push notifications enabled ✓';
                            enableBtn.disabled = true;
                            if (disableBtn) disableBtn.disabled = false;
                            this.showToast('Push notifications enabled!', 'success');
                        }
                    } else {
                        this.showToast('Permission denied — push notifications blocked.', 'warning');
                    }
                });
            }

            if (disableBtn) {
                disableBtn.addEventListener('click', async () => {
                    await this._unsubscribePush(registration);
                    disableBtn.textContent = 'Push notifications disabled';
                    disableBtn.disabled = true;
                    if (enableBtn) enableBtn.disabled = false;
                    this.showToast('Push notifications disabled.', 'info');
                });
            }

        } catch (err) {
            console.warn('[PWAManager] Push init failed:', err);
        }
    }

    async _syncPushSubscription(registration) {
        try {
            // Fetch VAPID public key from the server
            const res    = await fetch('/notifications/push/vapid-key/', { credentials: 'same-origin' });
            const { publicKey } = await res.json();
            if (!publicKey) { console.warn('[PWAManager] No VAPID key returned'); return false; }

            const appServerKey = this._urlBase64ToUint8Array(publicKey);

            let subscription = await registration.pushManager.getSubscription();
            if (!subscription) {
                subscription = await registration.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: appServerKey,
                });
            }

            // Always sync the current subscription to the server (handles rotations)
            await this._postJSON('/notifications/push/subscribe/', {
                subscription: subscription.toJSON(),
            });
            return true;
        } catch (err) {
            console.warn('[PWAManager] Push subscribe failed:', err);
            return false;
        }
    }

    async _unsubscribePush(registration) {
        try {
            const subscription = await registration.pushManager.getSubscription();
            if (subscription) {
                await this._postJSON('/notifications/push/unsubscribe/', {
                    endpoint: subscription.endpoint,
                });
                await subscription.unsubscribe();
            }
        } catch (err) {
            console.warn('[PWAManager] Push unsubscribe failed:', err);
        }
    }


}

document.addEventListener('DOMContentLoaded', () => {
    // Don't initialize PWA manager if running in PWA mode
    if (!window.matchMedia('(display-mode: standalone)').matches &&
        !window.navigator.standalone) {
        window.pwaManager = new PWAManager();
    }
});