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

    // ── Swipe-to-hide nav (iOS Safari compatible) ──────────────────────────
    //
    // KEY iOS FIXES applied here:
    //
    //  1. navVisible boolean  – iOS Safari doesn't always reflect in-progress
    //     CSS transitions back into element.style, so reading
    //     style.transform === 'translateY(-100%)' is unreliable mid-animation.
    //     We track state ourselves instead.
    //
    //  2. changedTouches guard – On iOS, changedTouches[0] can be undefined
    //     when a gesture is interrupted by a system swipe (home indicator,
    //     control centre, etc.). We fall back to touches[0].
    //
    //  3. touches.length guard – Protect every touchstart / touchmove handler
    //     from empty touch lists, which iOS can produce during multi-finger
    //     or system-interrupted gestures.
    //
    //  4. try/catch around preventDefault() – iOS Safari throws or silently
    //     ignores preventDefault() in certain scroll contexts even when the
    //     listener is { passive: false }. Wrapping it prevents an unhandled
    //     exception from killing the rest of the handler.
    //
    //  5. visualViewport resize listener – On iOS, window.innerWidth is
    //     reported BEFORE the viewport is fully settled on page load (split
    //     view, orientation change). Using visualViewport.width (with a
    //     window.innerWidth fallback) gives the correct value.
    //
    // Nothing below changes any existing behaviour for Android / desktop.
    // ──────────────────────────────────────────────────────────────────────

    // FIX 5: use visualViewport.width when available (iOS split-view safe)
    const getViewportWidth = () =>
      (window.visualViewport ? window.visualViewport.width : window.innerWidth);

    if (getViewportWidth() < 992) {
      let sidebarIsOpen = false;
      let lastScroll    = 0;
      let touchStartY   = 0;
      let touchStartX   = 0;
      let navVisible    = true;              // FIX 1: JS-tracked state
      const SWIPE_THRESHOLD = 30;            // px – unchanged

      function showNav() {
        navVisible = true;                   // FIX 1: update flag
        mainNavbar.style.transform = 'translateY(0)';
        mainNavbar.style.opacity   = '1';
        if (bottomNav) {
          bottomNav.style.transform = 'translateY(0)';
          bottomNav.style.opacity   = '1';
        }
      }

      function hideNav() {
        if (sidebarIsOpen) return;
        navVisible = false;                  // FIX 1: update flag
        mainNavbar.style.transform = 'translateY(-100%)';
        mainNavbar.style.opacity   = '0';
        if (bottomNav) {
          bottomNav.style.transform = 'translateY(100%)';
          bottomNav.style.opacity   = '0';
        }
      }

      // ── Touch: record start position ────────────────────────────────────
      window.addEventListener('touchstart', (e) => {
        if (e.touches.length === 0) return;  // FIX 3: empty-list guard
        touchStartY = e.touches[0].clientY;
        touchStartX = e.touches[0].clientX;
      }, { passive: true });

      // ── Touch: optionally block pull-to-refresh while nav is hidden ─────
      window.addEventListener('touchmove', (e) => {
        if (e.touches.length === 0) return;  // FIX 3: empty-list guard

        const deltaY = touchStartY - e.touches[0].clientY;
        const deltaX = Math.abs(touchStartX - e.touches[0].clientX);

        // Only intercept clearly-vertical downward swipes when nav is hidden
        if (deltaX < Math.abs(deltaY) && deltaY < -10 && !navVisible) { // FIX 1: use flag
          try {
            e.preventDefault();              // FIX 4: wrapped in try/catch
          } catch (_) {
            // iOS Safari may reject this; safe to swallow
          }
        }
      }, { passive: false }); // must stay non-passive to call preventDefault

      // ── Touch: act on completed swipe ───────────────────────────────────
      window.addEventListener('touchend', (e) => {
        // FIX 2: changedTouches[0] can be undefined on iOS system interrupts
        const touch =
          (e.changedTouches && e.changedTouches[0]) ||
          (e.touches        && e.touches[0]);
        if (!touch) return;

        const deltaY = touchStartY - touch.clientY;
        const deltaX = Math.abs(touchStartX - touch.clientX);

        // Ignore mostly-horizontal swipes (e.g. carousels) – unchanged
        if (deltaX > Math.abs(deltaY)) return;

        if (deltaY > SWIPE_THRESHOLD) {
          hideNav();   // swiped up  → hide
        } else if (deltaY < -SWIPE_THRESHOLD) {
          showNav();   // swiped down → show
        }
      }, { passive: true });

      // ── Regular scroll (scrollable pages) – unchanged ───────────────────
      window.addEventListener('scroll', () => {
        const currentScroll = window.scrollY;
        if (currentScroll > lastScroll + 4) {
          hideNav();
        } else if (currentScroll < lastScroll || currentScroll <= 0) {
          showNav();
        }
        lastScroll = currentScroll;
      }, { passive: true });

      // ── Keep nav visible while sidebar is open – unchanged ──────────────
      mainSidebar.addEventListener('show.bs.offcanvas', () => {
        sidebarIsOpen = true;
        showNav();
      });
      mainSidebar.addEventListener('hidden.bs.offcanvas', () => {
        sidebarIsOpen = false;
      });
    }
    // ── End of swipe/scroll block ──────────────────────────────────────────


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
    const pwaInstallBtn     = document.getElementById('pwaInstallBtn');

    // Check if already installed
    if (window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true) {
      if (pwaInstallSection) {
        pwaInstallSection.style.display = 'none';
      }
    }

    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      deferredPrompt = e;
      if (pwaInstallSection) {
        pwaInstallSection.style.display = 'block';
      }
    });

    if (pwaInstallBtn) {
      pwaInstallBtn.addEventListener('click', async () => {
        if (deferredPrompt) {
          deferredPrompt.prompt();
          const { outcome } = await deferredPrompt.userChoice;
          if (outcome === 'accepted') {
            console.log('User accepted the install prompt');
            pwaInstallSection.style.display = 'none';
          }
          deferredPrompt = null;
        }
      });
    }

    // Close sidebar when clicking on a link (mobile)
    if (getViewportWidth() < 992) {
      const sidebarLinks = document.querySelectorAll('#mainSidebar a:not([data-bs-toggle])');
      const sidebar      = document.getElementById('mainSidebar');

      sidebarLinks.forEach(link => {
        link.addEventListener('click', function() {
          const bsOffcanvas = bootstrap.Offcanvas.getInstance(sidebar);
          if (bsOffcanvas) {
            bsOffcanvas.hide();
          }
        });
      });
    }

    // Initialize Bootstrap components — Tooltips
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

    // Handle collapsible animations (animation handled by CSS – unchanged)
    const collapsibles = document.querySelectorAll('[data-bs-toggle="collapse"]');
    collapsibles.forEach(element => {
      element.addEventListener('click', function() {});
    });

    // Smooth sidebar opening
    const offcanvasConfig = {
      backdrop : true,
      keyboard : true,
      scroll   : false
    };

    const bsOffcanvas    = new bootstrap.Offcanvas(mainSidebar, offcanvasConfig);
    const originalShow   = bsOffcanvas.show;
    const originalHide   = bsOffcanvas.hide;

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