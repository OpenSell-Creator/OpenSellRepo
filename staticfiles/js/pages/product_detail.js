// Enhanced JavaScript for product_detail.html with WhatsApp integration

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function () {
    // -------------------------
    // 1. Time Functionality (Countdown Timer)
    // -------------------------
    const timers = document.querySelectorAll('.countdown-timer');
    timers.forEach(timer => {
        const expirationDateStr = timer.dataset.expiration;
        if (!expirationDateStr) {
            console.error('No expiration date provided');
            timer.innerHTML = 'Date not set';
            return;
        }

        const expirationDate = new Date(expirationDateStr);
        if (isNaN(expirationDate.getTime())) {
            console.error('Invalid date format:', expirationDateStr);
            timer.innerHTML = 'Invalid date';
            return;
        }

        function updateTimer() {
            const now = new Date();
            const timeLeft = expirationDate - now;

            if (timeLeft <= 0) {
                timer.innerHTML = '<span class="text-danger">Expired</span>';
                return;
            }

            const days = Math.floor(timeLeft / (1000 * 60 * 60 * 24));
            const hours = Math.floor((timeLeft % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((timeLeft % (1000 * 60)) / 1000);

            const daysElement = timer.querySelector('.days');
            const hoursElement = timer.querySelector('.hours');
            const minutesElement = timer.querySelector('.minutes');
            const secondsElement = timer.querySelector('.seconds');

            if (daysElement) daysElement.textContent = days;
            if (hoursElement) hoursElement.textContent = hours.toString().padStart(2, '0');
            if (minutesElement) minutesElement.textContent = minutes.toString().padStart(2, '0');
            if (secondsElement) secondsElement.textContent = seconds.toString().padStart(2, '0');
        }

        updateTimer();
        const intervalId = setInterval(updateTimer, 1000);
        timer.dataset.intervalId = intervalId;
    });

    // -------------------------
    // 2. Star Rating
    // -------------------------
    const ratingSelect = document.getElementById('rating');
    if (ratingSelect) {
        const starRating = document.createElement('div');
        starRating.classList.add('star-rating');

        ratingSelect.parentNode.insertBefore(starRating, ratingSelect);
        ratingSelect.style.display = 'none';

        // Create stars
        for (let i = 1; i <= 5; i++) {
            const star = document.createElement('span');
            star.innerHTML = '&#9734;'; // Empty star
            star.addEventListener('click', () => {
                ratingSelect.value = i;
                updateStars();
            });
            starRating.appendChild(star);
        }

        function updateStars() {
            const stars = starRating.children;
            for (let i = 0; i < stars.length; i++) {
                stars[i].innerHTML = i < ratingSelect.value ? '&#9733;' : '&#9734;';
            }
        }

        ratingSelect.addEventListener('change', updateStars);
        updateStars();
    }

    // -------------------------
    // 3. Quick Update Script
    // -------------------------
    const quickUpdateForm = document.getElementById('quickUpdateForm');
    if (quickUpdateForm) {
        quickUpdateForm.addEventListener('submit', function (e) {
            e.preventDefault();

            const submitButton = this.querySelector('button[type="submit"]');
            submitButton.disabled = true;
            submitButton.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Updating...';

            fetch(this.action, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': this.querySelector('[name="csrfmiddlewaretoken"]').value
                },
                credentials: 'same-origin'
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Update the countdown timer
                        const timer = document.querySelector('.countdown-timer');
                        if (timer) {
                            clearInterval(timer.dataset.intervalId);
                            timer.dataset.expiration = data.expiration_date;

                            const expirationDate = new Date(data.expiration_date);
                            const intervalId = setInterval(() => {
                                const now = new Date();
                                const timeLeft = expirationDate - now;

                                if (timeLeft <= 0) {
                                    timer.innerHTML = '<span class="text-danger">Expired</span>';
                                    clearInterval(intervalId);
                                    return;
                                }

                                const days = Math.floor(timeLeft / (1000 * 60 * 60 * 24));
                                const hours = Math.floor((timeLeft % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                                const minutes = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));
                                const seconds = Math.floor((timeLeft % (1000 * 60)) / 1000);

                                timer.querySelector('.days').textContent = days;
                                timer.querySelector('.hours').textContent = hours.toString().padStart(2, '0');
                                timer.querySelector('.minutes').textContent = minutes.toString().padStart(2, '0');
                                timer.querySelector('.seconds').textContent = seconds.toString().padStart(2, '0');
                            }, 1000);

                            timer.dataset.intervalId = intervalId;
                        }

                        // Show success message
                        const alertDiv = document.createElement('div');
                        alertDiv.className = 'alert alert-success alert-dismissible fade show mt-2';
                        alertDiv.innerHTML = `
                            ${data.message}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        `;
                        quickUpdateForm.after(alertDiv);

                        // Remove any existing deletion warnings
                        const deletionWarning = document.querySelector('.deletion-warning');
                        if (deletionWarning) {
                            deletionWarning.remove();
                        }

                        setTimeout(() => {
                            alertDiv.remove();
                        }, 3000);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    const alertDiv = document.createElement('div');
                    alertDiv.className = 'alert alert-danger alert-dismissible fade show mt-2';
                    alertDiv.innerHTML = `
                        Error updating listing
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    `;
                    quickUpdateForm.after(alertDiv);
                })
                .finally(() => {
                    submitButton.disabled = false;
                    submitButton.innerHTML = '<i class="fas fa-sync-alt me-1"></i>Reset Timer';
                });
        });
    }

    // -------------------------
    // 4. Safety Tips Toggle
    // -------------------------
    const hiddenTips = document.getElementById('hidden-tips');
    const toggleText = document.getElementById('toggle-text');
    const toggleTips = document.getElementById('toggle-tips');

    if (hiddenTips && toggleText && toggleTips) {
        hiddenTips.addEventListener('show.bs.collapse', function () {
            toggleText.textContent = 'See less safety tips';
        });

        hiddenTips.addEventListener('hide.bs.collapse', function () {
            toggleText.textContent = 'See more safety tips';
        });
    }

    // -------------------------
    // 5. Number Copying Script
    // -------------------------
    window.copyToClipboard = function(phoneNumber) {
        // Input validation
        if (!phoneNumber) {
            showToast('No phone number available');
            return;
        }

        // Check for clipboard API support
        if (!navigator.clipboard) {
            showToast('Clipboard access not available in your browser');
            return;
        }

        // Clean the phone number: remove all non-numeric characters
        let cleanPhone = phoneNumber.replace(/\D/g, '');

        // Add country code if missing (assuming Nigeria +234)
        if (!cleanPhone.startsWith('234')) {
            // Remove leading zero if present
            cleanPhone = cleanPhone.replace(/^0/, '');
            cleanPhone = '234' + cleanPhone;
        }

        // Disable the button and show loading state
        const copyButton = document.getElementById('copyButton');
        const originalContent = copyButton.innerHTML;
        copyButton.disabled = true;
        copyButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

        // Copy the cleaned phone number to clipboard
        navigator.clipboard.writeText(cleanPhone)
            .then(function() {
                showToast('Phone number copied: ' + cleanPhone);
            })
            .catch(function(err) {
                console.error('Failed to copy:', err);
                showToast('Failed to copy phone number. Please try again.');
            })
            .finally(function() {
                // Reset button state
                copyButton.disabled = false;
                copyButton.innerHTML = originalContent;
            });
    }

    // Function to show toast notification
    function showToast(message) {
        const toast = document.getElementById('copyToast');
        const toastMessage = document.getElementById('toastMessage');
        
        if (toast && toastMessage) {
            toastMessage.textContent = message;
            const bsToast = new bootstrap.Toast(toast);
            bsToast.show();
        }
    }

    // -------------------------
    // 6. Carousel Functionality
    // -------------------------
    const carousel = document.getElementById('productCarousel');
    if (carousel) {
        const carouselItems = carousel.querySelectorAll('.carousel-item');
        carouselItems.forEach((item, index) => {
            item.addEventListener('click', () => {
                const carousel = new bootstrap.Carousel(carousel, {
                    interval: false, // Disable automatic sliding
                });
                carousel.to(index);
            });
        });
    }

    // -------------------------
    // 7. Thumbnail Navigation
    // -------------------------
    const thumbnails = document.querySelectorAll('.thumbnail-wrapper img');
    thumbnails.forEach(thumbnail => {
        thumbnail.addEventListener('click', () => {
            const targetIndex = thumbnail.dataset.bsSlideTo;
            const carousel = new bootstrap.Carousel(document.getElementById('productCarousel'), {
                interval: false, // Disable automatic sliding
            });
            carousel.to(targetIndex);
        });
    });

    // -------------------------
    // 8. Enhanced Status Chips Animation
    // -------------------------
    const statusChips = document.querySelectorAll('.status-chip');
    statusChips.forEach(chip => {
        chip.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px) scale(1.02)';
        });
        
        chip.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
        });
    });

    // -------------------------
    // 9. Business Info Accordion (Mobile Enhancement)
    // -------------------------
    function initializeMobileBusinessAccordion() {
        if (window.innerWidth <= 768) {
            const businessInfo = document.querySelector('.business-info-section');
            if (businessInfo) {
                const header = businessInfo.querySelector('.business-header');
                const content = businessInfo.querySelector('.business-contact-grid');
                
                if (header && content) {
                    header.style.cursor = 'pointer';
                    header.addEventListener('click', function() {
                        content.style.display = content.style.display === 'none' ? 'grid' : 'none';
                    });
                }
            }
        }
    }

    // Initialize mobile accordion
    initializeMobileBusinessAccordion();
    
    // Re-initialize on window resize
    window.addEventListener('resize', initializeMobileBusinessAccordion);
});

