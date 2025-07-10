// Enhanced JavaScript for product_card.html with improved UX

// Optimized CSRF token retrieval with caching
let cachedCsrfToken = null;
function getCookie(name) {
    if (cachedCsrfToken && name === 'csrftoken') {
        return cachedCsrfToken;
    }
    
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    
    if (name === 'csrftoken') {
        cachedCsrfToken = cookieValue;
    }
    
    return cookieValue;
}

// Enhanced save/unsave functionality with better UX
const saveProductDebouncer = new Map();

function toggleSaveProduct(event, productId) {
    event.preventDefault();
    event.stopPropagation();
    
    // Debounce rapid clicks
    if (saveProductDebouncer.has(productId)) {
        return;
    }
    
    const button = event.currentTarget;
    const csrfToken = getCookie('csrftoken');
    
    if (!csrfToken) {
        console.error('CSRF token not found');
        showToast('Authentication error. Please refresh the page.', 'error');
        return;
    }

    // Set debounce flag
    saveProductDebouncer.set(productId, true);
    
    // Add loading state with visual feedback
    button.classList.add('loading');
    button.style.opacity = '0.6';
    button.disabled = true;
    
    // Create loading spinner
    const originalIcon = button.querySelector('i');
    const originalClass = originalIcon.className;
    originalIcon.className = 'bi bi-arrow-clockwise';
    originalIcon.style.animation = 'spin 1s linear infinite';
    
    // Use fetch with optimized options
    fetch('/products/toggle-save/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrfToken,
        },
        body: `product_id=${productId}`,
        keepalive: true,
        cache: 'no-cache'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        // Update all instances efficiently
        const buttons = document.querySelectorAll(`[data-product-id="${productId}"]`);
        
        // Use requestAnimationFrame for smooth DOM updates
        requestAnimationFrame(() => {
            buttons.forEach(btn => {
                const icon = btn.querySelector('i');
                if (data.status === 'saved') {
                    btn.classList.add('saved');
                    btn.title = 'Remove from saved';
                    if (icon) {
                        icon.className = 'bi bi-heart-fill';
                        // Trigger heart beat animation
                        icon.style.animation = 'heartBeat 0.6s ease-in-out';
                    }
                } else if (data.status === 'removed') {
                    btn.classList.remove('saved');
                    btn.title = 'Save this product';
                    if (icon) {
                        icon.className = 'bi bi-heart';
                        icon.style.animation = '';
                    }
                }
                btn.classList.remove('loading');
                btn.style.opacity = '1';
            });
        });
        
        // Show success message with icon
        if (data.message) {
            const icon = data.status === 'saved' ? '❤️' : '💔';
            showToast(`${icon} ${data.message}`, 'success');
        }
    })
    .catch(error => {
        console.error('Error toggling save status:', error);
        
        // Restore original state on error
        requestAnimationFrame(() => {
            originalIcon.className = originalClass;
            originalIcon.style.animation = '';
            button.classList.remove('loading');
            button.style.opacity = '1';
        });
        
        // User-friendly error message
        showToast('❌ Unable to save product. Please check your connection and try again.', 'error');
    })
    .finally(() => {
        // Clear loading state and debounce
        setTimeout(() => {
            button.disabled = false;
            saveProductDebouncer.delete(productId);
            
            // Clear loading spinner
            originalIcon.className = originalClass;
            originalIcon.style.animation = '';
        }, 300);
    });
}

// Enhanced toast notification system with better UX
let toastContainer = null;
let toastQueue = [];
let isShowingToast = false;

