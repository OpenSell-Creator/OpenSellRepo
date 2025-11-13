// Hero image slider with smooth crossfade
function initializeHeroImageSlider() {
    const images = [
        'market1.png',
        'market4.jpg',
        'cars.png'
    ];
    
    const heroImageSection = document.querySelector('.hero-image-section');
    if (!heroImageSection) return;
    
    const originalImage = heroImageSection.querySelector('.hero-image');
    if (!originalImage) return;
    
    // Create all image elements
    const imageElements = [];
    images.forEach((imageSrc, index) => {
        const img = document.createElement('img');
        img.src = originalImage.src.replace(/[^\/]*$/, imageSrc);
        img.alt = 'Marketplace';
        img.className = 'hero-image';
        
        if (index === 0) {
            img.classList.add('active');
        } else {
            img.classList.add('inactive');
        }
        
        // Insert before the overlay
        heroImageSection.insertBefore(img, heroImageSection.querySelector('.hero-image-overlay'));
        imageElements.push(img);
    });
    
    // Remove the original image
    originalImage.remove();
    
    let currentIndex = 0;
    const imageChangeInterval = 4000; // 4 seconds
    
    function changeHeroImage() {
        const currentImage = imageElements[currentIndex];
        currentIndex = (currentIndex + 1) % imageElements.length;
        const nextImage = imageElements[currentIndex];
        
        // Crossfade transition
        currentImage.classList.remove('active');
        currentImage.classList.add('inactive');
        
        nextImage.classList.remove('inactive');
        nextImage.classList.add('active');
    }
    
    // Start the image rotation
    setInterval(changeHeroImage, imageChangeInterval);
}

// Text rotation for all users (authenticated and non-authenticated)
function initializeTextRotation() {
    const phrases = [
        "Buy and sell locally — simple, fast, and direct.",
        "Transform unused items into cash — start selling today.",
        "Connect with buyers and sellers in your neighborhood.",
        "The easiest way to buy and sell anything, anywhere.",
        "Your local marketplace — discover great deals near you.",
        "Join thousands buying and selling in your community."
    ];
    
    const subtitleElement = document.getElementById('hero-subtitle-text');
    
    if (subtitleElement) {
        let currentIndex = 0;
        const transitionDelay = 5000; // 5 seconds per phrase
        
        // Set first phrase immediately
        subtitleElement.textContent = phrases[0];
        subtitleElement.style.opacity = '1';
        
        function rotateMessages() {
            // Fade out
            subtitleElement.style.opacity = '0';
            
            setTimeout(() => {
                currentIndex = (currentIndex + 1) % phrases.length;
                subtitleElement.textContent = phrases[currentIndex];
                // Fade in
                subtitleElement.style.opacity = '1';
            }, 500);
        }
        
        // Start rotation after initial delay
        setInterval(rotateMessages, transitionDelay);
    }
}

// Scroll indicator management
function initializeScrollIndicator() {
    const scrollIndicator = document.querySelector('.scroll-indicator');
    if (scrollIndicator && window.innerWidth <= 768) {
        setTimeout(() => {
            scrollIndicator.style.opacity = '0';
            setTimeout(() => {
                scrollIndicator.style.display = 'none';
            }, 300);
        }, 8000);
    }
}

// Category grid scroll behavior
function initializeCategoryScroll() {
    const categoriesGrid = document.querySelector('.categories-grid');
    if (categoriesGrid && window.innerWidth <= 767) {
        categoriesGrid.style.scrollSnapType = 'x mandatory';
        
        const categoryItems = categoriesGrid.querySelectorAll('.category-item');
        categoryItems.forEach(item => {
            item.style.scrollSnapAlign = 'start';
        });
    }
}

// Hero search enhancements
function initializeHeroSearch() {
    const heroSearchInput = document.querySelector('.hero-search input');
    if (heroSearchInput) {
        heroSearchInput.addEventListener('focus', function() {
            this.parentElement.classList.add('focused');
        });
        
        heroSearchInput.addEventListener('blur', function() {
            this.parentElement.classList.remove('focused');
        });
    }
}

// Create listing button functionality
function initializeCreateListingButton() {
    const createBtn = document.getElementById('create-listing-btn');
    if (createBtn) {
        createBtn.addEventListener('mouseenter', function() {
            this.querySelector('i').style.transform = 'rotate(90deg)';
        });
        
        createBtn.addEventListener('mouseleave', function() {
            this.querySelector('i').style.transform = 'rotate(0deg)';
        });
    }
}

// Initialize tooltips
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Progressive image loading for product cards
function initializeProgressiveLoading() {
    const productCards = document.querySelectorAll('.featured-products .col-6, .featured-products .col-md-4, .featured-products .col-lg-3, .local-products .col-6, .local-products .col-md-4, .local-products .col-lg-3');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                setTimeout(() => {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }, index * 50);
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '50px'
    });

    productCards.forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'all 0.5s ease';
        observer.observe(card);
    });
}

// Initialize all home page functionality
function initializeHomePage() {
    initializeHeroImageSlider();
    initializeTextRotation();
    initializeScrollIndicator();
    initializeCategoryScroll();
    initializeHeroSearch();
    initializeCreateListingButton();
    initializeTooltips();
    
    // Only initialize progressive loading if IntersectionObserver is supported
    if ('IntersectionObserver' in window) {
        initializeProgressiveLoading();
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initializeHomePage);

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initializeHomePage,
        initializeHeroImageSlider,
        initializeTextRotation,
        initializeHeroSearch
    };
}