// -------------------------
// ENHANCED WHATSAPP FUNCTIONALITY
// -------------------------

/**
 * Opens WhatsApp with a pre-filled message containing product details
 * This function is called when the WhatsApp button is clicked
 */
function openWhatsAppWithMessage() {
    try {
        // Get the WhatsApp button to extract data attributes
        const whatsappButton = document.querySelector('[onclick="openWhatsAppWithMessage()"]');
        
        if (!whatsappButton) {
            console.error('WhatsApp button not found');
            fallbackWhatsApp();
            return;
        }

        // Extract product and seller information from data attributes
        const sellerName = whatsappButton.getAttribute('data-seller-name') || 'Seller';
        const sellerPhone = whatsappButton.getAttribute('data-seller-phone') || '';
        const productTitle = whatsappButton.getAttribute('data-product-title') || 'Product';
        const productPrice = whatsappButton.getAttribute('data-product-price') || 'Price not available';
        const productUrl = whatsappButton.getAttribute('data-product-url') || window.location.href;

        // Clean phone number for WhatsApp
        const cleanedPhone = cleanPhoneNumber(sellerPhone);
        
        if (!cleanedPhone) {
            showToast('❌ Seller phone number not available');
            return;
        }

        // Create the WhatsApp message
        const message = createWhatsAppMessage(sellerName, productTitle, productPrice, productUrl);
        
        // Create WhatsApp URL
        const whatsappUrl = `https://wa.me/${cleanedPhone}?text=${encodeURIComponent(message)}`;
        
        // Add loading state to button
        const originalContent = whatsappButton.innerHTML;
        whatsappButton.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Opening WhatsApp...';
        whatsappButton.disabled = true;
        
        // Open WhatsApp
        window.open(whatsappUrl, '_blank');
        
        // Show success message
        showToast('✅ Opening WhatsApp with product details...');
        
        // Analytics tracking (if needed)
        if (typeof gtag !== 'undefined') {
            gtag('event', 'whatsapp_contact', {
                'event_category': 'contact',
                'event_label': productTitle,
                'custom_parameters': {
                    'seller_name': sellerName,
                    'product_price': productPrice
                }
            });
        }
        
        // Reset button after delay
        setTimeout(() => {
            whatsappButton.innerHTML = originalContent;
            whatsappButton.disabled = false;
        }, 3000);
        
    } catch (error) {
        console.error('Error opening WhatsApp:', error);
        showToast('❌ Error opening WhatsApp. Please try again.');
        fallbackWhatsApp();
    }
}

