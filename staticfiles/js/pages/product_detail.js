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
    // Share Product Functionality
    // -------------------------
    // ===== DEVELOPMENT-FRIENDLY SHARE FUNCTIONALITY =====
    function shareProduct() {
        const currentUrl = window.location.href;
        const productTitle = "{{ product.title|escapejs }}";
        const productPrice = "{{ product.formatted_price|escapejs }}";
        const shareText = `Check out this ${productTitle} for ${productPrice} on OpenSell!`;
        
        console.log('Share button clicked'); // Debug log
        
        // For development and mobile testing
        const isLocalhost = window.location.hostname === 'localhost' || 
                        window.location.hostname === '127.0.0.1' || 
                        window.location.hostname === '';
        
        // Check for mobile devices and Web Share API support
        const isMobile = /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        
        if (navigator.share && isMobile) {
            console.log('Using Web Share API'); // Debug log
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
            console.log('Using fallback share'); // Debug log
            fallbackShare(currentUrl, shareText);
        }
    }

    function fallbackShare(url, text) {
        // For development, always show the share modal instead of relying on clipboard
        const isLocalhost = window.location.hostname === 'localhost' || 
                        window.location.hostname === '127.0.0.1';
        
        if (!isLocalhost && navigator.clipboard && window.isSecureContext) {
            // Production HTTPS environment - try clipboard
            navigator.clipboard.writeText(url).then(() => {
                showShareSuccess('Product link copied to clipboard!');
                updateShareButtonState(true);
            }).catch((error) => {
                console.log('Clipboard error:', error);
                showShareModal(url, text);
            });
        } else {
            // Development environment or no clipboard support - show modal
            console.log('Showing share modal for development/fallback');
            showShareModal(url, text);
        }
    }

    function showShareSuccess(message) {
        showToast(message);
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
        // Remove any existing modal first
        const existingModal = document.getElementById('shareModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        const modal = document.createElement('div');
        modal.innerHTML = `
            <div class="modal fade" id="shareModal" tabindex="-1" aria-labelledby="shareModalLabel" aria-hidden="true">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="shareModalLabel">
                                <i class="fas fa-share-alt me-2"></i>Share this Product
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-4">
                                <label class="form-label fw-semibold">Product URL:</label>
                                <div class="input-group">
                                    <input type="text" class="form-control" value="${url}" id="urlInput" readonly>
                                    <button class="btn btn-outline-primary" onclick="copyFromInput()" id="copyUrlBtn" type="button">
                                        <i class="fas fa-copy"></i>
                                    </button>
                                </div>
                                <small class="text-muted">Click the copy button or select and copy the URL above</small>
                            </div>
                            <div class="share-buttons">
                                <h6 class="mb-3">Share on social media:</h6>
                                <div class="row g-2">
                                    <div class="col-6">
                                        <a href="https://wa.me/?text=${encodeURIComponent(text + ' ' + url)}" 
                                        target="_blank" 
                                        class="btn btn-success w-100"
                                        onclick="trackShare('whatsapp')">
                                            <i class="fab fa-whatsapp me-2"></i>WhatsApp
                                        </a>
                                    </div>
                                    <div class="col-6">
                                        <a href="https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}" 
                                        target="_blank" 
                                        class="btn btn-primary w-100"
                                        onclick="trackShare('facebook')">
                                            <i class="fab fa-facebook me-2"></i>Facebook
                                        </a>
                                    </div>
                                    <div class="col-6">
                                        <a href="https://twitter.com/intent/tweet?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}" 
                                        target="_blank" 
                                        class="btn btn-info w-100"
                                        onclick="trackShare('twitter')">
                                            <i class="fab fa-twitter me-2"></i>Twitter
                                        </a>
                                    </div>
                                    <div class="col-6">
                                        <a href="https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}" 
                                        target="_blank" 
                                        class="btn btn-secondary w-100"
                                        onclick="trackShare('telegram')">
                                            <i class="fab fa-telegram me-2"></i>Telegram
                                        </a>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Initialize and show modal
        const shareModal = new bootstrap.Modal(document.getElementById('shareModal'), {
            backdrop: true,
            keyboard: true,
            focus: true
        });
        
        shareModal.show();
        
        // Clean up when modal is hidden
        const modalElement = document.getElementById('shareModal');
        modalElement.addEventListener('hidden.bs.modal', function() {
            if (document.body.contains(modal)) {
                document.body.removeChild(modal);
            }
        });
        
        // Track that share modal was opened
        console.log('Share modal opened successfully');
    }

    function copyFromInput() {
        const input = document.getElementById('urlInput');
        const copyBtn = document.getElementById('copyUrlBtn');
        
        if (!input || !copyBtn) return;
        
        // Select the text
        input.select();
        input.setSelectionRange(0, 99999); // For mobile devices
        
        // Try modern clipboard API first
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(input.value).then(() => {
                showCopySuccess();
            }).catch(() => {
                // Fallback to execCommand
                fallbackCopy();
            });
        } else {
            // Fallback for development/older browsers
            fallbackCopy();
        }
        
        function fallbackCopy() {
            try {
                const successful = document.execCommand('copy');
                if (successful) {
                    showCopySuccess();
                } else {
                    showToast('Please manually copy the URL from the input field.');
                }
            } catch (err) {
                console.log('Copy fallback failed:', err);
                showToast('Please manually copy the URL from the input field.');
            }
        }
        
        function showCopySuccess() {
            copyBtn.innerHTML = '<i class="fas fa-check"></i>';
            copyBtn.classList.remove('btn-outline-primary');
            copyBtn.classList.add('btn-success');
            showToast('URL copied to clipboard!');
            
            setTimeout(() => {
                copyBtn.innerHTML = '<i class="fas fa-copy"></i>';
                copyBtn.classList.remove('btn-success');
                copyBtn.classList.add('btn-outline-primary');
            }, 2000);
        }
    }

    // Track share usage for analytics
    function trackShare(platform) {
        console.log(`Product shared via ${platform}`);
        showToast(`Opening ${platform}...`);
        // Add your analytics tracking here if needed
    }

    // ===== FIXED SAVE FUNCTIONALITY =====
    function toggleSaveProduct(event, productId) {
        event.preventDefault();
        
        const button = event.currentTarget;
        const icon = button.querySelector('i');
        const text = button.querySelector('.btn-text');
        const csrfToken = getCookie('csrftoken');
        
        if (!csrfToken) {
            showToast('Error: Please refresh the page and try again.');
            return;
        }

        // Store original state
        const originalIcon = icon.className;
        const originalText = text.textContent;
        const wasAlreadySaved = button.getAttribute('data-saved') === 'true';

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
                // Product was saved
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
                // Product was unsaved
                icon.className = 'far fa-heart me-2';
                text.textContent = 'Save';
                button.setAttribute('data-saved', 'false');
                button.classList.remove('saved-state');
            }
            
            showToast(data.message);
            
            // Update all other instances of this product's save button on the page
            updateAllSaveButtons(productId, data.status === 'saved');
            
        })
        .catch(error => {
            console.error('Error:', error);
            showToast('An error occurred. Please try again.');
            
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

    // Initialize save button states on page load
    document.addEventListener('DOMContentLoaded', function() {
        const saveButtons = document.querySelectorAll('.save-product-btn');
        saveButtons.forEach(button => {
            const isSaved = button.getAttribute('data-saved') === 'true';
            if (isSaved) {
                button.classList.add('saved-state');
            }
        });
    });

    // Initialize saved state on page load
    document.addEventListener('DOMContentLoaded', function() {
        const saveBtn = document.querySelector('.save-product-btn');
        if (saveBtn) {
            const isInitiallySaved = saveBtn.querySelector('i').classList.contains('fas');
            if (isInitiallySaved) {
                saveBtn.setAttribute('data-saved', 'true');
            }
        }
    });

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
});