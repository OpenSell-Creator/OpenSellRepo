document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Complete Product List System Initializing...');
    
    // =============== CONFIGURATION ===============
    const CONFIG = {
        loadThreshold: 500, // Pixels from bottom to trigger load
        debounceDelay: 250, // Scroll debounce delay
        retryAttempts: 3,   // Max retry attempts for failed requests
        debug: true         // Enable debug logging
    };
    
    // =============== STATE MANAGEMENT ===============
    const scrollState = {
        isLoading: false,
        hasMoreProducts: true,
        currentPage: 1,
        totalPages: 1,
        totalCount: 0,
        loadedCount: 0,
        retryCount: 0,
        initialized: false
    };
    
    let currentFilters = {};
    
    // =============== DOM ELEMENTS ===============
    const elements = {
        productsGrid: document.getElementById('products-grid'),
        loadingIndicator: document.getElementById('loading-indicator'),
        endOfResults: document.getElementById('end-of-results'),
        productsCountNumber: document.getElementById('products-count-number'),
        paginationData: document.getElementById('pagination-data'),
        sortSelect: document.getElementById('sortSelect'),
        
        // Filter form elements
        dropdownFilterForm: document.getElementById('dropdownFilterForm'),
        dropdownSubcategorySelect: document.getElementById('dropdown_subcategory'),
        dropdownBrandSelect: document.getElementById('dropdown_brand'),
        dropdownConditionSelect: document.getElementById('dropdown_condition'),
        dropdownPriceRangeSelect: document.getElementById('dropdown_price_range'),
        dropdownStateSelect: document.getElementById('dropdown_state'),
        dropdownLgaSelect: document.getElementById('dropdown_lga'),
        dropdownVerifiedBusinessSelect: document.getElementById('dropdown_verified_business'),
        clearDropdownFiltersBtn: document.getElementById('clearDropdownFilters')
    };
    
    // =============== UTILITY FUNCTIONS ===============
    function log(...args) {
        if (CONFIG.debug) {
            console.log('📜 [ProductList]', ...args);
        }
    }
    
    function error(...args) {
        console.error('❌ [ProductList]', ...args);
    }
    
    function warn(...args) {
        console.warn('⚠️ [ProductList]', ...args);
    }
    
    // =============== PAGINATION STATE INITIALIZATION ===============
    function initializePaginationState() {
        log('Initializing pagination state...');
        
        try {
            if (!elements.paginationData) {
                warn('No pagination data element found');
                return false;
            }
            
            const paginationData = JSON.parse(elements.paginationData.textContent);
            log('Raw pagination data:', paginationData);
            
            // Validate pagination data
            if (paginationData.total_count === undefined || paginationData.total_pages === undefined) {
                error('Invalid pagination data structure:', paginationData);
                return false;
            }
            
            // Update state from server data
            scrollState.currentPage = paginationData.current_page || 1;
            scrollState.totalPages = paginationData.total_pages || 1;
            scrollState.hasMoreProducts = paginationData.has_next || false;
            scrollState.totalCount = paginationData.total_count || 0;
            scrollState.loadedCount = paginationData.current_count || 0;
            
            // DEBUGGING: Log the exact calculation
            log(`Pagination Debug:
                - Current Page: ${scrollState.currentPage}
                - Total Pages: ${scrollState.totalPages}
                - Has Next: ${scrollState.hasMoreProducts}
                - Total Count: ${scrollState.totalCount}
                - Loaded Count: ${scrollState.loadedCount}
                - Can Load More: ${scrollState.currentPage < scrollState.totalPages}`);
            
            // Double-check the has_next calculation
            if (scrollState.currentPage >= scrollState.totalPages && scrollState.totalCount > scrollState.loadedCount) {
                warn('Pagination mismatch detected! Server says no more pages but count suggests otherwise');
                log('This indicates a duplicate product issue was likely fixed');
            }
            
            // Initialize UI based on state
            if (elements.endOfResults) {
                elements.endOfResults.style.display = 'none';
            }
            
            if (elements.loadingIndicator) {
                elements.loadingIndicator.style.display = 'none';
            }
            
            // Only show end of results if we have products but no more pages
            if (!scrollState.hasMoreProducts && scrollState.loadedCount > 0) {
                log('Initial state: No more products available, showing end message');
                showEndOfResults();
            } else if (scrollState.loadedCount === 0) {
                log('Initial state: No products found');
            } else {
                log('Initial state: More products available for loading');
            }
            
            scrollState.initialized = true;
            return true;
            
        } catch (e) {
            error('Failed to parse pagination data:', e);
            
            // Fallback: count products in DOM
            if (elements.productsGrid) {
                const productCount = elements.productsGrid.querySelectorAll('.col').length;
                scrollState.loadedCount = productCount;
                scrollState.hasMoreProducts = productCount >= 12; // Assume more if we have a full page
                log(`Fallback: Found ${productCount} products in DOM`);
            }
            
            return false;
        }
    }
    
    // =============== FILTER MANAGEMENT ===============
    function getCurrentFilters() {
        const urlParams = new URLSearchParams(window.location.search);
        const filters = {};
        
        for (const [key, value] of urlParams.entries()) {
            if (key !== 'page' && value.trim() !== '') {
                filters[key] = value;
            }
        }
        
        return filters;
    }
    
    function filtersChanged() {
        const newFilters = getCurrentFilters();
        const filtersString = JSON.stringify(newFilters);
        const currentFiltersString = JSON.stringify(currentFilters);
        
        if (filtersString !== currentFiltersString) {
            currentFilters = newFilters;
            return true;
        }
        return false;
    }
    
    function resetInfiniteScrollState() {
        log('🔄 Resetting infinite scroll state...');
        
        scrollState.isLoading = false;
        scrollState.hasMoreProducts = true;
        scrollState.currentPage = 1;
        scrollState.totalPages = 1;
        scrollState.retryCount = 0;
        scrollState.initialized = false;
        
        if (elements.endOfResults) elements.endOfResults.style.display = 'none';
        if (elements.loadingIndicator) elements.loadingIndicator.style.display = 'none';
        
        // Clear error messages
        const existingErrors = document.querySelectorAll('.infinite-scroll-error');
        existingErrors.forEach(error => error.remove());
        
        log('State reset complete');
    }
    
    // =============== PRICE RANGE HANDLING ===============
    function handlePriceRange(priceRange) {
        try {
            const existingMinPrice = elements.dropdownFilterForm.querySelector('input[name="min_price"]');
            const existingMaxPrice = elements.dropdownFilterForm.querySelector('input[name="max_price"]');
            
            if (existingMinPrice) existingMinPrice.remove();
            if (existingMaxPrice) existingMaxPrice.remove();

            if (priceRange) {
                const [minPrice, maxPrice] = priceRange.split('-');
                
                const minPriceInput = document.createElement('input');
                minPriceInput.type = 'hidden';
                minPriceInput.name = 'min_price';
                minPriceInput.value = minPrice;
                
                const maxPriceInput = document.createElement('input');
                maxPriceInput.type = 'hidden';
                maxPriceInput.name = 'max_price';
                maxPriceInput.value = maxPrice === '999999999' ? '' : maxPrice;
                
                elements.dropdownFilterForm.appendChild(minPriceInput);
                if (maxPrice !== '999999999') {
                    elements.dropdownFilterForm.appendChild(maxPriceInput);
                }
                
                log('Price range set:', minPrice, 'to', maxPrice);
            }
        } catch (error) {
            console.error('Error handling price range:', error);
        }
    }
    
    function submitFormSafely(delay = 100) {
        setTimeout(() => {
            try {
                log('Submitting filter form, resetting scroll state');
                resetInfiniteScrollState();
                elements.dropdownFilterForm.submit();
            } catch (error) {
                console.error('Error submitting form:', error);
            }
        }, delay);
    }
    
    // =============== URL AND PARAMETER MANAGEMENT ===============
    function buildNextPageUrl() {
        const nextPage = scrollState.currentPage + 1;
        const url = new URL(window.location.href);
        url.searchParams.set('page', nextPage);
        
        // Ensure all form parameters are included
        if (elements.dropdownFilterForm) {
            const formData = new FormData(elements.dropdownFilterForm);
            for (const [key, value] of formData.entries()) {
                if (value && key !== 'page') {
                    url.searchParams.set(key, value);
                }
            }
        }
        
        // Preserve current URL parameters
        const currentParams = new URLSearchParams(window.location.search);
        for (const [key, value] of currentParams.entries()) {
            if (key !== 'page' && value && !url.searchParams.has(key)) {
                url.searchParams.set(key, value);
            }
        }
        
        return url.toString();
    }
    
    // =============== UI MANAGEMENT ===============
    function showLoading() {
        if (elements.loadingIndicator) {
            elements.loadingIndicator.style.display = 'block';
        }
        scrollState.isLoading = true;
        log('Loading indicator shown');
    }
    
    function hideLoading() {
        if (elements.loadingIndicator) {
            elements.loadingIndicator.style.display = 'none';
        }
        scrollState.isLoading = false;
        log('Loading indicator hidden');
    }
    
    function showEndOfResults(message = null) {
        if (elements.endOfResults) {
            if (message) {
                const messageElement = elements.endOfResults.querySelector('p');
                if (messageElement) {
                    messageElement.textContent = message;
                }
            }
            elements.endOfResults.style.display = 'block';
            log('End of results shown');
        }
    }
    
    function updateProductCount() {
        if (elements.productsCountNumber && elements.productsGrid) {
            const currentCount = elements.productsGrid.querySelectorAll('.col').length;
            elements.productsCountNumber.textContent = currentCount;
            scrollState.loadedCount = currentCount;
            log(`Product count updated: ${currentCount}`);
        }
    }
    
    function showErrorMessage(message) {
        // Remove existing error messages
        const existingErrors = document.querySelectorAll('.infinite-scroll-error');
        existingErrors.forEach(error => error.remove());
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-warning alert-dismissible fade show infinite-scroll-error';
        errorDiv.style.marginTop = '1rem';
        errorDiv.innerHTML = `
            <i class="bi bi-exclamation-triangle-fill me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        if (elements.productsGrid && elements.productsGrid.parentNode) {
            elements.productsGrid.parentNode.insertBefore(
                errorDiv, 
                elements.loadingIndicator || elements.productsGrid.nextSibling
            );
        }
        
        // Auto-dismiss after 8 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.remove();
            }
        }, 8000);
        
        error('Error message shown:', message);
    }
    
    // =============== PRODUCT LOADING ===============
    async function loadMoreProducts() {
        log('🔄 loadMoreProducts() called');
        
        // Pre-flight checks
        if (!scrollState.initialized) {
            log('Not initialized yet, skipping load');
            return;
        }
        
        if (!elements.productsGrid) {
            warn('Products grid not found');
            return;
        }
        
        if (scrollState.isLoading) {
            log('Already loading, skipping');
            return;
        }
        
        if (!scrollState.hasMoreProducts) {
            log('No more products available');
            showEndOfResults();
            return;
        }
        
        if (scrollState.currentPage >= scrollState.totalPages) {
            log(`Already at last page (${scrollState.currentPage}/${scrollState.totalPages})`);
            scrollState.hasMoreProducts = false;
            showEndOfResults();
            return;
        }
        
        log(`Loading page ${scrollState.currentPage + 1}/${scrollState.totalPages}...`);
        
        showLoading();
        
        try {
            const url = buildNextPageUrl();
            log('Fetching URL:', url);
            
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json',
                    'Cache-Control': 'no-cache',
                }
            });
            
            log('Response status:', response.status);
            
            if (!response.ok) {
                if (response.status === 404) {
                    log('404 received, no more pages available');
                    scrollState.hasMoreProducts = false;
                    showEndOfResults();
                    return;
                }
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            log('AJAX response data:', data);
            
            if (data.success) {
                if (data.products_html && data.products_html.length > 0) {
                    await renderNewProducts(data.products_html);
                    
                    // Update state from server response
                    scrollState.currentPage = data.current_page || (scrollState.currentPage + 1);
                    scrollState.totalPages = data.total_pages || scrollState.totalPages;
                    scrollState.hasMoreProducts = data.has_more === true;
                    scrollState.totalCount = data.total_count || scrollState.totalCount;
                    
                    updateProductCount();
                    
                    log(`✅ Successfully loaded ${data.products_html.length} products`);
                    log('Updated state:', scrollState);
                    
                    // Reset retry count on success
                    scrollState.retryCount = 0;
                    
                    if (!scrollState.hasMoreProducts) {
                        showEndOfResults();
                    }
                } else {
                    log('No products in response');
                    scrollState.hasMoreProducts = false;
                    showEndOfResults();
                }
            } else {
                throw new Error(data.error || 'Server returned error response');
            }
            
        } catch (e) {
            error('Failed to load more products:', e);
            
            // Retry logic
            if (scrollState.retryCount < CONFIG.retryAttempts) {
                scrollState.retryCount++;
                log(`Retrying... (${scrollState.retryCount}/${CONFIG.retryAttempts})`);
                setTimeout(() => loadMoreProducts(), 2000 * scrollState.retryCount);
            } else {
                scrollState.hasMoreProducts = false;
                if (e.message.includes('404')) {
                    showEndOfResults('No more products available');
                } else {
                    showErrorMessage(`Failed to load more products: ${e.message}`);
                }
            }
            
        } finally {
            hideLoading();
        }
    }
    
    async function renderNewProducts(productsHtml) {
        log(`Rendering ${productsHtml.length} new products...`);
        
        for (let i = 0; i < productsHtml.length; i++) {
            const productHtml = productsHtml[i];
            
            try {
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = productHtml.trim();
                const productElement = tempDiv.firstElementChild;
                
                if (productElement) {
                    // Wrap in proper grid column
                    const colDiv = document.createElement('div');
                    colDiv.className = 'col';
                    colDiv.appendChild(productElement);
                    
                    // Add with animation delay
                    setTimeout(() => {
                        elements.productsGrid.appendChild(colDiv);
                        log(`Product ${i + 1} added to grid`);
                    }, i * 50); // 50ms delay between each product
                }
            } catch (e) {
                error(`Failed to render product ${i + 1}:`, e);
            }
        }
    }
    
    // =============== SCROLL DETECTION ===============
    function checkScroll() {
        if (!scrollState.initialized || scrollState.isLoading || !scrollState.hasMoreProducts) {
            return;
        }
        
        const scrollPosition = window.innerHeight + window.scrollY;
        const documentHeight = document.body.offsetHeight;
        const threshold = documentHeight - CONFIG.loadThreshold;
        
        if (CONFIG.debug && Math.random() < 0.01) { // Log occasionally to avoid spam
            log('Scroll check:', {
                scrollPosition,
                documentHeight,
                threshold,
                canTrigger: scrollPosition >= threshold
            });
        }
        
        if (scrollPosition >= threshold) {
            log('🎯 Scroll threshold reached! Triggering load...');
            loadMoreProducts();
        }
    }
    
    // Debounced scroll handler
    let scrollTimeout;
    function handleScroll() {
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(checkScroll, CONFIG.debounceDelay);
    }
    
    // =============== DROPDOWN FILTER HANDLERS ===============
    function handleFilterChange() {
        log('Filter changed:', this.id, this.value);
        if (this.id === 'dropdown_price_range') {
            handlePriceRange(this.value);
        }
        submitFormSafely();
    }
    
    function setupDropdownFilterHandlers() {
        if (!elements.dropdownFilterForm) return;
        
        const urlParams = new URLSearchParams(window.location.search);
        
        // Subcategory change handler
        if (elements.dropdownSubcategorySelect) {
            elements.dropdownSubcategorySelect.addEventListener('change', function() {
                const categorySlug = elements.dropdownFilterForm.querySelector('input[name="category"]').value;
                const subcategorySlug = this.value;
                
                log('Subcategory changed:', subcategorySlug);
                
                if (categorySlug) {
                    let apiUrl = `/api/brands/${categorySlug}/`;
                    if (subcategorySlug) {
                        apiUrl += `?subcategory=${subcategorySlug}`;
                    }
                    
                    fetch(apiUrl)
                        .then(response => {
                            if (!response.ok) throw new Error(`HTTP ${response.status}`);
                            return response.json();
                        })
                        .then(data => {
                            elements.dropdownBrandSelect.innerHTML = '<option value="">All Brands</option>';
                            data.forEach(brand => {
                                const option = document.createElement('option');
                                option.value = brand.slug;
                                option.textContent = `${brand.name}${brand.product_count ? ' (' + brand.product_count + ')' : ''}`;
                                elements.dropdownBrandSelect.appendChild(option);
                            });
                            log('Brands updated for subcategory');
                        })
                        .catch(error => {
                            console.error('Error fetching brands:', error);
                        });
                }
                
                submitFormSafely(200);
            });
        }
        
        // State change handler
        if (elements.dropdownStateSelect) {
            elements.dropdownStateSelect.addEventListener('change', function() {
                const stateId = this.value;
                log('State changed:', stateId);
                
                elements.dropdownLgaSelect.innerHTML = '<option value="">All LGAs</option>';
                elements.dropdownLgaSelect.value = '';
                
                if (stateId) {
                    elements.dropdownLgaSelect.disabled = false;
                    
                    fetch(`/api/lgas/${stateId}/`)
                        .then(response => {
                            if (!response.ok) throw new Error(`HTTP ${response.status}`);
                            return response.json();
                        })
                        .then(data => {
                            data.forEach(lga => {
                                const option = document.createElement('option');
                                option.value = lga.id;
                                option.textContent = lga.name;
                                elements.dropdownLgaSelect.appendChild(option);
                            });
                            
                            log('LGAs loaded for state');
                            submitFormSafely(100);
                        })
                        .catch(error => {
                            console.error('Error fetching LGAs:', error);
                            elements.dropdownLgaSelect.disabled = true;
                            submitFormSafely(100);
                        });
                } else {
                    elements.dropdownLgaSelect.disabled = true;
                    submitFormSafely(100);
                }
            });
        }
        
        // LGA change handler
        if (elements.dropdownLgaSelect) {
            elements.dropdownLgaSelect.addEventListener('change', function() {
                log('LGA changed:', this.value);
                submitFormSafely();
            });
        }
        
        // Verified Business change handler
        if (elements.dropdownVerifiedBusinessSelect) {
            elements.dropdownVerifiedBusinessSelect.addEventListener('change', function() {
                log('Verified business filter changed to:', this.value);
                submitFormSafely();
            });
        }
        
        // Add change listeners to all other filters
        [elements.dropdownBrandSelect, elements.dropdownConditionSelect, 
         elements.dropdownPriceRangeSelect, elements.dropdownVerifiedBusinessSelect].forEach(select => {
            if (select) {
                select.addEventListener('change', handleFilterChange);
            }
        });
        
        // Clear filters handler
        if (elements.clearDropdownFiltersBtn) {
            elements.clearDropdownFiltersBtn.addEventListener('click', function() {
                try {
                    log('Clearing all filters');
                    [elements.dropdownSubcategorySelect, elements.dropdownBrandSelect, 
                     elements.dropdownConditionSelect, elements.dropdownPriceRangeSelect, 
                     elements.dropdownStateSelect, elements.dropdownLgaSelect, 
                     elements.dropdownVerifiedBusinessSelect].forEach(select => {
                        if (select) {
                            select.value = '';
                        }
                    });

                    if (elements.dropdownLgaSelect) {
                        elements.dropdownLgaSelect.innerHTML = '<option value="">All LGAs</option>';
                        elements.dropdownLgaSelect.disabled = true;
                    }

                    const existingMinPrice = elements.dropdownFilterForm.querySelector('input[name="min_price"]');
                    const existingMaxPrice = elements.dropdownFilterForm.querySelector('input[name="max_price"]');
                    if (existingMinPrice) existingMinPrice.remove();
                    if (existingMaxPrice) existingMaxPrice.remove();

                    const categorySlug = elements.dropdownFilterForm.querySelector('input[name="category"]').value;
                    if (categorySlug && elements.dropdownBrandSelect) {
                        fetch(`/api/brands/${categorySlug}/`)
                            .then(response => {
                                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                                return response.json();
                            })
                            .then(data => {
                                elements.dropdownBrandSelect.innerHTML = '<option value="">All Brands</option>';
                                data.forEach(brand => {
                                    const option = document.createElement('option');
                                    option.value = brand.slug;
                                    option.textContent = `${brand.name}${brand.product_count ? ' (' + brand.product_count + ')' : ''}`;
                                    elements.dropdownBrandSelect.appendChild(option);
                                });
                                log('Brands reset to category default');
                            })
                            .catch(error => {
                                console.error('Error fetching brands:', error);
                            });
                    }

                    submitFormSafely(200);
                } catch (error) {
                    console.error('Error clearing filters:', error);
                }
            });
        }
        
        // Initialize price range on page load
        const currentPriceRange = elements.dropdownPriceRangeSelect ? elements.dropdownPriceRangeSelect.value : '';
        if (currentPriceRange) {
            handlePriceRange(currentPriceRange);
        }
        
        // Initialize location selections on page load
        function initializeLocationSelections() {
            try {
                const currentStateId = urlParams.get('state');
                const currentLgaId = urlParams.get('lga');
                
                if (currentStateId && elements.dropdownStateSelect) {
                    elements.dropdownStateSelect.value = currentStateId;
                    
                    if (elements.dropdownLgaSelect) {
                        elements.dropdownLgaSelect.disabled = false;
                        
                        fetch(`/api/lgas/${currentStateId}/`)
                            .then(response => {
                                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                                return response.json();
                            })
                            .then(data => {
                                elements.dropdownLgaSelect.innerHTML = '<option value="">All LGAs</option>';
                                data.forEach(lga => {
                                    const option = document.createElement('option');
                                    option.value = lga.id;
                                    option.textContent = lga.name;
                                    
                                    if (currentLgaId && lga.id.toString() === currentLgaId) {
                                        option.selected = true;
                                    }
                                    
                                    elements.dropdownLgaSelect.appendChild(option);
                                });
                                log('Location selections initialized');
                            })
                            .catch(error => {
                                console.error('Error fetching LGAs on page load:', error);
                                elements.dropdownLgaSelect.disabled = true;
                            });
                    }
                } else {
                    if (elements.dropdownLgaSelect) {
                        elements.dropdownLgaSelect.disabled = true;
                    }
                }
            } catch (error) {
                console.error('Error initializing location selections:', error);
            }
        }
        
        // Initialize verified business filter on page load
        function initializeVerifiedBusinessFilter() {
            try {
                const currentVerifiedBusiness = urlParams.get('verified_business');
                if (currentVerifiedBusiness && elements.dropdownVerifiedBusinessSelect) {
                    elements.dropdownVerifiedBusinessSelect.value = currentVerifiedBusiness;
                    log('Verified business filter initialized with:', currentVerifiedBusiness);
                }
            } catch (error) {
                console.error('Error initializing verified business filter:', error);
            }
        }
        
        initializeLocationSelections();
        initializeVerifiedBusinessFilter();
        
        // Monitor form submission for state reset
        elements.dropdownFilterForm.addEventListener('submit', function() {
            log('Form submitted, resetting infinite scroll state');
            resetInfiniteScrollState();
        });
    }
    
    // =============== SORT HANDLER ===============
    function setupSortHandler() {
        if (elements.sortSelect) {
            elements.sortSelect.addEventListener('change', function() {
                log('Sort changed to:', this.value);
                resetInfiniteScrollState();
                
                const currentUrl = new URL(window.location);
                currentUrl.searchParams.set('sort', this.value);
                currentUrl.searchParams.delete('page');
                window.location.href = currentUrl.toString();
            });
        }
    }
    
    // =============== INITIALIZATION ===============
    function initialize() {
        log('🎬 Starting complete product list initialization...');
        
        // Check required elements
        if (!elements.productsGrid) {
            warn('Products grid not found - infinite scroll disabled');
            return;
        }
        
        // Initialize pagination state
        if (!initializePaginationState()) {
            warn('Failed to initialize pagination state');
        }
        
        // Setup all event handlers
        setupDropdownFilterHandlers();
        setupSortHandler();
        
        // Initialize current filters
        currentFilters = getCurrentFilters();
        
        // Start scroll monitoring
        window.addEventListener('scroll', handleScroll, { passive: true });
        
        // Debug helper
        window.debugInfiniteScroll = function() {
            console.group('🔍 Product List Debug');
            console.log('Current state:', scrollState);
            console.log('Config:', CONFIG);
            console.log('Current filters:', currentFilters);
            console.log('Elements found:', Object.keys(elements).filter(key => elements[key]));
            console.log('Products in grid:', elements.productsGrid ? elements.productsGrid.querySelectorAll('.col').length : 'N/A');
            
            const scrollPos = window.innerHeight + window.scrollY;
            const docHeight = document.body.offsetHeight;
            console.log('Scroll info:', {
                position: scrollPos,
                documentHeight: docHeight,
                threshold: docHeight - CONFIG.loadThreshold,
                canTrigger: scrollPos >= (docHeight - CONFIG.loadThreshold)
            });
            console.groupEnd();
        };
        
        log('✅ Complete product list initialization complete!');
        log('Initial state:', scrollState);
        log('Current filters:', currentFilters);
        
        // Force a scroll check after a brief delay
        setTimeout(() => {
            log('🔍 Initial scroll check...');
            checkScroll();
        }, 1000);
    }
    
    // =============== START ===============
    initialize();
});