/**
 * PWA Installation Instructions Manager - Updated Version
 */
class PWAInstallInstructions {
    constructor() {
        this.modal = null;
        this.isInstalled = false;
        this.isPWAInstalledInBrowser = false;
        this.userAgent = navigator.userAgent.toLowerCase();
        this.platform = this.detectPlatform();
        this.browser = this.detectBrowser();
        this.deferredPrompt = null;
        
        // Show interval: twice a day (12 hours)
        this.showInterval = 12 * 60 * 60 * 1000; // 12 hours in milliseconds
        
        this.init();
    }

    init() {
        this.checkPWAStatus();
        this.createModalHTML();
        this.setupEventListeners();
        this.scheduleModalDisplay();
        
        // Listen for beforeinstallprompt
        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            this.deferredPrompt = e;
        });
        
        // Listen for app installation
        window.addEventListener('appinstalled', () => {
            this.isInstalled = true;
            this.hideModal();
            this.clearScheduledDisplays();
        });
    }

    detectPlatform() {
        if (/iphone|ipad|ipod/.test(this.userAgent)) {
            return 'ios';
        } else if (/android/.test(this.userAgent)) {
            return 'android';
        } else if (/win/.test(this.userAgent)) {
            return 'windows';
        } else if (/mac/.test(this.userAgent)) {
            return 'mac';
        } else if (/linux/.test(this.userAgent)) {
            return 'linux';
        }
        return 'unknown';
    }

    detectBrowser() {
        if (/chrome|chromium|crios/.test(this.userAgent) && !/edge|edg/.test(this.userAgent)) {
            return 'chrome';
        } else if (/firefox|fxios/.test(this.userAgent)) {
            return 'firefox';
        } else if (/safari/.test(this.userAgent) && !/chrome|chromium|crios/.test(this.userAgent)) {
            return 'safari';
        } else if (/edge|edg/.test(this.userAgent)) {
            return 'edge';
        } else if (/opera|opr/.test(this.userAgent)) {
            return 'opera';
        }
        return 'unknown';
    }

    checkPWAStatus() {
        // Check if running in PWA mode
        if (window.matchMedia('(display-mode: standalone)').matches || 
            window.navigator.standalone === true) {
            this.isInstalled = true;
            return;
        }
        
        // Additional check for installed PWA in browser
        this.checkIfPWAInstalled();
    }
    
    checkIfPWAInstalled() {
        // Check if PWA is installed by looking for related applications
        if ('getInstalledRelatedApps' in navigator) {
            navigator.getInstalledRelatedApps().then(relatedApps => {
                if (relatedApps.length > 0) {
                    this.isInstalled = true;
                    this.isPWAInstalledInBrowser = true;
                }
            }).catch(() => {
                // Fallback detection methods
                this.fallbackInstallCheck();
            });
        } else {
            this.fallbackInstallCheck();
        }
    }
    
    fallbackInstallCheck() {
        // Check localStorage for install tracking
        const installTime = localStorage.getItem('pwa_install_time');
        if (installTime && (Date.now() - parseInt(installTime)) < (30 * 24 * 60 * 60 * 1000)) {
            // Consider installed if marked as installed within last 30 days
            this.isPWAInstalledInBrowser = true;
        }
    }

    createModalHTML() {
        // Don't create modal if running in PWA mode
        if (this.isInstalled && !this.isPWAInstalledInBrowser) {
            return;
        }
        
        // Check if modal already exists
        if (document.getElementById('pwaInstallModal')) {
            this.modal = document.getElementById('pwaInstallModal');
            return;
        }

        // Conditionally include actions for non-iOS platforms
        const actionsHTML = this.platform !== 'ios' ? `
            <div class="pwa-install-actions" id="pwaInstallActions">
                <button type="button" class="pwa-install-btn" id="pwaDirectInstall">
                    <i class="bi bi-download"></i>
                    Install Now
                </button>
                <button type="button" class="pwa-later-btn" id="pwaLaterBtn">
                    Maybe Later
                </button>
            </div>
        ` : '';

        // Create modal HTML (using the template structure)
        const modalHTML = `
            <div class="pwa-install-modal" id="pwaInstallModal" aria-hidden="true" role="dialog">
                <div class="pwa-install-modal-content">
                    <div class="pwa-install-modal-header">
                        <h3 class="pwa-install-modal-title">
                            <i class="bi bi-download"></i>
                            Install OpenSell App
                        </h3>
                        <button type="button" class="pwa-install-modal-close" id="pwaModalClose" aria-label="Close">
                            <i class="bi bi-x"></i>
                        </button>
                    </div>
                    
                    <div class="pwa-install-modal-body">
                        <div class="pwa-install-intro">
                            <p>Get the full OpenSell experience with our app! Enjoy faster loading, offline access, and seamless shopping.</p>
                        </div>
                        
                        <div id="installStepsContainer"></div>

                        ${actionsHTML}

                        <div class="pwa-reminder-settings">
                            <label class="pwa-reminder-checkbox">
                                <input type="checkbox" id="pwaNoReminder"> 
                                Don't show this again today
                            </label>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.modal = document.getElementById('pwaInstallModal');
        this.renderInstructions();
    }

    renderInstructions() {
        const container = document.getElementById('installStepsContainer');
        const instructions = this.getInstructionsForPlatform();
        
        container.innerHTML = instructions;
    }

    getInstructionsForPlatform() {
        // For iOS, always show Safari instructions (simplified)
        if (this.platform === 'ios') {
            return this.getIOSInstructions();
        }
        
        // For Windows and Android, show platform-specific but simplified instructions
        if (this.platform === 'windows') {
            return this.getWindowsInstructions();
        }
        
        if (this.platform === 'android') {
            return this.getAndroidInstructions();
        }
        
        return this.getGenericInstructions();
    }

    getIOSInstructions() {
        return `
            <div class="pwa-install-steps">
                <div class="pwa-install-section-title">
                    <div class="browser-icon safari"></div>
                    Add to iPhone Home Screen
                </div>
                <div class="pwa-step">
                    <div class="pwa-step-number">1</div>
                    <div class="pwa-step-content">
                        <p class="pwa-step-text">Tap the Share button</p>
                        <div class="pwa-step-icon">
                            <i class="bi bi-box-arrow-up"></i> Share
                        </div>
                    </div>
                </div>
                <div class="pwa-step">
                    <div class="pwa-step-number">2</div>
                    <div class="pwa-step-content">
                        <p class="pwa-step-text">Select "Add to Home Screen"</p>
                        <div class="pwa-step-icon">
                            <i class="bi bi-plus-square-fill"></i> Add to Home Screen
                        </div>
                    </div>
                </div>
                <div class="pwa-step">
                    <div class="pwa-step-number">3</div>
                    <div class="pwa-step-content">
                        <p class="pwa-step-text">Tap "Add" to finish</p>
                        <div class="pwa-step-icon">
                            <i class="bi bi-check-circle-fill"></i> Add
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    getWindowsInstructions() {
        return `
            <div class="pwa-install-steps">
                <div class="pwa-install-section-title">
                    <i class="bi bi-windows"></i>
                    Install on Windows
                </div>
                <div class="pwa-step">
                    <div class="pwa-step-number">1</div>
                    <div class="pwa-step-content">
                        <p class="pwa-step-text">Click "Install Now" button below</p>
                        <div class="pwa-step-icon">
                            <i class="bi bi-download"></i> Install Now
                        </div>
                    </div>
                </div>
                <div class="pwa-step">
                    <div class="pwa-step-number">2</div>
                    <div class="pwa-step-content">
                        <p class="pwa-step-text">If browser doesn't support, look for install icon in address bar</p>
                        <div class="pwa-step-icon">
                            <i class="bi bi-app-indicator"></i> Install
                        </div>
                    </div>
                </div>
                <div class="pwa-step">
                    <div class="pwa-step-number">3</div>
                    <div class="pwa-step-content">
                        <p class="pwa-step-text">Or use browser menu → "Install App"</p>
                        <div class="pwa-step-icon">
                            <i class="bi bi-three-dots"></i> Menu
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    getAndroidInstructions() {
        return `
            <div class="pwa-install-steps">
                <div class="pwa-install-section-title">
                    <i class="bi bi-android2"></i>
                    Install on Android
                </div>
                <div class="pwa-step">
                    <div class="pwa-step-number">1</div>
                    <div class="pwa-step-content">
                        <p class="pwa-step-text">Tap "Install Now" button below</p>
                        <div class="pwa-step-icon">
                            <i class="bi bi-download"></i> Install Now
                        </div>
                    </div>
                </div>
                <div class="pwa-step">
                    <div class="pwa-step-number">2</div>
                    <div class="pwa-step-content">
                        <p class="pwa-step-text">If browser doesn't support, use menu (⋮)</p>
                        <div class="pwa-step-icon">
                            <i class="bi bi-three-dots-vertical"></i> Menu
                        </div>
                    </div>
                </div>
                <div class="pwa-step">
                    <div class="pwa-step-number">3</div>
                    <div class="pwa-step-content">
                        <p class="pwa-step-text">Select "Add to Home screen" or "Install app"</p>
                        <div class="pwa-step-icon">
                            <i class="bi bi-house-add-fill"></i> Add to Home screen
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    getGenericInstructions() {
        return `
            <div class="pwa-install-steps">
                <div class="pwa-install-section-title">
                    <i class="bi bi-download"></i>
                    Install Instructions
                </div>
                <div class="pwa-step">
                    <div class="pwa-step-number">1</div>
                    <div class="pwa-step-content">
                        <p class="pwa-step-text">Look for an "Install" or "Add to Home Screen" option in your browser menu</p>
                    </div>
                </div>
                <div class="pwa-step">
                    <div class="pwa-step-number">2</div>
                    <div class="pwa-step-content">
                        <p class="pwa-step-text">Check the address bar for an install button or app icon</p>
                    </div>
                </div>
                <div class="pwa-step">
                    <div class="pwa-step-number">3</div>
                    <div class="pwa-step-content">
                        <p class="pwa-step-text">Use the "Install App" button in our footer or navbar</p>
                    </div>
                </div>
            </div>
        `;
    }

    setupEventListeners() {
        // Close modal
        const closeBtn = document.getElementById('pwaModalClose');
        const laterBtn = document.getElementById('pwaLaterBtn');
        
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.hideModal());
        }
        
        if (laterBtn) {
            laterBtn.addEventListener('click', () => this.handleLater());
        }

        // Direct install button
        const installBtn = document.getElementById('pwaDirectInstall');
        if (installBtn) {
            installBtn.addEventListener('click', () => this.handleDirectInstall());
        }

        // Close on outside click
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.hideModal();
            }
        });

        // Escape key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.classList.contains('show')) {
                this.hideModal();
            }
        });
    }

    scheduleModalDisplay() {
        // Don't show if running in PWA mode or if installed
        if (this.isInstalled && !this.isPWAInstalledInBrowser) return;

        const now = Date.now();
        const lastShown = this.getLastShownTime();
        const noReminderUntil = this.getNoReminderTime();

        // Don't show if user said no reminder for today
        if (noReminderUntil && now < noReminderUntil) {
            return;
        }

        // Show if never shown or if interval has passed
        if (!lastShown || (now - lastShown) >= this.showInterval) {
            // Show after a short delay to let page load
            setTimeout(() => {
                this.showModal();
            }, 2000);
        }
    }

    showModal() {
        // Don't show if running in PWA mode
        if (this.isInstalled && !this.isPWAInstalledInBrowser) return;
        if (!this.modal) return;

        // Update install button state (except for iOS)
        if (this.platform !== 'ios') {
            this.updateInstallButton();
        }
        
        this.modal.classList.add('show');
        this.modal.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
        
        // Record when modal was shown
        this.setLastShownTime(Date.now());
        
        // Track analytics if available
        if (typeof gtag !== 'undefined') {
            gtag('event', 'pwa_install_modal_shown', {
                platform: this.platform,
                browser: this.browser,
                already_installed: this.isPWAInstalledInBrowser
            });
        }
    }

    hideModal() {
        if (!this.modal) return;

        this.modal.classList.add('fade-out');
        
        setTimeout(() => {
            this.modal.classList.remove('show', 'fade-out');
            this.modal.setAttribute('aria-hidden', 'true');
            document.body.style.overflow = '';
        }, 300);
    }

    handleLater() {
        const noReminderCheckbox = document.getElementById('pwaNoReminder');
        
        if (noReminderCheckbox && noReminderCheckbox.checked) {
            // Don't show again today (24 hours)
            const tomorrow = Date.now() + (24 * 60 * 60 * 1000);
            this.setNoReminderTime(tomorrow);
        }
        
        this.hideModal();
        
        // Track analytics
        if (typeof gtag !== 'undefined') {
            gtag('event', 'pwa_install_later', {
                no_reminder: noReminderCheckbox ? noReminderCheckbox.checked : false
            });
        }
    }

    async handleDirectInstall() {
        try {
            // If PWA is already installed in browser, try to open it
            if (this.isPWAInstalledInBrowser) {
                this.openInstalledPWA();
                return;
            }
            
            // For iOS, just show the manual instructions
            if (this.platform === 'ios') {
                this.showManualInstructions();
                this.trackInstallAttempt('ios_manual_guide');
                return;
            }

            // For Windows and Android, try native install first
            if (this.deferredPrompt) {
                // Use native install prompt
                this.deferredPrompt.prompt();
                const { outcome } = await this.deferredPrompt.userChoice;
                
                if (outcome === 'accepted') {
                    this.isInstalled = true;
                    this.hideModal();
                    this.clearScheduledDisplays();
                    // Mark as installed in localStorage
                    localStorage.setItem('pwa_install_time', Date.now().toString());
                }
                
                this.deferredPrompt = null;
                this.trackInstallAttempt('native_prompt', outcome);
            } else {
                // Fallback for Windows/Android without native support
                this.attemptUniversalInstall();
            }
        } catch (error) {
            console.error('Install failed:', error);
            this.attemptUniversalInstall();
        }
    }
    
    openInstalledPWA() {
        // Try to open the installed PWA
        const installBtn = document.getElementById('pwaDirectInstall');
        if (installBtn) {
            installBtn.innerHTML = '<i class="bi bi-check-circle"></i> Opening App...';
            installBtn.disabled = true;
        }
        
        // Try various methods to open the installed PWA
        try {
            // Method 1: Try to navigate to the PWA start_url
            window.open(window.location.origin, '_blank');
            
            setTimeout(() => {
                this.hideModal();
                this.showToast('App should open in a separate window', 'success');
            }, 1000);
        } catch (error) {
            // Fallback: Show message about finding the app
            this.showToast('OpenSell App is already installed. Look for it on your home screen or in your apps menu.', 'info', 5000);
            this.hideModal();
        }
        
        this.trackInstallAttempt('open_installed_app');
    }
    
    showToast(message, type = 'info', duration = 3000) {
        // Simple toast notification
        const toast = document.createElement('div');
        toast.className = `pwa-toast pwa-toast-${type}`;
        toast.innerHTML = `
            <div class="pwa-toast-content">
                <span>${message}</span>
                <button class="pwa-toast-close">&times;</button>
            </div>
        `;
        
        // Add toast styles if not present
        if (!document.querySelector('#pwa-toast-styles')) {
            const toastStyles = document.createElement('style');
            toastStyles.id = 'pwa-toast-styles';
            toastStyles.textContent = `
                .pwa-toast {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: var(--card-background);
                    border: 1px solid var(--border-color);
                    border-radius: var(--radius-md);
                    padding: 1rem;
                    z-index: 10000;
                    max-width: 400px;
                    opacity: 0;
                    transform: translateX(100px);
                    transition: all 0.3s ease;
                }
                .pwa-toast.pwa-toast-show { opacity: 1; transform: translateX(0); }
                .pwa-toast-success { border-left: 4px solid #28a745; }
                .pwa-toast-info { border-left: 4px solid #007bff; }
                .pwa-toast-content { display: flex; justify-content: space-between; align-items: center; }
                .pwa-toast-close { background: none; border: none; cursor: pointer; font-size: 1.2rem; }
            `;
            document.head.appendChild(toastStyles);
        }

        document.body.appendChild(toast);
        setTimeout(() => toast.classList.add('pwa-toast-show'), 100);

        if (duration > 0) {
            setTimeout(() => this.hideToast(toast), duration);
        }

        toast.querySelector('.pwa-toast-close').addEventListener('click', () => {
            this.hideToast(toast);
        });
    }
    
    hideToast(toast) {
        toast.classList.remove('pwa-toast-show');
        setTimeout(() => toast.remove(), 300);
    }

    attemptUniversalInstall() {
        // Universal install attempt for Windows/Android
        if (this.platform === 'windows' || this.platform === 'android') {
            // Try to trigger browser's install mechanism
            this.showInstallHint();
            this.trackInstallAttempt('universal_attempt');
        } else {
            this.showManualInstructions();
            this.trackInstallAttempt('manual_fallback');
        }
    }

    showInstallHint() {
        // Show visual hint for where to find install options
        const installBtn = document.getElementById('pwaDirectInstall');
        if (installBtn) {
            // Change button text temporarily
            const originalText = installBtn.innerHTML;
            installBtn.innerHTML = '<i class="bi bi-arrow-up"></i> Check browser menu or address bar';
            installBtn.style.background = '#28a745';
            
            // Highlight the instruction steps
            this.showManualInstructions();
            
            // Reset button after 3 seconds
            setTimeout(() => {
                installBtn.innerHTML = originalText;
                installBtn.style.background = '';
            }, 3000);
        }
    }

    showManualInstructions() {
        // Highlight the instruction steps
        const steps = this.modal.querySelectorAll('.pwa-step');
        steps.forEach((step, index) => {
            setTimeout(() => {
                step.style.background = 'var(--primary-color)';
                step.style.color = 'white';
                step.style.transform = 'scale(1.02)';
                step.style.transition = 'all 0.3s ease';
                
                setTimeout(() => {
                    step.style.background = '';
                    step.style.color = '';
                    step.style.transform = '';
                }, 1000);
            }, index * 300);
        });
    }

    updateInstallButton() {
        const installBtn = document.getElementById('pwaDirectInstall');
        if (!installBtn) return;

        // For iOS, don't update button since it's hidden
        if (this.platform === 'ios') {
            return;
        }

        // If PWA is already installed, show "Open App" button
        if (this.isPWAInstalledInBrowser) {
            installBtn.disabled = false;
            installBtn.innerHTML = '<i class="bi bi-box-arrow-up-right"></i> Open in App';
            installBtn.style.background = '#28a745'; // Green color
            return;
        }

        // Always enable install button for Windows and Android
        if (this.platform === 'windows' || this.platform === 'android') {
            installBtn.disabled = false;
            installBtn.innerHTML = '<i class="bi bi-download"></i> Install Now';
        }
        // For other platforms
        else {
            installBtn.disabled = false;
            installBtn.innerHTML = '<i class="bi bi-download"></i> Install Now';
        }
    }

    trackInstallAttempt(method, outcome = null) {
        if (typeof gtag !== 'undefined') {
            gtag('event', 'pwa_install_attempted', {
                method: method,
                platform: this.platform,
                browser: this.browser,
                outcome: outcome
            });
        }
    }

    // Storage helpers
    getLastShownTime() {
        try {
            return parseInt(localStorage.getItem('pwa_modal_last_shown')) || null;
        } catch (e) {
            return null;
        }
    }

    setLastShownTime(time) {
        try {
            localStorage.setItem('pwa_modal_last_shown', time.toString());
        } catch (e) {
            // Ignore storage errors
        }
    }

    getNoReminderTime() {
        try {
            return parseInt(localStorage.getItem('pwa_no_reminder_until')) || null;
        } catch (e) {
            return null;
        }
    }

    setNoReminderTime(time) {
        try {
            localStorage.setItem('pwa_no_reminder_until', time.toString());
        } catch (e) {
            // Ignore storage errors
        }
    }

    clearScheduledDisplays() {
        try {
            localStorage.removeItem('pwa_modal_last_shown');
            localStorage.removeItem('pwa_no_reminder_until');
        } catch (e) {
            // Ignore storage errors
        }
    }

    // Public methods for manual triggering
    show() {
        this.showModal();
    }

    hide() {
        this.hideModal();
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Don't initialize if running in PWA mode (standalone)
    if (window.matchMedia('(display-mode: standalone)').matches || 
        window.navigator.standalone === true) {
        return;
    }
    
    // Only initialize in browser context
    window.pwaInstallInstructions = new PWAInstallInstructions();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PWAInstallInstructions;
}