document.addEventListener('DOMContentLoaded', function() {
    // Infinite Scroll Variables
    let isLoading = false;
    let hasMoreProducts = true;
    let currentPage = 1;
    let totalPages = 1;
    let loadThreshold = 300;
    let currentFilters = {};
    
    // DOM Elements
    const searchProductsGrid = document.getElementById('search-products-grid');
    const searchLoadingIndicator = document.getElementById('search-loading-indicator');
    const searchEndOfResults = document.getElementById('search-end-of-results');
    const searchProductsCount = document.getElementById('search-products-count');
    const form = document.getElementById('advancedSearchForm');
    const categorySelect = document.getElementById('id_category');
    const subcategorySelect = document.getElementById('id_subcategory');
    const brandSelect = document.getElementById('id_brand');
    const stateSelect = document.getElementById('id_state');
    const lgaSelect = document.getElementById('id_lga');
    const activeFiltersCount = document.getElementById('activeFiltersCount');
    const clearFiltersBtn = document.getElementById('clearFilters');
    const clearFiltersEmptyBtn = document.getElementById('clearFiltersEmpty');
    
    // Initialize pagination state from server data
    function initializePaginationState() {
        try {
            const paginationDataElement = document.getElementById('pagination-data');
            if (paginationDataElement) {
                const paginationData = JSON.parse(paginationDataElement.textContent);
                currentPage = paginationData.current_page || 1;
                totalPages = paginationData.total_pages || 1;
                hasMoreProducts = paginationData.has_next || false;
                
                console.log('Search pagination initialized:', {
                    currentPage,
                    totalPages,
                    hasMoreProducts,
                    totalCount: paginationData.total_count
                });
                
                // If we're already on the last page or there are no products, show end state
                if (!hasMoreProducts && paginationData.current_count > 0) {
                    showEndOfResults();
                }
            } else {
                console.warn('Pagination data not found, using defaults');
                // Fallback logic
                const productElements = searchProductsGrid ? searchProductsGrid.querySelectorAll('.product-card') : [];
                if (productElements.length === 0) {
                    hasMoreProducts = false;
                } else if (productElements.length < 12) {
                    hasMoreProducts = false;
                    showEndOfResults();
                }
            }
        } catch (error) {
            console.error('Error initializing pagination state:', error);
            // Fallback to checking product count
            const productElements = searchProductsGrid ? searchProductsGrid.querySelectorAll('.product-card') : [];
            hasMoreProducts = productElements.length >= 12;
        }
    }
    
    // Function to get all current form parameters
    function getAllFormParams() {
        if (!form) return new URLSearchParams();
        
        const formData = new FormData(form);
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
    
    // Function to get current filter parameters
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
    
    // Function to check if filters have changed
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
    
    // Function to reset infinite scroll state
    function resetInfiniteScrollState() {
        isLoading = false;
        hasMoreProducts = true;
        currentPage = 1;
        totalPages = 1;
        
        if (searchEndOfResults) searchEndOfResults.style.display = 'none';
        if (searchLoadingIndicator) searchLoadingIndicator.style.display = 'none';
        
        // Clear any error messages
        const existingErrors = document.querySelectorAll('.search-error-message, .infinite-scroll-error');
        existingErrors.forEach(error => error.remove());
        
        console.log('Search infinite scroll state reset');
    }
    
    // Enhanced infinite scroll - load more search results
    async function loadMoreSearchResults() {
        // Pre-flight checks
        if (!searchProductsGrid) {
            console.log('Search products grid not found');
            return;
        }
        
        if (isLoading) {
            console.log('Already loading, skipping');
            return;
        }
        
        if (!hasMoreProducts) {
            console.log('No more search results available');
            showEndOfResults();
            return;
        }
        
        // Additional check: don't load if we've reached total pages
        if (currentPage >= totalPages && totalPages > 1) {
            console.log(`Already at last page (${currentPage}/${totalPages})`);
            hasMoreProducts = false;
            showEndOfResults();
            return;
        }
        
        isLoading = true;
        if (searchLoadingIndicator) searchLoadingIndicator.style.display = 'block';
        
        try {
            const nextPage = currentPage + 1;
            
            // Get all current parameters
            const params = getAllFormParams();
            params.set('page', nextPage);
            
            // Construct URL with all parameters
            const url = `${window.location.pathname}?${params.toString()}`;
            
            console.log(`Loading search page ${nextPage} from:`, url);
            
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json',
                    'Cache-Control': 'no-cache',
                }
            });
            
            if (!response.ok) {
                if (response.status === 404) {
                    console.log('Search page not found (404), end of results');
                    hasMoreProducts = false;
                    showEndOfResults();
                    return;
                }
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Check if response indicates success
            if (data.success) {
                if (data.products_html && data.products_html.length > 0) {
                    // Add new products to the grid using server-rendered HTML
                    data.products_html.forEach((productHtml, index) => {
                        const tempDiv = document.createElement('div');
                        tempDiv.innerHTML = productHtml.trim();
                        const productElement = tempDiv.firstElementChild;
                        
                        if (productElement) {
                            // Wrap in proper grid column
                            const colDiv = document.createElement('div');
                            colDiv.className = 'col-6 col-md-4 col-lg-3 col-xl-2';
                            colDiv.appendChild(productElement);
                            
                            // Add with slight animation delay
                            setTimeout(() => {
                                searchProductsGrid.appendChild(colDiv);
                            }, index * 30);
                        }
                    });
                    
                    // Update pagination state
                    currentPage = data.current_page || nextPage;
                    totalPages = data.total_pages || totalPages;
                    hasMoreProducts = data.has_more === true;
                    
                    console.log(`Added ${data.products_html.length} search results. Page ${currentPage}/${totalPages}, hasMore: ${hasMoreProducts}`);
                    
                    if (!hasMoreProducts) {
                        showEndOfResults();
                    }
                } else {
                    console.log('No search results in response, end of results');
                    hasMoreProducts = false;
                    showEndOfResults();
                }
            } else {
                throw new Error(data.error || 'Server returned error');
            }
            
        } catch (error) {
            console.error('Error loading more search results:', error);
            hasMoreProducts = false;
            
            if (error.message.includes('404')) {
                showEndOfResults('No more search results available');
            } else {
                showSearchErrorMessage(`Unable to load more results: ${error.message}`);
            }
            
        } finally {
            isLoading = false;
            if (searchLoadingIndicator) searchLoadingIndicator.style.display = 'none';
        }
    }
    
    // Function to show end of results
    function showEndOfResults(customMessage = null) {
        if (searchEndOfResults) {
            if (customMessage) {
                const messageElement = searchEndOfResults.querySelector('p');
                if (messageElement) {
                    messageElement.textContent = customMessage;
                }
            }
            searchEndOfResults.style.display = 'block';
        }
        console.log('Search end of results displayed');
    }
    
    // Enhanced error message function
    function showSearchErrorMessage(message) {
        // Remove any existing error messages first
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
        
        // Insert after the products grid
        if (searchProductsGrid && searchProductsGrid.parentNode) {
            searchProductsGrid.parentNode.insertBefore(errorDiv, searchLoadingIndicator || searchProductsGrid.nextSibling);
        }
        
        // Auto-dismiss after 10 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.remove();
            }
        }, 10000);
    }
    
    // Scroll detection with better throttling
    function checkSearchScroll() {
        if (!hasMoreProducts || isLoading) return;
        
        const scrollPosition = window.innerHeight + window.scrollY;
        const threshold = document.body.offsetHeight - loadThreshold;
        
        if (scrollPosition >= threshold) {
            loadMoreSearchResults();
        }
    }
    
    // Improved throttled scroll event listener
    let ticking = false;
    function onScroll() {
        if (!ticking) {
            requestAnimationFrame(() => {
                checkSearchScroll();
                ticking = false;
            });
            ticking = true;
        }
    }
    
    window.addEventListener('scroll', onScroll, { passive: true });
    
    // Function to update active filters count
    function updateActiveFiltersCount() {
        if (!form || !activeFiltersCount) return;
        
        let count = 0;
        const formElements = form.elements;
        
        for (let element of formElements) {
            if (element.type !== 'submit' && 
                element.type !== 'button' && 
                element.value && 
                element.value.trim() !== '' &&
                element.name !== 'query') { // Don't count main search query
                count++;
            }
        }
        
        activeFiltersCount.textContent = count;
        activeFiltersCount.style.display = count > 0 ? 'flex' : 'none';
    }

    // Function to show loading state
    function showLoading(button) {
        if (button) {
            button.classList.add('loading');
            button.disabled = true;
        }
    }

    // Function to hide loading state
    function hideLoading(button) {
        if (button) {
            button.classList.remove('loading');
            button.disabled = false;
        }
    }

    // Enhanced category change handler
    if (categorySelect) {
        categorySelect.addEventListener('change', function() {
            const categoryId = this.value;
            
            // Reset subcategory and brand
            if (subcategorySelect) {
                subcategorySelect.innerHTML = '<option value="">All Subcategories</option>';
                subcategorySelect.disabled = !categoryId;
            }
            if (brandSelect) {
                brandSelect.innerHTML = '<option value="">All Brands</option>';
                brandSelect.disabled = !categoryId;
            }
            
            if (categoryId) {
                // Load subcategories
                if (subcategorySelect) {
                    fetch(`/api/subcategories/${categoryId}/`)
                        .then(response => {
                            if (!response.ok) {
                                throw new Error('Failed to fetch subcategories');
                            }
                            return response.json();
                        })
                        .then(data => {
                            data.forEach(subcategory => {
                                const option = document.createElement('option');
                                option.value = subcategory.id;
                                option.textContent = subcategory.name;
                                subcategorySelect.appendChild(option);
                            });
                            subcategorySelect.disabled = false;
                        })
                        .catch(error => {
                            console.error('Error fetching subcategories:', error);
                            subcategorySelect.disabled = false;
                        });
                }

                // Load brands for the category
                if (brandSelect) {
                    fetch(`/api/brands/${categoryId}/`)
                        .then(response => {
                            if (!response.ok) {
                                throw new Error('Failed to fetch brands');
                            }
                            return response.json();
                        })
                        .then(data => {
                            data.forEach(brand => {
                                const option = document.createElement('option');
                                option.value = brand.id;
                                option.textContent = brand.name;
                                if (brand.product_count) {
                                    option.textContent += ` (${brand.product_count})`;
                                }
                                brandSelect.appendChild(option);
                            });
                            brandSelect.disabled = false;
                        })
                        .catch(error => {
                            console.error('Error fetching brands by category:', error);
                            brandSelect.disabled = false;
                        });
                }
            }
            
            updateActiveFiltersCount();
        });
    }

    // Enhanced subcategory change handler
    if (subcategorySelect) {
        subcategorySelect.addEventListener('change', function() {
            const subcategoryId = this.value;
            
            if (subcategoryId && brandSelect) {
                // Reset brands
                brandSelect.innerHTML = '<option value="">All Brands</option>';
                brandSelect.disabled = true;
                
                // Load brands for the subcategory
                fetch(`/ajax/load-brands/?subcategory=${subcategoryId}`)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('Failed to fetch brands for subcategory');
                        }
                        return response.json();
                    })
                    .then(data => {
                        data.forEach(brand => {
                            const option = document.createElement('option');
                            option.value = brand.id;
                            option.textContent = brand.name;
                            brandSelect.appendChild(option);
                        });
                        brandSelect.disabled = false;
                    })
                    .catch(error => {
                        console.error('Error fetching brands by subcategory:', error);
                        brandSelect.disabled = false;
                    });
            } else if (brandSelect && !subcategoryId) {
                // If no subcategory selected, reset to category-level brands
                const categoryId = categorySelect ? categorySelect.value : '';
                if (categoryId) {
                    brandSelect.innerHTML = '<option value="">All Brands</option>';
                    fetch(`/api/brands/${categoryId}/`)
                        .then(response => response.json())
                        .then(data => {
                            data.forEach(brand => {
                                const option = document.createElement('option');
                                option.value = brand.id;
                                option.textContent = brand.name;
                                if (brand.product_count) {
                                    option.textContent += ` (${brand.product_count})`;
                                }
                                brandSelect.appendChild(option);
                            });
                        })
                        .catch(error => {
                            console.error('Error reloading category brands:', error);
                        });
                }
            }
            
            updateActiveFiltersCount();
        });
    }

    // Enhanced state change handler
    if (stateSelect) {
        stateSelect.addEventListener('change', function() {
            const stateId = this.value;
            
            if (lgaSelect) {
                lgaSelect.innerHTML = '<option value="">All LGAs</option>';
                lgaSelect.disabled = !stateId;
                
                if (stateId) {
                    fetch(`/api/lgas/${stateId}/`)
                        .then(response => {
                            if (!response.ok) {
                                throw new Error('Failed to fetch LGAs');
                            }
                            return response.json();
                        })
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
                            console.error('Error fetching LGAs:', error);
                            lgaSelect.disabled = false;
                        });
                }
            }
            
            updateActiveFiltersCount();
        });
    }

    // Clear filters handler
    function clearAllFilters() {
        if (!form) return;
        
        const formElements = form.elements;
        for (let element of formElements) {
            if (element.type !== 'submit' && element.type !== 'button') {
                if (element.name !== 'query') { // Preserve search query
                    element.value = '';
                }
            }
        }
        
        // Reset dependent fields
        if (subcategorySelect) {
            subcategorySelect.innerHTML = '<option value="">All Subcategories</option>';
            subcategorySelect.disabled = true;
        }
        if (brandSelect) {
            brandSelect.innerHTML = '<option value="">All Brands</option>';
            brandSelect.disabled = true;
        }
        if (lgaSelect) {
            lgaSelect.innerHTML = '<option value="">All LGAs</option>';
            lgaSelect.disabled = true;
        }
        
        updateActiveFiltersCount();
    }

    if (clearFiltersBtn) {
        clearFiltersBtn.addEventListener('click', clearAllFilters);
    }
    
    if (clearFiltersEmptyBtn) {
        clearFiltersEmptyBtn.addEventListener('click', function() {
            clearAllFilters();
            // Also clear the search query for empty state
            const queryInput = form.querySelector('[name="query"]');
            if (queryInput) queryInput.value = '';
            updateActiveFiltersCount();
        });
    }

    // Listen for changes on all form inputs
    if (form) {
        form.addEventListener('change', updateActiveFiltersCount);
        form.addEventListener('input', updateActiveFiltersCount);
    }

    // Handle other form elements for active filter count
    const conditionSelect = document.getElementById('id_condition');
    if (conditionSelect) {
        conditionSelect.addEventListener('change', updateActiveFiltersCount);
    }

    const minPriceInput = document.getElementById('id_min_price');
    const maxPriceInput = document.getElementById('id_max_price');
    
    if (minPriceInput) {
        minPriceInput.addEventListener('input', updateActiveFiltersCount);
    }
    if (maxPriceInput) {
        maxPriceInput.addEventListener('input', updateActiveFiltersCount);
    }
    
    // Enhanced sort functionality
    const searchSortSelect = document.getElementById('searchSortSelect');
    if (searchSortSelect) {
        searchSortSelect.addEventListener('change', function() {
            resetInfiniteScrollState();
            const currentUrl = new URL(window.location);
            currentUrl.searchParams.set('sort', this.value);
            currentUrl.searchParams.delete('page'); // Reset to page 1
            window.location.href = currentUrl.toString();
        });
    }
    
    // Enhanced form submission with loading state
    if (form) {
        form.addEventListener('submit', function(e) {
            const submitBtns = form.querySelectorAll('button[type="submit"]');
            submitBtns.forEach(btn => {
                showLoading(btn);
            });
            
            // Reset infinite scroll state
            resetInfiniteScrollState();
            
            // Remove empty fields to keep URL clean
            const elements = form.elements;
            const elementsToDisable = [];
            
            for (let element of elements) {
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
    }
    
    // Initialize active filters count on page load
    updateActiveFiltersCount();
    
    // Initialize everything
    currentFilters = getCurrentFilters();
    initializePaginationState();
    
    console.log('Product search infinite scroll initialized');
    
    // Add visual feedback for AJAX loading
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
        
        .loading-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.1);
            z-index: 9999;
            display: none;
        }
    `;
    document.head.appendChild(style);
});