// Enhanced JavaScript for my_store.html with improved UX and animations

document.addEventListener("DOMContentLoaded", function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // -------------------------
    // Enhanced Store Status Chips Animation
    // -------------------------
    const statusChips = document.querySelectorAll('.store-status-chip');
    statusChips.forEach(chip => {
        chip.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-3px) scale(1.02)';
        });
        
        chip.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
        });
    });

    // -------------------------
    // Business Info Mobile Accordion
    // -------------------------
    function initializeMobileBusinessAccordion() {
        if (window.innerWidth <= 768) {
            const businessBanner = document.querySelector('.business-info-banner');
            const contactPreview = document.querySelector('.business-contact-preview');
            
            if (businessBanner && contactPreview) {
                const header = businessBanner.querySelector('.business-banner-content');
                
                if (header) {
                    header.style.cursor = 'pointer';
                    header.addEventListener('click', function() {
                        const isHidden = contactPreview.style.display === 'none';
                        contactPreview.style.display = isHidden ? 'block' : 'none';
                        
                        // Add visual feedback
                        const icon = header.querySelector('.toggle-icon') || document.createElement('i');
                        if (!header.querySelector('.toggle-icon')) {
                            icon.className = 'bi bi-chevron-down toggle-icon ms-auto';
                            header.appendChild(icon);
                        }
                        
                        icon.style.transform = isHidden ? 'rotate(180deg)' : 'rotate(0deg)';
                    });
                }
            }
        }
    }

    // -------------------------
    // Store Verification Status Animation
    // -------------------------
    function animateVerificationCards() {
        const verificationCards = document.querySelectorAll('.store-status-chip');
        
        verificationCards.forEach((card, index) => {
            // Stagger animation
            setTimeout(() => {
                card.style.opacity = '0';
                card.style.transform = 'translateY(20px)';
                card.style.transition = 'all 0.6s cubic-bezier(0.4, 0, 0.2, 1)';
                
                requestAnimationFrame(() => {
                    card.style.opacity = '1';
                    card.style.transform = 'translateY(0)';
                });
            }, index * 150);
        });
    }

    // -------------------------
    // Enhanced Button Interactions
    // -------------------------
    const actionButtons = document.querySelectorAll('.btn-add-product, .btn-edit-profile, .btn-verify-now');
    actionButtons.forEach(button => {
        button.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px) scale(1.02)';
        });
        
        button.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
        });
        
        button.addEventListener('mousedown', function() {
            this.style.transform = 'translateY(0) scale(0.98)';
        });
        
        button.addEventListener('mouseup', function() {
            this.style.transform = 'translateY(-2px) scale(1.02)';
        });
    });

    // -------------------------
    // Intersection Observer for Scroll Animations
    // -------------------------
    function initializeScrollAnimations() {
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animate-in');
                    
                    // Special handling for verification cards
                    if (entry.target.classList.contains('verification-overview-card')) {
                        setTimeout(() => {
                            animateVerificationCards();
                        }, 300);
                    }
                }
            });
        }, observerOptions);

        // Observe all major sections
        const sectionsToObserve = document.querySelectorAll(
            '.store-verification-status-section, .business-verification-card, .store-info-card, .products-section'
        );
        
        sectionsToObserve.forEach(section => {
            observer.observe(section);
        });
    }

    // -------------------------
    // Enhanced Email Verification Handler
    // -------------------------
    const verifyEmailForms = document.querySelectorAll('.verify-form');
    verifyEmailForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitButton = this.querySelector('button[type="submit"]');
            const originalContent = submitButton.innerHTML;
            
            // Add loading state
            submitButton.disabled = true;
            submitButton.innerHTML = '<i class="bi bi-arrow-clockwise spin me-1"></i>Sending...';
            
            // Reset button after 3 seconds (you can adjust based on your actual response handling)
            setTimeout(() => {
                submitButton.disabled = false;
                submitButton.innerHTML = originalContent;
            }, 3000);
        });
    });

    // -------------------------
    // Business Address Visibility Toggle (for owners)
    // -------------------------
    const addressVisibilityControls = document.querySelectorAll('.address-visibility-control');
    addressVisibilityControls.forEach(control => {
        control.addEventListener('click', function() {
            // This would be connected to an AJAX endpoint to toggle visibility
            const icon = this.querySelector('i');
            const text = this.querySelector('small');
            
            if (icon.classList.contains('bi-eye')) {
                icon.className = 'bi bi-eye-slash me-1';
                text.innerHTML = '<i class="bi bi-eye-slash me-1"></i>Address is hidden from customers';
            } else {
                icon.className = 'bi bi-eye me-1';
                text.innerHTML = '<i class="bi bi-eye me-1"></i>Address is visible to customers';
            }
            
            // Add visual feedback
            this.style.transform = 'scale(0.95)';
            setTimeout(() => {
                this.style.transform = 'scale(1)';
            }, 150);
        });
    });

    // -------------------------
    // Contact Item Copy Functionality
    // -------------------------
    const contactItems = document.querySelectorAll('.contact-preview-item, .contact-item');
    contactItems.forEach(item => {
        const textContent = item.querySelector('span');
        if (textContent && (textContent.textContent.includes('@') || textContent.textContent.match(/\d/))) {
            item.style.cursor = 'pointer';
            item.title = 'Click to copy';
            
            item.addEventListener('click', function() {
                const text = textContent.textContent.trim();
                
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(text).then(() => {
                        showCopyFeedback(this, 'Copied!');
                    }).catch(() => {
                        showCopyFeedback(this, 'Failed to copy');
                    });
                } else {
                    // Fallback for older browsers
                    showCopyFeedback(this, 'Copy not supported');
                }
            });
        }
    });

    // -------------------------
    // Copy Feedback Function
    // -------------------------
    function showCopyFeedback(element, message) {
        const originalText = element.innerHTML;
        const feedback = document.createElement('div');
        feedback.className = 'copy-feedback';
        feedback.textContent = message;
        feedback.style.cssText = `
            position: absolute;
            top: -30px;
            left: 50%;
            transform: translateX(-50%);
            background: var(--primary-color);
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            z-index: 1000;
            animation: fadeInOut 2s ease-in-out;
        `;
        
        element.style.position = 'relative';
        element.appendChild(feedback);
        
        setTimeout(() => {
            if (feedback.parentNode) {
                feedback.parentNode.removeChild(feedback);
            }
        }, 2000);
        
        // Add bounce effect to the element
        element.style.transform = 'scale(0.95)';
        setTimeout(() => {
            element.style.transform = 'scale(1)';
        }, 150);
    }

    // -------------------------
    // Enhanced Product Card Interactions
    // -------------------------
    const productCards = document.querySelectorAll('.product-card');
    productCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px) scale(1.02)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
        });
    });

    // -------------------------
    // Mobile Responsive Adjustments
    // -------------------------
    function handleResponsiveChanges() {
        const isMobile = window.innerWidth <= 768;
        const statusChips = document.querySelectorAll('.store-status-chip');
        
        statusChips.forEach(chip => {
            if (isMobile) {
                chip.style.padding = '1rem';
                chip.style.minHeight = '80px';
            } else {
                chip.style.padding = '1.25rem';
                chip.style.minHeight = '90px';
            }
        });
    }

    // -------------------------
    // Smooth Scrolling for Internal Links
    // -------------------------
    const internalLinks = document.querySelectorAll('a[href^="#"]');
    internalLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href').substring(1);
            const targetElement = document.getElementById(targetId);
            
            if (targetElement) {
                targetElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // -------------------------
    // Add CSS animations
    // -------------------------
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeInOut {
            0% { opacity: 0; transform: translateX(-50%) translateY(-10px); }
            50% { opacity: 1; transform: translateX(-50%) translateY(0); }
            100% { opacity: 0; transform: translateX(-50%) translateY(-10px); }
        }
        
        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        
        .spin {
            animation: spin 1s linear infinite;
        }
        
        .animate-in {
            animation: slideInUp 0.6s ease-out forwards;
        }
        
        @keyframes slideInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .toggle-icon {
            transition: transform 0.3s ease;
        }
    `;
    document.head.appendChild(style);

    // -------------------------
    // Initialize All Functions
    // -------------------------
    initializeMobileBusinessAccordion();
    initializeScrollAnimations();
    handleResponsiveChanges();
    
    // Handle window resize
    window.addEventListener('resize', () => {
        initializeMobileBusinessAccordion();
        handleResponsiveChanges();
    });

    // -------------------------
    // Lazy Loading for Images
    // -------------------------
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    if (img.dataset.src) {
                        img.src = img.dataset.src;
                        img.removeAttribute('data-src');
                        imageObserver.unobserve(img);
                    }
                }
            });
        });

        const lazyImages = document.querySelectorAll('img[data-src]');
        lazyImages.forEach(img => imageObserver.observe(img));
    }

    let scrollTimeout;
    window.addEventListener('scroll', () => {
        if (scrollTimeout) {
            clearTimeout(scrollTimeout);
        }
        
        scrollTimeout = setTimeout(() => {
            // Only handle non-parallax scroll effects here if needed
            // Remove any transform operations on .store-header
        }, 10);
    });

    console.log('Enhanced My Store JavaScript initialized successfully');
});