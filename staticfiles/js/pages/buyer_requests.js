document.addEventListener('DOMContentLoaded', function() {
    // Initialize page functionality
    initializeRequestListPage();
    initializeRequestFilters();
    // NOTE: initializeSidebarFilters() removed — the unified sidebar (.sidebar-filter-form)
    // manages its own events via its embedded <script>. No duplicate listeners needed here.
    initializeInfiniteScroll();
    initializeSaveToggle();
    initializeTooltips();
    initializeBumpFunctionality();
    initializeResponseModal();
    initializeSortControls();
    // Consolidate duplicate DOMContentLoaded registrations
    initializeRequestCardInteractions();
    initializePerformanceOptimizations();
    handleAccessLimitModal();
});

// Request List Page Initialization
function initializeRequestListPage() {
    const requestsGrid = document.getElementById('requests-grid');
    const searchRequestsGrid = document.getElementById('search-requests-grid');
    
    if (requestsGrid || searchRequestsGrid) {
        console.log('Buyer requests page initialized');
        
        // Handle category pills clicks
        const categoryPills = document.querySelectorAll('.category-pill');
        categoryPills.forEach(pill => {
            pill.addEventListener('click', function(e) {
                // Add loading state
                pill.style.opacity = '0.7';
                setTimeout(() => {
                    pill.style.opacity = '1';
                }, 500);
            });
        });
        
        // Handle action buttons
        const actionButtons = document.querySelectorAll('.action-btn');
        actionButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                if (!button.href) return;
                
                // Add loading state
                const originalContent = button.innerHTML;
                button.innerHTML = '<div class="spinner-border spinner-border-sm me-2" role="status"></div>Loading...';
                button.style.pointerEvents = 'none';
                
                // Restore after navigation
                setTimeout(() => {
                    button.innerHTML = originalContent;
                    button.style.pointerEvents = 'auto';
                }, 2000);
            });
        });
    }
}

// Filter System
function initializeRequestFilters() {
    const filterForm = document.getElementById('dropdownFilterForm');
    const searchForm = document.getElementById('advancedSearchForm');
    const clearFiltersBtn = document.getElementById('clearDropdownFilters');
    const clearFiltersEmptyBtn = document.getElementById('clearFiltersEmpty');
    
    if (filterForm) {
        // Handle filter changes
        const filterSelects = filterForm.querySelectorAll('.filter-select');
        filterSelects.forEach(select => {
            select.addEventListener('change', function() {
                // Auto-submit form on filter change
                setTimeout(() => {
                    filterForm.submit();
                }, 100);
            });
        });
        
        // State/LGA dependency handling
        const stateSelect = document.getElementById('dropdown_state');
        const lgaSelect = document.getElementById('dropdown_lga');
        
        if (stateSelect && lgaSelect) {
            stateSelect.addEventListener('change', function() {
                const stateId = this.value;
                lgaSelect.innerHTML = '<option value="">All LGAs</option>';
                lgaSelect.disabled = !stateId;
                
                if (stateId) {
                    // FIX: use the same API endpoint as the unified sidebar
                    fetch(`/api/lgas/${stateId}/`)
                        .then(response => response.json())
                        .then(data => {
                            data.forEach(lga => {
                                const option = document.createElement('option');
                                option.value = lga.id;
                                option.textContent = lga.name;
                                lgaSelect.appendChild(option);
                            });
                            lgaSelect.disabled = false;
                        })
                        .catch(error => {
                            console.error('Error loading LGAs:', error);
                            showNotification('Error loading LGAs', 'error');
                        });
                }
            });
        }
        
        // Clear filters
        if (clearFiltersBtn) {
            clearFiltersBtn.addEventListener('click', function() {
                // Reset all filters
                filterSelects.forEach(select => {
                    select.selectedIndex = 0;
                });
                
                // Submit form to clear filters
                setTimeout(() => {
                    filterForm.submit();
                }, 100);
            });
        }
    }
    
    if (searchForm) {
        // Handle advanced search form
        const categorySelect = searchForm.querySelector('[name="category"]');
        const subcategorySelect = searchForm.querySelector('[name="subcategory"]');
        const brandSelect = searchForm.querySelector('[name="brand"]');
        
        if (categorySelect && subcategorySelect && brandSelect) {
            // Category change handler
            categorySelect.addEventListener('change', function() {
                const categoryId = this.value;
                subcategorySelect.innerHTML = '<option value="">All Subcategories</option>';
                brandSelect.innerHTML = '<option value="">All Brands</option>';
                
                if (categoryId) {
                    loadSubcategories(categoryId, subcategorySelect);
                }
            });
            
            // Subcategory change handler
            subcategorySelect.addEventListener('change', function() {
                const subcategoryId = this.value;
                brandSelect.innerHTML = '<option value="">All Brands</option>';
                
                if (subcategoryId) {
                    loadBrands(subcategoryId, brandSelect);
                }
            });
        }
        
        // Filter counter
        updateActiveFiltersCount();
        searchForm.addEventListener('change', updateActiveFiltersCount);
    }
    
    // Clear filters for empty state
    if (clearFiltersEmptyBtn) {
        clearFiltersEmptyBtn.addEventListener('click', function() {
            const currentUrl = new URL(window.location.href);
            currentUrl.search = '';
            window.location.href = currentUrl.toString();
        });
    }
}

