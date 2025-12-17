/**
 * Alert System - Handles system notifications and alerts
 */

// Initialize alert system - ONLY after everything is loaded
function initializeAlertSystem() {
    const alertContainer = document.getElementById('alertSystemContainer');
    if (!alertContainer) return;
    
    const alerts = alertContainer.querySelectorAll('.system-alert');
    
    // CRITICAL FIX: Wait for navbar to be fully rendered
    // Use requestAnimationFrame to ensure layout is complete
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            updateAlertContainerPosition();
        });
    });
    
    // Handle each alert
    alerts.forEach((alert, index) => {
        setupAlert(alert, index);
    });
    
    // Update position on window resize with debouncing
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(updateAlertContainerPosition, 150);
    });
}

function updateAlertContainerPosition() {
    const alertContainer = document.getElementById('alertSystemContainer');
    if (!alertContainer) return;
    
    // Get actual navbar height - with fallback
    const navbar = document.getElementById('mainNavbar');
    if (navbar) {
        // Force reflow to ensure accurate measurement
        void navbar.offsetHeight;
        const navbarHeight = navbar.getBoundingClientRect().height;
        
        // Only update if we have a valid height
        if (navbarHeight > 0) {
            alertContainer.style.paddingTop = `${navbarHeight + 8}px`;
        }
    }
}

function setupAlert(alert, index) {
    if (alert.hasAttribute('data-persist') || alert.hasAttribute('data-no-auto-dismiss')) {
        return;
    }
    
    const autoDismissTime = parseInt(alert.dataset.autoDismiss) || 3500;
    
    const closeBtn = alert.querySelector('.alert-close-btn');
    if (closeBtn) {
        closeBtn.addEventListener('click', function(e) {
            e.preventDefault();
            dismissAlert(alert);
        });
    }
    
    setTimeout(() => {
        dismissAlert(alert);
    }, autoDismissTime);
    
    alert.addEventListener('click', function(e) {
        if (e.target === alert || e.target.closest('.alert-content')) {
            dismissAlert(alert);
        }
    });
}

function dismissAlert(alert) {
    if (!alert || alert.classList.contains('fade-out')) return;
    
    alert.classList.add('fade-out');
    
    setTimeout(() => {
        if (alert.parentNode) {
            alert.remove();
        }
        
        const container = document.getElementById('alertSystemContainer');
        if (container && container.children.length === 0) {
            container.remove();
        }
    }, 300);
}

function showSystemAlert(message, type = 'info', duration = 3500) {
    let container = document.getElementById('alertSystemContainer');
    
    if (!container) {
        container = document.createElement('div');
        container.id = 'alertSystemContainer';
        container.className = 'alert-system-container';
        document.body.appendChild(container);
        
        // Update position after container is added
        requestAnimationFrame(() => {
            updateAlertContainerPosition();
        });
    }
    
    const alert = document.createElement('div');
    alert.className = `system-alert alert-${type}`;
    alert.setAttribute('role', 'alert');
    alert.setAttribute('data-auto-dismiss', duration.toString());
    
    const icons = {
        success: 'bi-check-circle-fill',
        error: 'bi-exclamation-circle-fill',
        danger: 'bi-exclamation-circle-fill',
        warning: 'bi-exclamation-triangle-fill',
        info: 'bi-info-circle-fill'
    };
    
    alert.innerHTML = `
        <div class="alert-content">
            <div class="alert-icon">
                <i class="bi ${icons[type] || icons.info}"></i>
            </div>
            <div class="alert-message">${message}</div>
        </div>
        <button type="button" class="alert-close-btn" aria-label="Close">
            <i class="bi bi-x"></i>
        </button>
    `;
    
    container.appendChild(alert);
    setupAlert(alert, container.children.length - 1);
    
    return alert;
}

function setupModernAlerts() {
    const alerts = document.querySelectorAll('.alert');
    
    alerts.forEach(alert => {
        const closeBtn = alert.querySelector('.btn-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', function() {
                dismissLegacyAlert(alert);
            });
        }
        
        setTimeout(() => {
            dismissLegacyAlert(alert);
        }, 2000);
    });
}

function dismissLegacyAlert(alert) {
    if (!alert.classList.contains('fade-out')) {
        alert.classList.add('fade-out');
        setTimeout(() => {
            alert.remove();
        }, 300);
    }
}

// CRITICAL FIX: Initialize ONLY after full page load
// This prevents layout shifts during initial render
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        // Add extra delay to ensure CSS is applied
        requestAnimationFrame(() => {
            initializeAlertSystem();
            setupModernAlerts();
        });
    });
} else {
    // If script loads after DOMContentLoaded
    requestAnimationFrame(() => {
        initializeAlertSystem();
        setupModernAlerts();
    });
}

window.showSystemAlert = showSystemAlert;
window.dismissAlert = dismissAlert;

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initializeAlertSystem,
        showSystemAlert,
        dismissAlert,
        setupModernAlerts
    };
}