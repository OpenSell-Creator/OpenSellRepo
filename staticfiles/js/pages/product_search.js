document.addEventListener('DOMContentLoaded', function() {
    console.log('🔍 Complete Search System Initializing...');
    
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
        searchProductsGrid: document.getElementById('search-products-grid'),
        searchLoadingIndicator: document.getElementById('search-loading-indicator'),
        searchEndOfResults: document.getElementById('search-end-of-results'),
        searchProductsCount: document.getElementById('search-products-count'),
        paginationData: document.getElementById('pagination-data'),
        searchSortSelect: document.getElementById('searchSortSelect'),
        
        // Form elements
        form: document.getElementById('advancedSearchForm'),
        activeFiltersCount: document.getElementById('activeFiltersCount'),
        clearFiltersBtn: document.getElementById('clearFilters'),
        clearFiltersEmptyBtn: document.getElementById('clearFiltersEmpty'),
        
        // Filter form elements
        categorySelect: document.getElementById('id_category'),
        subcategorySelect: document.getElementById('id_subcategory'),
        brandSelect: document.getElementById('id_brand'),
        stateSelect: document.getElementById('id_state'),
        lgaSelect: document.getElementById('id_lga'),
        conditionSelect: document.getElementById('id_condition'),
        minPriceInput: document.getElementById('id_min_price'),
        maxPriceInput: document.getElementById('id_max_price'),
        queryInput: document.querySelector('[name="query"]'),
        verifiedBusinessSelect: document.querySelector('[name="verified_business"]')
    };
    
    // =============== UTILITY FUNCTIONS ===============
    function log(...args) {
        if (CONFIG.debug) {
            console.log('🔍 [SearchSystem]', ...args);
        }
    }
    
    function error(...args) {
        console.error('❌ [SearchSystem]', ...args);
    }
    
    function warn(...args) {
        console.warn('⚠️ [SearchSystem]', ...args);
    }
    
    // =============== PAGINATION STATE INITIALIZATION ===============
    function initializePaginationState() {
        log('Initializing search pagination state...');
        
        try {
            if (!elements.paginationData) {
                warn('No pagination data element found');
                return false;
            }
            
            const paginationData = JSON.parse(elements.paginationData.textContent);
            log('Raw search pagination data:', paginationData);
            
            // Update state from server data
            scrollState.currentPage = paginationData.current_page || 1;
            scrollState.totalPages = paginationData.total_pages || 1;
            scrollState.hasMoreProducts = paginationData.has_next || false;
            scrollState.totalCount = paginationData.total_count || 0;
            scrollState.loadedCount = paginationData.current_count || 0;
            
            log('Updated search scroll state:', scrollState);
            
            // Initialize UI based on state
            if (elements.searchEndOfResults) {
                elements.searchEndOfResults.style.display = 'none';
            }
            
            if (elements.searchLoadingIndicator) {
                elements.searchLoadingIndicator.style.display = 'none';
            }
            
            // Only show end of results if we have products but no more pages
            if (!scrollState.hasMoreProducts && scrollState.loadedCount > 0) {
                log('Search initial state: No more products available, showing end message');
                showEndOfResults();
            } else if (scrollState.loadedCount === 0) {
                log('Search initial state: No products found');
            } else {
                log('Search initial state: More products available for loading');
            }
            
            scrollState.initialized = true;
            return true;
            
        } catch (e) {
            error('Failed to parse search pagination data:', e);
            
            // Fallback: count products in DOM
            if (elements.searchProductsGrid) {
                const productCount = elements.searchProductsGrid.querySelectorAll('.col-6').length;
                scrollState.loadedCount = productCount;
                scrollState.hasMoreProducts = productCount >= 12;
                log(`Search fallback: Found ${productCount} products in DOM`);
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
        log('🔄 Resetting search infinite scroll state...');
        
        scrollState.isLoading = false;
        scrollState.hasMoreProducts = true;
        scrollState.currentPage = 1;
        scrollState.totalPages = 1;
        scrollState.retryCount = 0;
        scrollState.initialized = false;
        
        if (elements.searchEndOfResults) elements.searchEndOfResults.style.display = 'none';
        if (elements.searchLoadingIndicator) elements.searchLoadingIndicator.style.display = 'none';
        
        // Clear error messages
        const existingErrors = document.querySelectorAll('.search-error-message, .infinite-scroll-error');
        existingErrors.forEach(error => error.remove());
        
        log('Search state reset complete');
    }
    
    // =============== ACTIVE FILTERS MANAGEMENT ===============
    function updateActiveFiltersCount() {
        if (!elements.form || !elements.activeFiltersCount) return;
        
        let count = 0;
        const formElements = elements.form.elements;
        
        for (let element of formElements) {
            if (element.type !== 'submit' && 
                element.type !== 'button' && 
                element.value && 
                element.value.trim() !== '' &&
                element.name !== 'query') { // Don't count main search query
                count++;
            }
        }
        
        elements.activeFiltersCount.textContent = count;
        elements.activeFiltersCount.style.display = count > 0 ? 'flex' : 'none';
        
        log(`Active filters count updated: ${count}`);
    }
    
    function clearAllFilters() {
        if (!elements.form) return;
        
        log('Clearing all search filters');
        const formElements = elements.form.elements;
        for (let element of formElements) {
            if (element.type !== 'submit' && element.type !== 'button') {
                if (element.name !== 'query') { // Preserve search query
                    element.value = '';
                }
            }
        }
        
        // Reset dependent fields
        if (elements.subcategorySelect) {
            elements.subcategorySelect.innerHTML = '<option value="">All Subcategories</option>';
            elements.subcategorySelect.disabled = true;
        }
        if (elements.brandSelect) {
            elements.brandSelect.innerHTML = '<option value="">All Brands</option>';
            elements.brandSelect.disabled = true;
        }
        if (elements.lgaSelect) {
            elements.lgaSelect.innerHTML = '<option value="">All LGAs</option>';
            elements.lgaSelect.disabled = true;
        }
        
        updateActiveFiltersCount();
    }
    
    // =============== URL AND PARAMETER MANAGEMENT ===============
    function getAllFormParams() {
        if (!elements.form) return new URLSearchParams();
        
        const formData = new FormData(elements.form);
        const params = new URLSearchParams();
        
        // Add all form fields that have values
        for (const [key, value] of formData.entries()) {
            if (value.trim() !== '') {
                params.append(key, value);
            }
        }
        
        // Add current sort parameter if not in form
        const currentSort = new URLSearchParams(window.location.search).get('sort');
        if (currentSort && !params.has('sort')) {
            params.set('sort', currentSort);
        }
        
        return params;
    }
    
    function buildNextPageUrl() {
        const nextPage = scrollState.currentPage + 1;
        const params = getAllFormParams();
        params.set('page', nextPage);
        
        return `${window.location.pathname}?${params.toString()}`;
    }
    
    // =============== UI MANAGEMENT ===============
    function showLoading() {
        if (elements.searchLoadingIndicator) {
            elements.searchLoadingIndicator.style.display = 'block';
        }
        scrollState.isLoading = true;
        log('Search loading indicator shown');
    }
    
    function hideLoading() {
        if (elements.searchLoadingIndicator) {
            elements.searchLoadingIndicator.style.display = 'none';
        }
        scrollState.isLoading = false;
        log('Search loading indicator hidden');
    }
    
    function showEndOfResults(message = null) {
        if (elements.searchEndOfResults) {
            if (message) {
                const messageElement = elements.searchEndOfResults.querySelector('p');
                if (messageElement) {
                    messageElement.textContent = message;
                }
            }
            elements.searchEndOfResults.style.display = 'block';
            log('Search end of results shown');
        }
    }
    
    function updateProductCount() {
        if (elements.searchProductsCount && elements.searchProductsGrid) {
            const currentCount = elements.searchProductsGrid.querySelectorAll('.col-6').length;
            scrollState.loadedCount = currentCount;
            
            // Update the search results count display
            const countText = currentCount === 1 ? '1 product found' : `${currentCount} products found`;
            elements.searchProductsCount.textContent = countText;
            
            log(`Search product count updated: ${currentCount}`);
        }
    }
    
    function showErrorMessage(message) {
        // Remove existing error messages
        const existingErrors = document.querySelectorAll('.search-error-message, .infinite-scroll-error');
        existingErrors.forEach(error => error.remove());
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-warning alert-dismissible fade show search-error-message';
        errorDiv.style.marginTop = '1rem';
        errorDiv.innerHTML = `
            <i class="bi bi-exclamation-triangle-fill me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        if (elements.searchProductsGrid && elements.searchProductsGrid.parentNode) {
            elements.searchProductsGrid.parentNode.insertBefore(
                errorDiv, 
                elements.searchLoadingIndicator || elements.searchProductsGrid.nextSibling
            );
        }
        
        // Auto-dismiss after 10 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.remove();
            }
        }, 10000);
        
        error('Search error message shown:', message);
    }
    
    function showButtonLoading(button) {
        if (button) {
            button.classList.add('loading');
            button.disabled = true;
        }
    }
    
    function hideButtonLoading(button) {
        if (button) {
            button.classList.remove('loading');
            button.disabled = false;
        }
    }
    
    // =============== PRODUCT LOADING ===============
    async function loadMoreSearchResults() {
        log('🔄 loadMoreSearchResults() called');
        
        // Pre-flight checks
        if (!scrollState.initialized) {
            log('Search not initialized yet, skipping load');
            return;
        }
        
        if (!elements.searchProductsGrid) {
            warn('Search products grid not found');
            return;
        }
        
        if (scrollState.isLoading) {
            log('Already loading search results, skipping');
            return;
        }
        
        if (!scrollState.hasMoreProducts) {
            log('No more search results available');
            showEndOfResults();
            return;
        }
        
        if (scrollState.currentPage >= scrollState.totalPages) {
            log(`Already at last search page (${scrollState.currentPage}/${scrollState.totalPages})`);
            scrollState.hasMoreProducts = false;
            showEndOfResults();
            return;
        }
        
        log(`Loading search page ${scrollState.currentPage + 1}/${scrollState.totalPages}...`);
        
        showLoading();
        
        try {
            const url = buildNextPageUrl();
            log('Fetching search URL:', url);
            
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json',
                    'Cache-Control': 'no-cache',
                }
            });
            
            log('Search response status:', response.status);
            
            if (!response.ok) {
                if (response.status === 404) {
                    log('Search 404 received, no more pages available');
                    scrollState.hasMoreProducts = false;
                    showEndOfResults();
                    return;
                }
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            log('Search AJAX response data:', data);
            
            if (data.success) {
                if (data.products_html && data.products_html.length > 0) {
                    await renderNewSearchProducts(data.products_html);
                    
                    // Update state from server response
                    scrollState.currentPage = data.current_page || (scrollState.currentPage + 1);
                    scrollState.totalPages = data.total_pages || scrollState.totalPages;
                    scrollState.hasMoreProducts = data.has_more === true;
                    scrollState.totalCount = data.total_count || scrollState.totalCount;
                    
                    updateProductCount();
                    
                    log(`✅ Successfully loaded ${data.products_html.length} search results`);
                    log('Updated search state:', scrollState);
                    
                    // Reset retry count on success
                    scrollState.retryCount = 0;
                    
                    if (!scrollState.hasMoreProducts) {
                        showEndOfResults();
                    }
                } else {
                    log('No search results in response');
                    scrollState.hasMoreProducts = false;
                    showEndOfResults();
                }
            } else {
                throw new Error(data.error || 'Server returned error response');
            }
            
        } catch (e) {
            error('Failed to load more search results:', e);
            
            // Retry logic
            if (scrollState.retryCount < CONFIG.retryAttempts) {
                scrollState.retryCount++;
                log(`Retrying search... (${scrollState.retryCount}/${CONFIG.retryAttempts})`);
                setTimeout(() => loadMoreSearchResults(), 2000 * scrollState.retryCount);
            } else {
                scrollState.hasMoreProducts = false;
                if (e.message.includes('404')) {
                    showEndOfResults('No more search results available');
                } else {
                    showErrorMessage(`Failed to load more search results: ${e.message}`);
                }
            }
            
        } finally {
            hideLoading();
        }
    }
    
    async function renderNewSearchProducts(productsHtml) {
        log(`Rendering ${productsHtml.length} new search products...`);
        
        for (let i = 0; i < productsHtml.length; i++) {
            const productHtml = productsHtml[i];
            
            try {
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = productHtml.trim();
                const productElement = tempDiv.firstElementChild;
                
                if (productElement) {
                    // Wrap in proper grid column for search
                    const colDiv = document.createElement('div');
                    colDiv.className = 'col-6 col-md-4 col-lg-3 col-xl-2';
                    colDiv.appendChild(productElement);
                    
                    // Add with animation delay
                    setTimeout(() => {
                        elements.searchProductsGrid.appendChild(colDiv);
                        log(`Search product ${i + 1} added to grid`);
                    }, i * 50);
                }
            } catch (e) {
                error(`Failed to render search product ${i + 1}:`, e);
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
            log('Search scroll check:', {
                scrollPosition,
                documentHeight,
                threshold,
                canTrigger: scrollPosition >= threshold
            });
        }
        
        if (scrollPosition >= threshold) {
            log('🎯 Search scroll threshold reached! Triggering load...');
            loadMoreSearchResults();
        }
    }
    
    // Debounced scroll handler
    let scrollTimeout;
    function handleScroll() {
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(checkScroll, CONFIG.debounceDelay);
    }
    
    // =============== ASYNC DATA LOADERS ===============
    async function loadSubcategoriesForCategory(categoryId) {
        try {
            log('Loading subcategories for category:', categoryId);
            const response = await fetch(`/api/subcategories/${categoryId}/`);
            if (response.ok) {
                const data = await response.json();
                if (elements.subcategorySelect) {
                    data.forEach(subcategory => {
                        const option = document.createElement('option');
                        option.value = subcategory.id;
                        option.textContent = subcategory.name;
                        elements.subcategorySelect.appendChild(option);
                    });
                    elements.subcategorySelect.disabled = false;
                    log(`Loaded ${data.length} subcategories`);
                }
            }
        } catch (e) {
            error('Failed to load subcategories:', e);
        }
    }
    
    async function loadBrandsForCategory(categoryId) {
        try {
            log('Loading brands for category:', categoryId);
            const response = await fetch(`/api/brands/${categoryId}/`);
            if (response.ok) {
                const data = await response.json();
                if (elements.brandSelect) {
                    data.forEach(brand => {
                        const option = document.createElement('option');
                        option.value = brand.id;
                        option.textContent = brand.name;
                        if (brand.product_count) {
                            option.textContent += ` (${brand.product_count})`;
                        }
                        elements.brandSelect.appendChild(option);
                    });
                    elements.brandSelect.disabled = false;
                    log(`Loaded ${data.length} brands`);
                }
            }
        } catch (e) {
            error('Failed to load brands:', e);
        }
    }
    
    async function loadBrandsForSubcategory(subcategoryId) {
        try {
            log('Loading brands for subcategory:', subcategoryId);
            const response = await fetch(`/ajax/load-brands/?subcategory=${subcategoryId}`);
            if (response.ok) {
                const data = await response.json();
                if (elements.brandSelect) {
                    elements.brandSelect.innerHTML = '<option value="">All Brands</option>';
                    data.forEach(brand => {
                        const option = document.createElement('option');
                        option.value = brand.id;
                        option.textContent = brand.name;
                        elements.brandSelect.appendChild(option);
                    });
                    elements.brandSelect.disabled = false;
                    log(`Loaded ${data.length} brands for subcategory`);
                }
            }
        } catch (e) {
            error('Failed to load brands for subcategory:', e);
        }
    }
    
    async function loadLGAsForState(stateId) {
        try {
            log('Loading LGAs for state:', stateId);
            const response = await fetch(`/api/lgas/${stateId}/`);
            if (response.ok) {
                const data = await response.json();
                if (elements.lgaSelect) {
                    data.forEach(lga => {
                        const option = document.createElement('option');
                        option.value = lga.id;
                        option.textContent = lga.name;
                        elements.lgaSelect.appendChild(option);
                    });
                    elements.lgaSelect.disabled = false;
                    log(`Loaded ${data.length} LGAs`);
                }
            }
        } catch (e) {
            error('Failed to load LGAs:', e);
        }
    }
    
    // =============== FORM HANDLERS ===============
    function setupFormHandlers() {
        // Main search form handler
        if (elements.form) {
            elements.form.addEventListener('submit', function(e) {
                log('Search form submitted, resetting infinite scroll state');
                const submitBtns = elements.form.querySelectorAll('button[type="submit"]');
                submitBtns.forEach(btn => {
                    showButtonLoading(btn);
                });
                
                resetInfiniteScrollState();
                
                // Remove empty fields to keep URL clean
                const formElements = elements.form.elements;
                const elementsToDisable = [];
                
                for (let element of formElements) {
                    if (element.value === '' && 
                        element.type !== 'submit' && 
                        element.type !== 'button') {
                        elementsToDisable.push(element);
                    }
                }
                
                // Disable empty elements temporarily
                elementsToDisable.forEach(element => {
                    element.disabled = true;
                });
                
                // Re-enable them after a short delay to prevent form issues
                setTimeout(() => {
                    elementsToDisable.forEach(element => {
                        element.disabled = false;
                    });
                }, 100);
            });
            
            // Listen for changes on all form inputs
            elements.form.addEventListener('change', updateActiveFiltersCount);
            elements.form.addEventListener('input', updateActiveFiltersCount);
        }
        
        // Sort select handler
        if (elements.searchSortSelect) {
            elements.searchSortSelect.addEventListener('change', function() {
                log('Search sort changed to:', this.value);
                resetInfiniteScrollState();
                
                const currentUrl = new URL(window.location);
                currentUrl.searchParams.set('sort', this.value);
                currentUrl.searchParams.delete('page');
                window.location.href = currentUrl.toString();
            });
        }
        
        // Category change handler
        if (elements.categorySelect) {
            elements.categorySelect.addEventListener('change', function() {
                const categoryId = this.value;
                log('Search category changed to:', categoryId);
                
                // Reset subcategory and brand
                if (elements.subcategorySelect) {
                    elements.subcategorySelect.innerHTML = '<option value="">All Subcategories</option>';
                    elements.subcategorySelect.disabled = !categoryId;
                }
                if (elements.brandSelect) {
                    elements.brandSelect.innerHTML = '<option value="">All Brands</option>';
                    elements.brandSelect.disabled = !categoryId;
                }
                
                if (categoryId) {
                    loadSubcategoriesForCategory(categoryId);
                    loadBrandsForCategory(categoryId);
                }
                
                updateActiveFiltersCount();
            });
        }
        
        // Subcategory change handler
        if (elements.subcategorySelect) {
            elements.subcategorySelect.addEventListener('change', function() {
                const subcategoryId = this.value;
                log('Search subcategory changed to:', subcategoryId);
                
                if (subcategoryId && elements.brandSelect) {
                    loadBrandsForSubcategory(subcategoryId);
                } else if (elements.brandSelect && !subcategoryId) {
                    // If no subcategory selected, reset to category-level brands
                    const categoryId = elements.categorySelect ? elements.categorySelect.value : '';
                    if (categoryId) {
                        elements.brandSelect.innerHTML = '<option value="">All Brands</option>';
                        loadBrandsForCategory(categoryId);
                    }
                }
                
                updateActiveFiltersCount();
            });
        }
        
        // State change handler
        if (elements.stateSelect) {
            elements.stateSelect.addEventListener('change', function() {
                const stateId = this.value;
                log('Search state changed to:', stateId);
                
                if (elements.lgaSelect) {
                    elements.lgaSelect.innerHTML = '<option value="">All LGAs</option>';
                    elements.lgaSelect.disabled = !stateId;
                    
                    if (stateId) {
                        loadLGAsForState(stateId);
                    }
                }
                
                updateActiveFiltersCount();
            });
        }
        
        // Clear filters handlers
        if (elements.clearFiltersBtn) {
            elements.clearFiltersBtn.addEventListener('click', clearAllFilters);
        }
        
        if (elements.clearFiltersEmptyBtn) {
            elements.clearFiltersEmptyBtn.addEventListener('click', function() {
                clearAllFilters();
                // Also clear the search query for empty state
                if (elements.queryInput) elements.queryInput.value = '';
                updateActiveFiltersCount();
            });
        }
        
        // Individual filter handlers for active count
        [elements.conditionSelect, elements.minPriceInput, elements.maxPriceInput, 
         elements.brandSelect, elements.lgaSelect, elements.verifiedBusinessSelect].forEach(element => {
            if (element) {
                const eventType = element.type === 'text' || element.type === 'number' ? 'input' : 'change';
                element.addEventListener(eventType, updateActiveFiltersCount);
            }
        });
    }
    
    // =============== INITIALIZATION ===============
    function initialize() {
        log('🎬 Starting complete search system initialization...');
        
        // Check required elements
        if (!elements.searchProductsGrid) {
            warn('Search products grid not found - infinite scroll disabled');
            return;
        }
        
        // Initialize pagination state
        if (!initializePaginationState()) {
            warn('Failed to initialize search pagination state');
        }
        
        // Setup all event handlers
        setupFormHandlers();
        
        // Initialize active filters count
        updateActiveFiltersCount();
        
        // Initialize current filters
        currentFilters = getCurrentFilters();
        
        // Start scroll monitoring
        window.addEventListener('scroll', handleScroll, { passive: true });
        
        // Debug helper
        window.debugSearchInfiniteScroll = function() {
            console.group('🔍 Search System Debug');
            console.log('Current state:', scrollState);
            console.log('Config:', CONFIG);
            console.log('Current filters:', currentFilters);
            console.log('Elements found:', Object.keys(elements).filter(key => elements[key]));
            console.log('Products in grid:', elements.searchProductsGrid ? elements.searchProductsGrid.querySelectorAll('.col-6').length : 'N/A');
            
            const scrollPos = window.innerHeight + window.scrollY;
            const docHeight = document.body.offsetHeight;
            console.log('Scroll info:', {
                position: scrollPos,
                documentHeight: docHeight,
                threshold: docHeight - CONFIG.loadThreshold,
                canTrigger: scrollPos >= (docHeight - CONFIG.loadThreshold)
            });
            
            if (elements.form) {
                const formData = new FormData(elements.form);
                const formParams = {};
                for (const [key, value] of formData.entries()) {
                    if (value) formParams[key] = value;
                }
                console.log('Current form data:', formParams);
            }
            
            console.groupEnd();
        };
        
        // Add visual feedback styles
        const style = document.createElement('style');
        style.textContent = `
            .search-error-message, .infinite-scroll-error {
                animation: slideDown 0.3s ease-out;
            }
            
            @keyframes slideDown {
                from {
                    opacity: 0;
                    transform: translateY(-10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            .btn.loading {
                position: relative;
                color: transparent;
            }
            
            .btn.loading::after {
                content: "";
                position: absolute;
                width: 1rem;
                height: 1rem;
                top: 50%;
                left: 50%;
                margin-left: -0.5rem;
                margin-top: -0.5rem;
                border: 2px solid transparent;
                border-top-color: currentColor;
                border-radius: 50%;
                animation: spin 1s ease infinite;
            }
            
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        `;
        document.head.appendChild(style);
        
        log('✅ Complete search system initialization complete!');
        log('Initial search state:', scrollState);
        log('Current filters:', currentFilters);
        
        // Force a scroll check after a brief delay
        setTimeout(() => {
            log('🔍 Initial search scroll check...');
            checkScroll();
        }, 1000);
    }
    
    // =============== START ===============
    initialize();
});