// Active filters counter
function updateActiveFiltersCount() {
    const filterBadge = document.getElementById('activeFiltersCount');
    if (!filterBadge) return;
    
    const form = document.getElementById('advancedSearchForm');
    if (!form) return;
    
    let activeCount = 0;
    const formData = new FormData(form);
    
    for (let [key, value] of formData.entries()) {
        if (value && value.trim() && key !== 'query') {
            activeCount++;
        }
    }
    
    filterBadge.textContent = activeCount;
    filterBadge.style.display = activeCount > 0 ? 'inline-block' : 'none';
}

// Helper functions for loading dependent dropdowns
function loadSubcategories(categoryId, subcategorySelect) {
    fetch(`/ajax/load-subcategories/?category=${categoryId}`)
        .then(response => response.json())
        .then(data => {
            data.forEach(subcategory => {
                const option = document.createElement('option');
                option.value = subcategory.id;
                option.textContent = subcategory.name;
                subcategorySelect.appendChild(option);
            });
        })
        .catch(error => {
            console.error('Error loading subcategories:', error);
        });
}

function loadBrands(subcategoryId, brandSelect) {
    fetch(`/ajax/load-brands/?subcategory=${subcategoryId}`)
        .then(response => response.json())
        .then(data => {
            data.forEach(brand => {
                const option = document.createElement('option');
                option.value = brand.id;
                option.textContent = brand.name;
                brandSelect.appendChild(option);
            });
        })
        .catch(error => {
            console.error('Error loading brands:', error);
        });
}

