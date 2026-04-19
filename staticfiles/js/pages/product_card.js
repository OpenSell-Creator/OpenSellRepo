
// Enhanced tooltip initialization
function initializeTooltips() {
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    
    if (tooltipTriggerList.length > 0 && typeof bootstrap !== 'undefined') {
        const initTooltips = () => {
            tooltipTriggerList.forEach(tooltipTriggerEl => {
                try {
                    new bootstrap.Tooltip(tooltipTriggerEl, {
                        delay: { show: 600, hide: 100 },
                        placement: 'auto',
                        boundary: 'viewport'
                    });
                } catch (error) {
                    console.warn('Failed to initialize tooltip:', error);
                }
            });
        };
        
        if ('requestIdleCallback' in window) {
            requestIdleCallback(initTooltips);
        } else {
            setTimeout(initTooltips, 100);
        }
    }
}

// Enhanced intersection observer for performance
function initializeCardObserver() {
    if (!('IntersectionObserver' in window)) return;
    
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '50px 0px',
    };
    
    const cardObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const card = entry.target;
                card.classList.add('visible');
                
                const images = card.querySelectorAll('img[data-src]');
                images.forEach(img => {
                    if (img.dataset.src) {
                        img.src = img.dataset.src;
                        img.removeAttribute('data-src');
                    }
                });
                
                const productImages = card.querySelectorAll('.product-image');
                productImages.forEach(img => {
                    if (!img.complete && img.naturalHeight === 0) {
                        img.addEventListener('load', function() {
                            this.style.opacity = '1';
                        }, { once: true });
                    }
                });
                
                cardObserver.unobserve(card);
            }
        });
    }, observerOptions);
    
    const productCards = document.querySelectorAll('.product-card');
    productCards.forEach(card => cardObserver.observe(card));
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    initializeTooltips();
    initializeCardObserver();
});