/**
 * Cleans and formats phone number for WhatsApp
 * @param {string} phoneNumber - Raw phone number
 * @returns {string} - Cleaned phone number with country code
 */
function cleanPhoneNumber(phoneNumber) {
    if (!phoneNumber) {
        return '';
    }
    
    // Remove all non-numeric characters
    let cleaned = phoneNumber.replace(/\D/g, '');
    
    // Handle different formats
    if (cleaned.startsWith('234')) {
        // Already has country code
        return cleaned;
    } else if (cleaned.startsWith('0')) {
        // Remove leading 0 and add country code
        return '234' + cleaned.substring(1);
    } else if (cleaned.length === 10) {
        // Add country code
        return '234' + cleaned;
    } else if (cleaned.length === 11 && cleaned.startsWith('0')) {
        // Remove leading 0 and add country code
        return '234' + cleaned.substring(1);
    }
    
    // Return as-is if we can't determine format
    return cleaned;
}

/**
 * Creates a formatted WhatsApp message with product details
 * @param {string} sellerName - Name of the seller
 * @param {string} productTitle - Title of the product
 * @param {string} productPrice - Price of the product
 * @param {string} productUrl - URL to the product
 * @returns {string} - Formatted WhatsApp message
 */
function createWhatsAppMessage(sellerName, productTitle, productPrice, productUrl) {
    const messages = [
        `Hello ${sellerName}! 👋`,
        '',
        `I'm interested in your product listed on OpenSell:`,
        '',
        `📦 *${productTitle}*`,
        `💰 Price: ${productPrice}`,
        '',
        `Could you please provide more details about:`,
        `• Current availability and condition`,
        `• Payment and delivery options`,
        `• Any additional information`,
        '',
        `You can view the listing here:`,
        `${productUrl}`,
        '',
        `Looking forward to hearing from you!`,
        '',
        `*Sent via OpenSell Marketplace* 🛒`
    ];
    
    return messages.join('\n');
}