// Infinite Scroll for Request Lists
function initializeInfiniteScroll() {
    const loadingIndicator = document.getElementById('loading-indicator') || document.getElementById('search-loading-indicator');
    const endOfResults = document.getElementById('end-of-results') || document.getElementById('search-end-of-results');
    const requestsGrid = document.getElementById('requests-grid') || document.getElementById('search-requests-grid');
    
    if (!requestsGrid || !loadingIndicator || !endOfResults) return;
    
    let isLoading = false;
    let hasNextPage = true;
    let currentPage = 1;
    
    // Get pagination data
    const paginationData = document.getElementById('pagination-data');
    if (paginationData) {
        try {
            const data = JSON.parse(paginationData.textContent);
            currentPage = data.current_page || 1;
            hasNextPage = data.has_next || false;
        } catch (e) {
            console.error('Error parsing pagination data:', e);
        }
    }
    
    function loadMoreRequests() {
        if (isLoading || !hasNextPage) return;
        
        isLoading = true;
        loadingIndicator.style.display = 'block';
        
        const nextPage = currentPage + 1;
        const currentUrl = new URL(window.location.href);
        currentUrl.searchParams.set('page', nextPage);
        
        fetch(currentUrl.toString(), {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.html) {
                // Create temporary container to parse HTML
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = data.html;
                
                // Extract request cards
                const newCards = tempDiv.querySelectorAll('.col');
                newCards.forEach(card => {
                    requestsGrid.appendChild(card);
                });
                
                // Update pagination info
                currentPage = nextPage;
                hasNextPage = data.has_next;
                
                // Initialize tooltips for new cards
                initializeTooltips();
                
                if (!hasNextPage) {
                    endOfResults.style.display = 'block';
                }
            } else {
                hasNextPage = false;
                endOfResults.style.display = 'block';
            }
        })
        .catch(error => {
            console.error('Error loading more requests:', error);
            showNotification('Error loading more requests', 'error');
        })
        .finally(() => {
            isLoading = false;
            loadingIndicator.style.display = 'none';
        });
    }
    
    // Scroll event listener
    let scrollTimeout;
    window.addEventListener('scroll', function() {
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(() => {
            const scrollPosition = window.innerHeight + window.scrollY;
            const threshold = document.documentElement.offsetHeight - 1000;
            
            if (scrollPosition >= threshold && hasNextPage && !isLoading) {
                loadMoreRequests();
            }
        }, 100);
    });
}

// Save/Unsave Request Toggle
function initializeSaveToggle() {
    window.toggleSaveRequest = function(event, requestId) {
        event.preventDefault();
        event.stopPropagation();
        
        const button = event.target.closest('.save-button') || event.target.closest('.save-request-btn');
        if (!button) return;
        
        const icon = button.querySelector('i');
        const saveText = button.querySelector('.save-text');
        const originalIconClass = icon.className;
        const originalText = saveText ? saveText.textContent : '';
        
        // Add loading state
        button.disabled = true;
        icon.className = 'bi bi-spinner spinner-border spinner-border-sm';
        if (saveText) saveText.textContent = 'Saving...';
        
        fetch('/buyer-requests/toggle-save/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: `request_id=${requestId}`
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'saved') {
                icon.className = 'bi bi-bookmark-fill';
                if (saveText) saveText.textContent = 'Saved';
                button.classList.add('saved', 'saved-state');
                button.setAttribute('data-saved', 'true');
                button.title = 'Remove from saved';
                showNotification('Request saved successfully', 'success');
            } else if (data.status === 'removed') {
                icon.className = 'bi bi-bookmark';
                if (saveText) saveText.textContent = 'Save';
                button.classList.remove('saved', 'saved-state');
                button.setAttribute('data-saved', 'false');
                button.title = 'Save this request';
                showNotification('Request removed from saved', 'info');
            } else {
                throw new Error(data.message || 'Unknown error');
            }
        })
        .catch(error => {
            console.error('Error toggling save state:', error);
            icon.className = originalIconClass;
            if (saveText) saveText.textContent = originalText;
            showNotification('Error saving request. Please try again.', 'error');
        })
        .finally(() => {
            button.disabled = false;
        });
    };
}

// Bump Request Functionality
function initializeBumpFunctionality() {
    window.bumpRequest = function(requestId) {
        if (!confirm('Are you sure you want to bump this request to the top? You can only bump once every 24 hours.')) {
            return;
        }
        
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = `/buyer-requests/${requestId}/bump/`;
        
        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrfmiddlewaretoken';
        csrfInput.value = getCsrfToken();
        
        form.appendChild(csrfInput);
        document.body.appendChild(form);
        form.submit();
    };
}

// Response Modal Handling
// buyer_requests.js — replace initializeResponseModal() (lines 398–449)

