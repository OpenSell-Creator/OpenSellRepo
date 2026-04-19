document.addEventListener('DOMContentLoaded', function () {

    var CONFIG = {
        loadThreshold: 500,
        debounceDelay: 250,
        retryAttempts: 3
    };

    var scrollState = {
        isLoading: false,
        hasMoreProducts: true,
        currentPage: 1,
        totalPages: 1,
        totalCount: 0,
        loadedCount: 0,
        retryCount: 0,
        initialized: false
    };

    var elements = {
        productsGrid:     document.getElementById('products-grid'),
        loadingIndicator: document.getElementById('loading-indicator'),
        endOfResults:     document.getElementById('end-of-results'),
        paginationData:   document.getElementById('pagination-data'),
        sortSelect:       document.getElementById('sortSelect')
    };

    /* ── Pagination state ──────────────────────────────────────────────── */
    function initializePaginationState() {
        if (!elements.paginationData) return false;

        try {
            var data = JSON.parse(elements.paginationData.textContent);

            scrollState.currentPage      = data.current_page  || 1;
            scrollState.totalPages       = data.total_pages   || 1;
            scrollState.hasMoreProducts  = data.has_next      || false;
            scrollState.totalCount       = data.total_count   || 0;
            scrollState.loadedCount      = data.current_count || 0;

            if (elements.endOfResults)     elements.endOfResults.style.display     = 'none';
            if (elements.loadingIndicator) elements.loadingIndicator.style.display = 'none';

            if (!scrollState.hasMoreProducts && scrollState.loadedCount > 0) {
                showEndOfResults();
            }

            scrollState.initialized = true;
            return true;

        } catch (e) {
            console.error('[ProductList] Failed to parse pagination data:', e);
            return false;
        }
    }

    /* ── UI helpers ────────────────────────────────────────────────────── */
    function showLoading() {
        scrollState.isLoading = true;
        if (elements.loadingIndicator) elements.loadingIndicator.style.display = 'block';
    }

    function hideLoading() {
        scrollState.isLoading = false;
        if (elements.loadingIndicator) elements.loadingIndicator.style.display = 'none';
    }

    function showEndOfResults() {
        if (elements.endOfResults && scrollState.loadedCount > 0) {
            elements.endOfResults.style.display = 'block';
        }
    }

    function showErrorMessage(message) {
        var errorDiv       = document.createElement('div');
        errorDiv.className = 'alert alert-danger infinite-scroll-error mt-3';
        errorDiv.innerHTML =
            '<i class="bi bi-exclamation-triangle me-2"></i>' +
            '<strong>Error:</strong> ' + message +
            '<button type="button" class="btn-close" onclick="this.parentElement.remove()"></button>';

        if (elements.productsGrid && elements.productsGrid.parentNode) {
            elements.productsGrid.parentNode.insertBefore(errorDiv, elements.endOfResults);
        }

        setTimeout(function () {
            if (errorDiv.parentNode) errorDiv.remove();
        }, 8000);
    }

    /* ── Infinite scroll ───────────────────────────────────────────────── */
    function buildNextPageUrl() {
        var url = new URL(window.location.href);
        url.searchParams.set('page', scrollState.currentPage + 1);
        return url.toString();
    }

    function renderNewProducts(productsHtml) {
        productsHtml.forEach(function (html, i) {
            try {
                var tempDiv         = document.createElement('div');
                tempDiv.innerHTML   = html.trim();
                var productElement  = tempDiv.firstElementChild;

                if (productElement) {
                    var colDiv       = document.createElement('div');
                    colDiv.className = 'col';
                    colDiv.appendChild(productElement);

                    setTimeout(function () {
                        elements.productsGrid.appendChild(colDiv);
                    }, i * 50);
                }
            } catch (e) {
                console.error('[ProductList] Failed to render product:', e);
            }
        });
    }

    function loadMoreProducts() {
        if (!scrollState.initialized)    return;
        if (!elements.productsGrid)      return;
        if (scrollState.isLoading)       return;
        if (!scrollState.hasMoreProducts) { showEndOfResults(); return; }

        if (scrollState.currentPage >= scrollState.totalPages) {
            scrollState.hasMoreProducts = false;
            showEndOfResults();
            return;
        }

        showLoading();

        fetch(buildNextPageUrl(), {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json',
                'Cache-Control': 'no-cache'
            }
        })
        .then(function (response) {
            if (!response.ok) {
                if (response.status === 404) {
                    scrollState.hasMoreProducts = false;
                    showEndOfResults();
                    return null;
                }
                throw new Error('HTTP ' + response.status);
            }
            return response.json();
        })
        .then(function (data) {
            if (!data) return;

            if (data.success) {
                if (data.products_html && data.products_html.length > 0) {
                    renderNewProducts(data.products_html);

                    scrollState.currentPage     = data.current_page || (scrollState.currentPage + 1);
                    scrollState.totalPages      = data.total_pages  || scrollState.totalPages;
                    scrollState.hasMoreProducts = data.has_more === true;
                    scrollState.totalCount      = data.total_count  || scrollState.totalCount;
                    scrollState.loadedCount    += data.products_html.length;
                    scrollState.retryCount      = 0;

                    if (!scrollState.hasMoreProducts) showEndOfResults();
                } else {
                    scrollState.hasMoreProducts = false;
                    showEndOfResults();
                }
            } else {
                throw new Error(data.error || 'Server error');
            }
        })
        .catch(function (e) {
            console.error('[ProductList] Failed to load more products:', e);

            if (scrollState.retryCount < CONFIG.retryAttempts) {
                scrollState.retryCount++;
                setTimeout(loadMoreProducts, 2000 * scrollState.retryCount);
            } else {
                scrollState.hasMoreProducts = false;
                showErrorMessage('Failed to load more products. Please refresh the page.');
            }
        })
        .finally(function () {
            hideLoading();
        });
    }

    /* ── Scroll detection ──────────────────────────────────────────────── */
    function checkScroll() {
        if (scrollState.isLoading || !scrollState.hasMoreProducts) return;

        var scrollPosition = window.innerHeight + window.scrollY;
        var threshold      = document.body.offsetHeight - CONFIG.loadThreshold;

        if (scrollPosition >= threshold) {
            loadMoreProducts();
        }
    }

    var scrollTimeout;
    function handleScroll() {
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(checkScroll, CONFIG.debounceDelay);
    }

    /* ── Sort handler ──────────────────────────────────────────────────── */
    function setupSortHandler() {
        if (!elements.sortSelect) return;

        elements.sortSelect.addEventListener('change', function () {
            var url        = new URL(window.location.href);
            var sortValue  = this.value;

            if (sortValue === 'smart') {
                url.searchParams.delete('sort');
            } else {
                url.searchParams.set('sort', sortValue);
            }
            url.searchParams.delete('page');
            window.location.href = url.toString();
        });
    }

    /* ── Init ──────────────────────────────────────────────────────────── */
    function initialize() {
        if (!elements.productsGrid) return;

        initializePaginationState();
        setupSortHandler();

        window.addEventListener('scroll', handleScroll, { passive: true });

        setTimeout(checkScroll, 1000);
    }

    initialize();
});