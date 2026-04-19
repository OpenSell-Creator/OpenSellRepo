/**
 * UNIFIED SAVE SYSTEM - FIXED VERSION
 * Works for products, services, and buyer requests
 * 
 * IMPORTANT: Add this to your template BEFORE loading this script:
 * <script>
 *     window.SAVE_TOGGLE_URL = "{% url 'toggle_save' %}";
 * </script>
 */

// Cache CSRF token
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

// Debounce map to prevent double-clicks
const saveDebouncer = new Map();

/**
 * Unified save/unsave function
 * 
 * @param {Event} event - Click event
 * @param {string} itemId - UUID of item
 * @param {string} itemType - 'product', 'service', or 'request'
 */
function toggleSave(event, itemId, itemType) {
    event.preventDefault();
    event.stopPropagation();
    
    // Debounce rapid clicks
    const debounceKey = `${itemType}-${itemId}`;
    if (saveDebouncer.has(debounceKey)) {
        return;
    }
    
    const button = event.currentTarget;
    const csrfToken = getCookie('csrftoken');
    
    if (!csrfToken) {
        console.error('CSRF token not found');
        showToast('Authentication error. Please refresh the page.', 'error');
        return;
    }

    // Get URL from window object (set by Django template) or fallback
    const saveUrl = window.SAVE_TOGGLE_URL || '/save/toggle/';
    
    // Debug log
    console.log('Save URL:', saveUrl);

    // Set debounce flag
    saveDebouncer.set(debounceKey, true);
    
    // Add loading state
    button.classList.add('loading');
    button.style.opacity = '0.6';
    button.disabled = true;
    
    const originalIcon = button.querySelector('i');
    const originalClass = originalIcon.className;
    originalIcon.className = 'bi bi-arrow-clockwise';
    originalIcon.style.animation = 'spin 1s linear infinite';
    
    fetch(saveUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrfToken,
        },
        body: `item_id=${itemId}&item_type=${itemType}`,
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
        // ✅ UPDATE ALL INSTANCES GLOBALLY (product_list, search, detail, my_store, etc.)
        const allButtons = document.querySelectorAll(`[data-item-id="${itemId}"][data-item-type="${itemType}"]`);
        
        console.log(`Found ${allButtons.length} save buttons to update for ${itemType} ${itemId}`);
        
        requestAnimationFrame(() => {
            allButtons.forEach(btn => {
                const icon = btn.querySelector('i');
                const textSpan = btn.querySelector('.btn-text, span');
                
                if (data.status === 'saved') {
                    // SAVED STATE
                    btn.classList.add('saved');
                    btn.setAttribute('data-saved', 'true');
                    btn.title = 'Remove from saved';
                    
                    if (icon) {
                        if (itemType === 'product') {
                            icon.className = 'bi bi-heart-fill';
                        } else if (itemType === 'service') {
                            icon.className = 'bi bi-bookmark-fill';
                        } else {
                            icon.className = 'bi bi-bookmark-fill';
                        }
                        // Heartbeat animation
                        icon.style.animation = 'heartBeat 0.6s ease-in-out';
                        setTimeout(() => {
                            icon.style.animation = '';
                        }, 600);
                    }
                    
                    if (textSpan) {
                        textSpan.textContent = 'Saved';
                    }
                } else if (data.status === 'removed') {
                    // UNSAVED STATE
                    btn.classList.remove('saved');
                    btn.setAttribute('data-saved', 'false');
                    btn.title = `Save this ${itemType}`;
                    
                    if (icon) {
                        if (itemType === 'product') {
                            icon.className = 'bi bi-heart';
                        } else if (itemType === 'service') {
                            icon.className = 'bi bi-bookmark';
                        } else {
                            icon.className = 'bi bi-bookmark';
                        }
                        icon.style.animation = '';
                    }
                    
                    if (textSpan) {
                        textSpan.textContent = 'Save';
                    }
                }
                
                // Remove loading state
                btn.classList.remove('loading');
                btn.style.opacity = '1';
                btn.disabled = false;
            });
        });
        
        // Show toast notification
        if (data.message) {
            const icon = data.status === 'saved' ? '❤️' : '🗑️';
            showToast(`${icon} ${data.message}`, 'success');
        }
    })
    .catch(error => {
        console.error('Error toggling save:', error);
        
        // Restore original state on error
        requestAnimationFrame(() => {
            button.classList.remove('loading');
            button.style.opacity = '1';
            button.disabled = false;
        });
        
        showToast(`❌ Unable to save ${itemType}. Please try again.`, 'error');
    })
    .finally(() => {
        setTimeout(() => {
            saveDebouncer.delete(debounceKey);
        }, 300);
    });
}

// Toast notification system
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
    
    toast.addEventListener('click', () => dismissToast(toast));
    container.appendChild(toast);
    
    requestAnimationFrame(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateX(0)';
    });
    
    const dismissTimeout = setTimeout(() => {
        dismissToast(toast);
    }, 4000);
    
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
        setTimeout(processToastQueue, 200);
    }, 400);
}

// Add CSS for spin animation
const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    
    @keyframes heartBeat {
        0% { transform: scale(1); }
        25% { transform: scale(1.3); }
        50% { transform: scale(1); }
        75% { transform: scale(1.1); }
        100% { transform: scale(1); }
    }
`;
document.head.appendChild(style);

// Initialize on load
document.addEventListener('DOMContentLoaded', function() {
    getCookie('csrftoken'); // Cache token
    
    // Warn if SAVE_TOGGLE_URL is not set
    if (!window.SAVE_TOGGLE_URL) {
        console.warn('⚠️ window.SAVE_TOGGLE_URL not set. Using fallback URL /save/toggle/. Add this to your template:\n<script>\n    window.SAVE_TOGGLE_URL = "{% url \'toggle_save\' %}";\n</script>');
    }
});

// Cleanup
window.addEventListener('beforeunload', () => {
    saveDebouncer.clear();
    toastQueue.length = 0;
    isShowingToast = false;
});