function initializeResponseModal() {
    const responseModal = document.getElementById('responseModal');
    const responseForm  = document.getElementById('responseForm');

    if (!responseModal || !responseForm) return;

    responseForm.addEventListener('submit', function (e) {
        e.preventDefault();

        const submitBtn  = responseForm.querySelector('[type="submit"]');
        const originalHTML = submitBtn.innerHTML;

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Sending...';

        // Error display element inside the modal
        let errorDiv = document.getElementById('responseFormErrors');
        if (errorDiv) {
            errorDiv.classList.add('d-none');
            errorDiv.textContent = '';
        }

        let redirecting = false;

        fetch(responseForm.action, {
            method: 'POST',
            body: new FormData(responseForm),
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.redirect) {
                showNotification('Response sent successfully!', 'success');
                redirecting = true;

                // Safely get or create the Bootstrap modal instance
                const bsModal = bootstrap.Modal.getInstance(responseModal)
                             || new bootstrap.Modal(responseModal);

                // Navigate to conversation after modal finishes hiding
                responseModal.addEventListener('hidden.bs.modal', function () {
                    window.location.href = data.redirect;
                }, { once: true });

                bsModal.hide();
            } else {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalHTML;

                if (data.errors) {
                    displayFormErrors(data.errors);
                    // Also surface errors in the modal error div if present
                    if (errorDiv) {
                        let msg = '';
                        Object.entries(data.errors).forEach(([field, errs]) => {
                            msg += errs.join(' ') + ' ';
                        });
                        errorDiv.textContent = msg.trim();
                        errorDiv.classList.remove('d-none');
                    }
                } else {
                    const msg = data.error || 'An error occurred. Please try again.';
                    showNotification(msg, 'error');
                    if (errorDiv) {
                        errorDiv.textContent = msg;
                        errorDiv.classList.remove('d-none');
                    }
                }
            }
        })
        .catch(function () {
            if (redirecting) return; // page is navigating — ignore
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHTML;
            showNotification('Error sending response. Please try again.', 'error');
        });
    });
}

// Sort Controls
function initializeSortControls() {
    const sortSelect = document.getElementById('sortSelect');
    const searchSortSelect = document.getElementById('searchSortSelect');
    
    function handleSortChange(selectElement) {
        if (!selectElement) return;
        
        selectElement.addEventListener('change', function() {
            const currentUrl = new URL(window.location.href);
            const sortValue = this.value;
            
            if (sortValue === 'smart') {
                currentUrl.searchParams.delete('sort');
            } else {
                currentUrl.searchParams.set('sort', sortValue);
            }
            
            // Maintain current page filters
            window.location.href = currentUrl.toString();
        });
    }
    
    handleSortChange(sortSelect);
    handleSortChange(searchSortSelect);
}

// Initialize Bootstrap Tooltips
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        if (!tooltipTriggerEl._tooltip) {
            tooltipTriggerEl._tooltip = new bootstrap.Tooltip(tooltipTriggerEl, {
                delay: { show: 500, hide: 100 }
            });
        }
        return tooltipTriggerEl._tooltip;
    });
}

// Form Error Display
function displayFormErrors(errors) {
    // Clear previous errors
    document.querySelectorAll('.invalid-feedback').forEach(el => el.remove());
    document.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
    
    // Display new errors
    Object.keys(errors).forEach(fieldName => {
        const field = document.querySelector(`[name="${fieldName}"]`);
        if (field) {
            field.classList.add('is-invalid');
            
            const errorDiv = document.createElement('div');
            errorDiv.className = 'invalid-feedback d-block';
            errorDiv.textContent = errors[fieldName][0]; // Show first error
            
            field.parentNode.appendChild(errorDiv);
        }
    });
}

// Notification System
function showNotification(message, type = 'info') {
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="bi bi-${getIconForType(type)} me-2"></i>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    
    // Add to container
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '1055';
        document.body.appendChild(container);
    }
    
    container.appendChild(toast);
    
    // Show toast
    const bsToast = new bootstrap.Toast(toast, { delay: 4000 });
    bsToast.show();
    
    // Remove from DOM after hiding
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

function getIconForType(type) {
    const icons = {
        'success': 'check-circle-fill',
        'error': 'exclamation-triangle-fill',
        'danger': 'exclamation-triangle-fill',
        'warning': 'exclamation-triangle-fill',
        'info': 'info-circle-fill'
    };
    return icons[type] || 'info-circle-fill';
}

