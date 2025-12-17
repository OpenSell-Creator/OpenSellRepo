// Navigation scroll behavior for mobile
function initializeNavigationScroll() {
    if (window.innerWidth < 992) {
        let lastScroll = 0;
        
        window.addEventListener('scroll', () => {
            const currentScroll = window.scrollY;
            const navbar = document.getElementById('mainNavbar');
            const bottomNav = document.getElementById('bottomNav');
            
            if (currentScroll > lastScroll && currentScroll > 100) {
                // Scrolling down
                if (navbar) navbar.style.transform = 'translateY(-100%)';
                if (bottomNav) bottomNav.style.transform = 'translateY(100%)';
            } else {
                // Scrolling up
                if (navbar) navbar.style.transform = 'translateY(0)';
                if (bottomNav) bottomNav.style.transform = 'translateY(0)';
            }
            
            lastScroll = currentScroll;
        });
    }
}

// Smooth scrolling for anchor links
function initializeSmoothScrolling() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// PWA Detection and setup
function initializePWADetection() {
    if (window.matchMedia('(display-mode: standalone)').matches || 
        window.navigator.standalone === true) {
        document.body.classList.add('pwa-mode');
    } else {
        document.body.classList.add('browser-mode');
    }

}

// Cookie consent footer interaction
function initializeCookieSettings() {
    const cookieSettingsBtn = document.getElementById('cookie-settings-footer');
    if (cookieSettingsBtn) {
        cookieSettingsBtn.addEventListener('click', function(e) {
            e.preventDefault();
            // Trigger cookie consent modal if available
            if (typeof window.showCookieConsent === 'function') {
                window.showCookieConsent();
            }
        });
    }
}

// Footer authenticated user detection
function initializeFooterAdjustments() {
    // Check if bottom nav exists and add class to body
    if (document.querySelector('.bottom-nav')) {
        document.body.classList.add('user-authenticated');
    }
}

// Tooltip initialization
function initializeTooltips() {
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
}

// Form validation helpers
function initializeFormValidation() {
    const searchForms = document.querySelectorAll('.hero-search-form, .search-form');
    searchForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const input = this.querySelector('input[name="query"]');
            if (input && !input.value.trim()) {
                e.preventDefault();
                input.focus();
            }
        });
    });
}

// Performance optimizations for touch devices
function initializeTouchOptimizations() {
    if ('ontouchstart' in window) {
        const interactiveElements = document.querySelectorAll('.btn, .category-card, .value-card');
        interactiveElements.forEach(element => {
            // Add subtle performance optimization without changing visual behavior
            element.addEventListener('touchstart', function() {
                // Minimal optimization for touch responsiveness
            }, { passive: true });
        });
    }
}

// Performance monitoring (non-visual, development only)
function initializePerformanceMonitoring() {
    if ('performance' in window && window.location.hostname.includes('localhost')) {
        window.addEventListener('load', () => {
            const perfData = performance.getEntriesByType('navigation')[0];
            if (perfData) {
                const loadTime = perfData.loadEventEnd - perfData.loadEventStart;
                if (loadTime > 3000) {
                    console.log('Page load time:', loadTime + 'ms');
                }
            }
        });
    }
}

// Initialize all navigation features
function initializeNavigation() {
    initializeNavigationScroll();
    initializeSmoothScrolling();
    initializePWADetection();
    initializeCookieSettings();
    initializeFooterAdjustments();
    initializeTooltips();
    initializeFormValidation();
    initializeTouchOptimizations();
    initializePerformanceMonitoring();
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initializeNavigation);

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initializeNavigation,
        initializeNavigationScroll,
        initializeSmoothScrolling,
        initializePWADetection,
        initializeTooltips
    };
}