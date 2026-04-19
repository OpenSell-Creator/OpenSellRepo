class PWAManager {
    constructor() {
        this.deferredPrompt = null;
        this.isInstalled = false;
        this.installInstructions = null;
        this.init();
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
        window.addEventListener('beforeinstallprompt', (e) => {
            console.log('Install prompt available');
            e.preventDefault();
            this.deferredPrompt = e;
            this.showInstallButton();
            
            // Share the prompt with install instructions modal
            if (window.pwaInstallInstructions) {
                window.pwaInstallInstructions.deferredPrompt = e;
                window.pwaInstallInstructions.updateInstallButton();
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
        // Wait for install instructions to be loaded
        if (window.pwaInstallInstructions) {
            this.installInstructions = window.pwaInstallInstructions;
            this.sharePromptWithInstructions();
        } else {
            // Wait for it to load
            setTimeout(() => {
                if (window.pwaInstallInstructions) {
                    this.installInstructions = window.pwaInstallInstructions;
                    this.sharePromptWithInstructions();
                }
            }, 1000);
        }
    }

    sharePromptWithInstructions() {
        if (this.installInstructions && this.deferredPrompt) {
            this.installInstructions.deferredPrompt = this.deferredPrompt;
            this.installInstructions.updateInstallButton();
        }
    }

    async promptInstall() {
        if (!this.deferredPrompt) {
            // Show install instructions modal instead
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
            // Mark installation time
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
}

document.addEventListener('DOMContentLoaded', () => {
    // Don't initialize PWA manager if running in PWA mode
    if (!window.matchMedia('(display-mode: standalone)').matches && 
        !window.navigator.standalone) {
        window.pwaManager = new PWAManager();
    }
});