function createToastContainer() {
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container';
        toastContainer.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 9999;
            max-width: 350px;
            pointer-events: none;
        `;
        document.body.appendChild(toastContainer);
    }
    return toastContainer;
}

function showToast(message, type = 'info') {
    // Queue toasts to prevent overlap
    toastQueue.push({ message, type });
    
    if (!isShowingToast) {
        processToastQueue();
    }
}

function processToastQueue() {
    if (toastQueue.length === 0) {
        isShowingToast = false;
        return;
    }
    
    isShowingToast = true;
    const { message, type } = toastQueue.shift();
    
    const container = createToastContainer();
    const toast = document.createElement('div');
    
    // Enhanced toast styles based on type
    const typeStyles = {
        success: 'background: linear-gradient(135deg, #28a745, #20c997); color: white; border-left: 4px solid #1e7e34;',
        error: 'background: linear-gradient(135deg, #dc3545, #c82333); color: white; border-left: 4px solid #bd2130;',
        info: 'background: linear-gradient(135deg, #17a2b8, #138496); color: white; border-left: 4px solid #117a8b;'
    };
    
    toast.className = 'save-toast';
    toast.innerHTML = message;
    toast.style.cssText = `
        ${typeStyles[type] || typeStyles.info}
        padding: 16px 20px;
        border-radius: 12px;
        margin-bottom: 12px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        opacity: 0;
        transform: translateX(100%);
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        font-size: 0.9rem;
        font-weight: 500;
        max-width: 100%;
        word-wrap: break-word;
        backdrop-filter: blur(10px);
        pointer-events: auto;
        cursor: pointer;
    `;
    
    // Click to dismiss
    toast.addEventListener('click', () => {
        dismissToast(toast);
    });
    
    container.appendChild(toast);
    
    // Animate in
    requestAnimationFrame(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateX(0)';
    });
    
    // Auto-dismiss after delay
    const dismissTimeout = setTimeout(() => {
        dismissToast(toast);
    }, 4000);
    
    // Store timeout for manual dismissal
    toast.dismissTimeout = dismissTimeout;
}

function dismissToast(toast) {
    if (toast.dismissTimeout) {
        clearTimeout(toast.dismissTimeout);
    }
    
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
        // Process next toast in queue
        setTimeout(processToastQueue, 200);
    }, 400);
}

// Enhanced tooltip initialization
function initializeTooltips() {
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    
    if (tooltipTriggerList.length > 0 && typeof bootstrap !== 'undefined') {
        const initTooltips = () => {
            tooltipTriggerList.forEach(tooltipTriggerEl => {
                try {
                    new bootstrap.Tooltip(tooltipTriggerEl, {
                        delay: { show: 600, hide: 100 },
                        placement: 'auto',
                        boundary: 'viewport'
                    });
                } catch (error) {
                    console.warn('Failed to initialize tooltip:', error);
                }
            });
        };
        
        if ('requestIdleCallback' in window) {
            requestIdleCallback(initTooltips);
        } else {
            setTimeout(initTooltips, 100);
        }
    }
}

// Enhanced intersection observer for performance
function initializeCardObserver() {
    if (!('IntersectionObserver' in window)) return;
    
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '50px 0px',
    };
    
    const cardObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const card = entry.target;
                
                // Add 'visible' class for animations
                card.classList.add('visible');
                
                // Lazy load images
                const images = card.querySelectorAll('img[data-src]');
                images.forEach(img => {
                    if (img.dataset.src) {
                        img.src = img.dataset.src;
                        img.removeAttribute('data-src');
                    }
                });
                
                // Enhanced image loading
                const productImages = card.querySelectorAll('.product-image');
                productImages.forEach(img => {
                    if (!img.complete && img.naturalHeight === 0) {
                        img.addEventListener('load', function() {
                            this.style.opacity = '1';
                        }, { once: true });
                    }
                });
                
                cardObserver.unobserve(card);
            }
        });
    }, observerOptions);
    
    // Observe all product cards
    const productCards = document.querySelectorAll('.product-card');
    productCards.forEach(card => {
        cardObserver.observe(card);
    });
}

// Enhanced keyboard navigation support
function initializeKeyboardNavigation() {
    document.addEventListener('keydown', (e) => {
        // Space or Enter key on save buttons
        if ((e.code === 'Space' || e.code === 'Enter') && e.target.classList.contains('save-button')) {
            e.preventDefault();
            const productId = e.target.getAttribute('data-product-id');
            if (productId) {
                toggleSaveProduct(e, productId);
            }
        }
    });
}

// CSS animation for loading spinner
const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);

// Initialize everything when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize core functionality
    initializeTooltips();
    initializeCardObserver();
    initializeKeyboardNavigation();
    
    // Preload critical resources
    requestIdleCallback(() => {
        // Cache CSRF token
        getCookie('csrftoken');
        
        // Preconnect to save endpoint
        const link = document.createElement('link');
        link.rel = 'preconnect';
        link.href = '/products/toggle-save/';
        document.head.appendChild(link);
    });
});

// Global click handler for save buttons (event delegation)
document.addEventListener('click', function(event) {
    const saveButton = event.target.closest('.save-button[data-product-id]');
    if (saveButton) {
        const productId = saveButton.getAttribute('data-product-id');
        if (productId) {
            toggleSaveProduct(event, productId);
        }
    }
});

// Cleanup function
window.addEventListener('beforeunload', () => {
    saveProductDebouncer.clear();
    toastQueue.length = 0;
    isShowingToast = false;
});

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        toggleSaveProduct,
        showToast,
        getCookie
    };
}