// Keep all existing navbar JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const mainNavbar = document.getElementById('mainNavbar');
    const bottomNav = document.getElementById('bottomNav');
    const mainSidebar = document.getElementById('mainSidebar');
    const hamburgerBtn = document.querySelector('.navbar-toggler');
    const hamburgerIcon = hamburgerBtn.querySelector('.hamburger-icon');
    const closeIcon = hamburgerBtn.querySelector('.close-icon');
    
    // Get current URL path for active links
    const path = window.location.pathname;
    
    // Set active nav links based on current path
    document.querySelectorAll('.nav-link').forEach(link => {
      const href = link.getAttribute('href');
      if (href === path || (path.includes(href) && href !== '/')) {
        link.classList.add('active');
      }
    });
    
    // Handle hamburger to X animation
    mainSidebar.addEventListener('show.bs.offcanvas', function () {
      hamburgerIcon.style.opacity = '0';
      hamburgerIcon.style.transform = 'rotate(180deg)';
      closeIcon.style.display = 'block';
      closeIcon.style.opacity = '1';
      closeIcon.style.transform = 'rotate(0)';
      document.body.classList.add('sidebar-open');
    });
    
    mainSidebar.addEventListener('hide.bs.offcanvas', function () {
      closeIcon.style.opacity = '0';
      closeIcon.style.transform = 'rotate(-180deg)';
      setTimeout(() => {
        closeIcon.style.display = 'none';
        hamburgerIcon.style.opacity = '1';
        hamburgerIcon.style.transform = 'rotate(0)';
      }, 300);
      document.body.classList.remove('sidebar-open');
    });
  
    // ── Swipe-to-hide nav (works on scrollable AND non-scrollable pages) ──
    if (window.innerWidth < 992) {
      let sidebarIsOpen = false;
      let lastScroll = 0;
      let touchStartY = 0;
      let touchStartX = 0;
      const SWIPE_THRESHOLD = 30; // px of vertical movement to trigger

      function showNav() {
        mainNavbar.style.transform = 'translateY(0)';
        mainNavbar.style.opacity = '1';
        if (bottomNav) {
          bottomNav.style.transform = 'translateY(0)';
          bottomNav.style.opacity = '1';
        }
      }

      function hideNav() {
        if (sidebarIsOpen) return;
        mainNavbar.style.transform = 'translateY(-100%)';
        mainNavbar.style.opacity = '0';
        if (bottomNav) {
          bottomNav.style.transform = 'translateY(100%)';
          bottomNav.style.opacity = '0';
        }
      }

      // ── Touch swipe gesture (works on non-scrollable pages) ──
      window.addEventListener('touchstart', (e) => {
        touchStartY = e.touches[0].clientY;
        touchStartX = e.touches[0].clientX;
      }, { passive: true });

      window.addEventListener('touchend', (e) => {
        const deltaY = touchStartY - e.changedTouches[0].clientY; // positive = swiped up
        const deltaX = Math.abs(touchStartX - e.changedTouches[0].clientX);

        // Ignore mostly-horizontal swipes (e.g. carousels)
        if (deltaX > Math.abs(deltaY)) return;

        if (deltaY > SWIPE_THRESHOLD) {
          hideNav(); // swiped up → hide
        } else if (deltaY < -SWIPE_THRESHOLD) {
          showNav(); // swiped down → show
        }
      }, { passive: true });

      // ── Regular scroll (for scrollable pages) ──
      window.addEventListener('scroll', () => {
        const currentScroll = window.scrollY;
        if (currentScroll > lastScroll + 4) {
          hideNav();
        } else if (currentScroll < lastScroll || currentScroll <= 0) {
          showNav();
        }
        lastScroll = currentScroll;
      }, { passive: true });

      // ── Keep nav visible while sidebar is open ──
      mainSidebar.addEventListener('show.bs.offcanvas', () => {
        sidebarIsOpen = true;
        showNav();
      });
      mainSidebar.addEventListener('hidden.bs.offcanvas', () => {
        sidebarIsOpen = false;
      });
    }

    
    // Handle search form submissions
    const searchForms = document.querySelectorAll('.search-form, .sidebar-search-form');
    searchForms.forEach(form => {
      form.addEventListener('submit', function(e) {
        const input = this.querySelector('input[name="query"]');
        if (!input.value.trim()) {
          e.preventDefault();
          input.focus();
        }
      });
    });
    
    // PWA Install functionality
    let deferredPrompt;
    const pwaInstallSection = document.getElementById('pwaInstallSection');
    const pwaInstallBtn = document.getElementById('pwaInstallBtn');
    
    // Check if already installed
    if (window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true) {
      // Already installed, hide the install button
      if (pwaInstallSection) {
        pwaInstallSection.style.display = 'none';
      }
    }
    
    window.addEventListener('beforeinstallprompt', (e) => {
      // Prevent the mini-infobar from appearing on mobile
      e.preventDefault();
      // Stash the event so it can be triggered later
      deferredPrompt = e;
      // Show the install button
      if (pwaInstallSection) {
        pwaInstallSection.style.display = 'block';
      }
    });
    
    if (pwaInstallBtn) {
      pwaInstallBtn.addEventListener('click', async () => {
        if (deferredPrompt) {
          // Show the install prompt
          deferredPrompt.prompt();
          // Wait for the user to respond to the prompt
          const { outcome } = await deferredPrompt.userChoice;
          
          if (outcome === 'accepted') {
            console.log('User accepted the install prompt');
            // Hide the install button
            pwaInstallSection.style.display = 'none';
          }
          
          // Clear the deferred prompt
          deferredPrompt = null;
        }
      });
    }
    
    // Close sidebar when clicking on a link (mobile)
    if (window.innerWidth < 992) {
      const sidebarLinks = document.querySelectorAll('#mainSidebar a:not([data-bs-toggle])');
      const sidebar = document.getElementById('mainSidebar');
      
      sidebarLinks.forEach(link => {
        link.addEventListener('click', function() {
          const bsOffcanvas = bootstrap.Offcanvas.getInstance(sidebar);
          if (bsOffcanvas) {
            bsOffcanvas.hide();
          }
        });
      });
    }
    
    // Initialize Bootstrap components
    // Tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
      return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Handle notifications badge visibility
    function updateNotificationsBadges() {
      const notificationBadges = document.querySelectorAll('.notification-badge, .quick-action-badge');
      notificationBadges.forEach(badge => {
        const count = parseInt(badge.textContent.trim());
        
        if (isNaN(count) || count === 0) {
          badge.style.display = 'none';
        } else {
          badge.style.display = 'flex';
        }
      });
    }
    
    updateNotificationsBadges();
    
    // Handle collapsible animations
    const collapsibles = document.querySelectorAll('[data-bs-toggle="collapse"]');
    collapsibles.forEach(element => {
      element.addEventListener('click', function() {
        // Animation handled by CSS
      });
    });
    
    // Smooth sidebar opening
    const offcanvasConfig = {
        backdrop: true,
        keyboard: true,
        scroll: false
    };
    
    const bsOffcanvas = new bootstrap.Offcanvas(mainSidebar, offcanvasConfig);
    
    // Override the default show/hide to make it smoother
    const originalShow = bsOffcanvas.show;
    const originalHide = bsOffcanvas.hide;
    
    bsOffcanvas.show = function() {
        mainSidebar.style.transform = 'translateX(100%)';
        originalShow.call(this);
        setTimeout(() => {
        mainSidebar.style.transform = 'translateX(0)';
        }, 10);
    };
    
    bsOffcanvas.hide = function() {
        mainSidebar.style.transform = 'translateX(100%)';
        setTimeout(() => {
        originalHide.call(this);
        }, 300);
    };
});