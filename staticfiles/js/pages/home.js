// ─────────────────────────────────────────────
// Hero image slider
// Images are already in the HTML — JS only toggles active/inactive classes.
// This is critical: DO NOT create <img> elements in JS (kills LCP discovery).
// ─────────────────────────────────────────────
function initializeHeroImageSlider() {
    const heroImageSection = document.querySelector('.hero-image-section');
    if (!heroImageSection) return;

    const imageElements = Array.from(heroImageSection.querySelectorAll('.hero-image'));
    if (imageElements.length < 2) return;

    let currentIndex = 0;
    const imageChangeInterval = 4000; // 4 seconds

    function changeHeroImage() {
        imageElements[currentIndex].classList.remove('active');
        imageElements[currentIndex].classList.add('inactive');

        currentIndex = (currentIndex + 1) % imageElements.length;

        imageElements[currentIndex].classList.remove('inactive');
        imageElements[currentIndex].classList.add('active');
    }

    setInterval(changeHeroImage, imageChangeInterval);
}

// ─────────────────────────────────────────────
// Hero subtitle text rotation
// ─────────────────────────────────────────────
function initializeTextRotation() {
    const phrases = [
        "Buy and sell locally, simple, fast, and direct.",
        "Transform unused items into cash.",
        "Connect with buyers and sellers in your neighborhood.",
        "The easiest way to buy and sell anything, anywhere.",
        "Your local marketplace, discover great deals near you."
    ];

    const subtitleElement = document.getElementById('hero-subtitle-text');
    if (!subtitleElement) return;

    let currentIndex = 0;
    subtitleElement.textContent = phrases[0];
    subtitleElement.style.opacity = '1';

    function rotateMessages() {
        subtitleElement.style.opacity = '0';
        setTimeout(() => {
            currentIndex = (currentIndex + 1) % phrases.length;
            subtitleElement.textContent = phrases[currentIndex];
            subtitleElement.style.opacity = '1';
        }, 500);
    }

    setInterval(rotateMessages, 5000);
}

// ─────────────────────────────────────────────
// Category grid scroll indicators (mobile)
// ─────────────────────────────────────────────
function initializeCategoryScroll() {
    const categoriesGrid = document.querySelector('.categories-grid');
    if (!categoriesGrid || window.innerWidth > 767) return;

    categoriesGrid.style.scrollSnapType = 'x mandatory';
    categoriesGrid.querySelectorAll('.category-item').forEach(item => {
        item.style.scrollSnapAlign = 'start';
    });

    const prevIndicator = document.querySelector('.category-nav-prev');
    const nextIndicator = document.querySelector('.category-nav-next');
    if (!prevIndicator || !nextIndicator) return;

    function updateIndicators() {
        const scrollLeft = categoriesGrid.scrollLeft;
        const maxScroll = categoriesGrid.scrollWidth - categoriesGrid.clientWidth;
        prevIndicator.classList.toggle('hidden', scrollLeft <= 10);
        nextIndicator.classList.toggle('hidden', scrollLeft >= maxScroll - 10);
    }

    updateIndicators();
    categoriesGrid.addEventListener('scroll', updateIndicators, { passive: true });
    window.addEventListener('resize', () => {
        if (window.innerWidth <= 767) updateIndicators();
    });
}

// ─────────────────────────────────────────────
// Hero search focus styling
// ─────────────────────────────────────────────
function initializeHeroSearch() {
    const heroSearchInput = document.querySelector('.hero-search input');
    if (!heroSearchInput) return;

    heroSearchInput.addEventListener('focus', function () {
        this.parentElement.classList.add('focused');
    });
    heroSearchInput.addEventListener('blur', function () {
        this.parentElement.classList.remove('focused');
    });
}

// ─────────────────────────────────────────────
// Floating create button icon animation
// ─────────────────────────────────────────────
function initializeCreateListingButton() {
    const createBtn = document.getElementById('create-listing-btn');
    if (!createBtn) return;

    const icon = createBtn.querySelector('i');
    createBtn.addEventListener('mouseenter', () => { if (icon) icon.style.transform = 'rotate(90deg)'; });
    createBtn.addEventListener('mouseleave', () => { if (icon) icon.style.transform = 'rotate(0deg)'; });
}

// ─────────────────────────────────────────────
// Bootstrap tooltips
// ─────────────────────────────────────────────
function initializeTooltips() {
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
        new bootstrap.Tooltip(el);
    });
}

// ─────────────────────────────────────────────
// Progressive product card entrance animation
// ─────────────────────────────────────────────
function initializeProgressiveLoading() {
    const cardSelector = [
        '.featured-products .col-6',
        '.featured-products .col-md-4',
        '.featured-products .col-lg-3',
        '.local-products .col-6',
        '.local-products .col-md-4',
        '.local-products .col-lg-3',
    ].join(', ');

    const productCards = document.querySelectorAll(cardSelector);
    if (!productCards.length) return;

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
    }, { threshold: 0.1, rootMargin: '50px' });

    productCards.forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
        observer.observe(card);
    });
}

// ─────────────────────────────────────────────
// Init
// ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    initializeHeroImageSlider();
    initializeTextRotation();
    initializeCategoryScroll();
    initializeHeroSearch();
    initializeCreateListingButton();
    initializeTooltips();

    if ('IntersectionObserver' in window) {
        initializeProgressiveLoading();
    }
});