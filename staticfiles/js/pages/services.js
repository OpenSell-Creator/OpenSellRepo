document.addEventListener('DOMContentLoaded', function () {
    initializeServiceListPage();
    initializeInfiniteScroll();
    initializeSaveToggle();
    initializeTooltips();
    initializeInquiryFunctionality();
    initializeMessageFunctionality();
    initializeSortControls();
    initializeServiceCardInteractions();
    initializeLoadMoreReviews();
    initializePerformanceOptimizations();
    initializeServiceStatusToggle();
    initializeRealTimeMessages();
});

function initializeServiceListPage() {
    const servicesGrid = document.getElementById('services-grid');
    if (!servicesGrid) return;

    const categoryPills = document.querySelectorAll('.srl-cat-pill');
    categoryPills.forEach(function (pill) {
        pill.addEventListener('click', function () {
            pill.style.opacity = '0.7';
            setTimeout(function () { pill.style.opacity = '1'; }, 500);
        });
    });
}

function initializeInfiniteScroll() {
    const loadingIndicator = document.getElementById('loading-indicator');
    const endOfResults     = document.getElementById('end-of-results');
    const servicesGrid     = document.getElementById('services-grid');

    if (!servicesGrid || !loadingIndicator || !endOfResults) return;

    let isLoading   = false;
    let hasNextPage = true;
    let currentPage = 1;

    const paginationData = document.getElementById('pagination-data');
    if (paginationData) {
        try {
            const data  = JSON.parse(paginationData.textContent);
            currentPage = data.current_page || 1;
            hasNextPage = data.has_next     || false;
        } catch (e) {
            console.error('Error parsing pagination data:', e);
        }
    }

    const loadMoreBtn = document.getElementById('loadMoreServices');
    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', loadMoreServices);
    }

    function loadMoreServices() {
        if (isLoading || !hasNextPage) return;

        isLoading = true;
        if (loadMoreBtn) loadMoreBtn.style.display = 'none';
        loadingIndicator.style.display = 'block';

        const nextPage   = currentPage + 1;
        const currentUrl = new URL(window.location.href);
        currentUrl.searchParams.set('page', nextPage);

        fetch(currentUrl.toString(), {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (data.success && data.services_html && data.services_html.length > 0) {
                data.services_html.forEach(function (serviceHtml) {
                    const tempDiv = document.createElement('div');
                    tempDiv.innerHTML = serviceHtml;
                    const serviceCard = tempDiv.firstElementChild;
                    servicesGrid.appendChild(serviceCard);
                });

                currentPage = nextPage;
                hasNextPage = data.has_more;
                initializeTooltips();

                if (!hasNextPage) {
                    endOfResults.style.display = 'block';
                } else if (loadMoreBtn) {
                    loadMoreBtn.setAttribute('data-page', currentPage + 1);
                    loadMoreBtn.style.display = 'block';
                }
            } else {
                hasNextPage = false;
                endOfResults.style.display = 'block';
            }
        })
        .catch(function (error) {
            console.error('Error loading more services:', error);
            showNotification('Error loading more services', 'error');
            if (loadMoreBtn) loadMoreBtn.style.display = 'block';
        })
        .finally(function () {
            isLoading = false;
            loadingIndicator.style.display = 'none';
        });
    }

    let scrollTimeout;
    window.addEventListener('scroll', function () {
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(function () {
            const scrollPosition = window.innerHeight + window.scrollY;
            const threshold      = document.documentElement.offsetHeight - 1000;
            if (scrollPosition >= threshold && hasNextPage && !isLoading) {
                loadMoreServices();
            }
        }, 100);
    });
}

function initializeSaveToggle() {
    window.toggleSaveService = function (event, serviceId) {
        event.preventDefault();
        event.stopPropagation();

        const button = event.target.closest('.save-button') || event.target.closest('.save-service-btn');
        if (!button) return;

        const icon             = button.querySelector('i');
        const saveText         = button.querySelector('.save-text');
        const originalIconClass = icon.className;
        const originalText     = saveText ? saveText.textContent : '';

        button.disabled  = true;
        icon.className   = 'bi bi-spinner spinner-border spinner-border-sm';
        if (saveText) saveText.textContent = 'Saving...';

        fetch('/services/toggle-save/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: 'service_id=' + serviceId
        })
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (data.status === 'saved') {
                icon.className = 'bi bi-bookmark-fill';
                if (saveText) saveText.textContent = 'Saved';
                button.classList.add('saved', 'saved-state');
                button.setAttribute('data-saved', 'true');
                button.title = 'Remove from saved';
                showNotification('Service saved successfully', 'success');
            } else if (data.status === 'removed') {
                icon.className = 'bi bi-bookmark';
                if (saveText) saveText.textContent = 'Save';
                button.classList.remove('saved', 'saved-state');
                button.setAttribute('data-saved', 'false');
                button.title = 'Save this service';
                showNotification('Service removed from saved', 'info');
            } else {
                throw new Error(data.message || 'Unknown error');
            }
        })
        .catch(function (error) {
            console.error('Error toggling save state:', error);
            icon.className = originalIconClass;
            if (saveText) saveText.textContent = originalText;
            showNotification('Error saving service. Please try again.', 'error');
        })
        .finally(function () {
            button.disabled = false;
        });
    };
}