// Utility Functions
function getCsrfToken() {
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    if (csrfMeta) {
        return csrfMeta.getAttribute('content');
    }
    
    const csrfInput = document.querySelector('[name="csrfmiddlewaretoken"]');
    if (csrfInput) {
        return csrfInput.value;
    }
    
    const csrfCookie = getCookie('csrftoken');
    if (csrfCookie) {
        return csrfCookie;
    }
    
    console.warn('CSRF token not found');
    return '';
}

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

// Request Card Interactions
function initializeRequestCardInteractions() {
    // Handle request card clicks
    document.addEventListener('click', function(e) {
        const requestCard = e.target.closest('.request-card');
        if (!requestCard) return;
        
        // Don't trigger if clicking on interactive elements
        if (e.target.closest('.save-button, .btn-request-action, .buyer-link, .request-actions-overlay')) {
            return;
        }
        
        // Get request URL
        const titleLink = requestCard.querySelector('.request-title-link');
        if (titleLink) {
            window.location.href = titleLink.href;
        }
    });
    
    // Handle urgent request animations
    const urgentRequests = document.querySelectorAll('.urgent-request');
    urgentRequests.forEach(card => {
        // Add subtle pulsing animation for urgent requests
        card.style.animation = 'subtle-pulse 2s ease-in-out infinite';
    });
}

// NOTE: initializeRequestCardInteractions() is called from the main DOMContentLoaded above.

// Custom animations
const style = document.createElement('style');
style.textContent = `
    @keyframes subtle-pulse {
        0%, 100% { 
            box-shadow: 0 2px 8px rgba(220, 53, 69, 0.2); 
        }
        50% { 
            box-shadow: 0 4px 16px rgba(220, 53, 69, 0.4); 
        }
    }
    
    @keyframes request-card-hover {
        from { transform: translateY(0); }
        to { transform: translateY(-3px); }
    }
    
    .loading-state {
        opacity: 0.7;
        pointer-events: none;
        transition: opacity 0.3s ease;
    }
`;
document.head.appendChild(style);

// Access Limit Handling
function handleAccessLimitModal() {
    const accessLimitModal = document.getElementById('accessLimitModal');
    if (accessLimitModal) {
        const modal = new bootstrap.Modal(accessLimitModal);
        
        // Show modal if user has reached limit
        const dailyAccessCount = parseInt(document.body.dataset.dailyAccessCount || '0');
        const dailyAccessLimit = parseInt(document.body.dataset.dailyAccessLimit || '5');
        
        if (dailyAccessCount >= dailyAccessLimit) {
            // Show modal when trying to view requests
            document.addEventListener('click', function(e) {
                const requestLink = e.target.closest('a[href*="/buyer-requests/"]');
                if (requestLink && !requestLink.href.includes('/create/')) {
                    e.preventDefault();
                    modal.show();
                }
            });
        }
    }
}

// NOTE: handleAccessLimitModal() is called from the main DOMContentLoaded above.

// Performance optimizations
function initializePerformanceOptimizations() {
    // Lazy load request cards that are not in viewport
    const requestCards = document.querySelectorAll('.request-card');
    
    if ('IntersectionObserver' in window) {
        const cardObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const card = entry.target;
                    card.classList.add('loaded');
                    cardObserver.unobserve(card);
                }
            });
        }, { threshold: 0.1, rootMargin: '50px' });
        
        requestCards.forEach(card => {
            cardObserver.observe(card);
        });
    }
    
    // Debounce scroll events
    let ticking = false;
    function updateScrollState() {
        // Handle scroll-based animations or lazy loading
        ticking = false;
    }
    
    window.addEventListener('scroll', function() {
        if (!ticking) {
            requestAnimationFrame(updateScrollState);
            ticking = true;
        }
    });
}

// NOTE: initializePerformanceOptimizations() is called from the main DOMContentLoaded above.