// PWA Installation and Service Worker Registration
class PWAManager {
    constructor() {
        this.deferredPrompt = null;
        this.isInstalled = false;
        this.init();
    }

    async init() {
        // Register service worker
        await this.registerServiceWorker();
        
        // Setup install prompt
        this.setupInstallPrompt();
        
        // Check if already installed
        this.checkInstallStatus();
        
        // Setup UI updates
        this.setupUIUpdates();
    }

    async registerServiceWorker() {
        if ('serviceWorker' in navigator) {
            try {
                const registration = await navigator.serviceWorker.register('/static/sw.js');
                console.log('Service Worker registered successfully:', registration.scope);
                
                // Update available
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
        // Listen for install prompt
        window.addEventListener('beforeinstallprompt', (e) => {
            console.log('Install prompt available');
            e.preventDefault();
            this.deferredPrompt = e;
            this.showInstallButton();
        });

        // Handle successful installation
        window.addEventListener('appinstalled', () => {
            console.log('PWA was installed');
            this.deferredPrompt = null;
            this.hideInstallButton();
            this.showInstallSuccess();
        });
    }

    checkInstallStatus() {
        // Check if app is running in standalone mode
        if (window.matchMedia('(display-mode: standalone)').matches || 
            window.navigator.standalone === true) {
            this.isInstalled = true;
            this.hideInstallButton();
        }
    }

    async promptInstall() {
        if (!this.deferredPrompt) {
            this.showInstallInstructions();
            return;
        }

        // Show install prompt
        this.deferredPrompt.prompt();
        
        // Wait for user response
        const { outcome } = await this.deferredPrompt.userChoice;
        console.log(`User response to install prompt: ${outcome}`);
        
        // Reset deferred prompt
        this.deferredPrompt = null;
        this.hideInstallButton();
    }

    showInstallButton() {
        const installBtn = document.getElementById('pwa-install-btn');
        if (installBtn) {
            installBtn.style.display = 'block';
            installBtn.addEventListener('click', () => this.promptInstall());
        }
    }

    hideInstallButton() {
        const installBtn = document.getElementById('pwa-install-btn');
        if (installBtn) {
            installBtn.style.display = 'none';
        }
    }

    showInstallInstructions() {
        // Show platform-specific install instructions
        const userAgent = navigator.userAgent.toLowerCase();
        let instructions = '';

        if (/iphone|ipad|ipod/.test(userAgent)) {
            instructions = 'To install: Tap the share button and select "Add to Home Screen"';
        } else if (/android/.test(userAgent)) {
            instructions = 'To install: Tap the menu button and select "Add to Home Screen" or "Install App"';
        } else {
            instructions = 'To install: Look for the install button in your browser\'s address bar';
        }

        this.showToast(instructions, 'info', 5000);
    }

    showInstallSuccess() {
        this.showToast('OpenSell has been installed successfully!', 'success');
    }

    showUpdateAvailable() {
        this.showToast('A new version is available. Refresh to update.', 'info', 0, () => {
            window.location.reload();
        });
    }

    showToast(message, type = 'info', duration = 3000, action = null) {
        // Create toast notification
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

        // Show toast
        setTimeout(() => toast.classList.add('pwa-toast-show'), 100);

        // Auto hide
        if (duration > 0) {
            setTimeout(() => this.hideToast(toast), duration);
        }

        // Handle close button
        toast.querySelector('.pwa-toast-close').addEventListener('click', () => {
            this.hideToast(toast);
        });

        // Handle action button
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
        // Add offline/online indicators
        window.addEventListener('online', () => {
            this.showToast('You are back online!', 'success');
        });

        window.addEventListener('offline', () => {
            this.showToast('You are currently offline. Some features may be limited.', 'warning', 5000);
        });
    }
}

// Initialize PWA when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new PWAManager();
});