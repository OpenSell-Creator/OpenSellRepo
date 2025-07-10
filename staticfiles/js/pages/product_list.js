document.addEventListener('DOMContentLoaded', function() {
    // Infinite Scroll Variables
    let isLoading = false;
    let hasMoreProducts = true;
    let currentPage = 1;
    let totalPages = 1;
    let loadThreshold = 300;
    let currentFilters = {};
    
    // DOM Elements
    const productsGrid = document.getElementById('products-grid');
    const loadingIndicator = document.getElementById('loading-indicator');
    const endOfResults = document.getElementById('end-of-results');
    const productsCountNumber = document.getElementById('products-count-number');
    
    // Initialize pagination state from server data
    function initializePaginationState() {
        try {
            const paginationDataElement = document.getElementById('pagination-data');
            if (paginationDataElement) {
                const paginationData = JSON.parse(paginationDataElement.textContent);
                currentPage = paginationData.current_page || 1;
                totalPages = paginationData.total_pages || 1;
                hasMoreProducts = paginationData.has_next || false;
                
                console.log('Pagination initialized:', {
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
                const productElements = productsGrid ? productsGrid.querySelectorAll('.product-card') : [];
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
            const productElements = productsGrid ? productsGrid.querySelectorAll('.product-card') : [];
            hasMoreProducts = productElements.length >= 12;
        }
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
        
        if (endOfResults) endOfResults.style.display = 'none';
        if (loadingIndicator) loadingIndicator.style.display = 'none';
        
        // Clear any error messages
        const existingErrors = document.querySelectorAll('.infinite-scroll-error');
        existingErrors.forEach(error => error.remove());
        
        console.log('Infinite scroll state reset');
    }
    
    // Enhanced load more products function
    async function loadMoreProducts() {
        // Pre-flight checks
        if (!productsGrid) {
            console.log('Products grid not found');
            return;
        }
        
        if (isLoading) {
            console.log('Already loading, skipping');
            return;
        }
        
        if (!hasMoreProducts) {
            console.log('No more products available');
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
        if (loadingIndicator) loadingIndicator.style.display = 'block';
        
        try {
            const nextPage = currentPage + 1;
            const url = new URL(window.location.href);
            url.searchParams.set('page', nextPage);
            
            // Ensure all form parameters are included if we have an active filter form
            const filterForm = document.getElementById('dropdownFilterForm');
            if (filterForm) {
                const formData = new FormData(filterForm);
                for (const [key, value] of formData.entries()) {
                    if (value && key !== 'page') {
                        url.searchParams.set(key, value);
                    }
                }
            }
            
            console.log(`Loading page ${nextPage} from:`, url.toString());
            
            const response = await fetch(url.toString(), {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json',
                    'Cache-Control': 'no-cache',
                }
            });
            
            if (!response.ok) {
                if (response.status === 404) {
                    console.log('Page not found (404), end of results');
                    hasMoreProducts = false;
                    showEndOfResults();
                    return;
                }
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
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
                            colDiv.className = 'col';
                            colDiv.appendChild(productElement);
                            
                            // Add with slight animation delay
                            setTimeout(() => {
                                productsGrid.appendChild(colDiv);
                            }, index * 30);
                        }
                    });
                    
                    // Update pagination state
                    currentPage = data.current_page || nextPage;
                    totalPages = data.total_pages || totalPages;
                    hasMoreProducts = data.has_more === true;
                    
                    // Update product count
                    if (productsCountNumber) {
                        const currentCount = productsGrid.querySelectorAll('.product-card').length;
                        productsCountNumber.textContent = currentCount;
                    }
                    
                    console.log(`Added ${data.products_html.length} products. Page ${currentPage}/${totalPages}, hasMore: ${hasMoreProducts}`);
                    
                    if (!hasMoreProducts) {
                        showEndOfResults();
                    }
                } else {
                    console.log('No products in response, end of results');
                    hasMoreProducts = false;
                    showEndOfResults();
                }
            } else {
                throw new Error(data.error || 'Server returned error');
            }
            
        } catch (error) {
            console.error('Error loading more products:', error);
            hasMoreProducts = false;
            
            if (error.message.includes('404')) {
                showEndOfResults();
            } else {
                showErrorMessage(`Failed to load more products: ${error.message}`);
            }
            
        } finally {
            isLoading = false;
            if (loadingIndicator) loadingIndicator.style.display = 'none';
        }
    }
    
    // Function to show end of results
    function showEndOfResults(customMessage = null) {
        if (endOfResults) {
            if (customMessage) {
                const messageElement = endOfResults.querySelector('p');
                if (messageElement) {
                    messageElement.textContent = customMessage;
                }
            }
            endOfResults.style.display = 'block';
        }
        console.log('End of results displayed');
    }
    
    // Function to show error message
    function showErrorMessage(message) {
        // Remove any existing error messages first
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
        
        // Insert after the products grid
        if (productsGrid && productsGrid.parentNode) {
            productsGrid.parentNode.insertBefore(errorDiv, loadingIndicator || productsGrid.nextSibling);
        }
        
        // Auto-dismiss after 8 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.remove();
            }
        }, 8000);
    }
    
    // Scroll detection
    function checkScroll() {
        if (!hasMoreProducts || isLoading) return;
        
        const scrollPosition = window.innerHeight + window.scrollY;
        const threshold = document.body.offsetHeight - loadThreshold;
        
        if (scrollPosition >= threshold) {
            loadMoreProducts();
        }
    }
    
    // Optimized scroll listener
    let ticking = false;
    function onScroll() {
        if (!ticking) {
            requestAnimationFrame(() => {
                checkScroll();
                ticking = false;
            });
            ticking = true;
        }
    }
    
    window.addEventListener('scroll', onScroll, { passive: true });
    
    // Reset when sort changes
    const sortSelect = document.getElementById('sortSelect');
    if (sortSelect) {
        sortSelect.addEventListener('change', function() {
            const currentUrl = new URL(window.location);
            currentUrl.searchParams.set('sort', this.value);
            currentUrl.searchParams.delete('page'); // Reset to page 1
            window.location.href = currentUrl.toString();
        });
    }
    
    // Dropdown Filter Form Handler
    const dropdownFilterForm = document.getElementById('dropdownFilterForm');
    if (dropdownFilterForm) {
        const dropdownSubcategorySelect = document.getElementById('dropdown_subcategory');
        const dropdownBrandSelect = document.getElementById('dropdown_brand');
        const dropdownVerifiedBusinessSelect = document.getElementById('dropdown_verified_business');
        const dropdownConditionSelect = document.getElementById('dropdown_condition');
        const dropdownPriceRangeSelect = document.getElementById('dropdown_price_range');
        const dropdownStateSelect = document.getElementById('dropdown_state');
        const dropdownLgaSelect = document.getElementById('dropdown_lga');

        const urlParams = new URLSearchParams(window.location.search);

        function handlePriceRange(priceRange) {
            try {
                const existingMinPrice = dropdownFilterForm.querySelector('input[name="min_price"]');
                const existingMaxPrice = dropdownFilterForm.querySelector('input[name="max_price"]');
                
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
                    
                    dropdownFilterForm.appendChild(minPriceInput);
                    if (maxPrice !== '999999999') {
                        dropdownFilterForm.appendChild(maxPriceInput);
                    }
                }
            } catch (error) {
                console.error('Error handling price range:', error);
            }
        }

        function submitFormSafely(delay = 100) {
            setTimeout(() => {
                try {
                    resetInfiniteScrollState();
                    dropdownFilterForm.submit();
                } catch (error) {
                    console.error('Error submitting form:', error);
                }
            }, delay);
        }

        function handleFilterChange() {
            if (this.id === 'dropdown_price_range') {
                handlePriceRange(this.value);
            }
            submitFormSafely();
        }

        // Subcategory change handler
        if (dropdownSubcategorySelect) {
            dropdownSubcategorySelect.addEventListener('change', function() {
                const categorySlug = dropdownFilterForm.querySelector('input[name="category"]').value;
                const subcategorySlug = this.value;
                
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
                            if (dropdownBrandSelect) {
                                dropdownBrandSelect.innerHTML = '<option value="">All Brands</option>';
                                data.forEach(brand => {
                                    const option = document.createElement('option');
                                    option.value = brand.slug;
                                    option.textContent = `${brand.name}${brand.product_count ? ' (' + brand.product_count + ')' : ''}`;
                                    dropdownBrandSelect.appendChild(option);
                                });
                            }
                        })
                        .catch(error => {
                            console.error('Error fetching brands:', error);
                        });
                }
                
                submitFormSafely(200);
            });
        }

        // State change handler
        if (dropdownStateSelect) {
            dropdownStateSelect.addEventListener('change', function() {
                const stateId = this.value;
                
                if (dropdownLgaSelect) {
                    dropdownLgaSelect.innerHTML = '<option value="">All LGAs</option>';
                    dropdownLgaSelect.value = '';
                }
                
                if (stateId) {
                    if (dropdownLgaSelect) {
                        dropdownLgaSelect.disabled = false;
                    }
                    
                    fetch(`/api/lgas/${stateId}/`)
                        .then(response => {
                            if (!response.ok) throw new Error(`HTTP ${response.status}`);
                            return response.json();
                        })
                        .then(data => {
                            if (dropdownLgaSelect) {
                                data.forEach(lga => {
                                    const option = document.createElement('option');
                                    option.value = lga.id;
                                    option.textContent = lga.name;
                                    dropdownLgaSelect.appendChild(option);
                                });
                            }
                            
                            submitFormSafely(100);
                        })
                        .catch(error => {
                            console.error('Error fetching LGAs:', error);
                            if (dropdownLgaSelect) {
                                dropdownLgaSelect.disabled = true;
                            }
                            submitFormSafely(100);
                        });
                } else {
                    if (dropdownLgaSelect) {
                        dropdownLgaSelect.disabled = true;
                    }
                    submitFormSafely(100);
                }
            });
        }

        // LGA change handler
        if (dropdownLgaSelect) {
            dropdownLgaSelect.addEventListener('change', function() {
                submitFormSafely();
            });
        }

        // Add change listeners to all filter dropdowns
        [dropdownBrandSelect, dropdownVerifiedBusinessSelect, dropdownConditionSelect, dropdownPriceRangeSelect].forEach(select => {
            if (select) {
                select.addEventListener('change', handleFilterChange);
            }
        });

        // Clear filters handler
        const clearDropdownFiltersBtn = document.getElementById('clearDropdownFilters');
        if (clearDropdownFiltersBtn) {
            clearDropdownFiltersBtn.addEventListener('click', function() {
                try {
                    // Clear all filter selections
                    [dropdownSubcategorySelect, dropdownBrandSelect, dropdownVerifiedBusinessSelect, 
                     dropdownConditionSelect, dropdownPriceRangeSelect, dropdownStateSelect, 
                     dropdownLgaSelect].forEach(select => {
                        if (select) {
                            select.value = '';
                        }
                    });

                    // Reset LGA dropdown
                    if (dropdownLgaSelect) {
                        dropdownLgaSelect.innerHTML = '<option value="">All LGAs</option>';
                        dropdownLgaSelect.disabled = true;
                    }

                    // Remove price range hidden inputs
                    const existingMinPrice = dropdownFilterForm.querySelector('input[name="min_price"]');
                    const existingMaxPrice = dropdownFilterForm.querySelector('input[name="max_price"]');
                    if (existingMinPrice) existingMinPrice.remove();
                    if (existingMaxPrice) existingMaxPrice.remove();

                    // Reset brands dropdown to all brands for the category
                    const categorySlug = dropdownFilterForm.querySelector('input[name="category"]').value;
                    if (categorySlug && dropdownBrandSelect) {
                        fetch(`/api/brands/${categorySlug}/`)
                            .then(response => {
                                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                                return response.json();
                            })
                            .then(data => {
                                dropdownBrandSelect.innerHTML = '<option value="">All Brands</option>';
                                data.forEach(brand => {
                                    const option = document.createElement('option');
                                    option.value = brand.slug;
                                    option.textContent = `${brand.name}${brand.product_count ? ' (' + brand.product_count + ')' : ''}`;
                                    dropdownBrandSelect.appendChild(option);
                                });
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
        const currentPriceRange = dropdownPriceRangeSelect ? dropdownPriceRangeSelect.value : '';
        if (currentPriceRange) {
            handlePriceRange(currentPriceRange);
        }

        // Initialize location selections on page load
        function initializeLocationSelections() {
            try {
                const currentStateId = urlParams.get('state');
                const currentLgaId = urlParams.get('lga');
                
                if (currentStateId && dropdownStateSelect) {
                    dropdownStateSelect.value = currentStateId;
                    
                    if (dropdownLgaSelect) {
                        dropdownLgaSelect.disabled = false;
                        
                        fetch(`/api/lgas/${currentStateId}/`)
                            .then(response => {
                                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                                return response.json();
                            })
                            .then(data => {
                                dropdownLgaSelect.innerHTML = '<option value="">All LGAs</option>';
                                data.forEach(lga => {
                                    const option = document.createElement('option');
                                    option.value = lga.id;
                                    option.textContent = lga.name;
                                    
                                    if (currentLgaId && lga.id.toString() === currentLgaId) {
                                        option.selected = true;
                                    }
                                    
                                    dropdownLgaSelect.appendChild(option);
                                });
                            })
                            .catch(error => {
                                console.error('Error fetching LGAs on page load:', error);
                                dropdownLgaSelect.disabled = true;
                            });
                    }
                } else {
                    if (dropdownLgaSelect) {
                        dropdownLgaSelect.disabled = true;
                    }
                }
            } catch (error) {
                console.error('Error initializing location selections:', error);
            }
        }

        initializeLocationSelections();

        // Monitor form submission for state reset
        dropdownFilterForm.addEventListener('submit', function() {
            resetInfiniteScrollState();
        });
    }
    
    // Initialize everything
    currentFilters = getCurrentFilters();
    initializePaginationState();
    
    console.log('Product list infinite scroll initialized');
});