function initializeInquiryFunctionality() {
    const inquiryForm = document.getElementById('inquiryForm');
    if (!inquiryForm) return;

    inquiryForm.addEventListener('submit', function (e) {
        e.preventDefault();

        const submitBtn    = inquiryForm.querySelector('[type="submit"]');
        const originalHTML = submitBtn.innerHTML;

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Sending...';

        let errorDiv = document.getElementById('inquiryFormError');
        if (errorDiv) {
            errorDiv.classList.add('d-none');
            errorDiv.textContent = '';
        }

        let redirecting = false;

        fetch(inquiryForm.action, {
            method: 'POST',
            body: new FormData(inquiryForm),
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (data.success && data.redirect) {
                showNotification('Inquiry sent successfully!', 'success');
                redirecting = true;

                const modal = document.getElementById('inquiryModal');
                if (modal) {
                    let bsModal = bootstrap.Modal.getInstance(modal);
                    if (!bsModal) bsModal = new bootstrap.Modal(modal);
                    bsModal.hide();
                }

                setTimeout(function () {
                    window.location.href = data.redirect;
                }, 1000);
            } else {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalHTML;

                if (data.errors && errorDiv) {
                    errorDiv.textContent = Object.values(data.errors).flat().join(' ');
                    errorDiv.classList.remove('d-none');
                } else {
                    showNotification(data.error || 'Error sending inquiry. Please try again.', 'error');
                }
            }
        })
        .catch(function () {
            if (redirecting) return;
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHTML;
            showNotification('Error sending inquiry. Please try again.', 'error');
        });
    });
}

function initializeMessageFunctionality() {
    const messageForm = document.getElementById('messageForm');
    if (!messageForm) return;

    messageForm.addEventListener('submit', function (e) {
        e.preventDefault();

        const submitBtn    = messageForm.querySelector('[type="submit"]');
        const originalHTML = submitBtn.innerHTML;

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Sending...';

        let redirecting = false;

        fetch(messageForm.action, {
            method: 'POST',
            body: new FormData(messageForm),
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (data.success && data.redirect) {
                showNotification('Message sent!', 'success');
                redirecting = true;

                const modal = document.getElementById('messageModal');
                if (modal) {
                    let bsModal = bootstrap.Modal.getInstance(modal);
                    if (!bsModal) bsModal = new bootstrap.Modal(modal);
                    bsModal.hide();
                }

                setTimeout(function () {
                    window.location.href = data.redirect;
                }, 800);
            } else {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalHTML;

                if (data.errors) {
                    displayFormErrors(data.errors);
                } else {
                    showNotification(data.error || 'Error sending message. Please try again.', 'error');
                }
            }
            messageForm.reset();
        })
        .catch(function () {
            if (redirecting) return;
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHTML;
            showNotification('Error sending message. Please try again.', 'error');
        });
    });
}

function initializeSortControls() {
    const sortSelect = document.getElementById('sortSelect');
    if (!sortSelect) return;

    sortSelect.addEventListener('change', function () {
        const url       = new URL(window.location.href);
        const sortValue = this.value;

        if (sortValue === 'smart') {
            url.searchParams.delete('sort');
        } else {
            url.searchParams.set('sort', sortValue);
        }
        url.searchParams.delete('page');
        window.location.href = url.toString();
    });
}

function initializeTooltips() {
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
        if (!el._tooltip) {
            el._tooltip = new bootstrap.Tooltip(el, { delay: { show: 500, hide: 100 } });
        }
    });
}

function initializeServiceCardInteractions() {
    document.addEventListener('click', function (e) {
        const serviceCard = e.target.closest('.service-card');
        if (!serviceCard) return;

        if (e.target.closest('.save-button, .btn-service-action, .provider-link, .service-actions-overlay')) {
            return;
        }

        const titleLink = serviceCard.querySelector('.service-title-link');
        if (titleLink) {
            window.location.href = titleLink.href;
        }
    });
}

function initializeLoadMoreReviews() {
    const loadMoreBtn = document.getElementById('loadMoreReviews');
    if (!loadMoreBtn) return;

    loadMoreBtn.addEventListener('click', function () {
        const serviceId    = this.dataset.serviceId;
        const currentCount = document.querySelectorAll('.review-item').length;

        this.disabled   = true;
        this.innerHTML  = '<span class="spinner-border spinner-border-sm me-2"></span>Loading...';

        fetch('/services/' + serviceId + '/reviews/?offset=' + currentCount)
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (data.success && data.reviews_html) {
                const reviewsList = document.getElementById('reviewsList');
                reviewsList.insertAdjacentHTML('beforeend', data.reviews_html);
                if (!data.has_more) {
                    loadMoreBtn.style.display = 'none';
                }
            }
        })
        .catch(function (error) {
            console.error('Error loading reviews:', error);
            showNotification('Error loading more reviews', 'error');
        })
        .finally(function () {
            loadMoreBtn.disabled  = false;
            loadMoreBtn.innerHTML = 'Load More Reviews';
        });
    });
}

