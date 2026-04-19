/**
 * PWA Installation Instructions Manager - Syntax Error Free Version
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
        console.log('PWA Install Instructions initializing...');
        console.log('User Agent:', this.userAgent);
        console.log('Detected Platform:', this.platform);
        console.log('Detected Browser:', this.browser);
        
        this.checkPWAStatus();
        this.createModalHTML();
        this.setupEventListeners();
        this.scheduleModalDisplay();
        
        // Listen for beforeinstallprompt
        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            this.deferredPrompt = e;
            console.log('beforeinstallprompt event captured');
        });
        
        // Listen for app installation
        window.addEventListener('appinstalled', () => {
            this.isInstalled = true;
            this.hideModal();
            this.clearScheduledDisplays();
            console.log('App installed successfully');
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
            console.log('Running in PWA mode');
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
                    console.log('PWA detected as installed in browser');
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
            console.log('PWA marked as recently installed');
        }
    }

    createModalHTML() {
        // Don't create modal if running in PWA mode
        if (this.isInstalled && !this.isPWAInstalledInBrowser) {
            console.log('Skipping modal creation - running in PWA mode');
            return;
        }
        
        // Check if modal already exists (from template)
        const existingModal = document.getElementById('pwaInstallModal');
        if (existingModal) {
            console.log('Found existing modal from template');
            this.modal = existingModal;
            this.modifyExistingModal();
            return;
        }

        console.log('Creating modal dynamically for platform:', this.platform);

        // Create modal HTML dynamically (fallback if template not included)
        let actionsHTML = '';
        if (this.platform !== 'ios') {
            actionsHTML = `
            <div class="pwa-install-actions" id="pwaInstallActions">
                <button type="button" class="pwa-install-btn" id="pwaDirectInstall">
                    <i class="bi bi-download"></i>
                    Install Now
                </button>
                <button type="button" class="pwa-later-btn" id="pwaLaterBtn">
                    Maybe Later
                </button>
            </div>`;
        }

        const iosClass = this.platform === 'ios' ? 'ios-mode' : '';
        
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
                    
                    <div class="pwa-install-modal-body ${iosClass}">
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
            </div>`;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.modal = document.getElementById('pwaInstallModal');
        this.renderInstructions();
    }

    modifyExistingModal() {
        if (!this.modal) {
            console.error('No modal found to modify');
            return;
        }
        
        console.log('Modifying existing modal for platform:', this.platform);
        
        const modalBody = this.modal.querySelector('.pwa-install-modal-body');
        const installActions = this.modal.querySelector('#pwaInstallActions');
        
        // Apply platform-specific modifications
        if (this.platform === 'ios') {
            console.log('Applying iOS-specific modifications');
            
            // Hide install actions for iOS
            if (installActions) {
                installActions.classList.add('ios-hidden');
                installActions.style.display = 'none';
                console.log('Hidden install actions for iOS');
            }
            
            // Add iOS mode class to modal body
            if (modalBody) {
                modalBody.classList.add('ios-mode');
                console.log('Added iOS mode class to modal body');
            }
        } else {
            console.log('Applying non-iOS modifications for:', this.platform);
            
            // Ensure install actions are visible for non-iOS platforms
            if (installActions) {
                installActions.classList.remove('ios-hidden');
                installActions.style.display = 'flex';
                console.log('Showing install actions for', this.platform);
            }
            
            // Remove iOS mode class if present
            if (modalBody) {
                modalBody.classList.remove('ios-mode');
            }
        }
        
        // Always render instructions for the detected platform
        this.renderInstructions();
    }

    renderInstructions() {
        const container = document.getElementById('installStepsContainer');
        if (!container) {
            console.error('Install steps container not found');
            return;
        }
        
        const instructions = this.getInstructionsForPlatform();
        container.innerHTML = instructions;
        console.log('Rendered instructions for platform:', this.platform);
    }

    getInstructionsForPlatform() {
        console.log('Getting instructions for platform:', this.platform);
        
        // For iOS, always show Safari instructions
        if (this.platform === 'ios') {
            return this.getIOSInstructions();
        }
        
        // For Windows and Android, show platform-specific instructions
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
            <div class="pwa-install-steps" id="iosInstructions">
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
            </div>`;
    }

    getWindowsInstructions() {
        return `
            <div class="pwa-install-steps" id="windowsInstructions">
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
            </div>`;
    }

    getAndroidInstructions() {
        return `
            <div class="pwa-install-steps" id="androidInstructions">
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
            </div>`;
    }

    getGenericInstructions() {
        return `
            <div class="pwa-install-steps" id="genericInstructions">
                <div class="pwa-install-section-title">
                    <i class="bi bi-download"></i>
                    Install Instructions
                </div>
                <div class="pwa-step">
                    <div class="pwa-step-number">1</div>
                    <div class="pwa-step-content">
                        <p class="pwa-step-text">Look for an "Install" or "Add to Home Screen" option in your browser menu</p>
                        <div class="pwa-step-icon">
                            <i class="bi bi-search"></i> Find Install Option
                        </div>
                    </div>
                </div>
                <div class="pwa-step">
                    <div class="pwa-step-number">2</div>
                    <div class="pwa-step-content">
                        <p class="pwa-step-text">Check the address bar for an install button or app icon</p>
                        <div class="pwa-step-icon">
                            <i class="bi bi-app-indicator"></i> Address Bar
                        </div>
                    </div>
                </div>
                <div class="pwa-step">
                    <div class="pwa-step-number">3</div>
                    <div class="pwa-step-content">
                        <p class="pwa-step-text">Use the "Install App" button in our footer or navbar</p>
                        <div class="pwa-step-icon">
                            <i class="bi bi-layout-text-sidebar-reverse"></i> Footer/Navbar
                        </div>
                    </div>
                </div>
            </div>`;
    }

    setupEventListeners() {
        if (!this.modal) {
            console.error('Cannot setup event listeners - modal not found');
            return;
        }

        // Close modal
        const closeBtn = this.modal.querySelector('#pwaModalClose');
        const laterBtn = this.modal.querySelector('#pwaLaterBtn');
        
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                console.log('Close button clicked');
                this.hideModal();
            });
        }
        
        if (laterBtn) {
            laterBtn.addEventListener('click', () => {
                console.log('Later button clicked');
                this.handleLater();
            });
        }

        // Direct install button (only for non-iOS)
        const installBtn = this.modal.querySelector('#pwaDirectInstall');
        if (installBtn && this.platform !== 'ios') {
            installBtn.addEventListener('click', () => {
                console.log('Install button clicked');
                this.handleDirectInstall();
            });
        }

        // Close on outside click
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                console.log('Outside click detected');
                this.hideModal();
            }
        });

        // Escape key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.classList.contains('show')) {
                console.log('Escape key pressed');
                this.hideModal();
            }
        });

        console.log('Event listeners setup complete');
    }

    scheduleModalDisplay() {
        // Don't show if running in PWA mode or if installed
        if (this.isInstalled && !this.isPWAInstalledInBrowser) {
            console.log('Skipping modal display - PWA already installed');
            return;
        }

        const now = Date.now();
        const lastShown = this.getLastShownTime();
        const noReminderUntil = this.getNoReminderTime();

        console.log('Scheduling modal display check...');
        console.log('Last shown:', lastShown ? new Date(lastShown) : 'Never');
        console.log('No reminder until:', noReminderUntil ? new Date(noReminderUntil) : 'Not set');

        // Don't show if user said no reminder for today
        if (noReminderUntil && now < noReminderUntil) {
            console.log('User requested no reminders until', new Date(noReminderUntil));
            return;
        }

        // Show if never shown or if interval has passed
        if (!lastShown || (now - lastShown) >= this.showInterval) {
            console.log('Scheduling modal to show in 2 seconds');
            // Show after a short delay to let page load
            setTimeout(() => {
                this.showModal();
            }, 2000);
        } else {
            const timeRemaining = this.showInterval - (now - lastShown);
            console.log('Next modal show scheduled in', Math.round(timeRemaining / (60 * 60 * 1000)), 'hours');
        }
    }

    showModal() {
        // Don't show if running in PWA mode
        if (this.isInstalled && !this.isPWAInstalledInBrowser) {
            console.log('Skipping modal show - running in PWA mode');
            return;
        }
        
        if (!this.modal) {
            console.error('Cannot show modal - modal not found');
            return;
        }

        console.log('Showing PWA install modal for platform:', this.platform);

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
        if (!this.modal) {
            console.error('Cannot hide modal - modal not found');
            return;
        }

        console.log('Hiding PWA install modal');
        this.modal.classList.add('fade-out');
        
        setTimeout(() => {
            this.modal.classList.remove('show', 'fade-out');
            this.modal.setAttribute('aria-hidden', 'true');
            document.body.style.overflow = '';
        }, 300);
    }

    handleLater() {
        const noReminderCheckbox = this.modal.querySelector('#pwaNoReminder');
        
        if (noReminderCheckbox && noReminderCheckbox.checked) {
            // Don't show again today (24 hours)
            const tomorrow = Date.now() + (24 * 60 * 60 * 1000);
            this.setNoReminderTime(tomorrow);
            console.log('User requested no reminders until', new Date(tomorrow));
        }
        
        this.hideModal();
        
        // Track analytics
        if (typeof gtag !== 'undefined') {
            gtag('event', 'pwa_install_later', {
                no_reminder: noReminderCheckbox ? noReminderCheckbox.checked : false,
                platform: this.platform
            });
        }
    }

    async handleDirectInstall() {
        try {
            console.log('Handling direct install for platform:', this.platform);
            
            // If PWA is already installed in browser, try to open it
            if (this.isPWAInstalledInBrowser) {
                this.openInstalledPWA();
                return;
            }
            
            // For iOS, just show the manual instructions (this shouldn't happen since button is hidden)
            if (this.platform === 'ios') {
                console.log('iOS user clicked install button - this should not happen');
                this.showManualInstructions();
                this.trackInstallAttempt('ios_manual_guide');
                return;
            }

            // For Windows and Android, try native install first
            if (this.deferredPrompt) {
                console.log('Using native install prompt');
                // Use native install prompt
                this.deferredPrompt.prompt();
                const result = await this.deferredPrompt.userChoice;
                const outcome = result.outcome;
                
                console.log('Install prompt outcome:', outcome);
                
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
                console.log('No native prompt available, using fallback');
                // Fallback for Windows/Android without native support
                this.attemptUniversalInstall();
            }
        } catch (error) {
            console.error('Install failed:', error);
            this.attemptUniversalInstall();
        }
    }
    
    openInstalledPWA() {
        console.log('Attempting to open installed PWA');
        const installBtn = this.modal.querySelector('#pwaDirectInstall');
        if (installBtn) {
            installBtn.innerHTML = '<i class="bi bi-check-circle"></i> Opening App...';
            installBtn.disabled = true;
        }
        
        // Try to open the installed PWA
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
    
    showToast(message, type, duration) {
        type = type || 'info';
        duration = duration || 3000;
        
        // Use the existing alert system if available
        if (typeof showSystemAlert !== 'undefined') {
            showSystemAlert(message, type, duration);
            return;
        }
        
        console.log('Toast:', message, type);
        
        // Fallback to custom toast
        const toast = document.createElement('div');
        toast.className = 'pwa-toast pwa-toast-' + type;
        toast.innerHTML = '<div class="pwa-toast-content"><span>' + message + '</span><button class="pwa-toast-close">&times;</button></div>';
        
        // Add toast styles if not present
        if (!document.querySelector('#pwa-toast-styles')) {
            const toastStyles = document.createElement('style');
            toastStyles.id = 'pwa-toast-styles';
            toastStyles.textContent = `
                .pwa-toast {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: var(--card-background, #fff);
                    border: 1px solid var(--border-color, #ddd);
                    border-radius: var(--radius-md, 8px);
                    padding: 1rem;
                    z-index: 10000;
                    max-width: 400px;
                    opacity: 0;
                    transform: translateX(100px);
                    transition: all 0.3s ease;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                }
                .pwa-toast.pwa-toast-show { opacity: 1; transform: translateX(0); }
                .pwa-toast-success { border-left: 4px solid #28a745; }
                .pwa-toast-info { border-left: 4px solid #007bff; }
                .pwa-toast-content { display: flex; justify-content: space-between; align-items: center; }
                .pwa-toast-close { background: none; border: none; cursor: pointer; font-size: 1.2rem; margin-left: 1rem; }`;
            document.head.appendChild(toastStyles);
        }

        document.body.appendChild(toast);
        setTimeout(() => {
            toast.classList.add('pwa-toast-show');
        }, 100);

        if (duration > 0) {
            setTimeout(() => {
                this.hideToast(toast);
            }, duration);
        }

        toast.querySelector('.pwa-toast-close').addEventListener('click', () => {
            this.hideToast(toast);
        });
    }
    
    hideToast(toast) {
        toast.classList.remove('pwa-toast-show');
        setTimeout(() => {
            toast.remove();
        }, 300);
    }

    attemptUniversalInstall() {
        console.log('Attempting universal install for platform:', this.platform);
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
        console.log('Showing install hint');
        // Show visual hint for where to find install options
        const installBtn = this.modal.querySelector('#pwaDirectInstall');
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
        console.log('Highlighting manual instructions');
        // Highlight the instruction steps
        const steps = this.modal.querySelectorAll('.pwa-step');
        steps.forEach((step, index) => {
            setTimeout(() => {
                step.style.background = 'var(--primary-color, #007bff)';
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
        const installBtn = this.modal.querySelector('#pwaDirectInstall');
        if (!installBtn) return;

        console.log('Updating install button for platform:', this.platform);

        // For iOS, this method shouldn't be called since button is hidden
        if (this.platform === 'ios') {
            console.warn('updateInstallButton called for iOS - button should be hidden');
            return;
        }

        // If PWA is already installed, show "Open App" button
        if (this.isPWAInstalledInBrowser) {
            installBtn.disabled = false;
            installBtn.innerHTML = '<i class="bi bi-box-arrow-up-right"></i> Open in App';
            installBtn.style.background = '#28a745'; // Green color
            console.log('Updated button to "Open in App"');
            return;
        }

        // Always enable install button for Windows and Android
        if (this.platform === 'windows' || this.platform === 'android') {
            installBtn.disabled = false;
            installBtn.innerHTML = '<i class="bi bi-download"></i> Install Now';
            console.log('Updated button to "Install Now"');
        }
        // For other platforms
        else {
            installBtn.disabled = false;
            installBtn.innerHTML = '<i class="bi bi-download"></i> Install Now';
            console.log('Updated button to "Install Now" (generic)');
        }
    }

    trackInstallAttempt(method, outcome) {
        outcome = outcome || null;
        console.log('Tracking install attempt:', method, outcome);
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
            console.warn('Failed to save last shown time:', e);
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
            console.warn('Failed to save no reminder time:', e);
        }
    }

    clearScheduledDisplays() {
        try {
            localStorage.removeItem('pwa_modal_last_shown');
            localStorage.removeItem('pwa_no_reminder_until');
            console.log('Cleared scheduled displays');
        } catch (e) {
            console.warn('Failed to clear scheduled displays:', e);
        }
    }

    // Public methods for manual triggering
    show() {
        console.log('Manual show() called');
        this.showModal();
    }

    hide() {
        console.log('Manual hide() called');
        this.hideModal();
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, checking PWA mode...');
    
    // Don't initialize if running in PWA mode (standalone)
    if (window.matchMedia('(display-mode: standalone)').matches || 
        window.navigator.standalone === true) {
        console.log('Running in PWA mode, skipping PWA install instructions');
        return;
    }
    
    console.log('Initializing PWA Install Instructions');
    // Only initialize in browser context
    window.pwaInstallInstructions = new PWAInstallInstructions();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PWAInstallInstructions;
}