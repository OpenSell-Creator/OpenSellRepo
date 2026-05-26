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
        showSystemAlert('Authentication error. Please refresh the page.', 'error');
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
        
        // Show alert notification
        if (data.message) {
            showSystemAlert(data.message, 'success');
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
        
        showSystemAlert(`Unable to save ${itemType}. Please try again.`, 'error');
    })
    .finally(() => {
        setTimeout(() => {
            saveDebouncer.delete(debounceKey);
        }, 300);
    });
}

// Add CSS for spin animation (used on save button loading state)
const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);

// Aliases for any callers using the old toast API — delegates to alerts.js showSystemAlert
function showErrorToast(m)   { showSystemAlert(m, 'error'); }
function showSuccessToast(m) { showSystemAlert(m, 'success'); }
function showWarningToast(m) { showSystemAlert(m, 'warning'); }

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
});