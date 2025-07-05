/**
 * Home Page JavaScript - Handles home page specific interactions
 */

// Text rotation for logged-in users
function initializeTextRotation() {
    const phrases = [
        "Buy and sell locally — simple, fast, and direct.",
        "Transform unused items into cash — start selling today.",
        "Connecting people directly — no middlemen, just great deals.",
        "The simplest way to sell from anywhere, at your own pace.",
        "Your pocket marketplace — sell and buy anytime, anywhere.",
        "Discover what you need, from people near you."
    ];
    
    const subtitleElement = document.getElementById('logged-in-subtitle-text');
    
    if (subtitleElement) {
        let currentIndex = 0;
        const transitionDelay = 5000; // 5 seconds per phrase
        
        // Set first phrase immediately
        subtitleElement.textContent = phrases[0];
        
        function rotateMessages() {
            // Apply animation
            subtitleElement.style.animation = 'fadeTextTransition 5s forwards';
            
            setTimeout(() => {
                currentIndex = (currentIndex + 1) % phrases.length;
                subtitleElement.textContent = phrases[currentIndex];
                subtitleElement.style.animation = 'none';
                
                // Trigger reflow to reset animation
                void subtitleElement.offsetWidth;
                subtitleElement.style.animation = null;
            }, 4800);
        }
        
        // Start rotation after initial delay
        setInterval(rotateMessages, transitionDelay);
    } else {
        console.error("Element with ID 'logged-in-subtitle-text' not found");
    }
}

// Category collapse functionality
function initializeCategoryCollapse() {
    const collapseElement = document.getElementById('mobileCategories');
    const collapseButton = document.querySelector('[data-bs-target="#mobileCategories"]');

    if (collapseElement && collapseButton) {
        collapseElement.addEventListener('show.bs.collapse', function () {
            collapseButton.innerHTML = 'Show Less Categories <i class="bi bi-chevron-up collapse-icon"></i>';
        });

        collapseElement.addEventListener('hide.bs.collapse', function () {
            collapseButton.innerHTML = 'Show More Categories <i class="bi bi-chevron-down collapse-icon"></i>';
        });
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
        // Add scroll snap behavior
        categoriesGrid.style.scrollSnapType = 'x mandatory';
        
        // Optional: Add scroll buttons for better UX
        const categoryItems = categoriesGrid.querySelectorAll('.category-item');
        categoryItems.forEach(item => {
            item.style.scrollSnapAlign = 'start';
        });
    }
}

// Hero search enhancements
function initializeHeroSearch() {
    const heroSearchInput = document.querySelector('.hero-search-form .search-input');
    if (heroSearchInput) {
        // Add search suggestions or autocomplete here if needed
        heroSearchInput.addEventListener('focus', function() {
            this.parentElement.classList.add('focused');
        });
        
        heroSearchInput.addEventListener('blur', function() {
            this.parentElement.classList.remove('focused');
        });
        
        // Add search history or suggestions
        heroSearchInput.addEventListener('input', function() {
            const query = this.value.trim();
            if (query.length > 2) {
                // Implement search suggestions here
            }
        });
    }
}

// Value proposition card interactions
function initializeValueCards() {
    const valueCards = document.querySelectorAll('.value-card');
    valueCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            // Add subtle interaction feedback
            this.style.borderColor = 'var(--primary-color)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.borderColor = 'var(--border-color)';
        });
    });
}

// Testimonial carousel or interactions
function initializeTestimonials() {
    const testimonialCards = document.querySelectorAll('.testimonial-card');
    testimonialCards.forEach((card, index) => {
        // Add stagger animation delay
        card.style.animationDelay = `${index * 0.1}s`;
    });
}

// CTA button enhancements
function initializeCTAButtons() {
    const ctaButtons = document.querySelectorAll('.cta-btn-primary, .cta-btn-secondary');
    ctaButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            // Add click animation or tracking
            this.style.transform = 'scale(0.95)';
            setTimeout(() => {
                this.style.transform = '';
            }, 150);
        });
    });
}

// Featured products enhancements
function initializeFeaturedProducts() {
    const productCards = document.querySelectorAll('.featured-products .col-6, .featured-products .col-md-4, .featured-products .col-lg-3');
    productCards.forEach((card, index) => {
        // Add progressive loading effect
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            card.style.transition = 'all 0.5s ease';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 100);
    });
}

// Local products section
function initializeLocalProducts() {
    const localSection = document.querySelector('.local-products');
    if (localSection) {
        // Add location-based enhancements
        const locationButton = localSection.querySelector('.btn-outline-primary');
        if (locationButton) {
            locationButton.addEventListener('click', function() {
                // Handle location update
                console.log('Location update requested');
            });
        }
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

// Initialize all home page functionality
function initializeHomePage() {
    initializeTextRotation();
    initializeCategoryCollapse();
    initializeScrollIndicator();
    initializeCategoryScroll();
    initializeHeroSearch();
    initializeValueCards();
    initializeTestimonials();
    initializeCTAButtons();
    initializeFeaturedProducts();
    initializeLocalProducts();
    initializeCreateListingButton();
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initializeHomePage);

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initializeHomePage,
        initializeTextRotation,
        initializeCategoryCollapse,
        initializeHeroSearch
    };
}

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Category collapse button functionality
    const collapseElement = document.getElementById('mobileCategories');
    const collapseButton = document.querySelector('[data-bs-target="#mobileCategories"]');

    if (collapseElement && collapseButton) {
        collapseElement.addEventListener('show.bs.collapse', function () {
            collapseButton.innerHTML = 'Show Less Categories <i class="bi bi-chevron-up collapse-icon"></i>';
        });

        collapseElement.addEventListener('hide.bs.collapse', function () {
            collapseButton.innerHTML = 'Show More Categories <i class="bi bi-chevron-down collapse-icon"></i>';
        });
    }
});