/**
 * Fallback WhatsApp function for when data is not available
 */
function fallbackWhatsApp() {
    const phoneElements = document.querySelectorAll('[href^="tel:"]');
    if (phoneElements.length > 0) {
        const phone = phoneElements[0].href.replace('tel:', '');
        const cleanedPhone = cleanPhoneNumber(phone);
        
        if (cleanedPhone) {
            const fallbackMessage = `Hello! I'm interested in your product listed on OpenSell. Could you please provide more details?\n\n*Sent via OpenSell Marketplace* 🛒`;
            const whatsappUrl = `https://wa.me/${cleanedPhone}?text=${encodeURIComponent(fallbackMessage)}`;
            window.open(whatsappUrl, '_blank');
            showToast('✅ Opening WhatsApp...');
        } else {
            showToast('❌ Phone number not available');
        }
    } else {
        showToast('❌ Contact information not available');
    }
}

/**
 * Enhanced toast notification system for WhatsApp functionality
 * @param {string} message - Message to display
 * @param {string} type - Type of toast (success, error, info)
 */
function showToast(message, type = 'info') {
    // Remove existing toasts
    const existingToasts = document.querySelectorAll('.whatsapp-toast');
    existingToasts.forEach(toast => toast.remove());
    
    // Create toast container if it doesn't exist
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        toastContainer.style.zIndex = '9999';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast element
    const toast = document.createElement('div');
    toast.className = 'toast whatsapp-toast';
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    // Determine toast styling based on type
    let bgClass = 'bg-primary';
    let iconClass = 'bi-info-circle';
    
    if (type === 'success' || message.includes('✅')) {
        bgClass = 'bg-success';
        iconClass = 'bi-check-circle';
    } else if (type === 'error' || message.includes('❌')) {
        bgClass = 'bg-danger';
        iconClass = 'bi-exclamation-circle';
    }
    
    toast.innerHTML = `
        <div class="toast-header ${bgClass} text-white">
            <i class="bi ${iconClass} me-2"></i>
            <strong class="me-auto">OpenSell</strong>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
        <div class="toast-body">
            ${message}
        </div>
    `;
    
    toastContainer.appendChild(toast);
    
    // Initialize and show toast
    const bsToast = new bootstrap.Toast(toast, {
        autohide: true,
        delay: 4000
    });
    bsToast.show();
    
    // Remove toast element after it's hidden
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

// -------------------------
// SHARE PRODUCT FUNCTIONALITY (Enhanced)
// -------------------------
function shareProduct() {
    const currentUrl = window.location.href;
    const productTitle = document.querySelector('.product-title')?.textContent || 'Product';
    const productPrice = document.querySelector('.price-badge .h2')?.textContent || 'Price available';
    const shareText = `Check out this ${productTitle} for ${productPrice} on OpenSell!`;
    
    console.log('Share button clicked');
    
    // Check for mobile devices and Web Share API support
    const isMobile = /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    
    if (navigator.share && isMobile) {
        console.log('Using Web Share API');
        navigator.share({
            title: `${productTitle} - OpenSell`,
            text: shareText,
            url: currentUrl
        }).then(() => {
            showShareSuccess('Product shared successfully!');
        }).catch((error) => {
            console.log('Web Share API error:', error);
            fallbackShare(currentUrl, shareText);
        });
    } else {
        console.log('Using fallback share');
        fallbackShare(currentUrl, shareText);
    }
}

function fallbackShare(url, text) {
    const isLocalhost = window.location.hostname === 'localhost' || 
                    window.location.hostname === '127.0.0.1';
    
    if (!isLocalhost && navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(url).then(() => {
            showShareSuccess('Product link copied to clipboard!');
            updateShareButtonState(true);
        }).catch((error) => {
            console.log('Clipboard error:', error);
            showShareModal(url, text);
        });
    } else {
        console.log('Showing share modal for development/fallback');
        showShareModal(url, text);
    }
}

function showShareSuccess(message) {
    showToast(message, 'success');
}

function updateShareButtonState(success) {
    const shareButton = document.getElementById('shareButton');
    if (!shareButton) return;
    
    const originalContent = shareButton.innerHTML;
    
    if (success) {
        shareButton.innerHTML = '<i class="fas fa-check me-2"></i><span class="btn-text">Copied!</span>';
        shareButton.classList.add('btn-share-success');
        shareButton.classList.remove('btn-action-primary');
        
        setTimeout(() => {
            shareButton.innerHTML = originalContent;
            shareButton.classList.remove('btn-share-success');
            shareButton.classList.add('btn-action-primary');
        }, 2500);
    }
}

function showShareModal(url, text) {
    // Implementation for share modal (keeping existing code)
    // ... existing share modal code ...
}

// -------------------------
// SAVE FUNCTIONALITY (Enhanced)
// -------------------------
function toggleSaveProduct(event, productId) {
    event.preventDefault();
    
    const button = event.currentTarget;
    const icon = button.querySelector('i');
    const text = button.querySelector('.btn-text');
    const csrfToken = getCookie('csrftoken');
    
    if (!csrfToken) {
        showToast('Error: Please refresh the page and try again.', 'error');
        return;
    }

    // Store original state
    const originalIcon = icon.className;
    const originalText = text.textContent;

    // Disable button during request
    button.disabled = true;
    icon.className = 'fas fa-spinner fa-spin me-2';
    text.textContent = 'Saving...';
    
    fetch('/products/toggle-save/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrfToken,
        },
        body: `product_id=${productId}`
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        // Update button state based on response
        if (data.status === 'saved') {
            icon.className = 'fas fa-heart me-2';
            text.textContent = 'Saved';
            button.setAttribute('data-saved', 'true');
            button.classList.add('saved-state');
            
            // Trigger heart animation
            setTimeout(() => {
                icon.style.animation = 'heartBeat 0.6s ease';
                setTimeout(() => {
                    icon.style.animation = '';
                }, 600);
            }, 100);
            
        } else if (data.status === 'removed') {
            icon.className = 'far fa-heart me-2';
            text.textContent = 'Save';
            button.setAttribute('data-saved', 'false');
            button.classList.remove('saved-state');
        }
        
        showToast(data.message, 'success');
        
        // Update all other instances of this product's save button on the page
        updateAllSaveButtons(productId, data.status === 'saved');
        
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('An error occurred. Please try again.', 'error');
        
        // Restore original state on error
        icon.className = originalIcon;
        text.textContent = originalText;
    })
    .finally(() => {
        button.disabled = false;
    });
}

// Helper function to update all save buttons for this product
function updateAllSaveButtons(productId, isSaved) {
    const buttons = document.querySelectorAll(`[data-product-id="${productId}"]`);
    buttons.forEach(btn => {
        const icon = btn.querySelector('i');
        const text = btn.querySelector('.btn-text') || btn.querySelector('span');
        
        if (isSaved) {
            if (icon) icon.className = 'fas fa-heart me-2';
            if (text) text.textContent = 'Saved';
            btn.setAttribute('data-saved', 'true');
            btn.classList.add('saved-state');
        } else {
            if (icon) icon.className = 'far fa-heart me-2';
            if (text) text.textContent = 'Save';
            btn.setAttribute('data-saved', 'false');
            btn.classList.remove('saved-state');
        }
    });
}

// Get CSRF token
function getCookie(name) {
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
    return cookieValue;
}

// -------------------------
// INITIALIZATION
// -------------------------

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Performance optimization: Lazy load images
document.addEventListener('DOMContentLoaded', function() {
    const images = document.querySelectorAll('img[data-src]');
    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                img.removeAttribute('data-src');
                observer.unobserve(img);
            }
        });
    });
    
    images.forEach(img => imageObserver.observe(img));
});