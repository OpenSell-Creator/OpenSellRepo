/**
 * Alert System - Handles system notifications and alerts
 */

// Initialize alert system
function initializeAlertSystem() {
    const alertContainer = document.getElementById('alertSystemContainer');
    if (!alertContainer) return;
    
    const alerts = alertContainer.querySelectorAll('.system-alert');
    
    // Update container position based on actual navbar height
    updateAlertContainerPosition();
    
    // Handle each alert
    alerts.forEach((alert, index) => {
        setupAlert(alert, index);
    });
    
    // Update position on window resize
    window.addEventListener('resize', updateAlertContainerPosition);
}

function updateAlertContainerPosition() {
    const alertContainer = document.getElementById('alertSystemContainer');
    if (!alertContainer) return;
    
    // Get actual navbar height
    const navbar = document.getElementById('mainNavbar');
    if (navbar) {
        const navbarHeight = navbar.offsetHeight;
        const safeAreaTop = getComputedStyle(document.documentElement).getPropertyValue('--safe-area-inset-top') || '0px';
        
        // Set dynamic top position
        alertContainer.style.paddingTop = `calc(${navbarHeight}px + ${safeAreaTop} + 0.5rem)`;
    }
}

function setupAlert(alert, index) {

    if (alert.hasAttribute('data-persist') || alert.hasAttribute('data-no-auto-dismiss')) {
        return;
    }
    // Get auto-dismiss duration (default 3.5 seconds - moderate timing)
    const autoDismissTime = parseInt(alert.dataset.autoDismiss) || 3500;
    
    // Setup close button
    const closeBtn = alert.querySelector('.alert-close-btn');
    if (closeBtn) {
        closeBtn.addEventListener('click', function(e) {
            e.preventDefault();
            dismissAlert(alert);
        });
    }
    
    // Auto-dismiss after moderate time
    setTimeout(() => {
        dismissAlert(alert);
    }, autoDismissTime);
    
    // Allow click-to-dismiss on the alert itself
    alert.addEventListener('click', function(e) {
        // Only dismiss if clicking the alert body, not close button
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
        
        // Clean up container if no more alerts
        const container = document.getElementById('alertSystemContainer');
        if (container && container.children.length === 0) {
            container.remove();
        }
    }, 300);
}

// Function to create new alerts programmatically (for AJAX responses, etc.)
function showSystemAlert(message, type = 'info', duration = 3500) {
    let container = document.getElementById('alertSystemContainer');
    
    // Create container if it doesn't exist
    if (!container) {
        container = document.createElement('div');
        container.id = 'alertSystemContainer';
        container.className = 'alert-system-container';
        document.body.appendChild(container);
        updateAlertContainerPosition();
    }
    
    // Create alert element
    const alert = document.createElement('div');
    alert.className = `system-alert alert-${type}`;
    alert.setAttribute('role', 'alert');
    alert.setAttribute('data-auto-dismiss', duration.toString());
    
    // Icon mapping
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

// Legacy alert handling for Bootstrap alerts
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



// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initializeAlertSystem();
    setupModernAlerts();
});

// Make functions available globally
window.showSystemAlert = showSystemAlert;
window.dismissAlert = dismissAlert;

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initializeAlertSystem,
        showSystemAlert,
        dismissAlert,
        setupModernAlerts
    };
}