function initializePerformanceOptimizations() {
    if (!('IntersectionObserver' in window)) return;

    const cardObserver = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add('loaded');
                cardObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1, rootMargin: '50px' });

    document.querySelectorAll('.service-card').forEach(function (card) {
        cardObserver.observe(card);
    });
}

function initializeServiceStatusToggle() {
    window.toggleServiceStatus = function (serviceId, status) {
        const action = status === 'active' ? 'activate' : 'deactivate';
        if (!confirm('Are you sure you want to ' + action + ' this service?')) return;

        const form        = document.createElement('form');
        form.method       = 'POST';
        form.action       = '/services/' + serviceId + '/toggle-status/';

        const csrfInput   = document.createElement('input');
        csrfInput.type    = 'hidden';
        csrfInput.name    = 'csrfmiddlewaretoken';
        csrfInput.value   = getCsrfToken();

        const statusInput = document.createElement('input');
        statusInput.type  = 'hidden';
        statusInput.name  = 'status';
        statusInput.value = status;

        form.appendChild(csrfInput);
        form.appendChild(statusInput);
        document.body.appendChild(form);
        form.submit();
    };
}

function initializeRealTimeMessages() {
    const conversationId = document.body.dataset.conversationId;
    if (!conversationId) return;

    let lastMessageTime = new Date().toISOString();

    function checkForNewMessages() {
        fetch('/services/conversation/' + conversationId + '/messages/?after=' + lastMessageTime, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (data.success && data.messages && data.messages.length > 0) {
                const container = document.getElementById('messagesContainer');
                if (container) {
                    data.messages.forEach(function (message) {
                        container.insertAdjacentHTML('beforeend', createMessageBubble(message));
                        lastMessageTime = message.timestamp;
                    });
                    container.scrollTop = container.scrollHeight;
                }
            }
        })
        .catch(function (error) {
            console.error('Error checking for new messages:', error);
        });
    }

    setInterval(checkForNewMessages, 5000);
}

function createMessageBubble(message) {
    const cls = message.is_own ? 'message-bubble own' : 'message-bubble other';
    return (
        '<div class="' + cls + '">' +
            '<div class="message-content">' + message.content + '</div>' +
            '<div class="message-time">' + formatMessageTime(message.timestamp) + '</div>' +
        '</div>'
    );
}

function formatMessageTime(timestamp) {
    const date           = new Date(timestamp);
    const diffInMinutes  = Math.floor((Date.now() - date) / 60000);

    if (diffInMinutes < 1)    return 'Just now';
    if (diffInMinutes < 60)   return diffInMinutes + 'm ago';
    if (diffInMinutes < 1440) return Math.floor(diffInMinutes / 60) + 'h ago';
    return date.toLocaleDateString();
}

function displayFormErrors(errors) {
    document.querySelectorAll('.invalid-feedback').forEach(function (el) { el.remove(); });
    document.querySelectorAll('.is-invalid').forEach(function (el) { el.classList.remove('is-invalid'); });

    Object.keys(errors).forEach(function (fieldName) {
        const field = document.querySelector('[name="' + fieldName + '"]');
        if (field) {
            field.classList.add('is-invalid');
            const errorDiv       = document.createElement('div');
            errorDiv.className   = 'invalid-feedback d-block';
            errorDiv.textContent = errors[fieldName][0];
            field.parentNode.appendChild(errorDiv);
        }
    });
}

function showNotification(message, type) {
    type = type || 'info';

    const toast = document.createElement('div');
    toast.className = 'toast align-items-center text-white bg-' + type + ' border-0';
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    toast.innerHTML =
        '<div class="d-flex">' +
            '<div class="toast-body">' +
                '<i class="bi bi-' + getIconForType(type) + ' me-2"></i>' + message +
            '</div>' +
            '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>' +
        '</div>';

    let container = document.querySelector('.toast-container');
    if (!container) {
        container           = document.createElement('div');
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '1055';
        document.body.appendChild(container);
    }

    container.appendChild(toast);

    const bsToast = new bootstrap.Toast(toast, { delay: 4000 });
    bsToast.show();
    toast.addEventListener('hidden.bs.toast', function () { toast.remove(); });
}

function getIconForType(type) {
    var icons = {
        success: 'check-circle-fill',
        error:   'exclamation-triangle-fill',
        danger:  'exclamation-triangle-fill',
        warning: 'exclamation-triangle-fill',
        info:    'info-circle-fill'
    };
    return icons[type] || 'info-circle-fill';
}

function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content');

    var input = document.querySelector('[name="csrfmiddlewaretoken"]');
    if (input) return input.value;

    return getCookie('csrftoken') || '';
}

function getCookie(name) {
    if (!document.cookie) return null;
    var match = document.cookie.split(';').find(function (c) {
        return c.trim().startsWith(name + '=');
    });
    return match ? decodeURIComponent(match.trim().substring(name.length + 1)) : null;
}